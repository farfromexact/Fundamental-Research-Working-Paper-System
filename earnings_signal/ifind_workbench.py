from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
import re
from typing import Any

import numpy as np
import pandas as pd

from .ifind_client import IFindClient
from .workbench import WorkbenchPaths, build_master_table


CACHE_DIRNAME = "ifind_workbench"
DEFAULT_MAX_BYTES = 95 * 1024 * 1024
HUNDRED_MILLION = 100_000_000.0

IFIND_QUERIES = {
    "base": "A股 股票代码 股票简称 收盘价 总市值 所属同花顺二级行业 所属同花顺三级行业",
    "quality": "A股 股票代码 股票简称 收盘价 总市值 ROE ROIC PB 股息率",
    "finance": "A股 股票代码 股票简称 归母净利润TTM 自由现金流TTM 经营现金流TTM 货币资金 带息债务 总股本",
    "forecast": "A股 股票代码 股票简称 未来12个月一致预期净利润 一致预期净利润增长率",
    "listing": "A股 股票代码 股票简称 新股上市日期",
}


@dataclass(frozen=True)
class IFindWorkbenchCache:
    directory: Path
    universe: Path
    valuation: Path
    financial_history: Path
    peer_metrics: Path
    manifest: Path


def ifind_cache_paths(root: str | Path) -> IFindWorkbenchCache:
    base = Path(root) / "data" / CACHE_DIRNAME
    return IFindWorkbenchCache(
        directory=base,
        universe=base / "research_universe.parquet",
        valuation=base / "valuation_inputs.parquet",
        financial_history=base / "financial_history.parquet",
        peer_metrics=base / "peer_metrics.parquet",
        manifest=base / "manifest.json",
    )


def ifind_workbench_paths(root: str | Path) -> WorkbenchPaths:
    cache = ifind_cache_paths(root)
    return WorkbenchPaths(
        universe=cache.universe,
        valuation=cache.valuation,
        financial_history=cache.financial_history,
        peer_metrics=cache.peer_metrics,
    )


def read_manifest(root: str | Path) -> dict[str, Any]:
    path = ifind_cache_paths(root).manifest
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def refresh_ifind_workbench(
    *,
    root: str | Path,
    max_bytes: int = DEFAULT_MAX_BYTES,
    client: IFindClient | None = None,
) -> dict[str, Any]:
    close_client = client is None
    active_client = client or IFindClient()
    if close_client:
        active_client.login()
    try:
        raw_tables = {name: active_client.wc_query(query) for name, query in IFIND_QUERIES.items()}
    finally:
        if close_client:
            active_client.logout()

    tables = normalize_ifind_workbench(raw_tables)
    cache = ifind_cache_paths(root)
    manifest = write_ifind_workbench_cache(tables, cache, max_bytes=max_bytes)
    return manifest


def normalize_ifind_workbench(raw_tables: dict[str, pd.DataFrame], as_of: str | None = None) -> dict[str, pd.DataFrame]:
    base = normalize_base_table(raw_tables.get("base", pd.DataFrame()))
    quality = normalize_quality_table(raw_tables.get("quality", pd.DataFrame()))
    finance = normalize_finance_table(raw_tables.get("finance", pd.DataFrame()))
    forecast = normalize_forecast_table(raw_tables.get("forecast", pd.DataFrame()))
    listing = normalize_listing_table(raw_tables.get("listing", pd.DataFrame()))

    merged = base
    for frame in [quality, finance, forecast, listing]:
        if not frame.empty:
            merged = merged.merge(frame, on="stock_code", how="left", suffixes=("", "_drop"))
            drop_cols = [col for col in merged.columns if col.endswith("_drop")]
            if drop_cols:
                merged = merged.drop(columns=drop_cols)

    resolved_as_of = as_of or latest_column_date(raw_tables.values()) or date.today().isoformat()
    universe = build_universe_table(merged, resolved_as_of)
    valuation = build_valuation_table(merged)
    peer_metrics = build_peer_metrics_table(merged, valuation)
    financial_history = build_financial_history_table(merged)
    return {
        "universe": universe,
        "valuation": valuation,
        "financial_history": financial_history,
        "peer_metrics": peer_metrics,
    }


def normalize_base_table(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["stock_code", "stock_name"])
    out = pd.DataFrame()
    out["stock_code"] = require_series(frame, ["股票代码"]).astype(str).str.strip()
    out["stock_name"] = require_series(frame, ["股票简称"]).astype(str).str.strip()
    out["price"] = numeric_from_any(frame, [["收盘价"], ["最新价"]])
    out["market_cap_yuan"] = numeric_from(frame, ["总市值"])
    out["sw_l2"] = text_from(frame, ["二级行业"])
    out["sw_l3"] = text_from(frame, ["三级行业"])
    return dedupe_stock_rows(out)


