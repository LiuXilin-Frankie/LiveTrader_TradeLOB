import copy


class OrderData(object):
    """行情数据类"""

    def __repr__(self):
        return self.__dict__.__repr__()

    def copy(self):
        return copy.deepcopy(self)


class LiveOrder(OrderData):
    def __init__(self, timestamp, symbol, order_id, 
                 order_type, direction, quantity, price=None):
        # timestamp 指的是订单达到交易所的时间，也就是生效时间
        self.timestamp = timestamp
        self.symbol = symbol
        self.order_id = order_id
        self.order_type = order_type
        self.direction = direction
        self.quantity = quantity
        self.price = price
        self.help_state = 0



