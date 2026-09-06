import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("sniper_rates", SCRIPTS / "research_sniper_rates.py")
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)


def test_lag_excludes_recent_and_future_observations():
    frame = pd.DataFrame({"change1": [1, 2, 999], "change5": [1, 2, 999], "correlation": [-.3, -.4, .9]},
                         index=pd.to_datetime(["2020-01-03", "2020-01-06", "2020-01-07"]))
    result = study.lagged_features(frame, pd.to_datetime(["2020-01-06 08:00", "2020-01-09 08:00"]))
    np.testing.assert_allclose(result, [[1, 1, -.3], [2, 2, -.4]])


def test_missing_and_stale_observations_do_not_become_zero_signals():
    frame = pd.DataFrame({"change1": [1], "change5": [1], "correlation": [-.3]}, index=pd.to_datetime(["2020-01-03"]))
    result = study.lagged_features(frame, pd.to_datetime(["2020-01-01", "2020-02-01"]))
    assert np.isnan(result).all()