def normalize_quality_table(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["stock_code"])
    out = pd.DataFrame()
    out["stock_code"] = require_series(frame, ["股票代码"]).astype(str).str.strip()
    out["roe_pct"] = numeric_from(frame, ["roe"])
    out["roic_pct"] = numeric_from(frame, ["roic"])
    out["pb"] = numeric_from(frame, ["市净率", "pb"])
    out["dividend_yield_pct"] = numeric_from(frame, ["股息率"])
    return dedupe_stock_rows(out)


def normalize_finance_table(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["stock_code"])
    out = pd.DataFrame()
    out["stock_code"] = require_series(frame, ["股票代码"]).astype(str).str.strip()
    out["net_profit_ttm_yuan"] = numeric_from(frame, ["净利润", "ttm"])
    out["fcff_yuan"] = numeric_from(frame, ["自由现金流"])
    out["opcf_yuan"] = numeric_from(frame, ["经营活动", "现金流量净额"])
    out["cash_yuan"] = numeric_from(frame, ["货币资金"])
    out["interest_bearing_debt_yuan"] = numeric_from(frame, ["带息债务"])
    out["shares_outstanding"] = numeric_from(frame, ["总股本"])
    return dedupe_stock_rows(out)


def normalize_forecast_table(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["stock_code"])
    out = pd.DataFrame()
    out["stock_code"] = require_series(frame, ["股票代码"]).astype(str).str.strip()
    out["forecast_net_profit_yuan"] = numeric_from(frame, ["预测净利润平均值"])
    out["forecast_net_profit_growth_pct"] = numeric_from(frame, ["预测净利润平均值", "增长率"])
    return dedupe_stock_rows(out)


def normalize_listing_table(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["stock_code"])
    out = pd.DataFrame()
    out["stock_code"] = require_series(frame, ["股票代码"]).astype(str).str.strip()
    out["list_date"] = text_from(frame, ["上市日期"])
    return dedupe_stock_rows(out)


def build_universe_table(merged: pd.DataFrame, as_of: str) -> pd.DataFrame:
    if merged.empty:
        return pd.DataFrame()
    table = pd.DataFrame(
        {
            "date": pd.Timestamp(as_of),
            "stock_code": merged["stock_code"],
            "stock_name": merged["stock_name"],
            "track": merged.get("sw_l2", ""),
            "market": "A",
            "long_list": "",
            "short_list": "",
            "watch_list": "",
            "holding_list": "",
            "peer_list": "",
            "note": "",
            "concept_tag": "",
            "sw_l2": merged.get("sw_l2", ""),
            "sw_l3": merged.get("sw_l3", ""),
            "broad_index": "",
            "style": style_labels(merged),
            "list_date": merged.get("list_date", ""),
        }
    )
    return table.sort_values("stock_code").reset_index(drop=True)


def build_valuation_table(merged: pd.DataFrame) -> pd.DataFrame:
    if merged.empty:
        return pd.DataFrame()
    price = numeric_series(merged.get("price"))
    market_cap_yuan = numeric_series(merged.get("market_cap_yuan"))
    shares = numeric_series(merged.get("shares_outstanding"))
    implied_shares = market_cap_yuan / price.replace(0, np.nan)
    shares = shares.fillna(implied_shares)
    profit_yuan = numeric_series(merged.get("forecast_net_profit_yuan")).fillna(numeric_series(merged.get("net_profit_ttm_yuan")))
    fcff_yuan = numeric_series(merged.get("fcff_yuan")).fillna(numeric_series(merged.get("opcf_yuan")))
    fcff_profit_pct = (fcff_yuan / profit_yuan.replace(0, np.nan) * 100.0).replace([np.inf, -np.inf], np.nan)
    fcff_profit_pct = fcff_profit_pct.clip(lower=-200.0, upper=200.0)
    fallback_fcff_profit = fcff_profit_pct.groupby(merged.get("sw_l2", pd.Series(index=merged.index, dtype=str))).transform("median")
    fcff_profit_pct = fcff_profit_pct.fillna(fallback_fcff_profit).fillna(80.0)
    growth = numeric_series(merged.get("forecast_net_profit_growth_pct")).clip(lower=0.0, upper=20.0)

    table = pd.DataFrame(
        {
            "stock_code": merged["stock_code"],
            "stock_name": merged["stock_name"],
            "price": price,
            "shares_outstanding_100m": shares / HUNDRED_MILLION,
            "market_cap_100m": market_cap_yuan / HUNDRED_MILLION,
            "profit_1y_100m": profit_yuan / HUNDRED_MILLION,
            "fcff_profit_pct": fcff_profit_pct,
            "dividend_payout_pct": np.nan,
            "perpetual_growth_pct": 3.0,
            "discount_rate_pct": 12.0,
            "safety_margin_pct": 20.0,
            "dcf_eps_cagr_pct": growth.fillna(6.0),
            "dcf_eps_cagr_phase2_pct": 5.0,
            "cash_100m": numeric_series(merged.get("cash_yuan")) / HUNDRED_MILLION,
            "non_core_assets_100m": 0.0,
            "interest_bearing_debt_100m": numeric_series(merged.get("interest_bearing_debt_yuan")) / HUNDRED_MILLION,
            "parent_equity_ratio_pct": 100.0,
            "source_profit": np.where(numeric_series(merged.get("forecast_net_profit_yuan")).notna(), "forecast", "ttm"),
        }
    )
    return table.sort_values("stock_code").reset_index(drop=True)


