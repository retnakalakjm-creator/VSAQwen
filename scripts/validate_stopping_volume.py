from pathlib import Path

import pandas as pd

from data import download_data

from metrics_engine import MetricsEngine

from market_structure.swing_engine import SwingEngine

from market_structure.swing_history import SwingHistoryAnalyzer

from market_structure.trend_analyzer import TrendAnalyzer

from models import SwingContext

from smart_money.rules.stopping_volume import StoppingVolumeRule