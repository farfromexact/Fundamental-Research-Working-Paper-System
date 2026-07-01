from __future__ import annotations

from collections.abc import Iterable
import re
from typing import Any

import numpy as np
import pandas as pd


WINDOWS = (30, 60, 90)
RISK_KEYWORDS = ("监管", "诉讼", "处罚", "调查", "业绩下修", "亏损", "减持", "违约", "退市", "问询", "立案")


def build_features(
    score_frame: pd.DataFrame,
    research: pd.DataFrame | Iterable[dict[str, Any]] | None = None,
    iractivity: pd.DataFrame | Iterable[dict[str, Any]] | None = None,
    negative: pd.DataFrame | Iterable[dict[str, Any]] | None = None,
    consensus_history: pd.DataFrame | None = None,
    author_quality: pd.DataFrame | None = None,
) -> pd.DataFrame:
    scores = _prepare_score_frame(score_frame)
    reports = normalize_research(research)
    ir = normalize_iractivity(iractivity)
    neg = normalize_negative(negative)

    if author_quality is not None and not author_quality.empty:
        aq = author_quality[["author_name", "author_quality"]].copy()
        reports = reports.merge(aq, on="author_name", how="left")
    if "author_quality" not in reports:
        reports["author_quality"] = 1.0
    reports["author_quality"] = reports["author_quality"].fillna(1.0)
    reports["event_weight"] = reports["author_quality"] * (1.0 + 0.25 * reports["is_star"].fillna(0))

    features = scores.copy()
    features = _merge_event_counts(features, ir, "ir", WINDOWS)
    features = _merge_event_counts(features, reports, "report", WINDOWS, weight_col="event_weight")
    features = _merge_event_counts(features, neg, "neg", WINDOWS, weight_col="risk_weight")
    features = _merge_consensus_features(features, consensus_history)

    features["ir_heat_raw"] = (
        0.45 * _log1p(features["ir_count_30d"])
        + 0.35 * _log1p(features["ir_count_60d"])
        + 0.20 * _log1p(features["ir_count_90d"])
        + 0.30 * features["ir_count_chg_30d"]
    )
    features["research_influence_raw"] = (
        0.55 * _log1p(features["report_weight_30d"])
        + 0.30 * _log1p(features["report_weight_90d"])
        + 0.15 * _log1p(features["report_star_count_90d"])
    )
    features["consensus_revision_raw"] = (
        0.45 * features["consensus_np_revision_30d"]
        + 0.25 * features["consensus_np_revision_60d"]
        + 0.15 * features["consensus_revenue_revision_60d"]
        + 0.15 * features["analyst_count_change_90d"]
        - 0.10 * features["forecast_dispersion"]
    )
    features["evidence_density_raw"] = _log1p(
        features["ir_count_90d"] + features["report_count_90d"] + features["neg_count_90d"]
    )
    features["negative_risk_raw"] = (
        0.50 * _log1p(features["neg_count_30d"])
        + 0.35 * _log1p(features["neg_weight_90d"])
        + 0.15 * _log1p(features["neg_keyword_count_90d"])
    )
    return features


def normalize_research(raw: pd.DataFrame | Iterable[dict[str, Any]] | None) -> pd.DataFrame:
    frame = _as_frame(raw)
    if frame.empty:
        return _empty_events(["author_name", "institute", "is_star", "rating_score", "event_weight"])
    out = pd.DataFrame(
        {
            "stock_code": _pick(frame, "StkCode", "stock_code"),
            "event_date": _pick(frame, "ReportDate", "event_date"),
            "source_id": _pick(frame, "ReportID", "source_id"),
            "title": _pick(frame, "Title", "title"),
            "author_name": _pick(frame, "AuthorName", "author_name"),
            "institute": _pick(frame, "InstituteNameCN", "institute"),
            "is_star": pd.to_numeric(_pick(frame, "IsAuthorStar", "is_star"), errors="coerce").fillna(0),
            "rating_score": pd.to_numeric(_pick(frame, "Score", "rating_score"), errors="coerce"),
            "brief": _pick(frame, "BriefText", "brief"),
        }
    )
    out["event_type"] = "research"
    return _clean_events(out)