def build_peer_metrics_table(merged: pd.DataFrame, valuation: pd.DataFrame) -> pd.DataFrame:
    if merged.empty:
        return pd.DataFrame()
    market_cap_yuan = numeric_series(merged.get("market_cap_yuan"))
    fcff_yuan = numeric_series(merged.get("fcff_yuan")).fillna(numeric_series(merged.get("opcf_yuan")))
    peer = pd.DataFrame(
        {
            "stock_code": merged["stock_code"],
            "stock_name": merged["stock_name"],
            "industry": merged.get("sw_l2", ""),
            "roic_pct": numeric_series(merged.get("roic_pct")),
            "fcff_yield_pct": (fcff_yuan / market_cap_yuan.replace(0, np.nan) * 100.0).replace([np.inf, -np.inf], np.nan),
            "irr_worst_pct": np.nan,
            "roe_pct": numeric_series(merged.get("roe_pct")),
            "pb": numeric_series(merged.get("pb")),
            "dividend_yield_pct": numeric_series(merged.get("dividend_yield_pct")),
            "risk_budget_pct": np.nan,
            "absolute_return_pct": np.nan,
            "relative_return_pct": np.nan,
        }
    )
    dcf_master = build_master_table(
        build_universe_table(merged, date.today().isoformat()),
        valuation,
        peer,
    )
    if "dcf_current_safety_margin_pct" in dcf_master:
        peer = peer.merge(
            dcf_master[["stock_code", "dcf_current_safety_margin_pct"]],
            on="stock_code",
            how="left",
        )
        peer["dcf_auto_safety_margin_pct"] = peer["dcf_current_safety_margin_pct"].clip(lower=-100.0, upper=100.0)
        peer = peer.drop(columns=["dcf_current_safety_margin_pct"])
    else:
        peer["dcf_auto_safety_margin_pct"] = np.nan
    peer["safety_margin_pct"] = industry_pb_discount_margin(peer)
    peer["irr_worst_pct"] = peer["fcff_yield_pct"] + 3.0
    return peer.sort_values("stock_code").reset_index(drop=True)


def build_financial_history_table(merged: pd.DataFrame) -> pd.DataFrame:
    if merged.empty:
        return pd.DataFrame()
    metric_map = {
        "净利润TTM": numeric_series(merged.get("net_profit_ttm_yuan")) / HUNDRED_MILLION,
        "预测净利润": numeric_series(merged.get("forecast_net_profit_yuan")) / HUNDRED_MILLION,
        "企业自由现金流FCFF": numeric_series(merged.get("fcff_yuan")) / HUNDRED_MILLION,
        "经营活动现金流净额OPCF": numeric_series(merged.get("opcf_yuan")) / HUNDRED_MILLION,
        "货币资金": numeric_series(merged.get("cash_yuan")) / HUNDRED_MILLION,
        "带息债务": numeric_series(merged.get("interest_bearing_debt_yuan")) / HUNDRED_MILLION,
        "ROE": numeric_series(merged.get("roe_pct")),
        "ROIC": numeric_series(merged.get("roic_pct")),
    }
    rows = []
    for metric, values in metric_map.items():
        block = pd.DataFrame(
            {
                "stock_code": merged["stock_code"],
                "stock_name": merged["stock_name"],
                "metric": metric,
                "latest": values,
            }
        )
        rows.append(block)
    return pd.concat(rows, ignore_index=True).dropna(subset=["latest"], how="all")


