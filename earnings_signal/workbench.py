from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


MARKET_OPTIONS = {
    "全部市场": None,
    "A股和港股市场": {"A", "HK"},
    "美股市场": {"US"},
}

REQUIRED_UNIVERSE_COLUMNS = {
    "date",
    "stock_code",
    "stock_name",
    "track",
    "market",
}

REQUIRED_VALUATION_COLUMNS = {
    "stock_code",
    "price",
    "shares_outstanding_100m",
    "profit_1y_100m",
    "fcff_profit_pct",
    "perpetual_growth_pct",
    "discount_rate_pct",
    "safety_margin_pct",
    "cash_100m",
    "non_core_assets_100m",
    "interest_bearing_debt_100m",
    "parent_equity_ratio_pct",
}

SCATTER_SPECS = {
    "ROIC vs 安全边际": {
        "x": "roic_pct",
        "y": "safety_margin_pct",
        "x_label": "ROIC",
        "y_label": "安全边际(行业PB折价)",
        "x_threshold": 15.0,
        "y_threshold": 20.0,
    },
    "FCFF收益率 vs IRR_WorseCase": {
        "x": "fcff_yield_pct",
        "y": "irr_worst_pct",
        "x_label": "FCFF收益率",
        "y_label": "IRR_WorseCase",
        "x_threshold": 5.0,
        "y_threshold": 10.0,
    },
    "ROE/PB": {
        "x": "pb",
        "y": "roe_pct",
        "x_label": "PB",
        "y_label": "ROE",
        "x_threshold": 2.0,
        "y_threshold": 15.0,
    },
    "股息率 vs ROE/PB": {
        "x": "dividend_yield_pct",
        "y": "roe_pb",
        "x_label": "股息率",
        "y_label": "ROE/PB",
        "x_threshold": 3.0,
        "y_threshold": 8.0,
    },
}

FALLBACK_SCATTER_CHARTS = {
    "ROIC vs 安全边际": ("ROE/PB", "股息率 vs ROE/PB", "FCFF收益率 vs IRR_WorseCase"),
    "FCFF收益率 vs IRR_WorseCase": ("ROIC vs 安全边际", "ROE/PB", "股息率 vs ROE/PB"),
    "ROE/PB": ("股息率 vs ROE/PB", "ROIC vs 安全边际", "FCFF收益率 vs IRR_WorseCase"),
    "股息率 vs ROE/PB": ("ROE/PB", "ROIC vs 安全边际", "FCFF收益率 vs IRR_WorseCase"),
}


@dataclass(frozen=True)
class WorkbenchPaths:
    universe: Path
    valuation: Path
    financial_history: Path
    peer_metrics: Path


@dataclass(frozen=True)
class DcfResult:
    schedule: pd.DataFrame
    summary: dict[str, float]


def template_paths(root: str | Path) -> WorkbenchPaths:
    base = Path(root) / "data" / "templates"
    return WorkbenchPaths(
        universe=base / "research_universe_template.csv",
        valuation=base / "valuation_inputs_template.csv",
        financial_history=base / "financial_history_template.csv",
        peer_metrics=base / "peer_metrics_template.csv",
    )


