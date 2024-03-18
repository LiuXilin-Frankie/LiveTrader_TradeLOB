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

from event import OrderEvent
from object import Strategy
from Strategy.strategy import StrategyData, Strategy_Info

class LeadLagArbitrageStrategy(Strategy):
    """
    简单的策略进行测试
    我们买入等量的各种资产 s (默认1000美元)
    并且在每隔 20min 进行一次 rebalance
    """

    def __init__(self, events, datahandler, portfolio, executor, order_latency=50, 
                 k1=0.5 *1e-4, k2=1*1e-4, k3=1.5*1e-4, order_live_time = 20*1000):
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
        
        # arguments used in this strategy
        # Store useful infomation for order generate and stop loss
        self._gen_pair_list()
        self.signal_time = dict( (k,v) for k, v in [(s, None) for s in self.symbol_exchange_list] )
        self.last_trade = dict( (k,v) for k, v in [(s, None) for s in self.symbol_exchange_list] )

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
        traded_info = self.datahandler.registered_symbol_exchange_trade_data[s][self.datahandler.backtest_now]
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
        updated_trade_symbols = self.datahandler.get_updated_trade_symbols()
        for s in updated_trade_symbols:
            if self.signal_time[s] is None:
                self.calculate_signals(s)
            self.update_last_trade_s(s)
        
        # 检查已经开仓的symbols.


                
        