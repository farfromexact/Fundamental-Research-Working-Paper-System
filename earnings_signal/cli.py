from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .backtest import attach_next_report_labels, write_backtest_outputs
from .dzh_client import DzhClient
from .features import build_features
from .io import read_table, write_frame, write_json, write_rows_csv
from .scoring import score_features


def main() -> None:
    parser = argparse.ArgumentParser(prog="earnings-signal")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch-dzh", help="Fetch DataApi stock evidence")
    fetch.add_argument("--stock", required=True)
    fetch.add_argument("--start")
    fetch.add_argument("--end")
    fetch.add_argument("--out", required=True)
    fetch.add_argument("--resources", default="research,iractivity,negative,disclosure,compinfo")

    score = sub.add_parser("score", help="Build weekly features and scores from local files")
    score.add_argument("--score-frame", required=True)
    score.add_argument("--research")
    score.add_argument("--iractivity")
    score.add_argument("--negative")
    score.add_argument("--consensus")
    score.add_argument("--author-quality")
    score.add_argument("--out", required=True)

    backtest = sub.add_parser("backtest", help="Attach next-report labels and evaluate score groups")
    backtest.add_argument("--scores", required=True)
    backtest.add_argument("--forecasts", required=True)
    backtest.add_argument("--actuals", required=True)
    backtest.add_argument("--out", required=True)
    backtest.add_argument("--bins", type=int, default=5)

    demo = sub.add_parser("demo", help="Run a synthetic end-to-end smoke test")
    demo.add_argument("--out", required=True)

    args = parser.parse_args()
    if args.command == "fetch-dzh":
        _fetch_dzh(args)
    elif args.command == "score":
        _score(args)
    elif args.command == "backtest":
        _backtest(args)
    elif args.command == "demo":
        _demo(args)


def _fetch_dzh(args: argparse.Namespace) -> None:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    client = DzhClient()
    resource_map = {
        "research": client.research_reports,
        "iractivity": client.ir_activities,
        "negative": client.negative_news,
        "disclosure": client.disclosures,
        "compinfo": client.compinfo,
    }
    for resource in [part.strip() for part in args.resources.split(",") if part.strip()]:
        if resource not in resource_map:
            raise ValueError(f"unknown resource: {resource}")
        response = resource_map[resource](args.stock, args.start, args.end)
        payload = {
            "stock": args.stock,
            "resource": resource,
            "reccount": response.reccount,
            "page_size": response.page_size,
            "pages_fetched": response.pages_fetched,
            "duplicate_rows": response.duplicate_rows,
            "rows": response.rows,
        }
        write_json(out / f"{resource}.json", payload)
        write_rows_csv(out / f"{resource}.csv", response.rows)
        print(
            f"{resource}: reccount={response.reccount} fetched={len(response.rows)} "
            f"pages={response.pages_fetched} duplicates={response.duplicate_rows}"
        )


def _score(args: argparse.Namespace) -> None:
    score_frame = read_table(args.score_frame)
    research = read_table(args.research) if args.research else pd.DataFrame()
    iractivity = read_table(args.iractivity) if args.iractivity else pd.DataFrame()
    negative = read_table(args.negative) if args.negative else pd.DataFrame()
    consensus = read_table(args.consensus) if args.consensus else pd.DataFrame()
    author_quality = read_table(args.author_quality) if args.author_quality else pd.DataFrame()
    features = build_features(score_frame, research, iractivity, negative, consensus, author_quality)
    scored = score_features(features)
    write_frame(args.out, scored)
    print(f"wrote {len(scored)} scored rows to {args.out}")


def _backtest(args: argparse.Namespace) -> None:
    scores = read_table(args.scores)
    forecasts = read_table(args.forecasts)
    actuals = read_table(args.actuals)
    labels = attach_next_report_labels(scores, forecasts, actuals)
    write_backtest_outputs(args.out, labels, bins=args.bins)
    print(f"wrote backtest outputs to {args.out}")


def _demo(args: argparse.Namespace) -> None:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    score_frame, research, iractivity, negative, consensus, forecasts, actuals = _demo_data()
    scored = score_features(build_features(score_frame, research, iractivity, negative, consensus))
    labels = attach_next_report_labels(scored, forecasts, actuals)
    write_frame(out / "scores.csv", scored)
    write_backtest_outputs(out / "backtest", labels, bins=3)
    print(f"demo wrote scores and backtest files to {out}")


