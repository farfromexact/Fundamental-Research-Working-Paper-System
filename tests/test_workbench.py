import pandas as pd

from earnings_signal.workbench import (
    apply_numeric_filters,
    apply_universe_filters,
    calculate_dcf,
    choose_scatter_chart,
    normalize_peer_metrics,
    prepare_scatter_data,
    select_scatter_points,
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


def test_date_and_market_filters_do_not_mutate_source():
    frame = pd.DataFrame(
        [
            {"date": "2025-07-11", "stock_code": "000651.SZ", "stock_name": "格力电器", "track": "消费", "market": "A"},
            {"date": "2025-07-11", "stock_code": "0700.HK", "stock_name": "腾讯控股", "track": "互联网", "market": "HK"},
            {"date": "2025-07-11", "stock_code": "AAPL.US", "stock_name": "苹果", "track": "科技", "market": "US"},
        ]
    )
    original = frame.copy(deep=True)

    filtered = apply_universe_filters(frame, market_name="A股和港股市场")

    assert filtered["stock_code"].tolist() == ["000651.SZ", "0700.HK"]
    pd.testing.assert_frame_equal(frame, original)


def test_text_filters_treat_input_as_literal_text():
    frame = pd.DataFrame(
        [
            {"stock_code": "000001.SZ", "stock_name": "平安银行", "track": "银行", "market": "A"},
            {"stock_code": "000002.SZ", "stock_name": "万科A", "track": "地产", "market": "A", "note": "A+B"},
        ]
    )

    filtered = apply_universe_filters(frame, note="A+B")

    assert filtered["stock_code"].tolist() == ["000002.SZ"]


def test_numeric_filters_stack_min_and_max_conditions():
    frame = pd.DataFrame(
        [
            {"stock_code": "000001.SZ", "market_cap_100m": 2000, "cash_100m": 500, "interest_bearing_debt_100m": 100},
            {"stock_code": "000002.SZ", "market_cap_100m": 300, "cash_100m": 600, "interest_bearing_debt_100m": 50},
            {"stock_code": "000003.SZ", "market_cap_100m": 2400, "cash_100m": 100, "interest_bearing_debt_100m": 20},
            {"stock_code": "000004.SZ", "market_cap_100m": 2100, "cash_100m": 550, "interest_bearing_debt_100m": 900},
        ]
    )

    filtered = apply_numeric_filters(
        frame,
        [
            {"column": "market_cap_100m", "min_value": "1000", "max_value": ""},
            {"column": "cash_100m", "min_value": 300, "max_value": None},
            {"column": "interest_bearing_debt_100m", "max_value": "200"},
        ],
    )

    assert filtered["stock_code"].tolist() == ["000001.SZ"]


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


def test_scatter_falls_back_when_requested_chart_has_no_usable_rows():
    banks = normalize_peer_metrics(
        pd.DataFrame(
            [
                {"stock_code": "600000.SH", "stock_name": "浦发银行", "track": "银行", "roe_pct": 10.8, "pb": 0.5},
                {"stock_code": "600036.SH", "stock_name": "招商银行", "track": "银行", "roe_pct": 15.2, "pb": 0.9},
            ]
        )
    )

    chart_name, scatter, missing, _, fallback_from = choose_scatter_chart(banks, "ROIC vs 安全边际")

    assert chart_name == "ROE/PB"
    assert fallback_from == "ROIC vs 安全边际"
    assert not missing
    assert scatter["stock_code"].tolist() == ["600000.SH", "600036.SH"]


def test_select_scatter_points_caps_at_twenty():
    data = pd.DataFrame(
        [
            {"stock_code": f"{i:06d}.SZ", "stock_name": f"股票{i}", "roic_pct": float(i), "safety_margin_pct": float(100 - i)}
            for i in range(50)
        ]
    )
    _, _, spec = prepare_scatter_data(data, "ROIC vs 安全边际")

    selected = select_scatter_points(data, spec, max_points=50)

    assert len(selected) == 20
