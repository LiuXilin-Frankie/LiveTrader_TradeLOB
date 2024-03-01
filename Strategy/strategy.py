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
import Queue

from abc import ABCMeta, abstractmethod

from ..event import SignalEvent
from ..object import Strategy
    

class BuyAndHoldStrategy(Strategy):
    """
    简单的策略进行测试
    """

    def __init__(self, trades, events):
        """
        Initialises the buy and hold strategy.

        Parameters:
        trades - The DataHandler object that provides trade information
        events - The Event Queue object.
        """
        self.trades = trades
        self.symbol_exchange_list = self.trades.symbol_exchange_list
        self.events = events

        # Once buy & hold signal is given, these are set to True
        self.bought = self._calculate_initial_bought()

    def _calculate_initial_bought(self):
        """
        对于每一个资产，添加是否已经成交的信息
        """
        bought = {}
        for s in self.symbol_exchange_list:
            bought[s] = False
        return bought
    
    def calculate_signals(self, event):
        """
        如果一个资产没有被交易，我们生成信号并持有，如果已经有仓位，我们则忽略
        这也就意味着我们的 position_limit 为1
        """
        # 这里全部用来检测数据冗余
        if event.type == 'MARKET':
            for s in self.symbol_list:
                trades = self.trades.get_latest_trades(s, N=1)
                if trades is not None and trades != []:
                    if self.bought[s] == False:
                        # 开始进行策略判断
                        # SignalEvent is (Symbol, Datetime, Type = LONG, SHORT or EXIT)
                        signal = SignalEvent(trades[0][0], trades[0][1], 'LONG')
                        self.events.put(signal)
                        self.bought[s] = True