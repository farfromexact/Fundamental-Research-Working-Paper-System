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
    MARKET_OPTIONS,
    REQUIRED_UNIVERSE_COLUMNS,
    REQUIRED_VALUATION_COLUMNS,
    SCATTER_SPECS,
    apply_numeric_filters,
    apply_universe_filters,
    calculate_dcf,
    choose_scatter_chart,
    financial_history_for_stock,
    load_workbench,
    scatter_chart_availability,
    select_scatter_points,
    template_paths,
    validate_columns,
    valuation_row,
)


ROOT = Path(__file__).parent
OUTPUT_DIR = ROOT / "output"
DEMO_DIR = OUTPUT_DIR / "demo"
STREAMLIT_DZH_DIR = OUTPUT_DIR / "streamlit" / "dzh"
STREAMLIT_NOTES_PATH = OUTPUT_DIR / "streamlit" / "stock_notes.json"
STREAMLIT_MARKS_PATH = OUTPUT_DIR / "streamlit" / "stock_marks.json"
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
SCATTER_FORMULAS = {
    "ROIC vs 安全边际": "X = ROIC；Y = 行业内 PB 折价安全边际 = (行业PB中位数 - 公司PB) / 行业PB中位数 * 100%。银行等金融股通常没有 ROIC，系统会自动临时切到 ROE/PB。",
    "FCFF收益率 vs IRR_WorseCase": "X = FCFF收益率 = FCFF / 总市值 * 100%；Y = IRR_WorseCase = FCFF收益率 + 永续增长率，目前默认永续增长率取 3%。",
    "ROE/PB": "X = PB；Y = ROE。适合银行、保险等 ROIC 不稳定或不可比行业，左上方代表较低 PB 和较高 ROE。",
    "股息率 vs ROE/PB": "X = 股息率；Y = ROE/PB = ROE / PB，用于比较红利质量和估值效率。",
}


def scatter_formula_help() -> str:
    return "\n\n".join(f"{name}: {formula}" for name, formula in SCATTER_FORMULAS.items())


