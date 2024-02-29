# MarketDataStructure.py

"""
定义 行情数据类
定义行情数据基类，便于我们在其它的文件中约束数据格式

author: AbsoluteX
email: xilinliu@link.cuhk.edu.cn
"""

import copy


class MarketData(object):
    """行情数据类"""

    def __repr__(self):
        return self.__dict__.__repr__()

    def copy(self):
        return copy.deepcopy(self)


class Orderbook(MarketData):
    def __init__(self, symbol=None, bid1=None, bidqty1=None, 
                 ask1=None, askqty1=None, timestamp:int=None, 
                 receive_time=None):
        self.symbol = symbol
        self.bid1 = bid1
        self.bidqty1 = bidqty1
        self.ask1 = ask1
        self.askqty1 = askqty1
        self.timestamp = timestamp
        self.receive_time = receive_time


class Trade(MarketData):
    def __init__(self, symbol=None, price=None, qty=None, 
                 is_buyer_maker=None, timestamp:int=None, 
                 receive_time=None):
        self.symbol = symbol
        self.price = price
        self.qty = qty
        self.is_buyer_maker = is_buyer_maker
        self.timestamp = timestamp
        self.receive_time = receive_time


class Bar(MarketData):
    def __init__(self, symbol=None, bar_type=None, td=None, 
                 ts=None, open=None, high=None, low=None, 
                 close=None, timestamp:int=None, receive_time=None):
        self.symbol = symbol
        self.bar_type = bar_type
        self.td = td
        self.ts = ts
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.volume = None   # TODO: vol, amt, vwap, ticks
        self.amount = None
        self.vwap = None
        self.ticks = None
        self.timestamp = timestamp         # timestamp of last_price which close the bar, ie. new bar's open tick
        self.receive_time = receive_time   # receive_time of last_price which close the bar, ie. new bar's open tick


class Snapshot(MarketData):
    pass

