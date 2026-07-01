from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from earnings_signal.backtest import attach_next_report_labels, evaluate_backtest
from earnings_signal.cli import _demo_data
from earnings_signal.dzh_client import DzhApiError, DzhClient
from earnings_signal.features import build_features
from earnings_signal.io import extract_rows, read_table, write_json, write_rows_csv
from earnings_signal.scoring import score_features
from earnings_signal.ifind_workbench import ifind_cache_paths, ifind_workbench_paths, read_manifest
from earnings_signal.workbench import (
    LIST_COLUMNS,
    MARKET_OPTIONS,
    REQUIRED_UNIVERSE_COLUMNS,
    REQUIRED_VALUATION_COLUMNS,
    SCATTER_SPECS,
    apply_universe_filters,
    calculate_dcf,
    financial_history_for_stock,
    load_workbench,
    prepare_scatter_data,
    select_scatter_points,
    template_paths,
    validate_columns,
    valuation_row,
)


ROOT = Path(__file__).parent
OUTPUT_DIR = ROOT / "output"
DEMO_DIR = OUTPUT_DIR / "demo"
STREAMLIT_DZH_DIR = OUTPUT_DIR / "streamlit" / "dzh"
TEMPLATE_PATHS = template_paths(ROOT)
IFIND_CACHE_PATHS = ifind_cache_paths(ROOT)

PALETTE = {
    "red": "#A53122",
    "rose": "#C99A8A",
    "paper": "#F3EED9",
    "yellow": "#EDD87F",
    "blue": "#59819B",
    "ink": "#2B1248",
    "paper_light": "#FFF9EA",
}
PLOTLY_COLORS = [
    PALETTE["red"],
    PALETTE["blue"],
    PALETTE["rose"],
    PALETTE["yellow"],
    PALETTE["ink"],
]

PAGES = ["股票池底稿", "单股DCF", "交叉评估", "证据与评分", "本地数据"]
SCATTER_SORT_OPTIONS = {
    "综合靠前": "balanced",
    "纵轴最高": "y_desc",
    "横轴最高": "x_desc",
    "市值最大": "market_cap",
}


DISPLAY_COLUMNS = {
    "date": "日期",
    "stock_code": "股票代码",
    "stock_name": "股票名称",
    "track": "赛道",
    "long_list": "长名单",
    "short_list": "短名单",
    "watch_list": "观察名单",
    "holding_list": "持仓",
    "peer_list": "对标名单",
    "note": "备注",
    "broad_index": "所属宽基",
    "sw_l2": "Wind2级行业",
    "sw_l3": "Wind3级行业",
    "style": "所属风格",
    "price": "股价",
    "market_cap_100m": "总市值(亿)",
    "fcff_profit_pct": "FCFF/Profit%",
    "dividend_payout_pct": "股利支付率%",
    "dcf_per_share_value": "DCF每股价值",
    "dcf_safety_price": "DCF安全边际对应价",
    "dcf_current_safety_margin_pct": "DCF当前安全边际%",
    "roic_pct": "ROIC%",
    "safety_margin_pct": "安全边际%",
    "fcff_yield_pct": "FCFF收益率%",
    "irr_worst_pct": "IRR_WorseCase%",
    "roe_pct": "ROE%",
    "pb": "PB",
    "dividend_yield_pct": "股息率%",
}


