# event.py


"""
Events

- MarketEvent, 
            consumed by StrategyObject, and generate
            当 DataHandler 对象收到当前正在跟踪的任何交易品种的市场数据的新更新时，就被标记为这种事件。 它用于触发策略对象生成新的交易信号。 事件对象仅包含一个市场事件的标识，没有其他结构。
- SignalEvent, 
            consumed by PortfolioObject, and generate
            包含一个股票代码、生成时间的时间戳和方向（多头或空头）。
- OrderEvent, 
            handled by ExecutionHandler, generating
            当投资组合对象接收 SignalEvents 时，它会在投资组合的更广泛背景下根据风险和头寸规模对其进行评估。 这最终导致 OrderEvents 将被发送到 ExecutionHandler。
- FillEvent, 
            consumed by PortfolioObject, may then produce OrderEvent
            当 ExecutionHandler 收到 OrderEvent 时，它必须处理订单。 一旦订单被交易，它就会生成一个 FillEvent ，它描述购买或销售的成本以及交易成本，例如费用或滑点。
"""


class Event(object):
    """
    Event is base class providing an interface for all events, which will trigger further events.
    """
    pass


class MarketEvent(Event):
    """
    Handles the event of receiving a new market update with corresponding bars.
    """

    def __init__(self):
        self.type = 'MARKET'


class SignalEvent(Event):
    """
    Handles the event of sending a Signal from a Strategy object.
    This is received by a Portfolio object and acted upon.
    """

    def __init__(self, symbol, timestamp, signal_direction):
        """
        Initialises the SignalEvent.

        Parameters:
        symbol - The ticker symbol, e.g. 'GOOG'.
        datetime - The timestamp at which the signal was generated.
        signal_type - 'BUY' or 'SELL'.
        """
        self.type = 'SIGNAL'
        self.symbol = symbol
        self.timestamp = timestamp
        self.signal_direction = signal_direction   # 'BUY' or 'SELL'

    def __repr__(self):
        return "<SignalEvent> [%s] %s %s" % (self.timestamp, self.symbol, self.signal_direction)


class OrderEvent(Event):
    """
    Handles the event of sending an Order to an execution system.
    The order contains: 1.symbol, 2.type (market or limit or ....), 3.quantity, 4.direction, 5.arrive_time.
    """

    def __init__(self, timestamp, symbol, order_type, direction, quantity, price, arrive_time):
        """
        Parameters:
        symbol - The instrument to trade.
        order_type - 'MKT' or 'LMT' for Market or Limit.
        quantity - Non-negative integer for quantity.
        direction - 'BUY' or 'SELL' for long or short.
        """
        self.type = 'ORDER'
        self.timestamp = timestamp
        self.symbol = symbol
        self.order_type = order_type   # 'MKT', 'LMT' OR 'CANCEL_ORDER_REQ', or others....
        self.direction = direction     # 'BUY' or 'SELL'
        self.quantity = quantity       # non-negative
        self.price = price             # limit order price. If market order, this field is ignored
        self.arrive_time = arrive_time # 订单到达交易所的时间

    def __repr__(self):
        return "<OrderEvent> [%s] %s %s %s %d @ %.2f" % (self.timestamp, self.symbol, self.order_type, self.direction, self.quantity, self.price)


class FillEvent(Event):
    """
    FillEvent
    """

    def __init__(self, timestamp, symbol, exchange, direction, quantity, price, fill_flag, is_Maker):
        self.type = 'FILL'
        self.timestamp = timestamp     # timestamp of Fill
        self.symbol = symbol
        self.exchange = exchange       # 交易所，不用的交易所有不同的手续费
        self.direction = direction     # 'BUY' or 'SELL'
        self.quantity = quantity       # filled quantity
        self.price = price             # average price of filled orders
        self.fill_flag = fill_flag     # 'PARTIAL', 'ALL', 'CANCELED'
        self.is_Maker = is_Maker       # 是否是 Maker 成交，用于判断手续费

        self.fee = self.get_fee()      # 这里仅是费率，如果要考虑交易量的问题，应该进一步计算commission。这一版暂时忽略

    def get_fee(self):
        """
        获取交易所的手续费率
            如果是正数 则我们向交易所交钱
            如果返回的是负数 则我们获得激励金
        """
        if self.exchange.lower()=='okex':
            if self.is_Maker: return -0.00005
            else: return 0.00015
        if self.exchange.lower()=='binance':
            if self.is_Maker: return -0.00006
            else: return 0.000173

    def __repr__(self):
        return "<FillEvent> [%s] %s %s %d@%.2f" % (self.timestamp, self.symbol, self.direction, self.quantity, self.price)