def normalize_iractivity(raw: pd.DataFrame | Iterable[dict[str, Any]] | None) -> pd.DataFrame:
    frame = _as_frame(raw)
    if frame.empty:
        return _empty_events(["file_size", "type_name"])
    out = pd.DataFrame(
        {
            "stock_code": _pick(frame, "SecCode", "StkCode", "stock_code"),
            "event_date": _pick(frame, "PublishDate", "event_date"),
            "source_id": _pick(frame, "CompId", "source_id"),
            "title": _pick(frame, "Title", "title"),
            "type_name": _pick(frame, "TypeName", "type_name"),
            "file_size": pd.to_numeric(_pick(frame, "FileSize", "file_size"), errors="coerce"),
        }
    )
    out["event_type"] = "iractivity"
    return _clean_events(out)


def normalize_negative(raw: pd.DataFrame | Iterable[dict[str, Any]] | None) -> pd.DataFrame:
    frame = _as_frame(raw)
    if frame.empty:
        return _empty_events(["risk_weight", "risk_keyword_count", "category"])
    if "SecAlertList" in frame and not any(col in frame for col in ("SecCode", "StkCode", "stock_code")):
        frame = _explode_sec_alerts(frame)
    out = pd.DataFrame(
        {
            "stock_code": _pick(frame, "SecCode", "StkCode", "stock_code"),
            "event_date": _pick(frame, "PublishDate", "event_date", "pubdate"),
            "source_id": _pick(frame, "NewsId", "nID", "id", "source_id"),
            "title": _pick(frame, "Title", "title"),
            "brief": _pick(frame, "BriefText", "brief"),
            "category": _pick(frame, "CategoryName", "category"),
            "important": pd.to_numeric(_pick(frame, "Important", "important", "imp"), errors="coerce").fillna(0),
        }
    )
    text = (out["title"].fillna("") + " " + out["brief"].fillna("")).astype(str)
    out["risk_keyword_count"] = text.map(lambda value: sum(1 for keyword in RISK_KEYWORDS if keyword in value))
    out["risk_weight"] = 1.0 + out["important"].clip(lower=0) / 100.0 + out["risk_keyword_count"] * 0.5
    out["event_type"] = "negative"
    return _clean_events(out)


def compute_author_quality(
    research: pd.DataFrame,
    labels: pd.DataFrame,
    as_of_date: str | pd.Timestamp | None = None,
    shrinkage: float = 5.0,
) -> pd.DataFrame:
    reports = normalize_research(research)
    if reports.empty or labels.empty:
        return pd.DataFrame(columns=["author_name", "author_quality", "author_sample_size"])
    labels = labels.copy()
    labels["announce_date"] = pd.to_datetime(labels["announce_date"], errors="coerce")
    if as_of_date is not None:
        labels = labels[labels["announce_date"].le(pd.Timestamp(as_of_date))]
    labels = labels.dropna(subset=["stock_code", "announce_date", "net_profit_surprise"])

    outcomes: list[dict[str, Any]] = []
    for _, report in reports.iterrows():
        future = labels[
            labels["stock_code"].eq(report["stock_code"])
            & labels["announce_date"].gt(report["event_date"])
        ].sort_values("announce_date")
        if future.empty:
            continue
        surprise = float(future.iloc[0]["net_profit_surprise"])
        for author in split_authors(report.get("author_name")):
            outcomes.append({"author_name": author, "surprise": surprise})
    if not outcomes:
        return pd.DataFrame(columns=["author_name", "author_quality", "author_sample_size"])
    frame = pd.DataFrame(outcomes)
    grouped = frame.groupby("author_name")["surprise"].agg(["mean", "count"]).reset_index()
    grouped["author_quality"] = 1.0 + grouped["mean"].clip(-0.5, 0.5) * grouped["count"] / (grouped["count"] + shrinkage)
    grouped["author_sample_size"] = grouped["count"]
    return grouped[["author_name", "author_quality", "author_sample_size"]]


def split_authors(value: Any) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    return [part.strip() for part in re.split(r"[,，;；、]", str(value)) if part.strip()]


