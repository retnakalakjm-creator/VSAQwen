import config


def test_default_download_period_is_bounded_for_production() -> None:
    assert config.DEFAULT_PERIOD == config.PRODUCTION_DOWNLOAD_PERIOD
    assert config.DEFAULT_PERIOD != config.FULL_HISTORY_PERIOD
    assert config.FULL_HISTORY_PERIOD == "max"