import queue

from TradeLOBDataHandler import HistoricTradeLOBDataHandler


event_queue = queue.Queue()
data_handler = HistoricTradeLOBDataHandler(event_queue, 
                                           symbol_list=['btc_usdt','btc_usdt'],
                                           exchange_list=['binance','okex'], 
                                           file_dir = 'data_sample/', 
                                           is_csv=False)