DISPLAY_COLUMNS = {
    "date": "日期",
    "stock_code": "股票代码",
    "stock_name": "股票名称",
    "track": "赛道",
    "note": "备注",
    "concept_tag": "概念标注",
    "sw_l2": "Wind2级行业",
    "sw_l3": "Wind3级行业",
    "style": "所属风格",
    "long_list": "多头名单",
    "short_list": "空头名单",
    "watch_list": "观察名单",
    "holding_list": "持仓名单",
    "peer_list": "同业名单",
    "list_date": "上市日期",
    "price": "股价",
    "market_cap_100m": "总市值(亿)",
    "profit_1y_100m": "Profit_1Y(亿)",
    "fcff_profit_pct": "FCFF/Profit%",
    "dividend_payout_pct": "股利支付率%",
    "perpetual_growth_pct": "永续增长率%",
    "discount_rate_pct": "折现率%",
    "cash_100m": "现金(亿)",
    "non_core_assets_100m": "非核心资产(亿)",
    "interest_bearing_debt_100m": "带息债务(亿)",
    "parent_equity_ratio_pct": "归母权益占比%",
    "dcf_per_share_value": "DCF每股价值",
    "dcf_safety_price": "DCF安全边际对应价",
    "dcf_current_safety_margin_pct": "DCF当前安全边际%",
    "dcf_equity_value_100m": "DCF权益价值(亿)",
    "roic_pct": "ROIC%",
    "safety_margin_pct": "安全边际%",
    "safety_margin_pct_peer": "同业安全边际%",
    "dcf_auto_safety_margin_pct": "DCF自动安全边际%",
    "fcff_yield_pct": "FCFF收益率%",
    "irr_worst_pct": "IRR_WorseCase%",
    "roe_pct": "ROE%",
    "pb": "PB",
    "dividend_yield_pct": "股息率%",
    "risk_budget_pct": "风险预算%",
    "absolute_return_pct": "绝对收益%",
    "relative_return_pct": "相对收益%",
}
MARKED_DISPLAY_COLUMN = "标记"
NUMERIC_FILTER_SLOTS = 5
NUMERIC_FILTER_COLUMNS = [
    "price",
    "market_cap_100m",
    "profit_1y_100m",
    "fcff_profit_pct",
    "dividend_payout_pct",
    "perpetual_growth_pct",
    "discount_rate_pct",
    "cash_100m",
    "non_core_assets_100m",
    "interest_bearing_debt_100m",
    "parent_equity_ratio_pct",
    "dcf_per_share_value",
    "dcf_safety_price",
    "dcf_current_safety_margin_pct",
    "dcf_equity_value_100m",
    "roic_pct",
    "safety_margin_pct",
    "safety_margin_pct_peer",
    "dcf_auto_safety_margin_pct",
    "fcff_yield_pct",
    "irr_worst_pct",
    "roe_pct",
    "pb",
    "dividend_yield_pct",
    "risk_budget_pct",
    "absolute_return_pct",
    "relative_return_pct",
]
KRI_COLUMN_HELP = {
    "日期": "本行数据快照日期；同一股票会取不晚于筛选日期的最新记录。",
    "股票代码": "证券交易代码，用于精确定位标的和跨表关联。",
    "股票名称": "证券简称，用于人工识别和关键词检索。",
    "赛道": "研究分组或业务赛道，用于同类公司横向筛选。",
    "备注": "本地备注字段；新的重点关注请优先使用“标记”列。",
    "标记": "本地关注标记；勾选后保存，会写入本机缓存并随当前页展示。",
    "概念标注": "题材或业务概念标签，用于补充行业分类之外的横向筛选。",
    "Wind2级行业": "二级行业分类，用于行业内比较和估值分组。",
    "Wind3级行业": "三级行业分类，用于更细颗粒度的同行筛选。",
    "所属风格": "估值或交易风格标签，例如低PB、成长、红利等。",
    "多头名单": "是否进入多头候选池，用于记录优先研究方向。",
    "空头名单": "是否进入空头或负面观察池，用于记录需回避或跟踪风险的标的。",
    "观察名单": "是否进入观察池，用于后续跟踪但暂不下结论的标的。",
    "持仓名单": "是否属于现有持仓或重点持仓跟踪范围。",
    "同业名单": "是否作为同行可比样本，用于估值和经营质量对照。",
    "上市日期": "证券上市日期，可辅助判断样本历史长度和财务可比性。",
    "股价": "当前或缓存快照股价，是估值安全边际计算的输入。",
    "总市值(亿)": "总市值，单位亿元，用于规模、流动性和可比公司筛选。",
    "Profit_1Y(亿)": "DCF 使用的下一年度利润预测，单位亿元。",
    "FCFF/Profit%": "自由现金流与利润的比例，衡量利润转现金流能力。",
    "股利支付率%": "分红占利润比例，用于判断股东回报强度和持续性。",
    "永续增长率%": "DCF 永续阶段增长假设，过高会显著放大估值。",
    "折现率%": "DCF 折现率假设，反映资金成本和业务风险补偿。",
    "现金(亿)": "公司现金及等价资产，DCF 权益价值加项。",
    "非核心资产(亿)": "可独立估值或处置的非核心资产，DCF 权益价值加项。",
    "带息债务(亿)": "有息负债规模，DCF 权益价值扣减项。",
    "归母权益占比%": "权益价值归属于母公司股东的比例。",
    "DCF每股价值": "基于当前 DCF 假设计算出的每股内在价值。",
    "DCF安全边际对应价": "达到目标安全边际时对应的买入价。",
    "DCF当前安全边际%": "当前价格相对 DCF 每股价值的折价幅度。",
    "DCF权益价值(亿)": "DCF 估算的归母权益价值，单位亿元。",
    "ROIC%": "投入资本回报率，衡量业务质量和资本效率。",
    "安全边际%": "相对行业 PB 中位数的折价安全边际。",
    "同业安全边际%": "来自同业指标表的安全边际字段，用于与主安全边际口径交叉检查。",
    "DCF自动安全边际%": "基于自动估值字段得到的 DCF 安全边际参考值。",
    "FCFF收益率%": "自由现金流除以总市值，衡量现金流收益率。",
    "IRR_WorseCase%": "保守口径预期回报，当前近似为 FCFF 收益率加永续增长率。",
    "ROE%": "净资产收益率，金融和低PB公司对比时尤其重要。",
    "PB": "市净率，用于资产型、金融和周期公司估值比较。",
    "股息率%": "现金分红收益率，用于红利质量和防御性筛选。",
    "风险预算%": "组合层面的风险预算或最大风险暴露参考。",
    "绝对收益%": "以个股自身价格或估值为基准的绝对收益测算。",
    "相对收益%": "相对基准或可比组合的超额收益测算。",
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
    [data-testid="stHeader"] {
        border-bottom: 1px solid rgba(165, 49, 34, 0.18);
        min-height: 2.35rem;
    }
    [data-testid="stSidebar"] {
        background: #efe4cb !important;
        border-right: 1px solid var(--old-line);
    }
    .block-container {
        padding: 2.45rem 1rem 1.4rem 1rem;
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


def load_note_overrides() -> dict[str, str]:
    if not STREAMLIT_NOTES_PATH.exists():
        return {}
    try:
        raw = json.loads(STREAMLIT_NOTES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    return {str(code).strip(): str(text).strip() for code, text in raw.items() if text is not None}


def save_note_overrides(overrides: dict[str, str]) -> None:
    STREAMLIT_NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {code: note for code, note in sorted(overrides.items()) if note.strip()}
    STREAMLIT_NOTES_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_mark_overrides() -> set[str]:
    if not STREAMLIT_MARKS_PATH.exists():
        return set()
    try:
        raw = json.loads(STREAMLIT_MARKS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return set()
    if isinstance(raw, list):
        return {str(code).strip() for code in raw if str(code).strip()}
    if isinstance(raw, dict):
        return {str(code).strip() for code, marked in raw.items() if marked and str(code).strip()}
    return set()


def save_mark_overrides(marks: set[str]) -> None:
    STREAMLIT_MARKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STREAMLIT_MARKS_PATH.write_text(json.dumps(sorted(marks), ensure_ascii=False, indent=2), encoding="utf-8")


def apply_note_overrides(frame: pd.DataFrame, overrides: dict[str, str]) -> pd.DataFrame:
    if frame.empty or "stock_code" not in frame.columns:
        return frame
    if "note" not in frame.columns:
        frame = frame.copy()
        frame["note"] = ""
    view = frame.copy()
    view["note"] = view["stock_code"].astype(str).map(overrides).fillna(view["note"]).fillna("")
    return view


def apply_mark_overrides(frame: pd.DataFrame, marks: set[str]) -> pd.DataFrame:
    if frame.empty or "stock_code" not in frame.columns:
        return frame
    view = frame.copy()
    legacy_star = view.get("note", pd.Series("", index=view.index)).fillna("").astype(str).str.strip().eq("⭐")
    view["marked"] = view["stock_code"].astype(str).isin(marks) | legacy_star
    return view


def table_column_config(display: pd.DataFrame) -> dict[str, Any]:
    config: dict[str, Any] = {}
    for column in display.columns:
        help_text = KRI_COLUMN_HELP.get(column, "本地缓存字段，用于筛选、横向比较或导出留痕。")
        if column == MARKED_DISPLAY_COLUMN:
            config[column] = st.column_config.CheckboxColumn(column, help=help_text, width="small")
        elif pd.api.types.is_numeric_dtype(display[column]):
            config[column] = st.column_config.NumberColumn(column, help=help_text, format="%.2f")
        else:
            config[column] = st.column_config.TextColumn(column, help=help_text)
    return config


def marker_editor_key(page_view: pd.DataFrame) -> str:
    if page_view.empty or "stock_code" not in page_view.columns:
        return "universe_marker_editor:empty"
    return f"universe_marker_editor:{page_view['stock_code'].iloc[0]}:{page_view['stock_code'].iloc[-1]}"


def add_marker_display_column(display: pd.DataFrame, page_view: pd.DataFrame) -> pd.DataFrame:
    if display.empty or "stock_code" not in page_view.columns:
        return display
    marked_values = page_view.get("marked", pd.Series(False, index=page_view.index)).fillna(False).astype(bool).tolist()
    result = display.copy()
    insert_at = min(3, len(result.columns))
    if MARKED_DISPLAY_COLUMN in result.columns:
        result[MARKED_DISPLAY_COLUMN] = marked_values
    else:
        result.insert(insert_at, MARKED_DISPLAY_COLUMN, marked_values)
    return result


def save_marker_edits(edited: pd.DataFrame) -> bool:
    if MARKED_DISPLAY_COLUMN not in edited or "股票代码" not in edited:
        return False
    marks = load_mark_overrides()
    notes = load_note_overrides()
    changed = False
    for _, row in edited.iterrows():
        code = str(row["股票代码"]).strip()
        if not code:
            continue
        marked = bool(row.get(MARKED_DISPLAY_COLUMN))
        if marked and code not in marks:
            marks.add(code)
            changed = True
        if not marked and code in marks:
            marks.remove(code)
            changed = True
        if notes.get(code, "").strip() == "⭐":
            notes.pop(code, None)
            changed = True
    if changed:
        save_mark_overrides(marks)
        save_note_overrides(notes)
    return changed


def clear_page_markers(edited: pd.DataFrame) -> bool:
    if "股票代码" not in edited:
        return False
    marks = load_mark_overrides()
    notes = load_note_overrides()
    changed = False
    for code in edited["股票代码"].astype(str).str.strip():
        if code in marks:
            marks.remove(code)
            changed = True
        if notes.get(code, "").strip() == "⭐":
            notes.pop(code, None)
            changed = True
    if changed:
        save_mark_overrides(marks)
        save_note_overrides(notes)
    return changed


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
    mark_filter = filters.pop("mark_filter", "全部")
    numeric_filters = filters.pop("numeric_filters", [])
    note_overrides = load_note_overrides()
    mark_overrides = load_mark_overrides()
    note_enriched_master = apply_note_overrides(master, note_overrides)
    note_enriched_master = apply_mark_overrides(note_enriched_master, mark_overrides)
    view = apply_universe_filters(note_enriched_master, **filters)
    view = apply_marker_filter(view, mark_filter)
    view = apply_numeric_filters(view, numeric_filters)

    metric_cols = st.columns(6)
    metric_cols[0].metric("筛选结果", f"{len(view):,}")
    metric_cols[1].metric("赛道", f"{view['track'].nunique() if 'track' in view else 0:,}")
    metric_cols[2].metric("赛道覆盖", f"{len(view['track'].dropna().unique()) if 'track' in view else 0:,}")
    metric_cols[3].metric("代码覆盖", f"{view['stock_code'].nunique() if 'stock_code' in view else 0:,}")
    safety_col = "safety_margin_pct" if "safety_margin_pct" in view else "dcf_current_safety_margin_pct"
    metric_cols[4].metric("平均安全边际", f"{view[safety_col].mean():.1f}%" if safety_col in view else "NA")
    metric_cols[5].metric("平均ROIC", f"{view['roic_pct'].mean():.1f}%" if "roic_pct" in view else "NA")

    page_view, page_meta = paginate_view(view, key_prefix="universe")
    render_universe_table(page_view, page_meta, view)


def render_universe_filters(master: pd.DataFrame) -> dict[str, Any]:
    dates = pd.to_datetime(master["date"], errors="coerce") if "date" in master else pd.Series(dtype="datetime64[ns]")
    default_date = dates.max() if not dates.dropna().empty else pd.Timestamp.today()
    row1 = st.columns([0.9, 1.0, 1.1, 1.0, 1.2, 1.2, 1.2])
    selected_date = row1[0].date_input("日期", value=default_date)
    code = row1[1].text_input("代码", placeholder="股票代码")
    name = row1[2].text_input("名称", placeholder="股票名称")
    track = row1[3].selectbox(
        "赛道",
        filter_options(master, "track"),
        index=None,
        placeholder="选择或输入赛道",
        accept_new_options=True,
    )
    concept = row1[4].selectbox(
        "概念标注",
        filter_options(master, "concept_tag"),
        index=None,
        placeholder="选择或输入概念",
        accept_new_options=True,
    )
    sw_l2 = row1[5].selectbox(
        "申万2级行业",
        filter_options(master, "sw_l2"),
        index=None,
        placeholder="选择或输入Wind2级行业",
        accept_new_options=True,
    )
    sw_l3 = row1[6].selectbox(
        "申万3级行业",
        filter_options(master, "sw_l3"),
        index=None,
        placeholder="选择或输入Wind3级行业",
        accept_new_options=True,
    )

    row2 = st.columns([1.7, 0.7, 1.4])
    market_name = row2[0].radio("市场", list(MARKET_OPTIONS.keys()), horizontal=True, index=1)
    mark_filter = row2[1].selectbox("标记", ["全部", "仅标记", "未标记"], index=0)
    search = row2[2].text_input("搜索", placeholder="任意关键词")
    numeric_filters = render_numeric_filters(master)
    return {
        "date": selected_date,
        "code": code,
        "name": name,
        "track": normalize_filter_value(track),
        "note": "",
        "concept": normalize_filter_value(concept),
        "sw_l2": normalize_filter_value(sw_l2),
        "sw_l3": normalize_filter_value(sw_l3),
        "market_name": market_name,
        "search": search,
        "mark_filter": mark_filter,
        "numeric_filters": numeric_filters,
    }


def render_numeric_filters(master: pd.DataFrame) -> list[dict[str, Any]]:
    options = numeric_filter_options(master)
    if not options:
        return []
    filters: list[dict[str, Any]] = []
    invalid_inputs: list[str] = []
    with st.expander("数值筛选", expanded=True):
        for index in range(NUMERIC_FILTER_SLOTS):
            label_visibility = "visible" if index == 0 else "collapsed"
            columns = st.columns([1.4, 1.0, 1.0])
            selected_column = columns[0].selectbox(
                "字段",
                options,
                index=None,
                key=f"numeric_filter_column_{index}",
                format_func=lambda column: DISPLAY_COLUMNS.get(column, column),
                placeholder="选择数值列",
                label_visibility=label_visibility,
            )
            min_text = columns[1].text_input(
                "大于等于",
                key=f"numeric_filter_min_{index}",
                placeholder="下限",
                label_visibility=label_visibility,
            )
            max_text = columns[2].text_input(
                "小于等于",
                key=f"numeric_filter_max_{index}",
                placeholder="上限",
                label_visibility=label_visibility,
            )
            if not selected_column:
                continue
            min_value, min_valid = parse_numeric_filter_input(min_text)
            max_value, max_valid = parse_numeric_filter_input(max_text)
            label = DISPLAY_COLUMNS.get(selected_column, selected_column)
            if not min_valid:
                invalid_inputs.append(f"{label} 下限")
            if not max_valid:
                invalid_inputs.append(f"{label} 上限")
            if min_valid and max_valid and (min_value is not None or max_value is not None):
                filters.append({"column": selected_column, "min_value": min_value, "max_value": max_value})
        if invalid_inputs:
            st.warning("已忽略无法识别的数值输入：" + "、".join(invalid_inputs))
        action_columns = st.columns([0.7, 2.3])
        action_columns[0].button("应用筛选", key="numeric_filter_apply", width="stretch")
    return filters


def numeric_filter_options(frame: pd.DataFrame) -> list[str]:
    options: list[str] = []
    for column in NUMERIC_FILTER_COLUMNS:
        if column not in frame:
            continue
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.notna().any():
            options.append(column)
    return options


def parse_numeric_filter_input(value: Any) -> tuple[float | None, bool]:
    if value is None:
        return None, True
    text = str(value).strip().replace(",", "").replace("，", "")
    if not text:
        return None, True
    try:
        return float(text), True
    except ValueError:
        return None, False


def filter_options(frame: pd.DataFrame, column: str) -> list[str]:
    if column not in frame:
        return []
    values = frame[column].dropna().astype(str).str.strip()
    values = values[values.ne("")]
    return sorted(values.unique().tolist())


def normalize_filter_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def apply_marker_filter(frame: pd.DataFrame, mark_filter: str) -> pd.DataFrame:
    if frame.empty or "marked" not in frame or mark_filter == "全部":
        return frame
    marked = frame["marked"].fillna(False).astype(bool)
    if mark_filter == "仅标记":
        return frame[marked].reset_index(drop=True)
    if mark_filter == "未标记":
        return frame[~marked].reset_index(drop=True)
    return frame


def render_universe_table(page_view: pd.DataFrame, page_meta: dict[str, int], full_view: pd.DataFrame) -> None:
    display = add_marker_display_column(format_master_table(page_view), page_view)
    st.markdown(
        f'<div class="dense-note">当前渲染第 {page_meta["start"]}-{page_meta["end"]} 行 / 共 {page_meta["total"]} 行；导出包含全部筛选结果。</div>',
        unsafe_allow_html=True,
    )
    edited = st.data_editor(
        display,
        width="stretch",
        hide_index=True,
        height=470,
        key=marker_editor_key(page_view),
        num_rows="fixed",
        disabled=[column for column in display.columns if column != MARKED_DISPLAY_COLUMN],
        column_config=table_column_config(display),
    )
    action_cols = st.columns([0.9, 1.2, 0.75, 4.15])
    with action_cols[0]:
        if st.button("保存标记", key=f"marker_save:{marker_editor_key(page_view)}", width="stretch"):
            if save_marker_edits(edited):
                st.success("已保存本地标记")
            else:
                st.info("当前页标记无变更")
    with action_cols[1]:
        if st.button("清空当前页标记", key=f"marker_clear:{marker_editor_key(page_view)}", width="stretch"):
            if clear_page_markers(edited):
                st.success("已清空当前页标记")
            else:
                st.info("当前页没有本地标记可清空")
    with action_cols[2]:
        st.download_button(
            "导出",
            data=full_view.to_csv(index=False).encode("utf-8-sig"),
            file_name="research_universe_filtered.csv",
            mime="text/csv",
            width="stretch",
        )


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
    chart_name = controls[0].selectbox("图形", list(SCATTER_SPECS.keys()), help=scatter_formula_help())
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
    raw_candidate_count = len(scatter_source)
    effective_chart_name, scatter, missing, spec, fallback_from = choose_scatter_chart(scatter_source, chart_name)
    if fallback_from:
        st.info(
            f"当前筛选下 `{fallback_from}` 没有可用样本，已临时显示 `{effective_chart_name}`。"
            "银行/金融股通常没有可比 ROIC，用 ROE/PB 更合适。"
        )
    if missing or scatter.empty:
        if missing:
            st.warning(f"当前数据缺少字段：{', '.join(missing)}")
        else:
            st.warning(
                f"当前筛选下有 {raw_candidate_count:,} 只候选股票，但 `{chart_name}` 所需字段没有可用值。"
                "请切换图形，或先确认本地 peer_metrics 数据字段。"
            )
        st.dataframe(scatter_chart_availability(scatter_source), use_container_width=True, hide_index=True, height=220)
        return
    candidate_count = len(scatter)
    scatter = select_scatter_points(scatter, spec, max_points=max_points, mode=SCATTER_SORT_OPTIONS[sort_label])
    display_controls[2].markdown(
        f'<div class="dense-note">筛选后 {raw_candidate_count:,} 只，可用于本图 {candidate_count:,} 只，图中显示 {len(scatter):,} 只。先用筛选缩小赛道，再看排序后的代表样本。</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="dense-note">公式：{SCATTER_FORMULAS.get(effective_chart_name, "")}</div>',
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
        title=dict(text=effective_chart_name, font=dict(color=PALETTE["ink"], size=20)),
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
    extra = [col for col in frame.columns if col not in columns and col not in {"market", "broad_index", "marked"}]
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
