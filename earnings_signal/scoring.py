from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import numpy as np


@dataclass(frozen=True)
class ScoreWeights:
    ir_heat: float = 0.20
    research_influence: float = 0.25
    consensus_revision: float = 0.35
    evidence_density: float = 0.10
    negative_risk: float = -0.10


RAW_COLUMNS = {
    "ir_heat": "ir_heat_raw",
    "research_influence": "research_influence_raw",
    "consensus_revision": "consensus_revision_raw",
    "evidence_density": "evidence_density_raw",
    "negative_risk": "negative_risk_raw",
}


def score_features(features: pd.DataFrame, weights: ScoreWeights = ScoreWeights()) -> pd.DataFrame:
    frame = features.copy()
    for raw in RAW_COLUMNS.values():
        if raw not in frame:
            frame[raw] = 0.0
    for name, raw in RAW_COLUMNS.items():
        frame[f"{name}_z"] = _zscore_by_industry(frame, raw)

    frame["composite_score"] = (
        weights.ir_heat * frame["ir_heat_z"]
        + weights.research_influence * frame["research_influence_z"]
        + weights.consensus_revision * frame["consensus_revision_z"]
        + weights.evidence_density * frame["evidence_density_z"]
        + weights.negative_risk * frame["negative_risk_z"]
    )
    frame["score_percentile"] = frame.groupby("score_date")["composite_score"].rank(pct=True)
    return frame.sort_values(["score_date", "composite_score"], ascending=[True, False]).reset_index(drop=True)


def assign_score_groups(scores: pd.DataFrame, bins: int = 5) -> pd.DataFrame:
    frame = scores.copy()
    frame["score_group"] = frame.groupby("score_date", group_keys=False)["composite_score"].apply(
        lambda s: _quantile_labels(s, bins)
    )
    return frame


def _zscore_by_industry(frame: pd.DataFrame, column: str) -> pd.Series:
    values = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
    temp = frame[["score_date", "industry"]].copy()
    temp[column] = values
    grouped = temp.groupby(["score_date", "industry"])[column]
    mean = grouped.transform("mean")
    std = grouped.transform(lambda s: s.std(ddof=0)).replace(0, np.nan)
    return ((values - mean) / std).replace([np.inf, -np.inf], np.nan).fillna(0.0)


def _quantile_labels(series: pd.Series, bins: int) -> pd.Series:
    valid = series.dropna()
    labels = pd.Series(pd.NA, index=series.index, dtype="Int64")
    if valid.empty:
        return labels
    ranks = valid.rank(method="first")
    actual_bins = min(bins, len(valid))
    labels.loc[valid.index] = pd.qcut(ranks, actual_bins, labels=range(1, actual_bins + 1)).astype("Int64")
    return labels