def _demo_data() -> tuple[pd.DataFrame, ...]:
    score_frame = pd.DataFrame(
        [
            {"stock_code": "300750", "industry": "电气设备", "score_date": "2026-05-02"},
            {"stock_code": "300014", "industry": "电气设备", "score_date": "2026-05-02"},
            {"stock_code": "600000", "industry": "银行", "score_date": "2026-05-02"},
            {"stock_code": "601398", "industry": "银行", "score_date": "2026-05-02"},
        ]
    )
    research = pd.DataFrame(
        [
            {"StkCode": "300750", "ReportDate": "2026-04-20", "AuthorName": "甲", "InstituteNameCN": "A", "IsAuthorStar": 1, "Score": 1, "Title": "业绩超预期", "ReportID": 1},
            {"StkCode": "300014", "ReportDate": "2026-04-01", "AuthorName": "乙", "InstituteNameCN": "B", "IsAuthorStar": 0, "Score": 1, "Title": "稳健增长", "ReportID": 2},
            {"StkCode": "600000", "ReportDate": "2026-04-10", "AuthorName": "丙", "InstituteNameCN": "C", "IsAuthorStar": 0, "Score": 2, "Title": "中性", "ReportID": 3},
        ]
    )
    iractivity = pd.DataFrame(
        [
            {"SecCode": "300750", "PublishDate": "2026-04-28", "Title": "投资者关系活动", "CompId": 10},
            {"SecCode": "300750", "PublishDate": "2026-04-15", "Title": "投资者关系活动", "CompId": 11},
            {"SecCode": "300014", "PublishDate": "2026-03-20", "Title": "投资者关系活动", "CompId": 12},
        ]
    )
    negative = pd.DataFrame(
        [
            {"SecCode": "600000", "PublishDate": "2026-04-26", "Title": "监管问询", "NewsId": 100, "Important": 100},
        ]
    )
    consensus = pd.DataFrame(
        [
            {"stock_code": "300750", "forecast_date": "2026-02-01", "period_end": "2026-06-30", "consensus_net_profit": 180, "consensus_revenue": 1000, "consensus_eps": 4.0, "analyst_count": 8, "forecast_std": 10},
            {"stock_code": "300750", "forecast_date": "2026-04-25", "period_end": "2026-06-30", "consensus_net_profit": 210, "consensus_revenue": 1100, "consensus_eps": 4.6, "analyst_count": 12, "forecast_std": 8},
            {"stock_code": "300014", "forecast_date": "2026-02-01", "period_end": "2026-06-30", "consensus_net_profit": 50, "consensus_revenue": 300, "consensus_eps": 1.0, "analyst_count": 5, "forecast_std": 5},
            {"stock_code": "300014", "forecast_date": "2026-04-20", "period_end": "2026-06-30", "consensus_net_profit": 52, "consensus_revenue": 305, "consensus_eps": 1.02, "analyst_count": 5, "forecast_std": 5},
            {"stock_code": "600000", "forecast_date": "2026-04-15", "period_end": "2026-06-30", "consensus_net_profit": 100, "consensus_revenue": 900, "consensus_eps": 0.8, "analyst_count": 4, "forecast_std": 3},
            {"stock_code": "601398", "forecast_date": "2026-04-15", "period_end": "2026-06-30", "consensus_net_profit": 120, "consensus_revenue": 950, "consensus_eps": 0.9, "analyst_count": 4, "forecast_std": 3},
        ]
    )
    forecasts = consensus.copy()
    actuals = pd.DataFrame(
        [
            {"stock_code": "300750", "period_end": "2026-06-30", "announce_date": "2026-07-20", "actual_net_profit": 230, "actual_revenue": 1150, "actual_eps": 5.0},
            {"stock_code": "300014", "period_end": "2026-06-30", "announce_date": "2026-07-20", "actual_net_profit": 51, "actual_revenue": 300, "actual_eps": 1.0},
            {"stock_code": "600000", "period_end": "2026-06-30", "announce_date": "2026-07-20", "actual_net_profit": 90, "actual_revenue": 880, "actual_eps": 0.72},
            {"stock_code": "601398", "period_end": "2026-06-30", "announce_date": "2026-07-20", "actual_net_profit": 125, "actual_revenue": 960, "actual_eps": 0.94},
        ]
    )
    return score_frame, research, iractivity, negative, consensus, forecasts, actuals


if __name__ == "__main__":
    main()

