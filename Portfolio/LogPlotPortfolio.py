"""
新的一版 Portfolio
剥离了复杂的功能 如题 更多的是负责记录
1. 根据 MrketEvent 更新 holdings
2. 根据 FillEvent 更新 positions
3. 记录开平仓的信息 生成完整的策略历史操作报告
4. 与 performance 模块沟通并且生成
"""

import datetime
import numpy as np
import pandas as pd
import queue

from abc import ABCMeta, abstractmethod
from math import floor
import sys
sys.path.append("...")

from event import FillEvent, OrderEvent
from object import Portfolio
from performance import *