def read_csv_safely(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def read_table_safely(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        return pd.DataFrame()
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def load_workbench(paths: WorkbenchPaths) -> dict[str, pd.DataFrame]:
    universe = normalize_universe(read_table_safely(paths.universe))
    valuation = normalize_valuation(read_table_safely(paths.valuation))
    history = normalize_history(read_table_safely(paths.financial_history))
    peers = normalize_peer_metrics(read_table_safely(paths.peer_metrics))
    return {
        "universe": universe,
        "valuation": valuation,
        "financial_history": history,
        "peer_metrics": peers,
        "master": build_master_table(universe, valuation, peers),
    }


def validate_columns(frame: pd.DataFrame, required: set[str]) -> list[str]:
    return sorted(required - set(frame.columns))


def normalize_universe(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    if frame.empty:
        return pd.DataFrame(columns=sorted(REQUIRED_UNIVERSE_COLUMNS))
    frame["stock_code"] = frame["stock_code"].astype(str).str.strip()
    frame["stock_name"] = frame["stock_name"].astype(str).str.strip()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    if "market" not in frame:
        frame["market"] = frame["stock_code"].map(infer_market)
    frame["market"] = frame["market"].fillna(frame["stock_code"].map(infer_market)).astype(str)
    for column in ["track", "note", "concept_tag", "sw_l2", "sw_l3", "style"]:
        if column not in frame:
            frame[column] = ""
    return frame


def normalize_valuation(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    if frame.empty:
        return pd.DataFrame(columns=sorted(REQUIRED_VALUATION_COLUMNS))
    frame["stock_code"] = frame["stock_code"].astype(str).str.strip()
    for column in frame.columns:
        if column not in {"stock_code", "stock_name"}:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def normalize_history(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    if frame.empty:
        return pd.DataFrame(columns=["stock_code", "metric"])
    frame["stock_code"] = frame["stock_code"].astype(str).str.strip()
    for column in frame.columns:
        if column not in {"stock_code", "stock_name", "metric"}:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def normalize_peer_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    if frame.empty:
        return pd.DataFrame(columns=["stock_code", "stock_name"])
    frame["stock_code"] = frame["stock_code"].astype(str).str.strip()
    for column in frame.columns:
        if column not in {"stock_code", "stock_name", "track", "industry"}:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if "roe_pct" in frame and "pb" in frame:
        frame["roe_pb"] = frame["roe_pct"] / frame["pb"].replace(0, np.nan)
    return frame


def build_master_table(universe: pd.DataFrame, valuation: pd.DataFrame, peers: pd.DataFrame) -> pd.DataFrame:
    if universe.empty:
        return pd.DataFrame()
    master = universe.copy()
    valuation_cols = [
        col
        for col in [
            "stock_code",
            "price",
            "market_cap_100m",
            "profit_1y_100m",
            "fcff_profit_pct",
            "dividend_payout_pct",
            "perpetual_growth_pct",
            "discount_rate_pct",
            "safety_margin_pct",
            "cash_100m",
            "non_core_assets_100m",
            "interest_bearing_debt_100m",
            "parent_equity_ratio_pct",
        ]
        if col in valuation.columns
    ]
    if valuation_cols:
        master = master.merge(valuation[valuation_cols], on="stock_code", how="left")
    peer_cols = [
        col
        for col in [
            "stock_code",
            "roic_pct",
            "fcff_yield_pct",
            "irr_worst_pct",
            "roe_pct",
            "pb",
            "dividend_yield_pct",
            "risk_budget_pct",
            "absolute_return_pct",
            "relative_return_pct",
            "safety_margin_pct",
            "dcf_auto_safety_margin_pct",
        ]
        if col in peers.columns
    ]
    if peer_cols:
        master = master.merge(peers[peer_cols], on="stock_code", how="left", suffixes=("", "_peer"))
    return add_dcf_columns(master, valuation)


def add_dcf_columns(master: pd.DataFrame, valuation: pd.DataFrame) -> pd.DataFrame:
    if master.empty or valuation.empty:
        return master
    frame = valuation.copy()
    required = {"stock_code", "shares_outstanding_100m", "profit_1y_100m", "fcff_profit_pct", "perpetual_growth_pct", "discount_rate_pct"}
    if not required.issubset(frame.columns):
        return master

    shares = pd.to_numeric(frame["shares_outstanding_100m"], errors="coerce")
    price = pd.to_numeric(frame.get("price", pd.Series(np.nan, index=frame.index)), errors="coerce")
    profit_1y = pd.to_numeric(frame["profit_1y_100m"], errors="coerce")
    fcff_profit_pct = pd.to_numeric(frame["fcff_profit_pct"], errors="coerce")
    growth = pd.to_numeric(frame["perpetual_growth_pct"], errors="coerce") / 100.0
    discount = pd.to_numeric(frame["discount_rate_pct"], errors="coerce") / 100.0
    safety_margin = pd.to_numeric(frame.get("safety_margin_pct", pd.Series(20.0, index=frame.index)), errors="coerce") / 100.0
    cash = pd.to_numeric(frame.get("cash_100m", pd.Series(0.0, index=frame.index)), errors="coerce").fillna(0.0)
    non_core_assets = pd.to_numeric(frame.get("non_core_assets_100m", pd.Series(0.0, index=frame.index)), errors="coerce").fillna(0.0)
    debt = pd.to_numeric(frame.get("interest_bearing_debt_100m", pd.Series(0.0, index=frame.index)), errors="coerce").fillna(0.0)
    parent_ratio = pd.to_numeric(frame.get("parent_equity_ratio_pct", pd.Series(100.0, index=frame.index)), errors="coerce").fillna(100.0) / 100.0
    year_1_fcf = pd.to_numeric(frame.get("next_year_fcf_100m", pd.Series(np.nan, index=frame.index)), errors="coerce")
    year_1_fcf = year_1_fcf.fillna(profit_1y * fcff_profit_pct / 100.0)

    valid = shares.gt(0) & discount.gt(growth) & year_1_fcf.notna()
    pv_fcf_sum = pd.Series(np.nan, index=frame.index, dtype="float64")
    for year in range(1, 11):
        pv_fcf_sum = pv_fcf_sum.fillna(0.0)
        pv_fcf_sum = pv_fcf_sum + year_1_fcf * ((1.0 + growth) ** (year - 1)) / ((1.0 + discount) ** year)
    year_10_fcf = year_1_fcf * ((1.0 + growth) ** 9)
    terminal_value = year_10_fcf * (1.0 + growth) / (discount - growth)
    terminal_pv = terminal_value / ((1.0 + discount) ** 10)
    equity_value = pv_fcf_sum + terminal_pv + cash + non_core_assets - debt
    attributable_value = equity_value * parent_ratio
    per_share_value = attributable_value / shares
    safety_price = per_share_value * (1.0 - safety_margin)
    current_safety_margin = 1.0 - price / per_share_value

    dcf = pd.DataFrame(
        {
            "stock_code": frame["stock_code"],
            "dcf_per_share_value": per_share_value.where(valid),
            "dcf_safety_price": safety_price.where(valid),
            "dcf_current_safety_margin_pct": (current_safety_margin * 100.0).where(valid & price.notna() & per_share_value.ne(0)),
            "dcf_equity_value_100m": equity_value.where(valid),
        }
    )
    return master.merge(dcf, on="stock_code", how="left")


def apply_universe_filters(
    frame: pd.DataFrame,
    *,
    date: Any | None = None,
    code: str = "",
    name: str = "",
    track: str = "",
    note: str = "",
    concept: str = "",
    sw_l2: str = "",
    sw_l3: str = "",
    market_name: str = "全部市场",
    search: str = "",
) -> pd.DataFrame:
    view = frame.copy()
    if view.empty:
        return view
    if date is not None and "date" in view:
        selected = pd.Timestamp(date).normalize()
        dates = pd.to_datetime(view["date"], errors="coerce").dt.normalize()
        view = view[dates.le(selected)]
        if not view.empty:
            latest_by_stock = dates.loc[view.index].groupby(view["stock_code"]).transform("max")
            view = view[dates.loc[view.index].eq(latest_by_stock)]
    text_filters = {
        "stock_code": code,
        "stock_name": name,
        "track": track,
        "note": note,
        "concept_tag": concept,
        "sw_l2": sw_l2,
        "sw_l3": sw_l3,
    }
    for column, value in text_filters.items():
        if value and column in view:
            view = view[view[column].astype(str).str.contains(value, case=False, na=False, regex=False)]
    markets = MARKET_OPTIONS.get(market_name)
    if markets and "market" in view:
        view = view[view["market"].isin(markets)]
    if search:
        search_blob = view.fillna("").astype(str).agg(" ".join, axis=1)
        view = view[search_blob.str.contains(search, case=False, na=False, regex=False)]
    return view.reset_index(drop=True)


def apply_numeric_filters(frame: pd.DataFrame, numeric_filters: list[dict[str, Any]]) -> pd.DataFrame:
    view = frame.copy()
    if view.empty:
        return view
    for item in numeric_filters:
        column = str(item.get("column", "")).strip()
        if not column or column not in view:
            continue
        min_value = optional_float(item.get("min_value"))
        max_value = optional_float(item.get("max_value"))
        if min_value is None and max_value is None:
            continue
        values = pd.to_numeric(view[column], errors="coerce")
        mask = pd.Series(True, index=view.index)
        if min_value is not None:
            mask &= values.ge(min_value)
        if max_value is not None:
            mask &= values.le(max_value)
        view = view[mask]
    return view.reset_index(drop=True)


def optional_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    result = pd.to_numeric(value, errors="coerce")
    if pd.isna(result):
        return None
    return float(result)


def calculate_dcf(inputs: dict[str, Any]) -> DcfResult:
    price = to_float(inputs.get("price"), np.nan)
    profit_1y = to_float(inputs.get("profit_1y_100m"))
    fcff_profit_pct = to_float(inputs.get("fcff_profit_pct"))
    growth = to_float(inputs.get("perpetual_growth_pct")) / 100.0
    discount = to_float(inputs.get("discount_rate_pct")) / 100.0
    safety_margin = to_float(inputs.get("safety_margin_pct")) / 100.0
    cash = to_float(inputs.get("cash_100m"))
    non_core_assets = to_float(inputs.get("non_core_assets_100m"))
    debt = to_float(inputs.get("interest_bearing_debt_100m"))
    parent_ratio = to_float(inputs.get("parent_equity_ratio_pct"), 100.0) / 100.0
    shares = to_float(inputs.get("shares_outstanding_100m"))
    year_1_fcf = to_float(inputs.get("next_year_fcf_100m"), np.nan)
    if np.isnan(year_1_fcf):
        year_1_fcf = profit_1y * fcff_profit_pct / 100.0

    if discount <= growth:
        raise ValueError("discount_rate_pct must be greater than perpetual_growth_pct")
    if shares <= 0:
        raise ValueError("shares_outstanding_100m must be positive")

    rows = []
    for year in range(1, 11):
        fcf = year_1_fcf * ((1.0 + growth) ** (year - 1))
        discount_factor = (1.0 + discount) ** year
        pv = fcf / discount_factor
        rows.append(
            {
                "year": year,
                "fcf_100m": fcf,
                "discount_factor": discount_factor,
                "pv_fcf_100m": pv,
            }
        )
    schedule = pd.DataFrame(rows)
    year_10_fcf = float(schedule.iloc[-1]["fcf_100m"])
    terminal_value = year_10_fcf * (1.0 + growth) / (discount - growth)
    terminal_pv = terminal_value / ((1.0 + discount) ** 10)
    pv_fcf_sum = float(schedule["pv_fcf_100m"].sum())
    equity_value = pv_fcf_sum + terminal_pv + cash + non_core_assets - debt
    attributable_value = equity_value * parent_ratio
    per_share_value = attributable_value / shares
    safety_price = per_share_value * (1.0 - safety_margin)
    current_safety_margin = 1.0 - price / per_share_value if per_share_value and np.isfinite(price) else np.nan
    summary = {
        "year_1_fcf_100m": year_1_fcf,
        "pv_fcf_sum_100m": pv_fcf_sum,
        "terminal_value_100m": terminal_value,
        "terminal_pv_100m": terminal_pv,
        "cash_100m": cash,
        "non_core_assets_100m": non_core_assets,
        "interest_bearing_debt_100m": debt,
        "equity_value_100m": equity_value,
        "attributable_equity_value_100m": attributable_value,
        "per_share_value": per_share_value,
        "safety_price": safety_price,
        "current_safety_margin_pct": current_safety_margin * 100.0,
    }
    return DcfResult(schedule=schedule, summary=summary)


def prepare_scatter_data(frame: pd.DataFrame, chart_name: str) -> tuple[pd.DataFrame, list[str], dict[str, Any]]:
    spec = SCATTER_SPECS[chart_name]
    data = frame.copy()
    if chart_name == "股息率 vs ROE/PB" and "roe_pb" not in data and {"roe_pct", "pb"}.issubset(data.columns):
        data["roe_pb"] = data["roe_pct"] / data["pb"].replace(0, np.nan)
    required = ["stock_code", "stock_name", spec["x"], spec["y"]]
    missing = [column for column in required if column not in data.columns]
    if missing:
        return pd.DataFrame(), missing, spec
    data = data.dropna(subset=[spec["x"], spec["y"]])
    return data, [], spec


def choose_scatter_chart(
    frame: pd.DataFrame,
    chart_name: str,
) -> tuple[str, pd.DataFrame, list[str], dict[str, Any], str | None]:
    scatter, missing, spec = prepare_scatter_data(frame, chart_name)
    if not missing and not scatter.empty:
        return chart_name, scatter, missing, spec, None

    for fallback_name in FALLBACK_SCATTER_CHARTS.get(chart_name, ()):
        fallback_scatter, fallback_missing, fallback_spec = prepare_scatter_data(frame, fallback_name)
        if not fallback_missing and not fallback_scatter.empty:
            return fallback_name, fallback_scatter, [], fallback_spec, chart_name

    return chart_name, scatter, missing, spec, None


def scatter_chart_availability(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for chart_name, spec in SCATTER_SPECS.items():
        scatter, missing, _ = prepare_scatter_data(frame, chart_name)
        rows.append(
            {
                "图形": chart_name,
                "X字段": spec["x"],
                "Y字段": spec["y"],
                "可用样本": len(scatter),
                "缺少字段": ", ".join(missing),
            }
        )
    return pd.DataFrame(rows)


def select_scatter_points(frame: pd.DataFrame, spec: dict[str, Any], max_points: int = 20, mode: str = "balanced") -> pd.DataFrame:
    if frame.empty:
        return frame
    limit = max(1, min(int(max_points), 20))
    if len(frame) <= limit:
        return frame.reset_index(drop=True)
    data = frame.copy()
    x = pd.to_numeric(data[spec["x"]], errors="coerce")
    y = pd.to_numeric(data[spec["y"]], errors="coerce")
    if mode == "y_desc":
        data["_rank"] = y
    elif mode == "x_desc":
        data["_rank"] = x
    elif mode == "market_cap" and "market_cap_100m" in data:
        data["_rank"] = pd.to_numeric(data["market_cap_100m"], errors="coerce")
    else:
        data["_rank"] = x.rank(pct=True, na_option="bottom") + y.rank(pct=True, na_option="bottom")
    return data.sort_values("_rank", ascending=False).drop(columns=["_rank"]).head(limit).reset_index(drop=True)


def financial_history_for_stock(history: pd.DataFrame, stock_code: str) -> pd.DataFrame:
    if history.empty:
        return pd.DataFrame()
    return history[history["stock_code"].astype(str).eq(str(stock_code))].reset_index(drop=True)


def valuation_row(valuation: pd.DataFrame, stock_code: str) -> dict[str, Any]:
    if valuation.empty:
        return {}
    rows = valuation[valuation["stock_code"].astype(str).eq(str(stock_code))]
    if rows.empty:
        return {}
    return rows.iloc[0].to_dict()


def infer_market(stock_code: Any) -> str:
    code = str(stock_code).upper()
    if code.endswith((".HK", ".HKG")):
        return "HK"
    if code.endswith((".US", ".O", ".N")):
        return "US"
    return "A"


def to_float(value: Any, default: float = 0.0) -> float:
    result = pd.to_numeric(value, errors="coerce")
    if pd.isna(result):
        return default
    return float(result)
