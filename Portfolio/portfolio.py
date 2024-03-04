"""
portfolio 模块具有最复杂的功能
1. 持续跟踪目前持有仓位的净价值
2. 具有优化下单的能力，保证利益最大化
3. 能够处理 SignalEvent, 生成 OrderEvent, 解释 FillEvent 并且更新仓位

refer to https://www.quantstart.com/articles/Event-Driven-Backtesting-with-Python-Part-V/
"""

import datetime
import numpy as np
import pandas as pd
import queue

from abc import ABCMeta, abstractmethod
from math import floor
import sys
sys.path.append("...")

from event import FillEvent, OrderEvent
from object import Portfolio
from performance import *


class NaivePortfolio(Portfolio):
    """
    简单的 Portfolio 类
    没有进行风险管理，没有止损设置等等
    仅是进行简单的测试作用
    """
    
    def __init__(self, trades, events, start_time, initial_capital=100000.0):
        """
        使用行情数据进行初始化. 包括开始的时间以及初识的资金量

        Parameters:
        trades - The DataHandler object with current market data.
        events - The Event Queue object.
        start_date - The start date (bar) of the portfolio.
        initial_capital - The starting capital in USD.
        all_holdings - 历史净值的记录
        current_holdings - 目前的净值
        """
        self.trades = trades
        self.events = events
        self.symbol_exchange_list = self.trades.symbol_exchange_list
        self.start_time = start_time
        self.initial_capital = initial_capital
        
        self.all_positions = self.construct_all_positions()
        self.current_positions = dict( (k,v) for k, v in [(s, 0) for s in self.symbol_exchange_list] )

        self.all_holdings = self.construct_all_holdings()
        self.current_holdings = self.construct_current_holdings()
    
    def construct_all_positions(self):
        """
        创建用于记录仓位的字典
        为每一个 symbol_exchange 设置一个字典，并且初始化为 0
        并且添加相应的时间
        """
        d = dict( (k,v) for k, v in [(s, 0) for s in self.symbol_exchange_list] )
        d['datetime'] = self.start_date
        return [d]

    def construct_all_holdings(self):
        """
        创建用于记录净值的字典，方法本质上和 construct_all_positions 类似
        """
        d = dict( (k,v) for k, v in [(s, 0.0) for s in self.symbol_exchange_list] )
        d['datetime'] = self.start_date
        d['cash'] = self.initial_capital
        d['commission'] = 0.0
        d['total'] = self.initial_capital
        return [d]

    def construct_current_holdings(self):
        """
        创建用于记录目前净值的字典，方法本质上和 construct_all_positions 类似
        """
        d = dict( (k,v) for k, v in [(s, 0.0) for s in self.symbol_exchange_list] )
        d['cash'] = self.initial_capital
        d['commission'] = 0.0
        d['total'] = self.initial_capital
        return d

    def update_from_market(self, event):
        """
        根据最新的市场行情信息更新数据
        1. current holdings 在每次接收到 MarketEvent 就会更新
        2. current position 在每次接收到 FillEvent 就会更新
        """
        trades = {}
        for sym in self.symbol_exchange_list:
            trades[sym] = self.trades.get_latest_trades(sym, N=1)

        # Update positions
        dp = dict( (k,v) for k, v in [(s, 0) for s in self.symbol_exchange_list] )
        dp['datetime'] = trades[self.symbol_exchange_list[0]][0][1]

        for s in self.symbol_exchange_list:
            dp[s] = self.current_positions[s]

        # Append the current positions
        self.all_positions.append(dp)

        # Update holdings
        dh = dict( (k,v) for k, v in [(s, 0) for s in self.symbol_exchange_list] )
        dh['datetime'] = trades[self.symbol_exchange_list[0]][0][1]
        dh['cash'] = self.current_holdings['cash']
        dh['commission'] = self.current_holdings['commission']
        dh['total'] = self.current_holdings['cash']

        for s in self.symbol_exchange_list:
            # Approximation to the real value
            market_value = self.current_positions[s] * trades[s][0][0]  # prc
            dh[s] = market_value
            dh['total'] += market_value

        # Append the current holdings
        self.all_holdings.append(dh)

    def update_positions_from_fill(self, fill):
        """
        根据 FillEvent 更新目前的仓位信息
        """
        # Check whether the fill is a buy or sell
        fill_dir = 0
        if fill.direction == 'BUY':
            fill_dir = 1
        if fill.direction == 'SELL':
            fill_dir = -1

        # Update positions list with new quantities
        self.current_positions[fill.symbol_exchange] += fill_dir*fill.quantity

    def update_holdings_from_fill(self, fill):
        """
        同时需要根据 FillEvent 更新目前的净值信息

        Parameters:
        fill - The FillEvent object to update the holdings with.
        """
        # Check whether the fill is a buy or sell
        fill_dir = 0
        if fill.direction == 'BUY':
            fill_dir = 1
        if fill.direction == 'SELL':
            fill_dir = -1

        # Update holdings list with new quantities
        fill_cost = self.trades.get_latest_trades(fill.symbol)[0][0]  # Close price
        cost = fill_dir * fill_cost * fill.quantity
        self.current_holdings[fill.symbol_exchange] += cost
        self.current_holdings['commission'] += fill.commission
        self.current_holdings['cash'] -= (cost + fill.commission)
        self.current_holdings['total'] -= (cost + fill.commission)

    def update_from_fill(self, event):
        """
        根据 FillEvent 调用上面的方法
        """
        if event.type == 'FILL':
            self.update_positions_from_fill(event)
            self.update_holdings_from_fill(event)

    def generate_naive_order(self, signal):
        """
        针对 naive strategy 进行简单的下单

        Parameters:
        signal - The SignalEvent signal information.
        """
        order = None

        symbol_exchange = signal.symbol_exchange
        direction = signal.signal_type
        strength = signal.strength

        mkt_quantity = floor(100 * strength)
        cur_quantity = self.current_positions[symbol_exchange]
        order_type = 'MKT'

        if direction == 'LONG' and cur_quantity == 0:
            order = OrderEvent(symbol_exchange, order_type, mkt_quantity, 'BUY')
        if direction == 'SHORT' and cur_quantity == 0:
            order = OrderEvent(symbol_exchange, order_type, mkt_quantity, 'SELL')   
    
        if direction == 'EXIT' and cur_quantity > 0:
            order = OrderEvent(symbol_exchange, order_type, abs(cur_quantity), 'SELL')
        if direction == 'EXIT' and cur_quantity < 0:
            order = OrderEvent(symbol_exchange, order_type, abs(cur_quantity), 'BUY')
        return order

    def update_signal(self, event):
        """
        Acts on a SignalEvent to generate new orders based on the portfolio logic.
        """
        if event.type == 'SIGNAL':
            order_event = self.generate_naive_order(event)
            self.events.put(order_event)

    def create_equity_curve_dataframe(self):
        """
        生成净值曲线
        """
        curve = pd.DataFrame(self.all_holdings)
        curve.set_index('datetime', inplace=True)
        curve['returns'] = curve['total'].pct_change()
        curve['equity_curve'] = (1.0+curve['returns']).cumprod()
        self.equity_curve = curve

    def output_summary_stats(self):
        """
        一个计算策略表现的简单分析器
        需要提前定义一些函数并引用
        这里更多是样例的示范
        Creates a list of summary statistics for the portfolio such
        as Sharpe Ratio and drawdown information.
        """
        total_return = self.equity_curve['equity_curve'][-1]
        returns = self.equity_curve['returns']
        pnl = self.equity_curve['equity_curve']

        sharpe_ratio = create_sharpe_ratio(returns)
        max_dd, dd_duration = create_drawdowns(pnl)

        stats = [("Total Return", "%0.2f%%" % ((total_return - 1.0) * 100.0)),
                 ("Sharpe Ratio", "%0.2f" % sharpe_ratio),
                 ("Max Drawdown", "%0.2f%%" % (max_dd * 100.0)),
                 ("Drawdown Duration", "%d" % dd_duration)]
        return stats
