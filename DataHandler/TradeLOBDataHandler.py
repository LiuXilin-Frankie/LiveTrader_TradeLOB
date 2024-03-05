# TradeLOBDataHandler.py

"""
区别于公开的 event-driven backtest system, 我们这里开始发生区别
1. 我们是高频的策略回测系统，我们使用 LOB 以及 trade 数据进行回测
2. trade数据是主体, LOB数据我们只保留最优买卖 bid1/ask1 以及相对应的vol
3. 因为很多情况下我们拿不到orders数据, 过于强调订单在UHF下对整个市场的影响是没有意义的

Distinguishing ourselves from publicly available event-driven backtest systems, here are the key differences:
1. We operate as a high-frequency strategy backtesting system, utilizing Limit Order Book (LOB) and trade data for our tests.
2. Trade data takes precedence, while for LOB data, we only retain the best bid and ask prices (bid1/ask1) along with their corresponding volumes.
3. Given the often unavailability of order data, emphasizing the impact of orders on the entire market under ultra-high-frequency (UHF) conditions becomes irrelevant.

refer to https://www.quantstart.com/articles/Event-Driven-Backtesting-with-Python-Part-III/
"""

import datetime
import os, os.path
import pandas as pd
import queue
from typing import List, Tuple, Dict
from abc import ABCMeta, abstractmethod
import sys
sys.path.append("...")

from event import MarketEvent
from object import DataHandler, DataHandlerError
from DataHandler.MarketDataStructure import Orderbook, Trade


