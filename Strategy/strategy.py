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