def _merge_event_counts(
    features: pd.DataFrame,
    events: pd.DataFrame,
    prefix: str,
    windows: tuple[int, ...],
    weight_col: str | None = None,
) -> pd.DataFrame:
    for window in windows:
        features[f"{prefix}_count_{window}d"] = 0.0
        if weight_col:
            features[f"{prefix}_weight_{window}d"] = 0.0
    if prefix == "ir":
        features["ir_count_chg_30d"] = 0.0
    if prefix == "report":
        features["report_star_count_90d"] = 0.0
    if prefix == "neg":
        features["neg_keyword_count_90d"] = 0.0

    if events.empty:
        return features

    base = features[["row_id", "stock_code", "score_date"]].merge(events, on="stock_code", how="left")
    base = base.dropna(subset=["event_date"])
    base["age_days"] = (base["score_date"] - base["event_date"]).dt.days
    base = base[base["age_days"].ge(0)]

    for window in windows:
        current = base[base["age_days"].le(window)]
        counts = current.groupby("row_id").size()
        features.loc[features["row_id"].isin(counts.index), f"{prefix}_count_{window}d"] = (
            features.loc[features["row_id"].isin(counts.index), "row_id"].map(counts).astype(float)
        )
        if weight_col and weight_col in current:
            weights = current.groupby("row_id")[weight_col].sum()
            features.loc[features["row_id"].isin(weights.index), f"{prefix}_weight_{window}d"] = (
                features.loc[features["row_id"].isin(weights.index), "row_id"].map(weights).astype(float)
            )

    if prefix == "ir":
        recent = base[base["age_days"].le(30)].groupby("row_id").size()
        previous = base[base["age_days"].gt(30) & base["age_days"].le(60)].groupby("row_id").size()
        change = recent.subtract(previous, fill_value=0.0)
        features.loc[features["row_id"].isin(change.index), "ir_count_chg_30d"] = (
            features.loc[features["row_id"].isin(change.index), "row_id"].map(change).astype(float)
        )
    if prefix == "report" and "is_star" in base:
        stars = base[base["age_days"].le(90)].groupby("row_id")["is_star"].sum()
        features.loc[features["row_id"].isin(stars.index), "report_star_count_90d"] = (
            features.loc[features["row_id"].isin(stars.index), "row_id"].map(stars).astype(float)
        )
    if prefix == "neg" and "risk_keyword_count" in base:
        keywords = base[base["age_days"].le(90)].groupby("row_id")["risk_keyword_count"].sum()
        features.loc[features["row_id"].isin(keywords.index), "neg_keyword_count_90d"] = (
            features.loc[features["row_id"].isin(keywords.index), "row_id"].map(keywords).astype(float)
        )
    return features


def _merge_consensus_features(features: pd.DataFrame, consensus_history: pd.DataFrame | None) -> pd.DataFrame:
    defaults = {
        "consensus_np_revision_30d": 0.0,
        "consensus_np_revision_60d": 0.0,
        "consensus_np_revision_90d": 0.0,
        "consensus_revenue_revision_60d": 0.0,
        "analyst_count_change_90d": 0.0,
        "forecast_dispersion": 0.0,
    }
    for col, value in defaults.items():
        features[col] = value
    if consensus_history is None or consensus_history.empty:
        return features

    hist = consensus_history.copy()
    hist["forecast_date"] = pd.to_datetime(hist["forecast_date"], errors="coerce")
    if "period_end" in hist:
        hist["period_end"] = pd.to_datetime(hist["period_end"], errors="coerce")
    hist = hist.dropna(subset=["stock_code", "forecast_date"]).sort_values(["stock_code", "forecast_date"])
    grouped = {stock: group.reset_index(drop=True) for stock, group in hist.groupby("stock_code")}

    rows = []
    for _, row in features[["row_id", "stock_code", "score_date"]].iterrows():
        stock_hist = grouped.get(row["stock_code"])
        if stock_hist is None:
            rows.append({"row_id": row["row_id"]} | defaults)
            continue
        asof = stock_hist[stock_hist["forecast_date"].le(row["score_date"])]
        if asof.empty:
            rows.append({"row_id": row["row_id"]} | defaults)
            continue
        latest = asof.iloc[-1]
        period = latest.get("period_end")
        out = {"row_id": row["row_id"]}
        for window in (30, 60, 90):
            prior_pool = stock_hist[stock_hist["forecast_date"].le(row["score_date"] - pd.Timedelta(days=window))]
            if "period_end" in stock_hist and pd.notna(period):
                prior_pool = prior_pool[prior_pool["period_end"].eq(period)]
            prior = prior_pool.iloc[-1] if not prior_pool.empty else None
            out[f"consensus_np_revision_{window}d"] = _revision(latest, prior, "consensus_net_profit")
        prior60 = stock_hist[stock_hist["forecast_date"].le(row["score_date"] - pd.Timedelta(days=60))]
        if "period_end" in stock_hist and pd.notna(period):
            prior60 = prior60[prior60["period_end"].eq(period)]
        out["consensus_revenue_revision_60d"] = _revision(
            latest,
            prior60.iloc[-1] if not prior60.empty else None,
            "consensus_revenue",
        )
        prior90 = stock_hist[stock_hist["forecast_date"].le(row["score_date"] - pd.Timedelta(days=90))]
        if "period_end" in stock_hist and pd.notna(period):
            prior90 = prior90[prior90["period_end"].eq(period)]
        out["analyst_count_change_90d"] = _revision(
            latest,
            prior90.iloc[-1] if not prior90.empty else None,
            "analyst_count",
            denominator_abs=False,
        )
        out["forecast_dispersion"] = _dispersion(latest)
        rows.append(out)

    update = pd.DataFrame(rows)
    features = features.drop(columns=list(defaults), errors="ignore").merge(update, on="row_id", how="left")
    for col, value in defaults.items():
        features[col] = features[col].fillna(value)
    return features


