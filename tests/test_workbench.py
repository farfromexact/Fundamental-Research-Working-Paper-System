import pandas as pd

from earnings_signal.workbench import (
    apply_universe_filters,
    calculate_dcf,
    normalize_peer_metrics,
    prepare_scatter_data,
)


def test_dcf_formula_matches_expected_flow():
    result = calculate_dcf(
        {
            "price": 46.95,
            "shares_outstanding_100m": 56.01,
            "profit_1y_100m": 352.89,
            "fcff_profit_pct": 84.44,
            "perpetual_growth_pct": 3.0,
            "discount_rate_pct": 12.0,
            "safety_margin_pct": 20.0,
            "cash_100m": 1139.0,
            "non_core_assets_100m": 209.04,
            "interest_bearing_debt_100m": 579.51,
            "parent_equity_ratio_pct": 97.11,
        }
    )

    assert round(result.schedule.loc[0, "fcf_100m"], 2) == 297.98
    assert round(result.schedule.loc[1, "fcf_100m"], 2) == 306.92
    assert result.summary["per_share_value"] > result.summary["safety_price"]
    assert result.summary["current_safety_margin_pct"] > 0


def test_dcf_missing_price_does_not_become_full_safety_margin():
    result = calculate_dcf(
        {
            "price": None,
            "shares_outstanding_100m": 10.0,
            "profit_1y_100m": 10.0,
            "fcff_profit_pct": 80.0,
            "perpetual_growth_pct": 3.0,
            "discount_rate_pct": 12.0,
            "safety_margin_pct": 20.0,
        }
    )

    assert pd.isna(result.summary["current_safety_margin_pct"])


def test_list_and_market_filters_do_not_mutate_source():
    frame = pd.DataFrame(
        [
            {"date": "2025-07-11", "stock_code": "000651.SZ", "stock_name": "格力电器", "track": "消费", "market": "A", "long_list": "Y", "watch_list": "Y"},
            {"date": "2025-07-11", "stock_code": "0700.HK", "stock_name": "腾讯控股", "track": "互联网", "market": "HK", "long_list": "", "watch_list": "Y"},
            {"date": "2025-07-11", "stock_code": "AAPL.US", "stock_name": "苹果", "track": "科技", "market": "US", "long_list": "Y", "watch_list": ""},
        ]
    )
    original = frame.copy(deep=True)

    filtered = apply_universe_filters(frame, list_name="长名单", market_name="A股和港股市场")

    assert filtered["stock_code"].tolist() == ["000651.SZ"]
    pd.testing.assert_frame_equal(frame, original)


def test_scatter_missing_columns_returns_missing_list():
    data = pd.DataFrame([{"stock_code": "000651.SZ", "stock_name": "格力电器", "roic_pct": 17.5}])

    scatter, missing, _ = prepare_scatter_data(data, "ROIC vs 安全边际")

    assert scatter.empty
    assert "safety_margin_pct" in missing


def test_scatter_can_compute_roe_pb():
    peers = normalize_peer_metrics(
        pd.DataFrame(
            [
                {"stock_code": "000651.SZ", "stock_name": "格力电器", "roe_pct": 25.0, "pb": 2.0, "dividend_yield_pct": 5.0},
            ]
        )
    )

    scatter, missing, _ = prepare_scatter_data(peers, "股息率 vs ROE/PB")

    assert not missing
    assert round(scatter.loc[0, "roe_pb"], 2) == 12.5
