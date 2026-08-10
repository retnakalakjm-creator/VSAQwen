"""
Professional VSA Swing Scanner

Canonical DataFrame column names.

Every module should import these constants instead of
using string literals.
"""

# -----------------------------------------------------------------------------
# OHLCV
# -----------------------------------------------------------------------------

COL_WEEK = "week_beginning"

COL_OPEN = "open"
COL_HIGH = "high"
COL_LOW = "low"
COL_CLOSE = "close"
COL_VOLUME = "volume"

# -----------------------------------------------------------------------------
# Basic Metrics
# -----------------------------------------------------------------------------

COL_SPREAD = "spread"
COL_BODY = "body"

COL_UPPER_SHADOW = "upper_shadow"
COL_LOWER_SHADOW = "lower_shadow"

COL_CLOSE_RATIO = "close_ratio"

# -----------------------------------------------------------------------------
# Previous Bar
# -----------------------------------------------------------------------------

COL_PREV_OPEN = "prev_open"
COL_PREV_HIGH = "prev_high"
COL_PREV_LOW = "prev_low"
COL_PREV_CLOSE = "prev_close"
COL_PREV_VOLUME = "prev_volume"
COL_PREV_SPREAD = "prev_spread"

# -----------------------------------------------------------------------------
# Price Movement
# -----------------------------------------------------------------------------

COL_PRICE_CHANGE = "price_change"
COL_PRICE_CHANGE_PCT = "price_change_pct"

# -----------------------------------------------------------------------------
# Rolling Statistics
# -----------------------------------------------------------------------------

COL_AVG_VOLUME = "avg_volume"
COL_STD_VOLUME = "std_volume"

COL_AVG_SPREAD = "avg_spread"
COL_STD_SPREAD = "std_spread"

COL_VOLUME_RATIO = "volume_ratio"
COL_SPREAD_RATIO = "spread_ratio"

# -----------------------------------------------------------------------------
# Percentiles
# -----------------------------------------------------------------------------

COL_VOLUME_PERCENTILE = "volume_percentile"
COL_SPREAD_PERCENTILE = "spread_percentile"

# -----------------------------------------------------------------------------
# Semantic Classification
# -----------------------------------------------------------------------------

COL_VOLUME_CLASS = "volume_class"
COL_SPREAD_CLASS = "spread_class"
COL_DIRECTION = "direction"
COL_CLOSE_POSITION = "close_position"

"""
Canonical metric dataframe column names.
"""

COL_ATR = "atr"



TRUE_RANGE_COLUMN = "true_range"

VWAP_COLUMN = "vwap"