"""
简单的策略实践
1.用于接收market事件产生交易信号

后续需要开发：
1.跟踪portfolip净值并且设置止损
2.支持连续的策略动作 (signal1 + order1 + signal2 + order2 + ......)

refer to https://www.quantstart.com/articles/Event-Driven-Backtesting-with-Python-Part-IV/
"""

import datetime
import numpy as np
import pandas as pd
import queue
import sys
import copy
sys.path.append("...")

from abc import ABCMeta, abstractmethod

from event import OrderEvent
from object import Strategy


class StrategyData(object):
    """行情数据类"""

    def __repr__(self):
        return self.__dict__.__repr__()

    def copy(self):
        return copy.deepcopy(self)

class Strategy_Info(StrategyData):
    """
    用于记录策略的开仓信息
    """
    def __init__(self, symbol, order_id, 
                 signal_timestamp=None, traded_timestamp=None):
        self.symbol = symbol
        self.order_id = order_id
        self.signal_timestamp = signal_timestamp
        self.traded_timestamp = traded_timestamp


class BuyAndHoldStrategy(Strategy):
    """
    简单的策略进行测试
    我们买入等量的各种资产 s (默认1000美元)
    并且在每隔 20min 进行一次 rebalance
    """

    def __init__(self, events, datahandler, order_latency=50):
        """
        Initialises the buy and hold strategy.

        Parameters:
        trades - The DataHandler object that provides trade information
        events - The Event Queue object.
        """
        self.datahandler = datahandler
        self.symbol_exchange_list = self.datahandler.symbol_exchange_list
        self.events = events
        self.order_latency = order_latency
        self.order_id = 0
        
        # Store useful infomation for order generate and stop loss
        self.bought = self._calculate_initial_bought()

    def _calculate_initial_bought(self):
        """
        对于每一个资产，添加是否已经成交的信息
        """
        bought = {}
        for s in self.symbol_exchange_list:
            bought[s] = None
        return bought
    
    def _get_order_id(self):
        """
        用于返回 order_id 的函数，并且将 order_id 自动加一
        """
        tmp = self.order_id
        self.order_id += 1
        return tmp
    
    def calculate_signals(self, event):
        """
        如果一个资产没有被交易，我们生成信号并持有，如果已经有仓位，我们则忽略
        这也就意味着我们的 position_limit 为1
        """
        # 获取当前时间戳
        time_now = self.datahandler.backtest_now
        
        # 这里全部用来检测数据冗余
        if event.type == 'MARKET':
            for s in self.symbol_exchange_list:
                # 如果我们还没有进行第一次建仓
                if self.bought[s] is None:
                    if self.datahandler.latest_symbol_exchange_LOB_data_time[s] is None: continue
                    orderbook_info = self.datahandler.registered_symbol_exchange_LOB_data[s][self.datahandler.latest_symbol_exchange_LOB_data_time[s]][0]
                    # 生成order信息
                    # 这里 timestamp=(time_now + 2*self.order_latency) 指的是 order 到达交易所的时间，即挂在orderbook上的时间
                    order = OrderEvent(timestamp=time_now+2*self.order_latency, symbol=s, order_id = self._get_order_id(),
                                       order_type="MKT", direction='BUY', quantity=(1000/orderbook_info.ask1))
                    self.events.put(order)
                    self.bought[s] = Strategy_Info(symbol=order.symbol, order_id=order.order_id,  signal_timestamp=time_now)

                # 每过 20min 我们rebalance一次
                if self.bought[s] is not None:
                    last_trade_time = self.bought[s].signal_timestamp
                    if time_now - last_trade_time <  (1000*60*20): continue # 20min调仓一次
                    pass