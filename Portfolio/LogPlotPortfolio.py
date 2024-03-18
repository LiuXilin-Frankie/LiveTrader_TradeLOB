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
sys.path.append("..")

from event import FillEvent, OrderEvent
from object import Portfolio
from Portfolio.Performance import *

class LogPlotPortfolio(Portfolio):
    """
    只用于记录的 Portfolio 模块
    """
    
    def __init__(self, events, datahandler, initial_capital=100000.0, log_interval=None):
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
        self.log_interval = log_interval
        self.last_log_time = None
        
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
        self.all_holdings['cash'] = {self.start_time:self.initial_capital,}
        # 我们可以在 current_holdings 中加入更多的计算
        # 这些东西同样也可以加入到 all_holdings 中
        # 这里暂时设置为 None
        self.current_holdings = dict( (k,v) for k, v in [(s, 0) for s in self.symbol_exchange_list] )
        self.current_holdings['cash'] = self.initial_capital
        self.current_holdings['commission'] = None
        self.current_holdings['net_value'] = 0

    def on_market_event(self,event):
        self.update_holdings_from_market()

    def update_holdings_from_market(self):
        """
        根据 MarketEvent 更新 holdings 信息
        1.目前是默认全部重新计算一遍，其实可以只计算产生更新的，后续可以从这里优化运算时间。
        只有发生更改我们才会记录
        """
        # 间隔一定的时间进行记录
        if self.log_interval is not None:
            if self.datahandler.backtest_now - self.last_log_time > self.log_interval:
                self.last_log_time = self.datahandler.backtest_now
            else: return

        # 开始更新记录
        trades = self.datahandler.get_latest_prices()
        net_value = 0
        if trades is not None:
            for s in self.symbol_exchange_list:
                if s not in trades: continue
                # 记录之前的值观察是否出现变动
                current_value_s = trades[s] * self.current_positions[s]
                if current_value_s != self.current_holdings[s]:
                    self.current_holdings[s] = current_value_s
                    self.all_holdings[s][self.datahandler.backtest_now] = self.current_holdings[s]
                net_value += self.current_holdings[s]
            # 记录总值
            if net_value!= self.current_holdings['net_value']:
                self.current_holdings['net_value'] = net_value
                self.all_holdings['net_value'][self.datahandler.backtest_now] = net_value

    def on_fill_event(self,event):
        if event.type == "FILL":
            if event.fill_flag == 'ALL':
                self.update_positions_from_fill(event)

    def update_positions_from_fill(self, event):
        """
        根据推送过来的订单成交信息更新 positions 和 holdings
        只更新 成交币对的 positions 和 holdings
        """
        if event.type == "FILL":
            # 更新持仓信息
            if event.direction=="BUY":
                self.current_positions[event.symbol] += abs(event.quantity)
            if event.direction=="SELL":
                self.current_positions[event.symbol] -= abs(event.quantity)
            self.all_positions[event.symbol][self.datahandler.backtest_now] = self.current_positions[event.symbol]
            
            # 更新账户余额
            self.current_holdings['cash'] -= event.cash_cost
            self.all_holdings['cash'][self.datahandler.backtest_now] = self.current_holdings['cash']
            
            # 更新净值信息
            change_of_holdings = event.price * self.current_positions[event.symbol] - self.current_holdings[event.symbol]
            self.current_holdings[event.symbol] += change_of_holdings
            self.all_holdings[event.symbol][self.datahandler.backtest_now] = self.current_holdings[event.symbol]
            self.current_holdings['net_value'] += change_of_holdings
            self.all_holdings['net_value'][self.datahandler.backtest_now] = self.current_holdings['net_value']

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
