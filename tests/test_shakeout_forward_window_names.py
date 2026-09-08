import config


def test_shakeout_forward_window_names_replace_lookahead_names() -> None:
    assert config.SHAKEOUT_TEST_FORWARD_WINDOW == 15
    assert config.SHAKEOUT_RECOVERY_FORWARD_WINDOW == 5


def test_legacy_shakeout_lookahead_names_remain_aliases() -> None:
    assert config.SHAKEOUT_TEST_LOOKAHEAD == config.SHAKEOUT_TEST_FORWARD_WINDOW
    assert config.SHAKEOUT_RECOVERY_LOOKAHEAD == config.SHAKEOUT_RECOVERY_FORWARD_WINDOW
