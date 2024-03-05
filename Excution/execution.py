"""
excution 模块
1. 研究 portfolio 模块订单的执行
2. 简单研究我们的订单能不能成交，忽略高频层次上对于市场的影响

refer to https://www.quantstart.com/articles/Event-Driven-Backtesting-with-Python-Part-VI/
"""


import datetime
import queue

from abc import ABCMeta, abstractmethod

from event import FillEvent, OrderEvent
from object import ExecutionHandler
from OrderDataStructure import LiveOrder


class SimulatedExecutionHandler(ExecutionHandler):
    """
    The simulated execution handler simply converts all order
    objects into their equivalent fill objects automatically
    without latency, slippage or fill-ratio issues.

    This allows a straightforward "first go" test of any strategy,
    before implementation with a more sophisticated execution
    handler.
    """
    
    def __init__(self, events, datahandler):
        """
        Initialises the handler, setting the event queues
        up internally.

        Parameters:
        events - The Queue of Event objects.
        """
        self.events = events
        self.datahandler = datahandler
        self.symbol_exchange_list = self.datahandler.symbol_exchange_list
        # 每一个symbol存在的挂单
        self.live_orders_on_exchange = dict( (k,v) for k, v in [(s, []) for s in self.symbol_exchange_list] )
        # 每一个symbol存在的挂单中，最小的生效时间（为了考虑挂单延迟生成的辅助属性
        self.live_orders_on_exchange_min_time = dict( (k,v) for k, v in [(s, None) for s in self.symbol_exchange_list] )

    def _cal_live_orders_on_exchange_min_time(self):
        """
        用于计算每个 symbol 最小有效时间的订单
        在每次策略挂单发生变动的时候调用
        能够有效地检查当 MarketEvent 频繁到达而导致的重复检查浪费时间问题
        """
        for s in self.symbol_exchange_list:
            if len(self.live_orders_on_exchange[s])==0:
                self.live_orders_on_exchange_min_time[s] = None
            else:
                tmp = min([i.timestamp for i in self.live_orders_on_exchange])
                self.live_orders_on_exchange_min_time[s] = tmp

    def on_order_event(self, event):
        """
        接收新的下单信息 把新的订单加入到live_orders_on_exchange中
        """
        if event.type == 'ORDER':
            order = LiveOrder(timestamp = event.timestamp, symbol= event.symbol,
                              order_id= event.order_id, order_type= event.order_type, 
                              direction= event.direction, quantity= event.quantity, 
                              price= event.price)
            self.live_orders_on_exchange[order.symbol].append(order)
            # 更新 live_orders_on_exchange_min_time
            self._cal_live_orders_on_exchange_min_time()

    def on_market_event(self, event):
        """
        市场行情信息发生了更新，我们检查是否有 live_orders_on_exchange 发生撮合
        """
        time_now = self.datahandler.backtest_now
        if event.type == 'MARKET':
            for s in self.symbol_exchange_list:
                # 如果没有订单或者订单的生效时间在之后，我们都不对其进行撮合检查
                if self.live_orders_on_exchange_min_time[s] is None: continue
                if self.live_orders_on_exchange_min_time[s] > time_now: continue
                # 检查撮合
                self.try_excute_order(s)

    def try_excute_order(self, s):
        """
        检查 s 的订单是否发生撮合
        """
        time_now = self.datahandler.backtest_now
        live_order_list = self.live_orders_on_exchange[s]
        if len(live_order_list)==0: return  # 再做一次冗余性检查

        for i in range(len(live_order_list)):
            order_tobe_execute = live_order_list[i]
            if order_tobe_execute.timestamp > time_now: continue

            if 



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
