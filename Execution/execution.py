"""
excution 模块
1. 研究 portfolio 模块订单的执行
2. 简单研究我们的订单能不能成交，忽略高频层次上对于市场的影响

refer to https://www.quantstart.com/articles/Event-Driven-Backtesting-with-Python-Part-VI/
"""


import datetime
import queue
from abc import ABCMeta, abstractmethod
import sys
sys.path.append("..")

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
        if len(self.live_orders_on_exchange[s])==0: return  # 再做一次冗余性检查

        for i in range(len(self.live_orders_on_exchange[s])):
            order_tobe_execute = self.live_orders_on_exchange[s][i]
            if order_tobe_execute.timestamp > time_now: continue

            if order_tobe_execute.order_type == "MARKET":
                is_traded = self.execute_market_order(order_tobe_execute)
                if is_traded: 
                    self.live_orders_on_exchange[s].pop(i)
                    # 这里调用有点危险 先这样再说吧
                    self._cal_live_orders_on_exchange_min_time()
                continue

            # if order_tobe_execute
    
    def execute_market_order(self, order:LiveOrder) -> bool:
        """
        执行 MKT order, 会直接强制成交所有的交易量（即使在订单簿存在订单量不够的情况下
        暂不支持部分成交
        return type:
            True 全部成交
            False 未成交
        """
        # 重复检查
        if order.timestamp > self.datahandler.backtest_now : return False
        if order.order_type != "MARKET":
            raise RuntimeError('Not market order but use execute_market_order func, please check your code')
        
        # 获取最新的LOB数据
        ### 这里可能出现 订单簿的更显时间与回测系统的 backtest_now 不一致的情况。默认订单簿没有发生改变
        live_LOB = self.datahandler.registered_symbol_exchange_LOB_data[self.datahandler.latest_symbol_exchange_LOB_data_time[order.symbol]][0]
        
        # 生成成交价格
        ### 系统忽略交易量这个概念，如果订单下单量超过订单簿的量会生成警告
        if order.direction == 'BUY':
            traded_prc = live_LOB.ask1
            if order.quantity > live_LOB.askqty1:
                raise Warning("mkt order exceed the LOB ask1 size for order_id: "+str(order.order_id))
        if order.direction == 'SELL':
            traded_prc = live_LOB.bid1
            if order.quantity > live_LOB.bidqty1:
                raise Warning("mkt order exceed the LOB ask1 size for order_id: "+str(order.order_id))
            
        # 向 event_queue put fill event
        fill_event = FillEvent(timestamp=self.datahandler.backtest_now, 
                               symbol=order.symbol, exchange=order.symbol.split("_")[-1], 
                               order_id=order.order_id, direction=order.direction, 
                               quantity=order.quantity, price=traded_prc, is_Maker=False)
        self.events.put(fill_event)
        return True



    # def execute_order(self, event):
    #     """
    #     需要后续添加:
    #         1. latency
    #         2. different fees depends on exchange
    #         3. 区分 maker & taker

    #     Parameters:
    #     event - Contains an Event object with order information.
    #     """
    #     if event.type == 'ORDER':
    #         # 这里直接假设成交
    #         # fill_cost 被设定为 None, 后续有更加严格的需求可以设定为其它值
    #         # ARCA 是简单的交易所占位符
    #         fill_event = FillEvent(datetime.datetime.utcnow(), event.symbol,
    #                                'ARCA', event.quantity, event.direction, None)
    #         self.events.put(fill_event)
