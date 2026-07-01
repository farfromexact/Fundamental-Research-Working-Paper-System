# 调研-研报影响力-一致预期兑现评分系统

本项目实现一个周频 A 股评分与回测框架，目标是预测下一报告期业绩兑现程度，而不是直接预测股价。

数据分工：

- 大智慧 DataApi：调研记录、研报、负面新闻、公告、附件下载证据。
- iFinD：A 股样本、行业、结构化一致预期、财报实际值、披露日期。

凭据只从环境变量读取，不写入配置或代码：

```powershell
$env:DZH_API_KEY="<your dataapi key>"
$env:IFIND_USERNAME="<your ifind username>"
$env:IFIND_PASSWORD="<your ifind password>"
```

## 快速运行

打开 Streamlit 底稿工作台：

```powershell
python -m streamlit run app.py
```

页面默认优先读取 `data/ifind_workbench/` 下的 iFinD 全 A 本地缓存；没有缓存时才回落到 `data/templates/` 示例模板：

- `research_universe_template.csv`：股票池、标签、行业、赛道、名单。
- `valuation_inputs_template.csv`：DCF 参数、股本、市值、现金、债务。
- `financial_history_template.csv`：历史财务参考数据。
- `peer_metrics_template.csv`：ROIC、安全边际、收益/风险散点图字段。

刷新全市场 A 股底稿缓存：

```powershell
$env:IFIND_USERNAME="<your ifind username>"
$env:IFIND_PASSWORD="<your ifind password>"
python -m earnings_signal.ifind_workbench --root . --max-mb 95
```

刷新后会生成：

- `data/ifind_workbench/research_universe.parquet`
- `data/ifind_workbench/valuation_inputs.parquet`
- `data/ifind_workbench/financial_history.parquet`
- `data/ifind_workbench/peer_metrics.parquet`
- `data/ifind_workbench/manifest.json`

这些文件使用 parquet 压缩保存，并由 `--max-mb` 做体积上限检查，默认控制在 95MB 以内，便于之后上传 GitHub。不要保存 iFinD 原始大 JSON 或多年日频明细到仓库。

离线跑一个端到端 demo：

```powershell
python -m earnings_signal.cli demo --out output/demo
```

拉取单股票大智慧事件数据：

```powershell
python -m earnings_signal.cli fetch-dzh --stock 300750 --start 2024-01-01 --end 2026-07-01 --out data/raw/dzh/300750
```

用本地文件生成评分：

```powershell
python -m earnings_signal.cli score `
  --score-frame data/score_frame.csv `
  --research data/raw/dzh/300750/research.json `
  --iractivity data/raw/dzh/300750/iractivity.json `
  --negative data/raw/dzh/300750/negative.json `
  --consensus data/ifind/consensus.csv `
  --out output/scores.csv
```

回测业绩兑现：

```powershell
python -m earnings_signal.cli backtest `
  --scores output/scores.csv `
  --forecasts data/ifind/forecasts.csv `
  --actuals data/ifind/actuals.csv `
  --out output/backtest
```

## 核心字段约定

评分基准表 `score_frame` 至少需要：

- `stock_code`
- `score_date`
- `industry`

iFinD 一致预期历史表至少需要：

- `stock_code`
- `forecast_date`
- `period_end`
- `consensus_net_profit`
- 可选：`consensus_revenue`, `consensus_eps`, `analyst_count`, `forecast_std`

财报实际值表至少需要：

- `stock_code`
- `period_end`
- `announce_date`
- `actual_net_profit`
- 可选：`actual_revenue`, `actual_eps`

## 设计原则

- 所有事件特征只统计 `event_date <= score_date`。
- 一致预期只使用 `forecast_date <= score_date` 的快照。
- 标签使用 `announce_date > score_date` 的下一报告期实际披露。
- 评分先做行业内标准化，再合成总分，避免大市值热门行业天然占优。
