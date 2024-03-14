# CSVDataHandler

"""
区别于公开的 event-driven backtest system, 我们这里开始发生区别
1. 我们是高频的策略回测系统，我们使用 LOB 以及 trade 数据进行回测
2. LOB数据是主体, 我们只保留最优买卖 bid1/ask1. trade数据可以为空
3. 因为很多情况下我们拿不到orders数据, 过于强调订单在UHF下对整个市场的影响是没有意义的

refer to https://www.quantstart.com/articles/Event-Driven-Backtesting-with-Python-Part-III/
"""

import datetime
import os, os.path
import pandas as pd
import sys
sys.path.append("..")

from abc import ABCMeta, abstractmethod

from event import MarketEvent
from object import DataHandler, DataHandlerError


class HistoricCSVDataHandler(DataHandler):
    """
    HistoricCSVDataHandler is designed to read CSV files for
    each requested symbol from disk and provide an interface
    to obtain the "latest" tick/trade in a manner identical to a live
    trading interface. 
    """

    def __init__(self, events, csv_dir, symbol_list, exchange_list):
        """
        Initialises the historic data handler by requesting
        the location of the CSV files and a list of symbols.

        It will be assumed that all files are of the form
        'symbol_exchange.csv', where symbol is a string in the list.

        Parameters:
        events - The Event Queue.
        csv_dir - Absolute directory path to the CSV files.
        symbol_list - A list of symbol strings.
        exchange_list - A list of symbol exchange corresponding to the symbol_list

        注意：
        为了支持一些跨交易所套利，以及适应不同的交易所不同的手续费率，增加了 exchange_list
        init中会将 symbol_list, exchange_list 聚合成新的 symbol_exchange_list
        exchange_list 不可为空，如果您的数据回测全部在同一个交易所，也请提交长度与 symbol_list 等长的 exchange_list
        symbol_exchange_list 应该能够构成数据的 keys
        """
        self.events = events
        self.csv_dir = csv_dir
        # self.symbol_list = symbol_list
        # self.exchange_list = exchange_list
        self.symbol_exchange_list = self._agg_symbol_exchange_list(symbol_list, exchange_list)

        # trade 数据
        self.symbol_exchange_trade_data = {}
        self.latest_symbol_exchange_trade_data = {}
        # tick 数据 (最高频的LOB 仅保存bid1&ask1)
        self.symbol_exchange_tick_data = {}
        self.latest_symbol_exchange_tick_data = {}
        self.continue_backtest = True       

        self._open_convert_csv_files()

    def _agg_symbol_exchange_list(self, symbol_list, exchange_list):
        """
        用于聚合 symbol_exchange_list 的工具函数
        """
        symbol_exchange_list_temp  = []
        if len(symbol_list) != len(exchange_list):
            raise DataHandlerError(' symbol_list 和 exchange_list 长度不同, 请检查您的输入')
        for i in range(len(symbol_list)):
            symbol_exchange = str(symbol_list[i]) + '_' + str(exchange_list[i])
            if symbol_exchange in symbol_exchange_list_temp:
                raise DataHandlerError(' symbol_list 和 exchange_list 聚合后不能形成数据的 key, 请检查您的输入')
            symbol_exchange_list_temp.append(symbol_exchange)
        
        return symbol_exchange_list_temp

    def _process_duplicated_time(self, df):
        """
        因为 Sys 把 timestep 作为数据的 key 推送， 必须删除其中重复的
        我们仅保留最后一次出现的样本
        """
        df = df.drop_duplicates(subset=['time'],keep='last').reset_index(drop=True)
        return df

    def _open_convert_csv_files_trade(self):
        """
        用于读取 trade csv数据
        """
        ## trade
        comb_index = None
        for s in self.symbol_exchange_list:
            # 读取csv数据，csv的存储格式采用默认的方式
            self.symbol_exchange_trade_data[s] = pd.read_csv(
                os.path.join(self.csv_dir, '%s_trade.csv' % s)
            )
            self.symbol_exchange_trade_data[s] = self.symbol_exchange_trade_data[s][['time','price','qty','is_buyer_maker']] # 约束有哪些列
            self.symbol_exchange_trade_data[s] = self._process_duplicated_time(self.symbol_exchange_trade_data[s])  # 删除时间副本
            self.symbol_exchange_trade_data[s] = self.symbol_exchange_trade_data[s].set_index(keys='time')
            self.symbol_exchange_trade_data[s].sort_index(inplace=True)

            # 将index(time)值合并，级把所有的time融合，保持数据的一致性。
            if comb_index is None:
                comb_index = self.symbol_exchange_trade_data[s].index
            else:
                comb_index.union(self.symbol_exchange_trade_data[s].index)

            # Set the latest symbol_data to None
            self.latest_symbol_exchange_trade_data[s] = []

        for s in self.symbol_exchange_list:
            self.symbol_exchange_trade_data[s] = self.symbol_exchange_trade_data[s].reindex(
                index=comb_index, method='pad'
            )
            self.symbol_exchange_trade_data[s]["returns"] = self.symbol_exchange_trade_data[s]["adj_close"].pct_change().fillna(0)
            self.symbol_exchange_trade_data[s]["price_change"] = (self.symbol_exchange_trade_data[s]["price"].shift(1) - self.symbol_exchange_trade_data[s]["price"]).fillna(0)
            self.symbol_exchange_trade_data[s] = self.symbol_exchange_trade_data[s].iterrows()

        # Reindex the dataframes
        for s in self.symbol_list:
            self.symbol_exchange_trade_data[s] = self.symbol_exchange_trade_data[s].reindex(index=comb_index, method='pad').iterrows()

    def _get_new_trade(self, symbol_exchange):
        """
        return the latest trade data for the "symbol_exchange"
        """
        for b in self.symbol_exchange_trade_data[symbol_exchange]:
            yield tuple([symbol_exchange, b[0], 
                        b[1][0], b[1][1], b[1][2], b[1][3], b[1][4]])

    def get_latest_trades(self, symbol_exchange, N=1):
        """
        Returns the last N bars from the latest_symbol list,
        or N-k if less available.
        """
        try:
            trades_list = self.latest_symbol_exchange_trade_data[symbol_exchange]
        except KeyError:
            print("That symbol_exchange is not available in the historical data set.")
        else:
            return trades_list[-N:]
        
    def update_trades(self):
        """
        Pushes the latest bar to the latest_symbol_data structure
        for all symbols in the symbol list.
        """
        for s in self.symbol_exchange:
            try:
                trade = self._get_new_trade(s).next()
            except StopIteration:
                self.continue_backtest = False
            else:
                if trade is not None:
                    self.latest_symbol_exchange_trade_data[s].append(trade)
        self.events.put(MarketEvent())










