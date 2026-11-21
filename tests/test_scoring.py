import pandas as pd

from src.finance.foreign_flow import _sell_streak


def test_sell_streak():
    net = pd.Series([5, -1, -2, -3, 4, -1])
    assert list(_sell_streak(net)) == [0, 1, 2, 3, 0, 1]