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
import numpy as np

from event import FillEvent, OrderEvent
from object import ExecutionHandler
from Execution.OrderDataStructure import LiveOrder


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
        
        # 我们这个虚假交易所是否需要帮助优化 POST_ONLY 挂单
        self.change_post_only = True

    def cancel_all_orders(self):
        """
        取消所有订单
        暂时不返回 fill event
        """
        self.live_orders_on_exchange = dict( (k,v) for k, v in [(s, []) for s in self.symbol_exchange_list] )
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
                tmp = min([i.timestamp for i in self.live_orders_on_exchange[s]])
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

            # 调用尝试撮合函数
            self.on_market_event(event)
    
    def on_fill_event(self, event):
        """
        接受订单Fill信息
        成交/取消订单
        1.从 live_orders_on_exchange 中删除
        2.重新计算 live_orders_on_exchange_min_time
        """
        if event.type == 'FILL':
            new_orders = [i for i in self.live_orders_on_exchange[event.symbol] if i.order_id != event.order_id]
            self.live_orders_on_exchange[event.symbol] = new_orders
            # 更新 live_orders_on_exchange_min_time
            self._cal_live_orders_on_exchange_min_time()

    def on_market_event(self, event):
        """
        市场行情信息发生了更新，我们检查是否有 live_orders_on_exchange 发生撮合
        """
        time_now = self.datahandler.backtest_now
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

            # 市价单
            if order_tobe_execute.order_type == "MARKET":
                is_traded = self.execute_market_order(order_tobe_execute)
                # if is_traded: 
                #     # !!!这里应该交给 Fill event 来解决
                #     self.live_orders_on_exchange[s].pop(i)
                #     self._cal_live_orders_on_exchange_min_time()
            
            # IOC订单
            if order_tobe_execute.order_type == "IOC":
                is_traded = self.execute_IOC_order(order_tobe_execute)

            # LIMIT订单
            if order_tobe_execute.order_type == "LIMIT":
                is_traded = self.execute_LIMIT_order(order_tobe_execute)

            # POST_ONLY订单
            if order_tobe_execute.order_type == "POST_ONLY":
                is_traded = self.execute_POST_ONLY_order(order_tobe_execute)

    def execute_POST_ONLY_order(self, order:LiveOrder) -> bool:
        """
        执行 POST_ONLY order,

        传统的 POST_ONLY 订单应该是如果不能做市，交易所帮你取消
        这里设置了一个 self.change_post_only 如果为True会自动帮你改到合适的价格
        """
        # 重复检查
        if order.timestamp > self.datahandler.backtest_now : return False
        if order.order_type != "POST_ONLY":
            raise RuntimeError('Not POST_ONLY order but use execute_POST_ONLY_order func, please check your code')
        
        # 获取最新的LOB数据
        ### 这里可能出现 订单簿的更显时间与回测系统的 backtest_now 不一致的情况。默认订单簿没有发生改变
        live_LOB = self.datahandler.get_latest_LOBs()[order.symbol]

        # 检查是否能够成交
        traded_type = False
        traded_prc = np.nan
        
        if order.direction == 'BUY':
            if order.price >= live_LOB.ask1:
                traded_type = True
                traded_prc = live_LOB.ask1
                # print(order,'\n',live_LOB,'\n',traded_prc)
        
        if order.direction == 'SELL':
            if order.price <= live_LOB.bid1:
                traded_type = True
                traded_prc = live_LOB.bid1
                # print(order,'\n',live_LOB,'\n',traded_prc)
        
        # 检查对于一个限价订单挂过来，是不是会立刻作为 Taker 成交
        # 本来这个功能可以在 on_order_event 中实现，但是1.需要考虑订单的挂单延迟，2.一开始没有提前做好规划
        if order.help_state==0:
            if traded_type:
                if order.direction == 'BUY':
                    order.price = live_LOB.bid1
                if order.direction == 'SELL':
                    order.price = live_LOB.ask1
                traded_type = False
        if order.help_state==1:
            # sys.exit()
            is_Maker = True
            traded_prc = order.price
        order.help_state = 1

        if traded_type:
            # 向 event_queue put fill event
            fill_event = FillEvent(timestamp=self.datahandler.backtest_now, 
                                symbol=order.symbol, exchange=order.symbol.split("_")[-1], 
                                order_id=order.order_id, direction=order.direction, 
                                quantity=order.quantity, price=traded_prc, 
                                is_Maker=is_Maker, fill_flag = 'ALL')
            self.events.put(fill_event)
        return traded_type

    def execute_LIMIT_order(self, order:LiveOrder) -> bool:
        """
        执行 LIMIT order,
        """
        # 重复检查
        if order.timestamp > self.datahandler.backtest_now : return False
        if order.order_type != "LIMIT":
            raise RuntimeError('Not LIMIT order but use execute_LIMIT_order func, please check your code')
        
        # 获取最新的LOB数据
        ### 这里可能出现 订单簿的更显时间与回测系统的 backtest_now 不一致的情况。默认订单簿没有发生改变
        live_LOB = self.datahandler.get_latest_LOBs()[order.symbol]

        # 检查是否能够成交
        traded_type = False
        traded_prc = np.nan
        
        if order.direction == 'BUY':
            if order.price >= live_LOB.ask1:
                traded_type = True
                traded_prc = live_LOB.ask1
                # print(order,'\n',live_LOB,'\n',traded_prc)
        
        if order.direction == 'SELL':
            if order.price <= live_LOB.bid1:
                traded_type = True
                traded_prc = live_LOB.bid1
                # print(order,'\n',live_LOB,'\n',traded_prc)
        
        # 检查对于一个限价订单挂过来，是不是会立刻作为 Taker 成交
        # 本来这个功能可以在 on_order_event 中实现，但是1.需要考虑订单的挂单延迟，2.一开始没有提前做好规划
        if order.help_state==0:
            is_Maker = False
        if order.help_state==1:
            # sys.exit()
            is_Maker = True
            traded_prc = order.price
        order.help_state = 1

        if traded_type:
            # 向 event_queue put fill event
            fill_event = FillEvent(timestamp=self.datahandler.backtest_now, 
                                symbol=order.symbol, exchange=order.symbol.split("_")[-1], 
                                order_id=order.order_id, direction=order.direction, 
                                quantity=order.quantity, price=traded_prc, 
                                is_Maker=is_Maker, fill_flag = 'ALL')
            self.events.put(fill_event)
        return traded_type

    def execute_IOC_order(self, order:LiveOrder) -> bool:
        """
        执行 IOC order,
        无论如何都会 put FillEvent, 如果可以被成交告知其它模块，如果不能被成交则删除订单
        暂不支持部分成交
        return type:
            True 全部成交
            False 未成交
        """
        # 重复检查
        if order.timestamp > self.datahandler.backtest_now : return False
        if order.order_type != "IOC":
            raise RuntimeError('Not IOC order but use execute_IOC_order func, please check your code')
        
        # 获取最新的LOB数据
        ### 这里可能出现 订单簿的更显时间与回测系统的 backtest_now 不一致的情况。默认订单簿没有发生改变
        live_LOB = self.datahandler.get_latest_LOBs()[order.symbol]
        
        # 检查是否能够成交
        traded_type = False
        traded_prc = np.nan
        fill_flag = "CANCELED"
        
        if order.direction == 'BUY':
            if order.price >= live_LOB.ask1:
                traded_type = True
                traded_prc = live_LOB.ask1
                fill_flag = "ALL"
                # print(order,'\n',live_LOB,'\n',traded_prc)
        
        if order.direction == 'SELL':
            if order.price <= live_LOB.bid1:
                traded_type = True
                traded_prc = live_LOB.bid1
                fill_flag = "ALL"
                # print(order,'\n',live_LOB,'\n',traded_prc)
        
        # 向 event_queue put fill event
        fill_event = FillEvent(timestamp=self.datahandler.backtest_now, 
                               symbol=order.symbol, exchange=order.symbol.split("_")[-1], 
                               order_id=order.order_id, direction=order.direction, 
                               quantity=order.quantity, price=traded_prc, 
                               is_Maker=False, fill_flag = fill_flag)
        self.events.put(fill_event)
        return traded_type

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
        live_LOB = self.datahandler.get_latest_LOBs()[order.symbol]

        # 生成成交价格
        ### 系统忽略交易量这个概念，如果订单下单量超过订单簿的量会生成警告
        if order.direction == 'BUY':
            traded_prc = live_LOB.ask1
        if order.direction == 'SELL':
            traded_prc = live_LOB.bid1
         
        # 向 event_queue put fill event
        fill_event = FillEvent(timestamp=self.datahandler.backtest_now, 
                               symbol=order.symbol, exchange=order.symbol.split("_")[-1], 
                               order_id=order.order_id, direction=order.direction, 
                               quantity=order.quantity, price=traded_prc, is_Maker=False)
        self.events.put(fill_event)
        return True

