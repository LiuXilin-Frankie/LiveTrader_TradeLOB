"""
excution 模块
1. 研究 portfolio 模块订单的执行
2. 简单研究我们的订单能不能成交，忽略高频层次上对于市场的影响

refer to https://www.quantstart.com/articles/Event-Driven-Backtesting-with-Python-Part-VI/
"""


import datetime
import Queue

from abc import ABCMeta, abstractmethod

from event import FillEvent, OrderEvent


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


class SimulatedExecutionHandler(ExecutionHandler):
    """
    The simulated execution handler simply converts all order
    objects into their equivalent fill objects automatically
    without latency, slippage or fill-ratio issues.

    This allows a straightforward "first go" test of any strategy,
    before implementation with a more sophisticated execution
    handler.
    """
    
    def __init__(self, events):
        """
        Initialises the handler, setting the event queues
        up internally.

        Parameters:
        events - The Queue of Event objects.
        """
        self.events = events

    def execute_order(self, event):
        """
        需要后续添加:
            1. latency
            2. different fees depends on exchange
            3. 区分 maker & taker

        Parameters:
        event - Contains an Event object with order information.
        """
        if event.type == 'ORDER':
            # 这里直接假设成交
            # fill_cost 被设定为 None, 后续有更加严格的需求可以设定为其它值
            # ARCA 是简单的交易所占位符
            fill_event = FillEvent(datetime.datetime.utcnow(), event.symbol,
                                   'ARCA', event.quantity, event.direction, None)
            self.events.put(fill_event)