def write_ifind_workbench_cache(
    tables: dict[str, pd.DataFrame],
    cache: IFindWorkbenchCache,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> dict[str, Any]:
    cache.directory.mkdir(parents=True, exist_ok=True)
    file_map = {
        "universe": cache.universe,
        "valuation": cache.valuation,
        "financial_history": cache.financial_history,
        "peer_metrics": cache.peer_metrics,
    }
    for name, path in file_map.items():
        write_frame(tables[name], path)

    total_bytes = sum(path.stat().st_size for path in file_map.values() if path.exists())
    if total_bytes > max_bytes:
        raise ValueError(f"iFinD cache is {total_bytes:,} bytes, exceeding limit {max_bytes:,}")

    manifest = {
        "generated_at": pd.Timestamp.now().isoformat(),
        "max_bytes": max_bytes,
        "total_bytes": total_bytes,
        "queries": IFIND_QUERIES,
        "files": {
            name: {
                "path": str(path.as_posix()),
                "rows": int(len(tables[name])),
                "bytes": int(path.stat().st_size if path.exists() else 0),
            }
            for name, path in file_map.items()
        },
    }
    cache.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def write_frame(frame: pd.DataFrame, path: Path) -> None:
    try:
        frame.to_parquet(path, index=False, compression="zstd")
    except Exception:
        frame.to_parquet(path, index=False, compression="snappy")


def latest_column_date(tables: Any) -> str | None:
    dates: list[pd.Timestamp] = []
    for table in tables:
        for column in getattr(table, "columns", []):
            for value in re.findall(r"\[(\d{8})(?:[-\]]|$)", str(column)):
                parsed = pd.to_datetime(value, format="%Y%m%d", errors="coerce")
                if pd.notna(parsed):
                    dates.append(parsed)
    if not dates:
        return None
    return max(dates).date().isoformat()


def find_column(frame: pd.DataFrame, patterns: list[str]) -> str | None:
    lowered_patterns = [pattern.lower() for pattern in patterns]
    for column in frame.columns:
        text = str(column).lower()
        if all(pattern in text for pattern in lowered_patterns):
            return column
    return None


def require_series(frame: pd.DataFrame, patterns: list[str]) -> pd.Series:
    column = find_column(frame, patterns)
    if column is None:
        raise ValueError(f"Missing iFinD column containing: {patterns}")
    return frame[column]


def numeric_from(frame: pd.DataFrame, patterns: list[str]) -> pd.Series:
    column = find_column(frame, patterns)
    if column is None:
        return pd.Series(np.nan, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


def numeric_from_any(frame: pd.DataFrame, candidates: list[list[str]]) -> pd.Series:
    for patterns in candidates:
        values = numeric_from(frame, patterns)
        if values.notna().any():
            return values
    return pd.Series(np.nan, index=frame.index, dtype="float64")


def text_from(frame: pd.DataFrame, patterns: list[str]) -> pd.Series:
    column = find_column(frame, patterns)
    if column is None:
        return pd.Series("", index=frame.index, dtype="object")
    return frame[column].fillna("").astype(str)


def numeric_series(value: Any) -> pd.Series:
    if isinstance(value, pd.Series):
        return pd.to_numeric(value, errors="coerce")
    return pd.Series(dtype="float64")


def dedupe_stock_rows(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.dropna(subset=["stock_code"]).drop_duplicates("stock_code").reset_index(drop=True)


def style_labels(frame: pd.DataFrame) -> pd.Series:
    roe = numeric_series(frame.get("roe_pct"))
    pb = numeric_series(frame.get("pb"))
    dividend = numeric_series(frame.get("dividend_yield_pct"))
    labels = pd.Series("", index=frame.index, dtype="object")
    labels = labels.mask(roe.ge(18), "高ROE")
    labels = labels.mask(pb.le(1.2) & labels.eq(""), "低PB")
    labels = labels.mask(dividend.ge(4) & labels.eq(""), "高股息")
    return labels


def industry_pb_discount_margin(peer: pd.DataFrame) -> pd.Series:
    pb = numeric_series(peer.get("pb"))
    valid_pb = pb.where(pb.gt(0) & pb.lt(100))
    industry = peer.get("industry", pd.Series("", index=peer.index)).fillna("").astype(str)
    industry_median = valid_pb.groupby(industry).transform("median")
    market_median = valid_pb.median()
    benchmark = industry_median.fillna(market_median)
    margin = (benchmark - pb) / benchmark.replace(0, np.nan) * 100.0
    return margin.replace([np.inf, -np.inf], np.nan).clip(lower=-100.0, upper=100.0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh local all-A-share iFinD workbench cache.")
    parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")
    parser.add_argument("--max-mb", type=float, default=95.0, help="Maximum cache size in MB.")
    args = parser.parse_args(argv)

    manifest = refresh_ifind_workbench(root=args.root, max_bytes=int(args.max_mb * 1024 * 1024))
    print(json.dumps(manifest, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
