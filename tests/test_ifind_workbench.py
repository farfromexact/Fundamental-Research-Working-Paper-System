import pandas as pd
import pytest
from pathlib import Path
import shutil

from earnings_signal.ifind_workbench import (
    IFindWorkbenchCache,
    industry_pb_discount_margin,
    normalize_ifind_workbench,
    write_ifind_workbench_cache,
)


def test_normalize_ifind_workbench_maps_chinese_columns_to_local_tables():
    raw = {
        "base": pd.DataFrame(
            [
                {
                    "股票代码": "000651.SZ",
                    "股票简称": "格力电器",
                    "收盘价:不复权[20260701]": 46.95,
                    "总市值[20260701]": 2629.86 * 100_000_000,
                    "所属同花顺二级行业": "家用电器",
                    "所属同花顺三级行业": "白色家电",
                }
            ]
        ),
        "quality": pd.DataFrame(
            [
                {
                    "股票代码": "000651.SZ",
                    "股票简称": "格力电器",
                    "净资产收益率roe(加权,公布值)[20260331]": 25.6,
                    "投入资本回报率roic[20260331]": 18.0,
                    "市净率(pb)[20260701]": 2.0,
                    "股息率(股票获利率)[20251231]": 4.5,
                }
            ]
        ),
        "finance": pd.DataFrame(
            [
                {
                    "股票代码": "000651.SZ",
                    "归属母公司股东的净利润(ttm)[20260630]": 352.89 * 100_000_000,
                    "企业自由现金流量fcff[20260331]": 297.98 * 100_000_000,
                    "经营活动产生的现金流量净额[20260331]": 360 * 100_000_000,
                    "货币资金[20260331]": 1139 * 100_000_000,
                    "带息债务[20260331]": 579.51 * 100_000_000,
                    "总股本[20260701]": 56.01 * 100_000_000,
                }
            ]
        ),
        "forecast": pd.DataFrame(
            [
                {
                    "股票代码": "000651.SZ",
                    "预测净利润平均值[20261231]": 360 * 100_000_000,
                    "预测净利润平均值区间增长率[20261231-20281231]": 8.0,
                }
            ]
        ),
    }

    tables = normalize_ifind_workbench(raw)

    universe = tables["universe"]
    valuation = tables["valuation"]
    peers = tables["peer_metrics"]
    assert universe.loc[0, "stock_code"] == "000651.SZ"
    assert universe.loc[0, "track"] == "家用电器"
    assert valuation.loc[0, "price"] == 46.95
    assert round(valuation.loc[0, "market_cap_100m"], 2) == 2629.86
    assert round(valuation.loc[0, "shares_outstanding_100m"], 2) == 56.01
    assert round(valuation.loc[0, "fcff_profit_pct"], 2) == 82.77
    assert peers.loc[0, "roic_pct"] == 18.0
    assert "safety_margin_pct" in peers.columns


def test_write_ifind_workbench_cache_enforces_size_limit():
    cache_root = Path("test_artifacts") / "ifind_workbench_size_limit"
    if cache_root.exists():
        shutil.rmtree(cache_root)
    cache_root.mkdir(parents=True)
    tables = {
        "universe": pd.DataFrame([{"stock_code": "000001.SZ"}]),
        "valuation": pd.DataFrame([{"stock_code": "000001.SZ"}]),
        "financial_history": pd.DataFrame([{"stock_code": "000001.SZ"}]),
        "peer_metrics": pd.DataFrame([{"stock_code": "000001.SZ"}]),
    }
    cache = IFindWorkbenchCache(
        directory=cache_root,
        universe=cache_root / "research_universe.parquet",
        valuation=cache_root / "valuation_inputs.parquet",
        financial_history=cache_root / "financial_history.parquet",
        peer_metrics=cache_root / "peer_metrics.parquet",
        manifest=cache_root / "manifest.json",
    )
    try:
        with pytest.raises(ValueError):
            write_ifind_workbench_cache(tables, cache, max_bytes=1)
    finally:
        shutil.rmtree(cache_root, ignore_errors=True)


def test_industry_pb_discount_margin_is_industry_relative():
    peer = pd.DataFrame(
        [
            {"stock_code": "A", "industry": "家电", "pb": 1.0},
            {"stock_code": "B", "industry": "家电", "pb": 2.0},
            {"stock_code": "C", "industry": "家电", "pb": 4.0},
        ]
    )

    margin = industry_pb_discount_margin(peer)

    assert margin.iloc[0] > 0
    assert round(margin.iloc[1], 6) == 0
    assert margin.iloc[2] < 0
