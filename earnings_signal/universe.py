from __future__ import annotations

import pandas as pd


def filter_universe(universe: pd.DataFrame, as_of_date: str | pd.Timestamp) -> pd.DataFrame:
    frame = universe.copy()
    as_of = pd.Timestamp(as_of_date)
    if "list_date" in frame:
        frame["list_date"] = pd.to_datetime(frame["list_date"], errors="coerce")
        frame = frame[frame["list_date"].le(as_of - pd.Timedelta(days=365))]
    if "is_st" in frame:
        frame = frame[~frame["is_st"].fillna(False).astype(bool)]
    if "suspend_status" in frame:
        bad = frame["suspend_status"].astype(str).str.contains("长期|停牌|suspend", case=False, na=False)
        frame = frame[~bad]
    return frame.reset_index(drop=True)


def build_weekly_score_frame(
    universe: pd.DataFrame,
    start_date: str,
    end_date: str,
    frequency: str = "W-FRI",
) -> pd.DataFrame:
    required = {"stock_code", "industry"}
    missing = required - set(universe.columns)
    if missing:
        raise ValueError(f"universe missing required columns: {sorted(missing)}")
    dates = pd.date_range(start_date, end_date, freq=frequency)
    rows = []
    for score_date in dates:
        filtered = filter_universe(universe, score_date)
        rows.append(
            filtered[["stock_code", "industry"]]
            .assign(score_date=score_date.normalize())
        )
    if not rows:
        return pd.DataFrame(columns=["stock_code", "industry", "score_date"])
    return pd.concat(rows, ignore_index=True)

