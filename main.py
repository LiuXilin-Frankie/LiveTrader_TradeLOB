# 主程序
# 命令行运行：
# $ python main.py


import queue
import time

from DataHandler.others.CSVDataHandler import CSVDataHandler
from Strategy.strategy import RandomStrategy
from Portfolio.portfolio import NaivePortfolio
from BarBacktestExecutor import BarBacktestExector


event_queue = queue.Queue()   # 事件队列

data_handler = CSVDataHandler(event_queue, 'data/IF.csv')  # 数据引擎

strategy = RandomStrategy(event_queue, data_handler)       # 策略实例。实际应用中应该有多个策略实例
portfolio = NaivePortfolio(event_queue, data_handler)      # 组合
executor = BarBacktestExector(event_queue, data_handler)   # 回测模拟成交器；如果是实盘这里就是算法交易模块

# 启动行情回放
data_handler.run()

while True:
    try:
        event = event_queue.get(block=True, timeout=3)
    except queue.Empty:
        break
    else:
        # 根据事件的不同类型，调用各自的 handlers 处理事件
        if event.type == 'MARKET':
            strategy.on_market_event(event)    # MarketEvent, 喂给策略，生成信号
            portfolio.on_market_event(event)    # MarketEvent, 喂给portfolio, 调整position_sizing && 调整限价单价格
            executor.on_market_event(event)   # 如果需要通过order_book精确的估计能否成交 ...

        elif event.type == 'SIGNAL':
            portfolio.on_signal_event(event)    # 信号 -> 组合

        elif event.type == 'ORDER':
            executor.on_order_event(event)    # 执行订单

        elif event.type == 'FILL':
            portfolio.on_fill_event(event)    # 根据成交回报更新持仓信息

while True:
    # Update the bars (specific backtest code, as opposed to live trading)
    if data_handler.continue_backtest == True:
        data_handler.update_bars()
    else:
        break
    
    # Handle the events
    while True:
        try:
            event = event_queue.get(False)
        except queue.Empty:
            break
        else:
            if event is not None:
                if event.type == 'MARKET':
                    strategy.calculate_signals(event)
                    portfolio.update_timeindex(event)

                elif event.type == 'SIGNAL':
                    portfolio.update_signal(event)

                elif event.type == 'ORDER':
                    executor.execute_order(event)

                elif event.type == 'FILL':
                    portfolio.update_fill(event)


