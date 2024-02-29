"""
类似于event
定义 object 的抽象类
包含 DataHandler, Portfolio, Excution, Strategy, Performance 模块
"""

from abc import ABCMeta, abstractmethod


class DataHandlerError(Exception):
    def __init__(self,errorinfo):
        self.errorinfo = errorinfo
    def __str__(self):
        print("DataHandlerError:",self.errorinfo)

class DataHandler(object):
    """
    DataHandler is an abstract base class providing an interface for all subsequent (inherited) data handlers (both live and historic).

    The goal of a (derived) DataHandler object is to output a generated set of tick(trades) for each symbol(in each exchange) requested. 

    This will replicate how a live strategy would function as current market data would be sent "down the pipe". 
    Thus a historic and live system will be treated identically by the rest of the backtesting suite.
    """

    __metaclass__ = ABCMeta

    @abstractmethod
    def get_latest_ticks(self, symbol, exchange, N=1):
        """
        Returns the last N ticks from the latest_symbol(exchange) list,
        or fewer if less ticks are available.
        """
        raise NotImplementedError("Should implement get_latest_ticks()")

    @abstractmethod
    def update_ticks(self):
        """
        Pushes the latest ticks to the latest symbol(exchange) structure
        for all symbols in the symbol(exchange) list.
        """
        raise NotImplementedError("Should implement update_ticks()")
    

class Strategy(object):
    """
    Strategy 是一个抽象基类，为所有后续（继承的）策略处理对象提供接口。
    通过计算trade中产生的交易信号, 对特定的标的产生 SignalEvent()
    """

    __metaclass__ = ABCMeta

    @abstractmethod
    def calculate_signals(self):
        """
        Provides the mechanisms to calculate the list of signals.
        """
        raise NotImplementedError("Should implement calculate_signals()")
    

class ExecutionHandler(object):
    """
    模拟交易所的撮合引擎
    抽象类，与之前类似
    """

    __metaclass__ = ABCMeta

    @abstractmethod
    def execute_order(self, event):
        """
        Takes an Order event and executes it, producing
        a Fill event that gets placed onto the Events queue.

        Parameters:
        event - Contains an Event object with order information.
        """
        raise NotImplementedError("Should implement execute_order()")
    

class Portfolio(object):
    """
    The Portfolio class handles the positions and market
    value of all instruments at a resolution of a frame.
    The Size of frame depends on the data you input
    """

    __metaclass__ = ABCMeta

    @abstractmethod
    def update_signal(self, event):
        """
        Acts on a SignalEvent to generate new orders 
        based on the portfolio logic.
        """
        raise NotImplementedError("Should implement update_signal()")

    @abstractmethod
    def update_fill(self, event):
        """
        Updates the portfolio current positions and holdings 
        from a FillEvent.
        """
        raise NotImplementedError("Should implement update_fill()")
    