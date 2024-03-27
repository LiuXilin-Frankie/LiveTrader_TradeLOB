"""
领先滞后套利策略
"""

import datetime
import numpy as np
import pandas as pd
import queue
import sys
import copy
sys.path.append("..")

from abc import ABCMeta, abstractmethod

from event import OrderEvent, FillEvent
from object import Strategy
from Strategy.strategy import StrategyData, Strategy_Info

class LeadLagArbitrageStrategy(Strategy):
    """
    简单的策略进行测试
    我们买入等量的各种资产 s (默认1000美元)
    并且在每隔 20min 进行一次 rebalance
    """

    def __init__(self, events, datahandler, portfolio, executor, order_latency=50, 
                 k1=0.5*1e-4, 
                 k2=1*1e-4, 
                 k3=1.5*1e-4, 
                 order_live_time = 10*1000, 
                 dynamic_stop_hedge = 5*1000,
                 stop_loss_threshold = 3*1e-4):
        """
        Initialises the buy and hold strategy.

        Parameters:
        trades - The DataHandler object that provides trade information
        events - The Event Queue object.
        """
        self.datahandler = datahandler
        self.symbol_exchange_list = self.datahandler.symbol_exchange_list
        self.events = events
        self.portfolio = portfolio
        self.executor = executor
        self.order_latency = order_latency
        self.order_id = 0

        # hyper-parameters of this strategy
        self.k1 = k1
        self.k2 = k2
        self.k3 = k3
        self.order_live_time = order_live_time
        self.dynamic_stop_hedge = dynamic_stop_hedge
        self.stop_loss_threshold = stop_loss_threshold
        
        # arguments used in this strategy
        # Store useful infomation for order generate and stop loss
        self._gen_pair_list()
        # self.signal_time = dict( (k,v) for k, v in [(s, None) for s in self.symbol_exchange_list] )
        self.last_trade = dict( (k,v) for k, v in [(s, None) for s in self.symbol_exchange_list] )
        
        # 记录历史开仓数据
        self.strategy_history = []
        # 记录目前交易的详情
        self.trade_state = {'leader_t':None}

    def _gen_pair_list(self):
        self.pair_list = {self.symbol_exchange_list[0]:self.symbol_exchange_list[1],
                          self.symbol_exchange_list[1]:self.symbol_exchange_list[0]}
        if len(self.symbol_exchange_list)> 2:
            print('this version of backtest only support 2 symbols, others will be ignored')
            print('backtest on:', self.symbol_exchange_list[:2],)
 
    def _get_order_id(self):
        """
        用于返回 order_id 的函数，并且将 order_id 自动加一
        """
        tmp = self.order_id
        self.order_id += 1
        return tmp
    
    def on_order_fill(self,event):
        pass
    
    def update_last_trade_s(self, s):
        """
        更新上一次交易历史的记录
        """
        self.last_trade[s] = self.datahandler.get_latest_trades()[s]

    def calculate_signals(self, s):
        """
        如果一个资产没有被交易，我们生成信号并持有，如果已经有仓位，我们则忽略
        这也就意味着我们的 position_limit 为 1
        """
        # 生成交易记录的list
        traded_info = self.datahandler.latest_symbol_exchange_trade_data[s]
        if self.last_trade[s] is not None:
            traded_info = [self.last_trade[s]] + traded_info
        
        for i in range(1, len(traded_info)):
            if (traded_info[i].price/traded_info[i-1].price - 1) > self.k1:
                ## 下订单
                signal_time = self.datahandler.backtest_now
                IOC_symbol = self.pair_list[s]
                IOC_price = traded_info[i-1].price*(1-self.k2)
                # IOC_price = traded_info[i].price*(1-(self.k2+self.k1))
                order = OrderEvent(timestamp=signal_time+2*self.order_latency, 
                                   symbol=IOC_symbol, 
                                   order_id = self._get_order_id(),
                                   order_type="IOC", 
                                   direction='BUY',
                                   price = IOC_price,
                                   quantity=(10000/IOC_price))
                self.events.put(order)

    def on_market_event(self, event):
        """
        Market Event 到达之后需要更新的信息
        1. 检查开仓信号
        2. 更新数据
        3. 检查订单/存在的开仓是否需要开始平仓操作
        """
        # 计算信号
        updated_trade_symbols = self.datahandler.get_updated_trade_symbols()
        for s in updated_trade_symbols:
            if self.trade_state['leader_t'] is None:
                self.calculate_signals(s)
            self.update_last_trade_s(s)

        # 检查是否仓位暴露过久需要强行平仓
        # 调用活跃订单监控函数
        if self.trade_state['leader_t'] is not None:
            self.monitor_stop_loss()
            self.monitor_live_order()

    def monitor_stop_loss(self):
        price = self.datahandler.get_latest_prices()[self.trade_state['hedge_symbol']]
        if self.trade_state['leader_direction'] == "BUY":
            if (price - self.trade_state['leader_price'])/self.trade_state['leader_price'] < - self.stop_loss_threshold:
                self.trade_state['stop_time'] = self.datahandler.backtest_now -1
        if self.trade_state['leader_direction'] == "SELL":
            if (price - self.trade_state['leader_price'])/self.trade_state['leader_price'] > self.stop_loss_threshold:
                self.trade_state['stop_time'] = self.datahandler.backtest_now -1

    def monitor_live_order(self):
        """
        监控活跃的订单
        比如说超过一段时间我们要强行平仓等等
        """
        if self.datahandler.backtest_now > self.trade_state['stop_time']:
            # print('===== start force hedge =====')     
            # 取消上一次订单
            fill_event = FillEvent(timestamp=self.datahandler.backtest_now, 
                                    symbol=self.trade_state['hedge_symbol'],
                                    exchange=self.trade_state['hedge_symbol'].split("_")[-1], 
                                    order_id=self.trade_state['hedge_order_id'],
                                    direction=self.trade_state['hedge_direction'], 
                                    quantity=self.trade_state['hedge_qty'], 
                                    price=self.trade_state['hedge_price'], 
                                    is_Maker=False,
                                    fill_flag = 'CANCELED')
            self.events.put(fill_event)

            new_order_type = 'MARKET'
            new_order_price = np.nan
            # 策略额外部分，动态平仓尝试
            if self.dynamic_stop_hedge:
                if self.trade_state['has_start_force'] ==0:
                    self.trade_state['stop_time'] += self.dynamic_stop_hedge
                    self.trade_state['has_start_force'] = 1
                    new_order_type = 'LIMIT'
                    live_LOB = self.datahandler.get_latest_LOBs()[self.trade_state['hedge_symbol']]
                    if self.trade_state['hedge_direction'] =="BUY":
                        new_order_price = live_LOB.bid1
                    if self.trade_state['hedge_direction'] =="SELL":
                        new_order_price = live_LOB.ask1

            order = OrderEvent(timestamp= self.datahandler.backtest_now, 
                                symbol= self.trade_state['hedge_symbol'], 
                                order_id = self._get_order_id(),
                                order_type= new_order_type, 
                                direction=self.trade_state['hedge_direction'],
                                price = new_order_price,
                                quantity=self.trade_state['hedge_qty'])
            self.trade_state['hedge_order_id'] = order.order_id
            self.events.put(order)

    def on_fill_event(self, event):
        """
        对 fill event 作出反应
        """
        # 只对全部成交作出反应
        if event.type != 'FILL': return
        if event.fill_flag != 'ALL': return

        # 如果是信号的开仓订单
        if self.trade_state['leader_t'] is None:
            self.trade_state['leader_t'] = event.timestamp
            self.trade_state['leader_price'] = event.price
            self.trade_state['leader_traded_is_Maker'] = event.is_Maker
            self.trade_state['leader_direction'] = event.direction
            self.trade_state['leader_order_id'] = event.order_id
            self.trade_state['leader_order_qty'] = event.quantity
            self.trade_state['leader_symbol'] = event.symbol
            self.trade_state['has_start_force'] = 0
            self.trade_state['leader_is_Maker'] = event.is_Maker
            self.trade_state['leader_fee'] = event.fee
            self.executor.cancel_all_orders()

            hedge_price = event.price*(1+self.k3)
            arrive_time = event.timestamp+ 2*self.order_latency
            stop_time = arrive_time + self.order_live_time
            hedge_symbol = self.pair_list[event.symbol]
            if event.direction =='BUY':
                hedge_direction = "SELL"
            if event.direction =='SELL':
                hedge_direction = "BUY"

            order = OrderEvent(timestamp = arrive_time, 
                                symbol = hedge_symbol, 
                                order_id = self._get_order_id(),
                                order_type = "POST_ONLY", 
                                direction = hedge_direction,
                                price = hedge_price,
                                quantity = event.quantity)
            self.events.put(order)
            # print(order)
            self.trade_state['stop_time'] = stop_time
            self.trade_state['hedge_order_id'] = order.order_id
            self.trade_state['hedge_symbol'] = order.symbol
            self.trade_state['hedge_direction'] = order.direction
            self.trade_state['hedge_qty'] = order.quantity
            self.trade_state['hedge_price'] = order.price
            return
        
        # 说明是在确认之前开仓的收益
        # 我们完成对一笔交易的记录
        elif self.trade_state['leader_t'] is not None:
            self.trade_state['hedge_t'] = event.timestamp
            self.trade_state['hedge_price'] = event.price
            self.trade_state['hedge_traded_is_Maker'] = event.is_Maker
            self.trade_state['hedge_order_id'] = event.order_id
            self.trade_state['hedge_fee'] = event.fee

            ## 一次交易完成，开始初始化
            ## 初始化之后我们可以重新计算信号并且开仓
            self.strategy_history.append(self.trade_state)
            self.trade_state = {'leader_t':None}
            self.executor.cancel_all_orders()
            # sys.exit()
            


                
        