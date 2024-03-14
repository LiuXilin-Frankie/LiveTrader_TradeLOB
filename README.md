# LiveTrader_TradeLOB
面向数据编程, 基于 trade, LOB 数据的 Event-driven Backtest System

## 详情：
策略交易回测 - Event Driven Backtest System:
+ 同时可以获得两个资产的行情信息
+ 基于高频的 trade, tick, depth 数据，不基于kline数据
+ 根据后续行情模拟撮合(因为没有orders数据，所以不会是特别严谨的撮合逻辑)
+ 为您提供了数据样例以及快速运行的指导

# quickstart
```shell
pip install -r requirements.txt

# Other quick start instructions will be added soon
```

# System FrameWork
Idea from [quantstart article](https://www.quantstart.com/articles/Event-Driven-Backtesting-with-Python-Part-I/), 以下是该网站对于这一类回测系统基本架构的描述。如果您想了解本回测框架相比于该网站的区别，请看下文‘特性’。

### File Structure
+ _doc: contain some docs
+ data_sample: data_sample for u to run the sys
+ DataHandler: Module to push data
    + LOBHourlyDataHandler: hourly read and one-by-one push LOB data
    + TradeLOBHourlyDataHandler: hourly read and one-by-one push Trade & LOB data
    + MarketDataStructure: DataStructure will used in each DataHandler
    + others: histroy file, please ignore
+ Execution: Mock exchange execute
    + excution: please order in the mock exchange orderbook, mock trade
    + OrderDataStructure: DataStructure will used in each excution
+ Portfolio: used to log holdings and positions
+ Strategy: your strategy here
+ event: base event
+ object: base object
+ performance: used to gerate strategy performance report

### 特性：
1. 为了满足跨交易所交易的策略需求，品类命名被写为 "symbol_exchange" 的形式，比如说 "btc_usdt_binance", 所有需要考虑的品类名被存储在 symbol_exchange_list 中

2. 推送的顺序规则为: 1.品类名按照字母大小顺序排序, 2. trade 优先于 tick(LOB) 

3. 同一个时间点 timestamp 可能有多种数据，可能有多次 trade 信息。但是只会有一次LOB信息

4. 区别于原网站 1.使用迭代器推送整个数据，2.对时间异步的情况使用插值fillna的方法。本回测框架作出改进：1.将回测进行到的时间戳作为迭代器并且可以由外部访问；2.如果该时间下该币对没有数据，则不推送；3.约束了推送的数据格式，每一条交易是一个单独的object，同一时间的所有交易信息由list推送过来

5. Portfolio 不再掌管策略的下单，而是仅保留记录净值，仓位，成本等信息的功能。这也就代表了，portfolio模块可以相对固定，仅需要修改Strategy就可以使得代码运行起来。

6. 删除了 SignalEvent 这个事件，现在策略下单直接由 Strategy 掌握，同时止损也可以由 Strategy 接受 portfolio 中的信息进行下单

7. 使用 obejct 约束了数据的格式，访问数据的各种属性变得十分方便，不比像原作者一样需要记住所访问数据所在的位置


### 后续开发计划

1. datahandler 中转换数据为object开启多线程。

2. performance中分析方法的进一步补充

