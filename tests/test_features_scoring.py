import pandas as pd

from earnings_signal.features import build_features
from earnings_signal.scoring import score_features


def test_features_exclude_future_events_and_score_by_industry():
    score_frame = pd.DataFrame(
        [
            {"stock_code": "300750", "industry": "电气设备", "score_date": "2026-05-01"},
            {"stock_code": "300014", "industry": "电气设备", "score_date": "2026-05-01"},
        ]
    )
    ir = pd.DataFrame(
        [
            {"SecCode": "300750", "PublishDate": "2026-04-20", "Title": "调研", "CompId": 1},
            {"SecCode": "300750", "PublishDate": "2026-05-02", "Title": "未来调研", "CompId": 2},
        ]
    )
    research = pd.DataFrame(
        [{"StkCode": "300750", "ReportDate": "2026-04-25", "ReportID": 10, "AuthorName": "甲", "IsAuthorStar": 1}]
    )
    consensus = pd.DataFrame(
        [
            {"stock_code": "300750", "forecast_date": "2026-03-01", "period_end": "2026-06-30", "consensus_net_profit": 100, "consensus_revenue": 500, "analyst_count": 3},
            {"stock_code": "300750", "forecast_date": "2026-04-25", "period_end": "2026-06-30", "consensus_net_profit": 120, "consensus_revenue": 550, "analyst_count": 5},
            {"stock_code": "300014", "forecast_date": "2026-04-25", "period_end": "2026-06-30", "consensus_net_profit": 80, "consensus_revenue": 400, "analyst_count": 2},
        ]
    )

    features = build_features(score_frame, research=research, iractivity=ir, consensus_history=consensus)
    scored = score_features(features)
    catl = scored[scored["stock_code"].eq("300750")].iloc[0]

    assert catl["ir_count_30d"] == 1
    assert catl["report_count_30d"] == 1
    assert catl["consensus_np_revision_30d"] == 0.2
    assert catl["consensus_np_revision_60d"] == 0.2
    assert "composite_score" in scored
