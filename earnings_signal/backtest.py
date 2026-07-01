from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .scoring import assign_score_groups


def attach_next_report_labels(scores: pd.DataFrame, forecasts: pd.DataFrame, actuals: pd.DataFrame) -> pd.DataFrame:
    score_frame = scores.copy()
    score_frame["score_date"] = pd.to_datetime(score_frame["score_date"], errors="coerce")

    fc = forecasts.copy()
    fc["forecast_date"] = pd.to_datetime(fc["forecast_date"], errors="coerce")
    fc["period_end"] = pd.to_datetime(fc["period_end"], errors="coerce")

    ac = actuals.copy()
    ac["announce_date"] = pd.to_datetime(ac["announce_date"], errors="coerce")
    ac["period_end"] = pd.to_datetime(ac["period_end"], errors="coerce")
    ac = ac.dropna(subset=["stock_code", "period_end", "announce_date", "actual_net_profit"])

    forecasts_by_stock = {stock: group.sort_values("forecast_date") for stock, group in fc.groupby("stock_code")}
    actuals_by_stock = {stock: group.sort_values("announce_date") for stock, group in ac.groupby("stock_code")}

    labels: list[dict[str, Any]] = []
    for _, row in score_frame.iterrows():
        actual_pool = actuals_by_stock.get(row["stock_code"])
        if actual_pool is None:
            labels.append({"label_status": "missing_actual"})
            continue
        future_actuals = actual_pool[actual_pool["announce_date"].gt(row["score_date"])]
        if future_actuals.empty:
            labels.append({"label_status": "missing_future_actual"})
            continue
        actual = future_actuals.iloc[0]
        forecast_pool = forecasts_by_stock.get(row["stock_code"])
        if forecast_pool is None:
            labels.append({"label_status": "missing_forecast"})
            continue
        forecast_candidates = forecast_pool[
            forecast_pool["period_end"].eq(actual["period_end"])
            & forecast_pool["forecast_date"].le(row["score_date"])
        ]
        if forecast_candidates.empty:
            labels.append({"label_status": "missing_asof_forecast"})
            continue
        forecast = forecast_candidates.iloc[-1]
        labels.append(
            {
                "label_status": "ok",
                "period_end": actual["period_end"],
                "announce_date": actual["announce_date"],
                "forecast_date": forecast["forecast_date"],
                "actual_net_profit": actual["actual_net_profit"],
                "forecast_net_profit": forecast["consensus_net_profit"],
                "net_profit_surprise": _surprise(actual["actual_net_profit"], forecast["consensus_net_profit"]),
                "actual_revenue": actual.get("actual_revenue"),
                "forecast_revenue": forecast.get("consensus_revenue"),
                "revenue_surprise": _surprise(actual.get("actual_revenue"), forecast.get("consensus_revenue")),
                "actual_eps": actual.get("actual_eps"),
                "forecast_eps": forecast.get("consensus_eps"),
                "eps_surprise": _surprise(actual.get("actual_eps"), forecast.get("consensus_eps")),
            }
        )
    return pd.concat([score_frame.reset_index(drop=True), pd.DataFrame(labels)], axis=1)


def evaluate_backtest(scored_labels: pd.DataFrame, bins: int = 5) -> tuple[pd.DataFrame, pd.DataFrame]:
    labeled = scored_labels[scored_labels["label_status"].eq("ok")].copy()
    grouped_scores = assign_score_groups(labeled, bins=bins)
    grouped_scores = grouped_scores.dropna(subset=["score_group"])
    summary = (
        grouped_scores.groupby("score_group")
        .agg(
            observations=("stock_code", "count"),
            mean_net_profit_surprise=("net_profit_surprise", "mean"),
            mean_revenue_surprise=("revenue_surprise", "mean"),
            mean_eps_surprise=("eps_surprise", "mean"),
            hit_rate=("net_profit_surprise", lambda s: float((s > 0).mean())),
        )
        .reset_index()
        .sort_values("score_group")
    )
    coverage = (
        scored_labels.groupby(["score_date", "label_status"])
        .size()
        .rename("count")
        .reset_index()
        .sort_values(["score_date", "label_status"])
    )
    return summary, coverage


def validate_no_future_leakage(scored_labels: pd.DataFrame) -> None:
    ok = scored_labels[scored_labels["label_status"].eq("ok")].copy()
    if ok.empty:
        return
    score_date = pd.to_datetime(ok["score_date"])
    forecast_date = pd.to_datetime(ok["forecast_date"])
    announce_date = pd.to_datetime(ok["announce_date"])
    if forecast_date.gt(score_date).any():
        raise ValueError("future leakage: forecast_date after score_date")
    if announce_date.le(score_date).any():
        raise ValueError("future leakage: announce_date not after score_date")


def write_backtest_outputs(out_dir: str | Path, scored_labels: pd.DataFrame, bins: int = 5) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    validate_no_future_leakage(scored_labels)
    summary, coverage = evaluate_backtest(scored_labels, bins=bins)
    scored_labels.to_csv(out / "scored_labels.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(out / "group_summary.csv", index=False, encoding="utf-8-sig")
    coverage.to_csv(out / "coverage.csv", index=False, encoding="utf-8-sig")


def _surprise(actual: Any, forecast: Any) -> float | None:
    actual_num = pd.to_numeric(actual, errors="coerce")
    forecast_num = pd.to_numeric(forecast, errors="coerce")
    if pd.isna(actual_num) or pd.isna(forecast_num) or forecast_num == 0:
        return None
    return float((actual_num - forecast_num) / abs(forecast_num))

