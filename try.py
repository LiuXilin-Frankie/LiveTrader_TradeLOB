import queue
import time
import os
import sys

from DataHandler.TradeLOBDataHandler import HistoricTradeLOBDataHandler
from Strategy.strategy import BuyAndHoldStrategy
from Portfolio.LogPlotPortfolio import LogPlotPortfolio
from Execution.execution import SimulatedExecutionHandler

event_queue = queue.Queue()
data_handler = HistoricTradeLOBDataHandler(event_queue, 
                                           symbol_list=['btc_usdt','eth_usdt','xrp_usdt'],
                                           exchange_list=['binance','binance','binance'], 
                                           file_dir = 'data_sample/small_sample/', 
                                           # file_dir = 'data_sample/',
                                           is_csv=False)


portfolio = LogPlotPortfolio(event_queue, data_handler)      # 组合
executor = SimulatedExecutionHandler(event_queue, data_handler)   # 回测模拟成交器；如果是实盘这里就是算法交易模块
strategy = BuyAndHoldStrategy(event_queue, data_handler, portfolio, executor)       # 策略实例。实际应用中应该有多个策略实例

cnt = 0
while True:
    # Update the trade/LOB (specific backtest code, as opposed to live trading)
    if data_handler.continue_backtest == True:
        data_handler.update_TradeLOB()
    else:
        break
    
    # cnt+=1
    # if cnt>2000: break

    # Handle the events
    while True:
        try:
            event = event_queue.get(False)
        except queue.Empty:
            break
        else:
            if event is not None:

                if event.type == 'MARKET':
                    print('get market event', event)
                    strategy.calculate_signals(event)
                    portfolio.update_holdings_from_market()
                    executor.on_market_event(event)

                # elif event.type == 'ORDER':
                #     executor.on_order_event(event)

                # elif event.type == 'FILL':
                #     print('get fill event', event)
                #     #portfolio.update_positions_from_fill(event)
                #     strategy
                #     sys.exit()