st.set_page_config(
    page_title="基本面研究底稿系统",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    :root {
        --old-red: #A53122;
        --old-rose: #C99A8A;
        --old-paper: #F3EED9;
        --old-yellow: #EDD87F;
        --old-blue: #59819B;
        --old-ink: #2B1248;
        --old-paper-light: #FFF9EA;
        --old-line: rgba(165, 49, 34, 0.35);
    }
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stHeader"] {
        background: var(--old-paper) !important;
        color: var(--old-ink) !important;
    }
    [data-testid="stHeader"] {border-bottom: 1px solid rgba(165, 49, 34, 0.18);}
    [data-testid="stSidebar"] {
        background: #efe4cb !important;
        border-right: 1px solid var(--old-line);
    }
    .block-container {
        padding: 0.8rem 1rem 1.4rem 1rem;
        max-width: 100%;
        background: var(--old-paper);
    }
    h1 {
        font-size: 1.45rem;
        margin-bottom: 0.15rem;
        color: var(--old-ink) !important;
        border-left: 0.35rem solid var(--old-red);
        padding-left: 0.55rem;
    }
    h2, h3 {
        font-size: 1.02rem;
        color: var(--old-ink) !important;
    }
    p, label, [data-testid="stCaptionContainer"] {
        color: var(--old-ink) !important;
    }
    [data-testid="stCaptionContainer"] p {color: #6b5570 !important;}
    div[data-baseweb="tab-list"] {
        border-bottom: 1px solid var(--old-line);
        gap: 1rem;
    }
    button[data-baseweb="tab"] {
        color: var(--old-ink) !important;
        background: transparent !important;
        border-radius: 0 !important;
    }
    button[data-baseweb="tab"] p {color: var(--old-ink) !important;}
    button[data-baseweb="tab"][aria-selected="true"] {
        color: var(--old-red) !important;
        border-bottom: 3px solid var(--old-red) !important;
        font-weight: 700;
    }
    button[data-baseweb="tab"][aria-selected="true"] p {color: var(--old-red) !important;}
    div[data-testid="stMetric"] {
        border: 1px solid rgba(165, 49, 34, 0.48);
        border-left: 5px solid var(--old-red);
        padding: 0.42rem 0.55rem;
        border-radius: 4px;
        background: var(--old-yellow);
        color: var(--old-ink) !important;
        box-shadow: inset 0 0 0 1px rgba(255, 249, 234, 0.45);
    }
    div[data-testid="stMetric"] * {color: var(--old-ink) !important;}
    div[data-testid="stMetricValue"] {font-size: 1.05rem;}
    div[data-testid="stMetricLabel"] {
        font-size: 0.78rem;
        color: #6b351d !important;
    }
    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input,
    div[data-testid="stDateInput"] input,
    div[data-baseweb="select"] > div {
        background: var(--old-paper-light) !important;
        color: var(--old-ink) !important;
        border: 1px solid var(--old-rose) !important;
        box-shadow: none !important;
    }
    div[data-testid="stTextInput"] input:focus,
    div[data-testid="stNumberInput"] input:focus,
    div[data-testid="stDateInput"] input:focus {
        border-color: var(--old-red) !important;
        box-shadow: 0 0 0 1px rgba(165, 49, 34, 0.25) !important;
    }
    input:disabled {
        -webkit-text-fill-color: var(--old-ink) !important;
        color: var(--old-ink) !important;
        opacity: 1 !important;
        background: #ead8ca !important;
    }
    div[data-testid="stTextInput"] input::placeholder {color: #7b6472 !important;}
    div[data-testid="stRadio"] label,
    div[data-testid="stRadio"] label p,
    div[role="radiogroup"] label p {
        color: var(--old-ink) !important;
    }
    div[data-testid="stButton"] button,
    div[data-testid="stDownloadButton"] button {
        background: var(--old-red) !important;
        color: var(--old-paper) !important;
        border: 1px solid #8e271c !important;
        border-radius: 4px !important;
        font-weight: 700 !important;
    }
    div[data-testid="stButton"] button:hover,
    div[data-testid="stDownloadButton"] button:hover {
        background: #8e271c !important;
        color: var(--old-paper-light) !important;
        border-color: var(--old-ink) !important;
    }
    div[data-testid="stExpander"] {
        background: rgba(255, 249, 234, 0.72);
        border: 1px solid var(--old-line);
        border-radius: 4px;
    }
    .dense-note {
        font-size: 0.82rem;
        color: #6b5570 !important;
        margin: 0.1rem 0 0.35rem 0;
    }
    .section-title {
        background: var(--old-red);
        border: 1px solid #8e271c;
        color: var(--old-paper) !important;
        padding: 0.55rem 0.7rem;
        font-weight: 700;
        margin-top: 0.7rem;
        box-shadow: inset 0 -3px 0 rgba(43, 18, 72, 0.16);
    }
    .section-title * {color: var(--old-paper) !important;}
    .red-label {color: var(--old-red); font-weight: 700;}
    .stDataFrame {
        border-top: 2px solid var(--old-red);
        border-left: 1px solid var(--old-line);
        border-right: 1px solid var(--old-line);
        background: var(--old-paper-light);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def main() -> None:
    st.title("基本面研究底稿系统")
    st.caption("本地 iFinD 全 A 宽表、单股 DCF 推演、二维交叉评估、调研研报证据")

    sidebar_data_status()
    page = st.radio("页面", PAGES, horizontal=True, label_visibility="collapsed", key="active_page")

    if page == "证据与评分":
        scores, labels, group_summary, coverage = load_score_auxiliary()
        evidence = load_evidence_rows(include_existing_catl=True)
        render_evidence_score_tab(scores, labels, group_summary, coverage, evidence)
        return

    workbench = load_workbench_from_local()
    if page == "股票池底稿":
        render_universe_tab(workbench["master"])
    elif page == "单股DCF":
        render_dcf_tab(workbench)
    elif page == "交叉评估":
        render_scatter_tab(workbench)
    elif page == "本地数据":
        render_template_tab(workbench)


def sidebar_data_status() -> None:
    st.sidebar.header("本地数据")
    manifest = read_manifest(ROOT)
    if IFIND_CACHE_PATHS.universe.exists():
        st.sidebar.success("已读取 iFinD 全 A 本地缓存")
        generated_at = manifest.get("generated_at", "NA")
        total_mb = float(manifest.get("total_bytes", 0)) / 1024 / 1024
        st.sidebar.caption(f"更新时间：{generated_at}")
        st.sidebar.caption(f"缓存体积：{total_mb:.2f} MB")
    else:
        st.sidebar.warning("未找到 iFinD 本地缓存，当前使用模板示例数据。")
    st.sidebar.code("python -m earnings_signal.ifind_workbench --root . --max-mb 95", language="powershell")


def workbench_fingerprint(paths: Any) -> tuple[tuple[str, int, int], ...]:
    return tuple(
        (name, int(path.stat().st_mtime_ns), int(path.stat().st_size))
        for name, path in vars(paths).items()
        if isinstance(path, Path) and path.exists()
    )


def load_workbench_from_local() -> dict[str, pd.DataFrame]:
    if IFIND_CACHE_PATHS.universe.exists() and IFIND_CACHE_PATHS.valuation.exists() and IFIND_CACHE_PATHS.peer_metrics.exists():
        paths = ifind_workbench_paths(ROOT)
        return load_workbench_cached("ifind", workbench_fingerprint(paths))
    return load_workbench_cached("templates", workbench_fingerprint(TEMPLATE_PATHS))


@st.cache_data(show_spinner=False)
def load_workbench_cached(source: str, fingerprint: tuple[tuple[str, int, int], ...]) -> dict[str, pd.DataFrame]:
    paths = ifind_workbench_paths(ROOT) if source == "ifind" else TEMPLATE_PATHS
    return load_workbench(paths)


@st.cache_data(show_spinner=False)
def load_score_auxiliary() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    scores_path = DEMO_DIR / "scores.csv"
    labels_path = DEMO_DIR / "backtest" / "scored_labels.csv"
    summary_path = DEMO_DIR / "backtest" / "group_summary.csv"
    coverage_path = DEMO_DIR / "backtest" / "coverage.csv"
    if scores_path.exists() and labels_path.exists():
        return (
            safe_read_frame(scores_path),
            safe_read_frame(labels_path),
            safe_read_frame(summary_path),
            safe_read_frame(coverage_path),
        )
    score_frame, research, iractivity, negative, consensus, forecasts, actuals = _demo_data()
    scores = score_features(build_features(score_frame, research, iractivity, negative, consensus))
    labels = attach_next_report_labels(scores, forecasts, actuals)
    summary, coverage = evaluate_backtest(labels, bins=3)
    return scores, labels, summary, coverage


def render_universe_tab(master: pd.DataFrame) -> None:
    if master.empty:
        st.warning("未找到股票池数据。请先运行侧边栏里的 iFinD 更新命令；若没有缓存，系统会尝试读取模板示例。")
        return
    st.markdown('<div class="section-title">基本面数据列表</div>', unsafe_allow_html=True)
    filters = render_universe_filters(master)
    view = apply_universe_filters(master, **filters)

    metric_cols = st.columns(6)
    metric_cols[0].metric("筛选结果", f"{len(view):,}")
    metric_cols[1].metric("赛道", f"{view['track'].nunique() if 'track' in view else 0:,}")
    metric_cols[2].metric("观察名单", f"{int(view.get('watch_list', pd.Series(dtype=str)).eq('Y').sum())}")
    metric_cols[3].metric("持仓", f"{int(view.get('holding_list', pd.Series(dtype=str)).eq('Y').sum())}")
    safety_col = "safety_margin_pct" if "safety_margin_pct" in view else "dcf_current_safety_margin_pct"
    metric_cols[4].metric("平均安全边际", f"{view[safety_col].mean():.1f}%" if safety_col in view else "NA")
    metric_cols[5].metric("平均ROIC", f"{view['roic_pct'].mean():.1f}%" if "roic_pct" in view else "NA")

    page_view, page_meta = paginate_view(view, key_prefix="universe")
    display = format_master_table(page_view)
    left, right = st.columns([0.2, 2.8])
    with left:
        st.download_button(
            "导出",
            data=view.to_csv(index=False).encode("utf-8-sig"),
            file_name="research_universe_filtered.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with right:
        st.markdown(
            f'<div class="dense-note">当前渲染第 {page_meta["start"]}-{page_meta["end"]} 行 / 共 {page_meta["total"]} 行；导出仍包含全部筛选结果。</div>',
            unsafe_allow_html=True,
        )
    st.dataframe(display, use_container_width=True, hide_index=True, height=470)


def render_universe_filters(master: pd.DataFrame) -> dict[str, Any]:
    dates = pd.to_datetime(master["date"], errors="coerce") if "date" in master else pd.Series(dtype="datetime64[ns]")
    default_date = dates.max() if not dates.dropna().empty else pd.Timestamp.today()
    row1 = st.columns([0.9, 1.0, 1.1, 1.0, 1.2, 1.2, 1.2, 1.2])
    selected_date = row1[0].date_input("日期", value=default_date)
    code = row1[1].text_input("代码", placeholder="股票代码")
    name = row1[2].text_input("名称", placeholder="股票名称")
    track = row1[3].text_input("赛道", placeholder="消费")
    note = row1[4].text_input("备注", placeholder="备注")
    concept = row1[5].text_input("概念标注", placeholder="概念标注")
    sw_l2 = row1[6].text_input("申万2级行业", placeholder="Wind2级行业")
    broad_index = row1[7].text_input("所属宽基", placeholder="所属宽基")

    row2 = st.columns([2.0, 2.1, 1.2])
    list_name = row2[0].radio("名单", list(LIST_COLUMNS.keys()), horizontal=True, index=0)
    market_name = row2[1].radio("市场", list(MARKET_OPTIONS.keys()), horizontal=True, index=1)
    search = row2[2].text_input("搜索", placeholder="任意关键词")
    return {
        "date": selected_date,
        "code": code,
        "name": name,
        "track": track,
        "note": note,
        "concept": concept,
        "sw_l2": sw_l2,
        "sw_l3": "",
        "broad_index": broad_index,
        "list_name": list_name,
        "market_name": market_name,
        "search": search,
    }


def render_dcf_tab(workbench: dict[str, pd.DataFrame]) -> None:
    master = workbench["master"]
    valuation = workbench["valuation"]
    history = workbench["financial_history"]
    if master.empty or valuation.empty:
        st.warning("缺少股票池或 DCF 参数表。")
        return
    st.markdown('<div class="section-title">折现现金流模型演算过程</div>', unsafe_allow_html=True)
    stock_options = master["stock_code"].astype(str) + " " + master["stock_name"].astype(str)
    default_idx = next((i for i, value in enumerate(stock_options) if "000651" in value), 0)
    selected_label = st.selectbox("股票", stock_options.tolist(), index=default_idx)
    stock_code = selected_label.split()[0]
    row = valuation_row(valuation, stock_code)
    if not row:
        st.warning("该股票缺少 DCF 参数。")
        return

    inputs = render_dcf_inputs(row)
    try:
        dcf = calculate_dcf(inputs)
    except ValueError as exc:
        st.error(str(exc))
        return

    render_dcf_summary(inputs, dcf)
    st.markdown('<div class="section-title">参考数据</div>', unsafe_allow_html=True)
    stock_history = financial_history_for_stock(history, stock_code)
    if stock_history.empty:
        st.info("该股票暂无历史财务数据。")
    else:
        st.dataframe(stock_history.drop(columns=["stock_code"], errors="ignore"), use_container_width=True, hide_index=True)


def render_dcf_inputs(row: dict[str, Any]) -> dict[str, Any]:
    st.markdown('<span class="red-label">*红色标签对应关键手工假设，可直接调参。</span>', unsafe_allow_html=True)
    labels = [
        ("股票代码", "stock_code", "text"),
        ("股票名称", "stock_name", "text"),
        ("Profit_1Y", "profit_1y_100m", "number"),
        ("FCFF/Profit %", "fcff_profit_pct", "number"),
        ("股利支付率 %", "dividend_payout_pct", "number"),
        ("*股票市价", "price", "number"),
        ("总股本（亿股）", "shares_outstanding_100m", "number"),
        ("总市值（亿）", "market_cap_100m", "number"),
        ("上年末总市值（亿）", "last_year_market_cap_100m", "number"),
        ("*永续年金增长率（g）", "perpetual_growth_pct", "number"),
        ("*折现率（R）", "discount_rate_pct", "number"),
        ("*安全边际", "safety_margin_pct", "number"),
        ("*DCF_EPS_CAGR", "dcf_eps_cagr_pct", "number"),
        ("*DCF_EPS_CAGR_PHASE2", "dcf_eps_cagr_phase2_pct", "number"),
        ("*现金(亿)", "cash_100m", "number"),
        ("*非核心资产(亿)", "non_core_assets_100m", "number"),
        ("*带息债务(亿)", "interest_bearing_debt_100m", "number"),
        ("*归母权益占比", "parent_equity_ratio_pct", "number"),
    ]
    values = dict(row)
    for start in range(0, len(labels), 5):
        cols = st.columns(5)
        for col, (label, key, kind) in zip(cols, labels[start : start + 5]):
            if kind == "text":
                values[key] = col.text_input(label, value=str(values.get(key, "")), disabled=True)
            else:
                values[key] = col.number_input(
                    label,
                    value=float(pd.to_numeric(values.get(key), errors="coerce") if pd.notna(pd.to_numeric(values.get(key), errors="coerce")) else 0.0),
                    step=0.1,
                    format="%.2f",
                )
    st.markdown(
        '<div class="dense-note">注：下一年度自由现金流 = Profit_1Y * FCFF/Profit；永续价值使用 Gordon Growth；金额单位为亿元，股价/每股价值单位为元。</div>',
        unsafe_allow_html=True,
    )
    return values


def render_dcf_summary(inputs: dict[str, Any], dcf: Any) -> None:
    schedule = dcf.schedule.copy()
    schedule_display = pd.DataFrame(
        {
            "年数": schedule["year"].astype(int),
            "自由现金流(亿)": schedule["fcf_100m"].round(2),
            "自由现金流折现(亿)": schedule["pv_fcf_100m"].round(2),
        }
    ).T
    schedule_display.columns = [str(i) for i in range(1, 11)]
    st.dataframe(schedule_display, use_container_width=True)

    summary = dcf.summary
    rows = [
        ("+ 自由现金流折现合计(亿)", summary["pv_fcf_sum_100m"]),
        ("永续年金价值(亿)", summary["terminal_value_100m"]),
        ("+ 永续年金价值折现(亿)", summary["terminal_pv_100m"]),
        ("+ 现金(亿)", summary["cash_100m"]),
        ("+ 非核心资产(亿)", summary["non_core_assets_100m"]),
        ("- 带息债务(亿)", summary["interest_bearing_debt_100m"]),
        ("* 归属于母公司所有者权益占比", float(inputs.get("parent_equity_ratio_pct", 100)) / 100.0),
        ("所有者权益合计(亿)", summary["equity_value_100m"]),
        ("计算每股价值(元)", summary["per_share_value"]),
        ("达到目标安全边际，对应的股价(元)", summary["safety_price"]),
        ("当前安全边际(%)", summary["current_safety_margin_pct"]),
    ]
    summary_frame = pd.DataFrame(rows, columns=["项目", "数值"])
    summary_frame["数值"] = summary_frame["数值"].map(lambda x: round(float(x), 4))
    st.dataframe(summary_frame, use_container_width=True, hide_index=True)


def render_scatter_tab(workbench: dict[str, pd.DataFrame]) -> None:
    master = workbench["master"]
    peers = workbench["peer_metrics"]
    if master.empty or peers.empty:
        st.warning("缺少股票池或交叉评估数据。")
        return
    st.markdown('<div class="section-title">交叉评估图</div>', unsafe_allow_html=True)
    controls = st.columns([1.1, 1.0, 1.0, 1.2])
    chart_name = controls[0].selectbox("图形", list(SCATTER_SPECS.keys()))
    track_options = ["全部"] + sorted(master["track"].dropna().astype(str).unique().tolist())
    track = controls[1].selectbox("赛道", track_options)
    market = controls[2].selectbox("市场", list(MARKET_OPTIONS.keys()), index=1)
    name_filter = controls[3].text_input("名称/代码", "")
    display_controls = st.columns([0.8, 1.0, 2.2])
    max_points = display_controls[0].slider("图中股票数", min_value=5, max_value=20, value=20, step=5)
    sort_label = display_controls[1].selectbox("展示规则", list(SCATTER_SORT_OPTIONS.keys()))

    universe_view = apply_universe_filters(master, track="" if track == "全部" else track, market_name=market, search=name_filter)
    peer_base = peers.drop(columns=[col for col in ["stock_name", "track", "market", "style"] if col in peers.columns])
    universe_cols = [col for col in ["stock_code", "stock_name", "track", "market", "style", "market_cap_100m"] if col in universe_view.columns]
    scatter_source = peer_base.merge(
        universe_view[universe_cols].drop_duplicates("stock_code"),
        on="stock_code",
        how="inner",
    )
    scatter, missing, spec = prepare_scatter_data(scatter_source, chart_name)
    if missing:
        st.warning(f"当前数据缺少字段：{', '.join(missing)}")
        return
    candidate_count = len(scatter)
    scatter = select_scatter_points(scatter, spec, max_points=max_points, mode=SCATTER_SORT_OPTIONS[sort_label])
    display_controls[2].markdown(
        f'<div class="dense-note">候选样本 {candidate_count:,} 只，图中显示 {len(scatter):,} 只。先用筛选缩小赛道，再看排序后的代表样本。</div>',
        unsafe_allow_html=True,
    )
    fig = px.scatter(
        scatter,
        x=spec["x"],
        y=spec["y"],
        text="stock_name",
        color="track",
        color_discrete_sequence=PLOTLY_COLORS,
        hover_data=[col for col in ["stock_code", "industry", "style", "market_cap_100m"] if col in scatter.columns],
        labels={spec["x"]: spec["x_label"], spec["y"]: spec["y_label"]},
        height=620,
    )
    fig.update_traces(
        textposition="top center",
        textfont=dict(color=PALETTE["ink"], size=12),
        marker=dict(size=10, opacity=0.82, line=dict(width=1, color=PALETTE["paper"])),
    )
    fig.add_vline(
        x=spec["x_threshold"],
        line_dash="dash",
        line_color=PALETTE["red"],
        annotation_text=str(spec["x_threshold"]),
        annotation_font_color=PALETTE["red"],
    )
    fig.add_hline(
        y=spec["y_threshold"],
        line_dash="dash",
        line_color=PALETTE["blue"],
        annotation_text=str(spec["y_threshold"]),
        annotation_font_color=PALETTE["blue"],
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=45, b=20),
        title=dict(text=chart_name, font=dict(color=PALETTE["ink"], size=20)),
        paper_bgcolor=PALETTE["paper"],
        plot_bgcolor="rgba(255, 249, 234, 0.72)",
        font=dict(color=PALETTE["ink"]),
        legend=dict(
            bgcolor="rgba(255, 249, 234, 0.78)",
            bordercolor=PALETTE["rose"],
            borderwidth=1,
        ),
    )
    fig.update_xaxes(
        gridcolor="rgba(89, 129, 155, 0.20)",
        zerolinecolor="rgba(43, 18, 72, 0.45)",
        linecolor=PALETTE["ink"],
    )
    fig.update_yaxes(
        gridcolor="rgba(89, 129, 155, 0.20)",
        zerolinecolor="rgba(43, 18, 72, 0.45)",
        linecolor=PALETTE["ink"],
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(format_master_table(scatter), use_container_width=True, hide_index=True, height=360)


def render_evidence_score_tab(
    scores: pd.DataFrame,
    labels: pd.DataFrame,
    group_summary: pd.DataFrame,
    coverage: pd.DataFrame,
    evidence: pd.DataFrame,
) -> None:
    st.markdown('<div class="section-title">调研 / 研报 / 一致预期评分</div>', unsafe_allow_html=True)
    render_fetch_controls()
    render_score_auxiliary(scores, labels, group_summary, coverage)
    st.markdown('<div class="section-title">大智慧证据流</div>', unsafe_allow_html=True)
    render_evidence_table(evidence)


def render_fetch_controls() -> None:
    with st.expander("实时拉取单股大智慧证据", expanded=False):
        cols = st.columns([0.8, 0.8, 0.8, 1.4, 0.8])
        stock = cols[0].text_input("股票代码", "300750")
        start = cols[1].date_input("开始日期", value=pd.Timestamp("2026-01-01"))
        end = cols[2].date_input("结束日期", value=pd.Timestamp("2026-07-01"))
        api_key = cols[3].text_input("API Key", type="password", placeholder="留空则使用 DZH_API_KEY")
        clicked = cols[4].button("提取数据", use_container_width=True)
        if clicked:
            key = api_key or os.environ.get("DZH_API_KEY")
            if not key:
                st.error("请填写 API Key，或设置 DZH_API_KEY 环境变量。")
                return
            try:
                with st.spinner("正在分页拉取研报、调研、负面、公告和综合资讯..."):
                    written = fetch_dzh_evidence(stock.strip(), str(start), str(end), key, STREAMLIT_DZH_DIR / stock.strip())
            except (DzhApiError, ValueError) as exc:
                st.error(f"拉取失败：{exc}")
            else:
                st.success(f"已写入 {STREAMLIT_DZH_DIR / stock.strip()}")
                st.dataframe(pd.DataFrame(written), use_container_width=True, hide_index=True)


def render_score_auxiliary(scores: pd.DataFrame, labels: pd.DataFrame, group_summary: pd.DataFrame, coverage: pd.DataFrame) -> None:
    cols = st.columns(4)
    cols[0].metric("评分样本", f"{len(scores):,}")
    cols[1].metric("回测样本", f"{int(labels.get('label_status', pd.Series(dtype=str)).eq('ok').sum()) if not labels.empty else 0:,}")
    cols[2].metric("评分日期", f"{scores['score_date'].nunique() if 'score_date' in scores else 0}")
    top_score = pd.to_numeric(scores.get("composite_score", pd.Series(dtype=float)), errors="coerce").max() if not scores.empty else np.nan
    cols[3].metric("最高评分", f"{top_score:.2f}" if pd.notna(top_score) else "NA")
    left, right = st.columns([1.1, 0.9])
    with left:
        if not scores.empty:
            show = scores.sort_values("composite_score", ascending=False).head(30)
            st.dataframe(show, use_container_width=True, hide_index=True)
        else:
            st.info("暂无评分数据。")
    with right:
        if not group_summary.empty and "score_group" in group_summary:
            st.bar_chart(group_summary.set_index("score_group")[["mean_net_profit_surprise"]])
            st.dataframe(group_summary, use_container_width=True, hide_index=True)
        elif not coverage.empty:
            st.dataframe(coverage, use_container_width=True, hide_index=True)
        else:
            st.info("暂无回测结果。")


def render_evidence_table(evidence: pd.DataFrame) -> None:
    if evidence.empty:
        st.info("暂无证据数据。可通过上方实时拉取，或放入 output/streamlit/dzh/{stock}/。")
        return
    filters = st.columns([0.8, 0.8, 1.6])
    resource = filters[0].selectbox("类型", ["全部"] + sorted(evidence["resource"].dropna().astype(str).unique().tolist()))
    code = filters[1].text_input("代码筛选")
    keyword = filters[2].text_input("标题/摘要关键词")
    view = evidence.copy()
    if resource != "全部":
        view = view[view["resource"].eq(resource)]
    if code:
        view = view[view["stock_code"].astype(str).str.contains(code, na=False)]
    if keyword:
        blob = view["title"].fillna("").astype(str) + " " + view["brief"].fillna("").astype(str)
        view = view[blob.str.contains(keyword, case=False, na=False)]
    cols = ["event_date", "stock_code", "stock_name", "resource", "source", "title", "brief", "source_id", "file"]
    st.dataframe(view[[c for c in cols if c in view]], use_container_width=True, hide_index=True, height=420)


def render_template_tab(workbench: dict[str, pd.DataFrame]) -> None:
    st.markdown('<div class="section-title">本地 iFinD 数据与字段校验</div>', unsafe_allow_html=True)
    manifest = read_manifest(ROOT)
    if manifest:
        file_rows = []
        for name, meta in manifest.get("files", {}).items():
            file_rows.append(
                {
                    "文件": name,
                    "行数": meta.get("rows"),
                    "体积MB": round(float(meta.get("bytes", 0)) / 1024 / 1024, 3),
                    "路径": meta.get("path"),
                }
            )
        left, right = st.columns([0.8, 1.2])
        left.metric("缓存总大小", f"{float(manifest.get('total_bytes', 0)) / 1024 / 1024:.2f} MB")
        left.metric("大小上限", f"{float(manifest.get('max_bytes', 0)) / 1024 / 1024:.0f} MB")
        right.dataframe(pd.DataFrame(file_rows), use_container_width=True, hide_index=True)
    else:
        st.info("尚未生成 data/ifind_workbench 本地缓存，当前页面使用模板示例数据。")
    st.code("python -m earnings_signal.ifind_workbench --root . --max-mb 95", language="powershell")

    st.markdown('<div class="section-title">模板下载与字段校验</div>', unsafe_allow_html=True)
    cols = st.columns(4)
    template_files = [
        ("股票池模板", TEMPLATE_PATHS.universe),
        ("DCF参数模板", TEMPLATE_PATHS.valuation),
        ("历史财务模板", TEMPLATE_PATHS.financial_history),
        ("交叉评估模板", TEMPLATE_PATHS.peer_metrics),
    ]
    for col, (label, path) in zip(cols, template_files):
        col.download_button(
            label,
            data=path.read_bytes(),
            file_name=path.name,
            mime="text/csv",
            use_container_width=True,
        )
    validation = pd.DataFrame(
        [
            {
                "表": "research_universe",
                "缺失字段": ", ".join(validate_columns(workbench["universe"], REQUIRED_UNIVERSE_COLUMNS)) or "OK",
                "行数": len(workbench["universe"]),
            },
            {
                "表": "valuation_inputs",
                "缺失字段": ", ".join(validate_columns(workbench["valuation"], REQUIRED_VALUATION_COLUMNS)) or "OK",
                "行数": len(workbench["valuation"]),
            },
            {"表": "financial_history", "缺失字段": "OK" if not workbench["financial_history"].empty else "无数据", "行数": len(workbench["financial_history"])},
            {"表": "peer_metrics", "缺失字段": "OK" if not workbench["peer_metrics"].empty else "无数据", "行数": len(workbench["peer_metrics"])},
        ]
    )
    st.dataframe(validation, use_container_width=True, hide_index=True)
    st.markdown('<div class="dense-note">模板只作为无 iFinD 缓存时的兜底示例；正式页面默认读取 data/ifind_workbench 下的本地 parquet。</div>', unsafe_allow_html=True)


def paginate_view(frame: pd.DataFrame, key_prefix: str) -> tuple[pd.DataFrame, dict[str, int]]:
    total = len(frame)
    if total == 0:
        return frame, {"start": 0, "end": 0, "total": 0}
    controls = st.columns([0.5, 0.7, 1.8])
    page_size = int(controls[0].selectbox("每页行数", [100, 200, 500], index=1, key=f"{key_prefix}_page_size"))
    total_pages = max(1, int(np.ceil(total / page_size)))
    page = int(controls[1].number_input("页码", min_value=1, max_value=total_pages, value=1, step=1, key=f"{key_prefix}_page"))
    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, total)
    controls[2].markdown(
        f'<div class="dense-note">为保证刷新速度，表格只渲染当前页；完整筛选结果可用“导出”。共 {total_pages:,} 页。</div>',
        unsafe_allow_html=True,
    )
    return frame.iloc[start_idx:end_idx].copy(), {"start": start_idx + 1, "end": end_idx, "total": total}


def format_master_table(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    columns = [col for col in DISPLAY_COLUMNS if col in frame.columns]
    extra = [col for col in frame.columns if col not in columns and col not in {"market"}]
    ordered = columns + extra[:8]
    display = frame[ordered].copy()
    if "date" in display:
        display["date"] = pd.to_datetime(display["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    for column in display.select_dtypes(include=["float", "int"]).columns:
        display[column] = display[column].round(2)
    return display.rename(columns=DISPLAY_COLUMNS)


def safe_read_frame(path: str | Path | None) -> pd.DataFrame:
    if not path:
        return pd.DataFrame()
    path = Path(path)
    if not path.exists():
        return pd.DataFrame()
    try:
        return read_table(path)
    except Exception:
        return pd.DataFrame()


def load_evidence_rows(include_existing_catl: bool = True) -> pd.DataFrame:
    evidence_rows: list[dict[str, Any]] = []
    if STREAMLIT_DZH_DIR.exists():
        for path in STREAMLIT_DZH_DIR.rglob("*.json"):
            evidence_rows.extend(rows_from_evidence_file(path))
    if include_existing_catl and OUTPUT_DIR.exists():
        for path in OUTPUT_DIR.glob("catl_300750_*_all.json"):
            evidence_rows.extend(rows_from_evidence_file(path))
    if not evidence_rows:
        return pd.DataFrame(columns=["resource", "stock_code", "event_date", "title", "source", "source_id"])
    frame = pd.DataFrame(evidence_rows)
    frame["event_date"] = pd.to_datetime(frame["event_date"], errors="coerce")
    return frame.sort_values("event_date", ascending=False, na_position="last").reset_index(drop=True)


def rows_from_evidence_file(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    resource = data.get("resource") if isinstance(data, dict) else None
    if not resource:
        stem = path.stem.lower()
        if "research" in stem:
            resource = "research"
        elif "iractivity" in stem:
            resource = "iractivity"
        elif "negative" in stem or "neg" in stem:
            resource = "negative"
        elif "disclosure" in stem:
            resource = "disclosure"
        elif "news" in stem:
            resource = "news"
        elif "compinfo" in stem:
            resource = "compinfo"
        else:
            resource = stem
    return [normalize_evidence_row(row, resource, path) for row in extract_rows(data)]


def normalize_evidence_row(row: dict[str, Any], resource: str, path: Path) -> dict[str, Any]:
    props = row.get("Properties") if isinstance(row.get("Properties"), dict) else {}
    return {
        "resource": resource,
        "stock_code": first_present(row, "StkCode", "SecCode", "stock_code") or props.get("scode"),
        "stock_name": first_present(row, "StkName", "SecName", "sname"),
        "event_date": first_present(row, "ReportDate", "PublishDate", "CreateTime", "pubdate"),
        "title": first_present(row, "Title", "title", "Content", "Question"),
        "source": first_present(row, "InstituteNameCN", "SourceName", "Disclosure_Name", "TypeName", "AuthorName") or props.get("instname"),
        "source_id": first_present(row, "ReportID", "CompId", "NewsId", "InfoId", "nID", "id"),
        "brief": first_present(row, "BriefText", "brief", "Reply"),
        "file": str(path),
    }


def first_present(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def fetch_dzh_evidence(stock: str, start: str, end: str, api_key: str, out_dir: Path) -> list[dict[str, Any]]:
    client = DzhClient(api_key=api_key, sleep_seconds=0.15)
    resources = {
        "research": client.research_reports,
        "iractivity": client.ir_activities,
        "negative": client.negative_news,
        "disclosure": client.disclosures,
        "compinfo": client.compinfo,
    }
    written: list[dict[str, Any]] = []
    for name, func in resources.items():
        response = func(stock, start, end)
        payload = {
            "stock": stock,
            "resource": name,
            "reccount": response.reccount,
            "page_size": response.page_size,
            "pages_fetched": response.pages_fetched,
            "duplicate_rows": response.duplicate_rows,
            "rows": response.rows,
        }
        write_json(out_dir / f"{name}.json", payload)
        write_rows_csv(out_dir / f"{name}.csv", response.rows)
        written.append(
            {
                "resource": name,
                "reccount": response.reccount,
                "fetched": len(response.rows),
                "pages": response.pages_fetched,
                "duplicates": response.duplicate_rows,
            }
        )
    return written


if __name__ == "__main__":
    main()
