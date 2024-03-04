"""
新的一版 Portfolio
剥离了复杂的功能 如题 更多的是负责记录
1. 根据 MrketEvent 更新 holdings
2. 根据 FillEvent 更新 positions
3. 记录开平仓的信息 生成完整的策略历史操作报告
4. 与 performance 模块沟通并且生成
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

class LogPlotPortfolio(Portfolio):
    """
    只用于记录的 Portfolio 模块
    """
    
    def __init__(self, events, datahandler, initial_capital=100000.0):
        """
        使用行情数据进行初始化. 包括开始的时间以及初识的资金量

        Parameters:
        trades - The DataHandler object with current market data.
        events - The Event Queue object.
        start_date - The start date (bar) of the portfolio.
        initial_capital - The starting capital in USD.
        all_positions - 历史仓位的记录
        current_positions - 目前仓位的净值
        all_holdings - 历史净值的记录
        current_holdings - 目前的净值
        """
        self.datahandler = datahandler
        self.events = events
        self.symbol_exchange_list = self.datahandler.symbol_exchange_list
        self.start_time = self.datahandler.start_time
        self.initial_capital = initial_capital
        
        self.construct_positions_holdings()

    def construct_positions_holdings(self):
        """
        init 用于记录仓位和净值的字典
        其实可以直接在 __init__ 中进行，但是由于想要展示可能的拓展性，所以单独写了一个函数
        """
        # {'btc_usdt_binance':{170000000:2, 170000200:5},....}
        self.all_positions = dict( (k,v) for k, v in [(s, {}) for s in self.symbol_exchange_list] )
        # {'btc_usdt_binance':2,....}
        self.current_positions = dict( (k,v) for k, v in [(s, 0) for s in self.symbol_exchange_list] ) 

        self.all_holdings = dict( (k,v) for k, v in [(s, {}) for s in self.symbol_exchange_list] )
        self.all_holdings['net_value'] = {}  # 记录净值曲线随着时间的变动
        # 我们可以在 current_holdings 中加入更多的计算
        # 这些东西同样也可以加入到 all_holdings 中
        # 这里暂时设置为 None
        self.current_holdings = dict( (k,v) for k, v in [(s, 0) for s in self.symbol_exchange_list] )
        self.current_holdings['cash'] = self.initial_capital
        self.current_holdings['commission'] = None
        self.current_holdings['net_value'] = 0

    def update_holdings_from_market(self):
        """
        根据 MarketEvent 更新 holdings 信息
        1.目前是默认全部重新计算一遍，其实可以只计算产生更新的，后续可以从这里优化运算时间。
        """
        trades = self.datahandler.get_latest_trades()
        net_value = 0
        for s in self.symbol_exchange_list:
            self.current_holdings[s] = trades[s].price * self.current_positions[s]
            self.all_holdings[s][self.datahandler.backtest_now] = self.current_holdings[s]
            net_value += self.current_holdings[s]
        self.current_holdings['net_value'] = net_value
        self.all_holdings['net_value'][self.datahandler.backtest_now] = net_value

    def update_positions_from_fill(self, event):
        """
        根据推送过来的订单成交信息更新 positions 和 holdings
        只更新 成交币对的 positions 和 holdings
        """
        



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
