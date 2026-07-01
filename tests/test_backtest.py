import pandas as pd

from earnings_signal.backtest import attach_next_report_labels, validate_no_future_leakage


def test_attach_next_report_labels_uses_asof_forecast_only():
    scores = pd.DataFrame(
        [{"stock_code": "300750", "industry": "电气设备", "score_date": "2026-05-01", "composite_score": 1.0}]
    )
    forecasts = pd.DataFrame(
        [
            {"stock_code": "300750", "period_end": "2026-06-30", "forecast_date": "2026-04-20", "consensus_net_profit": 100},
            {"stock_code": "300750", "period_end": "2026-06-30", "forecast_date": "2026-05-10", "consensus_net_profit": 200},
        ]
    )
    actuals = pd.DataFrame(
        [{"stock_code": "300750", "period_end": "2026-06-30", "announce_date": "2026-07-20", "actual_net_profit": 120}]
    )

    labeled = attach_next_report_labels(scores, forecasts, actuals)

    assert labeled.loc[0, "label_status"] == "ok"
    assert labeled.loc[0, "forecast_net_profit"] == 100
    assert labeled.loc[0, "net_profit_surprise"] == 0.2
    validate_no_future_leakage(labeled)