def _prepare_score_frame(score_frame: pd.DataFrame) -> pd.DataFrame:
    required = {"stock_code", "score_date", "industry"}
    missing = required - set(score_frame.columns)
    if missing:
        raise ValueError(f"score_frame missing required columns: {sorted(missing)}")
    frame = score_frame.copy()
    frame["score_date"] = pd.to_datetime(frame["score_date"], errors="coerce")
    frame = frame.dropna(subset=["stock_code", "score_date", "industry"]).reset_index(drop=True)
    frame["row_id"] = range(len(frame))
    return frame


def _clean_events(frame: pd.DataFrame) -> pd.DataFrame:
    frame["event_date"] = pd.to_datetime(frame["event_date"], errors="coerce")
    frame = frame.dropna(subset=["stock_code", "event_date"]).copy()
    frame["stock_code"] = frame["stock_code"].astype(str).str.extract(r"(\d{6})", expand=False).fillna(frame["stock_code"].astype(str))
    return frame.reset_index(drop=True)


def _empty_events(extra_columns: list[str]) -> pd.DataFrame:
    columns = ["stock_code", "event_date", "source_id", "title", "brief", "event_type"] + extra_columns
    return pd.DataFrame(columns=columns)


def _as_frame(raw: pd.DataFrame | Iterable[dict[str, Any]] | None) -> pd.DataFrame:
    if raw is None:
        return pd.DataFrame()
    if isinstance(raw, pd.DataFrame):
        return raw.copy()
    return pd.DataFrame(list(raw))


def _pick(frame: pd.DataFrame, *names: str) -> pd.Series:
    for name in names:
        if name in frame:
            return frame[name]
    return pd.Series([None] * len(frame), index=frame.index)


def _explode_sec_alerts(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        alerts = row.get("SecAlertList")
        if not isinstance(alerts, list) or not alerts:
            rows.append(row.to_dict())
            continue
        for alert in alerts:
            item = row.to_dict()
            if isinstance(alert, dict):
                item["SecCode"] = alert.get("SecCode")
                item["SecName"] = alert.get("SecName")
                item["Important"] = alert.get("Important") or alert.get("Alert")
            rows.append(item)
    return pd.DataFrame(rows)


def _revision(latest: pd.Series, prior: pd.Series | None, column: str, denominator_abs: bool = True) -> float:
    if prior is None or column not in latest or column not in prior:
        return 0.0
    latest_value = pd.to_numeric(latest[column], errors="coerce")
    prior_value = pd.to_numeric(prior[column], errors="coerce")
    if pd.isna(latest_value) or pd.isna(prior_value):
        return 0.0
    denominator = abs(prior_value) if denominator_abs else max(abs(prior_value), 1.0)
    if denominator == 0:
        return 0.0
    return float((latest_value - prior_value) / denominator)


def _dispersion(row: pd.Series) -> float:
    if "forecast_std" not in row or "consensus_net_profit" not in row:
        return 0.0
    std = pd.to_numeric(row["forecast_std"], errors="coerce")
    mean = pd.to_numeric(row["consensus_net_profit"], errors="coerce")
    if pd.isna(std) or pd.isna(mean) or mean == 0:
        return 0.0
    return float(abs(std / mean))


def _log1p(series: pd.Series) -> pd.Series:
    return np.log1p(series.clip(lower=0))
