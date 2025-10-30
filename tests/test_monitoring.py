import json
import math
import pandas as pd


def test_clean_nan_values():
    import app.monitoring as m
    data = {"a": float("nan"), "b": [1, float("inf"), -float("inf")], "c": None}
    cleaned = m.clean_nan_values(data)
    assert cleaned["a"] is None
    assert cleaned["b"][1] is None and cleaned["b"][2] is None


def test_get_latest_and_by_timestamp(tmp_path, monkeypatch):
    import app.monitoring as m
    # Redirect evaluation dir
    monkeypatch.setattr(m, "EVAL_DIR", str(tmp_path))

    # Create latest file
    latest = tmp_path / "evaluation_results.csv"
    df = pd.DataFrame([
        {"score": 4, "question": "Q1", "citation_score": 3},
        {"score": 2, "question": "Q2", "citation_score": 1},
    ])
    df.to_csv(latest, index=False)

    res = m.get_latest_evaluation()
    assert res["total_questions"] == 2

    # Write timestamped file and fetch by timestamp
    ts = "20250101_010101"
    by_ts = tmp_path / f"evaluation_{ts}.csv"
    df.to_csv(by_ts, index=False)
    res2 = m.get_evaluation_by_timestamp(ts)
    assert res2["total_questions"] == 2

