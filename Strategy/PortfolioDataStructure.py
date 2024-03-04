# PortfolioDataStructure.py

"""
定义用于记录交易信息的数据结构
便于我们在其它的文件中约束数据格式

author: AbsoluteX
email: xilinliu@link.cuhk.edu.cn
"""

import copy


class PortfolioData(object):
    """行情数据类"""

    def __repr__(self):
        return self.__dict__.__repr__()

    def copy(self):
        return copy.deepcopy(self)


class OpenPositionHistory(PortfolioData):
    """
    用于记录策略的开仓信息
    """
    def __init__(self, symbol, order_id, 
                 price=None, qty=None, is_maker=None, signal_timestamp=None,
                 traded_timestamp=None, positoin_closed=None, closed_order_id=None):
        self.symbol = symbol
        self.order_id = order_id
        self.price = price
        self.qty = qty
        self.is_maker = is_maker
        self.signal_timestamp = signal_timestamp
        self.traded_timestamp = traded_timestamp
        self.positoin_closed = positoin_closed
        self.closed_order_id = closed_order_id