class HistoricTradeLOBDataHandler(DataHandler):
    """
    从本地文件中读取历史数据生成 DataHandler, 读取的数据主要为 trade, LOB
    读取程序兼容 parquet 以及 csv 文件

    Read historical data from local files to generate a DataHandler, with the primary data being trade and Limit Order Book (LOB) data. 
    The reading program is compatible with both Parquet and CSV files.
    """
    def __init__(self, events:queue.Queue, symbol_list:List[str], exchange_list:List[str], 
                 file_dir: str, is_csv:bool = True) -> None:
        """
        初始化历史数据处理程序
        请求CSV文件的位置和符号列表。假设所有文件的格式都是 'symbol_exchange_trade.csv'/'symbol_exchange_LOB.csv'，其中 symbol/exchange 是列表中的str。
        Initialises the historic data handler by requesting the location of the CSV files and a list of symbols.
        It will be assumed that all files are of the form 'symbol_exchange.csv', where symbol/exchange is a string in the list.

        Parameters:
        events - The Event Queue.
        csv_dir - Absolute directory path to the CSV files.
        symbol_list - A list of symbol strings.
        exchange_list - A list of symbol exchange corresponding to the symbol_list
        """ 

        self.events = events
        self.file_dir = file_dir
        self.is_csv = is_csv
        self.symbol_exchange_list = self._agg_symbol_exchange_list(symbol_list, exchange_list)
        print('backtest on: ', self.symbol_exchange_list)

        # trade 数据
        self.__symbol_exchange_trade_data = {}                # 从csv读取的表单
        self.registered_symbol_exchange_trade_data = {}     # 最新的以及历史的数据
        self.latest_symbol_exchange_trade_data_time = {}    # 更新到的时间表
        # LOB 数据 (最高频的LOB 仅保存bid1&ask1)
        self.__symbol_exchange_LOB_data = {}                  # 从csv读取的表单
        self.registered_symbol_exchange_LOB_data = {}       # 最新的以及历史的数据
        self.latest_symbol_exchange_LOB_data_time = {}      # 更新到的时间表
        # 时间相关的指标
        self.start_time = None
        self.comb_time_index_iter = None
        self.backtest_now = None
        self.continue_backtest = True 

        # 需要处理的数据队列
        self.market_data_q = queue.Queue()    # MarketData队列（带数据）     

        print('/*----- start initialize the DataHandler -----*/')
        self._open_convert_csv_files()
        print('/*----- DataHandler initialization ends -----*/')

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
    
    def _open_convert_csv_files(self):
        """
        用于读取 trade LOB csv数据
        """
        ## trade
        comb_time_index = None
        for s in self.symbol_exchange_list:
            # 读取 csv/parquet 数据
            if self.is_csv:
                history_data_trade = pd.read_csv(
                    os.path.join(self.file_dir, '%s_trade.csv' % s)
                    )
                history_data_LOB = pd.read_csv(
                    os.path.join(self.file_dir, '%s_LOB.csv' % s)
                    )
            if not self.is_csv:
                history_data_trade = pd.read_parquet(
                    os.path.join(self.file_dir, '%s_trade.parquet' % s)
                    )
                history_data_LOB = pd.read_parquet(
                    os.path.join(self.file_dir, '%s_LOB.parquet' % s)
                    )

            # 约束存在的列
            history_data_trade = history_data_trade[['time','price','qty','is_buyer_maker']]
            history_data_LOB = history_data_LOB[['time','bid1','bidqty1','ask1','askqty1']]
            history_data_LOB = self._process_duplicated_time(history_data_LOB)  #删除重复的时间
            
            # 记录trade数据 目前很花时间
            self.__symbol_exchange_trade_data[s] = {i:[] for i in history_data_trade.time.unique()}
            for i in range(len(history_data_trade.time)):
                market_event = Trade(symbol=s, price=history_data_trade['price'][i], qty=history_data_trade['qty'][i], 
                                     is_buyer_maker=history_data_trade['is_buyer_maker'][i], timestamp=history_data_trade['time'][i])
                self.__symbol_exchange_trade_data[s][market_event.timestamp] += [market_event]
            
            # 记录LOB数据 目前很花时间
            self.__symbol_exchange_LOB_data[s] = {i:[] for i in history_data_LOB.time.unique()}
            for i in range(len(history_data_LOB.time)):
                market_event = Orderbook(symbol=s, bid1=history_data_LOB['bid1'][i], bidqty1=history_data_LOB['bidqty1'][i], 
                                         ask1=history_data_LOB['ask1'][i], askqty1=history_data_LOB['askqty1'][i], 
                                         timestamp=history_data_LOB['time'][i])
                self.__symbol_exchange_LOB_data[s][market_event.timestamp] += [market_event]

            # 初始化 latest 和 registered
            self.registered_symbol_exchange_trade_data[s] = {}
            self.latest_symbol_exchange_trade_data_time[s] = None
            self.registered_symbol_exchange_LOB_data[s] = {}
            self.latest_symbol_exchange_LOB_data_time[s] = None
            print('complete init of the data:',s)

            # 集合时间的index
            if comb_time_index is None:
                comb_time_index = history_data_trade.time.to_list() + history_data_LOB.time.to_list()
            else:
                comb_time_index += (history_data_trade.time.to_list() + history_data_LOB.time.to_list())

        comb_time_index = list(set(comb_time_index))
        comb_time_index.sort()
        self.start_time = comb_time_index[0]
        self.comb_time_index_iter = iter(comb_time_index)

    def _get_new_data(self):
        for s in self.symbol_exchange_list:
            try:
                self.registered_symbol_exchange_trade_data[s][self.backtest_now] = self.__symbol_exchange_trade_data[s][self.backtest_now]
                self.latest_symbol_exchange_trade_data_time[s] = self.backtest_now
            except: pass
            try:
                self.registered_symbol_exchange_LOB_data[s][self.backtest_now] = self.__symbol_exchange_LOB_data[s][self.backtest_now]
                self.latest_symbol_exchange_LOB_data_time[s] = self.backtest_now
            except: pass

    def update_TradeLOB(self):
        """
        Pushes the latest trade/LOB info in that time
        """
        try: # 获取现在迭代的时间戳
            self.backtest_now = self.comb_time_index_iter.__next__()
            print('\n===== processing market event in ',self.backtest_now,' =====')
            self._get_new_data()
            self.events.put(MarketEvent())
            print('get new market events and push to queue')
        except StopIteration:
            self.continue_backtest = False

    def get_latest_trades(self):
        outcomes = dict()
        for s in self.symbol_exchange_list:
            latest_time = self.latest_symbol_exchange_trade_data_time[s]
            if latest_time is not None:
                outcomes[s] = self.registered_symbol_exchange_trade_data[s][latest_time][-1]
        return outcomes