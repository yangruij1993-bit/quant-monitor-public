# 策略信号接入规范

## 快速开始

把自己的策略信号接入监控系统，只需要 **1 个 JSON 文件**。

### 1. 创建策略目录

```
strategies/
  my-strategy/
    signal_latest.json
```

目录名就是策略 ID（只能用小写字母、数字、`-`）。

### 2. 编写信号文件

`signal_latest.json` 格式：

```json
{
  "strategy_id": "my-strategy",
  "strategy_name": "我的动量策略",
  "signal_date": "2026-06-12",
  "holdings": [
    {"ticker": "510300.SH", "name": "沪深300", "weight": 0.6},
    {"ticker": "518880.SH", "name": "黄金", "weight": 0.4}
  ],
  "signal_detail": {
    "signal": "做多",
    "reason": "突破20日均线"
  }
}
```

**必填字段：**
- `strategy_id` — 跟目录名一致
- `strategy_name` — 显示名称
- `signal_date` — 信号日期（YYYY-MM-DD）
- `holdings` — 当前持仓列表，每项含 `ticker`、`name`、`weight`
- `signal_detail` — 任意 JSON 对象，前端会显示为 key-value 标签

**可选字段：**
- `nav` — 净值曲线数据：
  ```json
  "nav": {
    "dates": ["2026-01-02", "2026-01-03", "2026-01-06"],
    "values": [1.0, 1.005, 0.998],
    "benchmark_nav": [1.0, 1.002, 0.997],
    "benchmark_name": "沪深300"
  }
  ```
  `benchmark_nav`/`benchmark_name` 可选；提供后前端自动叠加基准曲线与累计超额曲线。
- `metrics` — 回测指标（**可选**）。若缺省且 `nav` 存在，后端自动计算 22 项 PMS 风格指标；若提供则优先后端透传。完整字段见下表（除前 5 项必填外均可选）。

  | 字段名 | 含义 |
  | --- | --- |
  | **必填字段** | |
  | period_start | 回测区间起始日期 |
  | period_end | 回测区间结束日期 |
  | annual_return | 年化收益率 |
  | max_drawdown | 最大回撤 |
  | sharpe_ratio | 夏普比率 |
  | **收益类** | |
  | absolute_return | 绝对收益 |
  | relative_return | 相对回报（算术） |
  | relative_return_geometric | 相对回报（几何） |
  | weekly_return | 周回报 |
  | monthly_return | 月回报 |
  | quarterly_return | 季回报 |
  | ytd_return | 年初至今回报 |
  | **风险类** | |
  | annual_volatility | 年化波动率 |
  | calmar | Calmar 比率 |
  | **相对基准类** | |
  | alpha | Alpha |
  | beta | Beta |
  | tracking_error | 跟踪误差（区间） |
  | annual_tracking_error | 跟踪误差（年化） |
  | information_ratio | 信息比率 |
  | daily_win_rate | 日胜率 |
  | weekly_win_rate | 周胜率 |
  | monthly_win_rate | 月胜率 |
  | **交易类** | |
  | turnover | 换手率（需 history 提供 holdings 快照） |
  | avg_holding_days | 平均持仓天数（需 history 提供 holdings 快照） |

### 3. 可选：历史记录

放一个 `signal_history.jsonl`（每行一个 JSON）：

```
{"date": "2026-06-10", "action": "买入", "detail": {"reason": "突破均线"}}
{"date": "2026-06-11", "action": "持有", "detail": {"reason": "趋势延续"}}
{"date": "2026-06-12", "action": "卖出", "detail": {"reason": "跌破均线"}}
```

每行可带 `holdings` 快照（可选）。≥2 个快照时后端自动计算换手率与平均持仓天数：

```
{"date": "2026-06-12", "action": "调仓", "detail": {...}, "holdings": [{"ticker": "510300.SH", "name": "沪深300", "weight": 0.6}]}
```

### 4. 配置目录路径

环境变量 `STRATEGY_DIR` 指向策略目录（`.env.example` 默认 `../strategies`，即项目根的 `strategies/`）：

```bash
# backend/.env
STRATEGY_DIR=../strategies
# 或绝对路径
STRATEGY_DIR=/path/to/your/strategies
```

### 5. 自动化

你的策略脚本跑完后，把最新的 JSON 写到 `signal_latest.json` 就行：

```bash
# 示例：策略脚本输出信号
python my_strategy.py > strategies/my-strategy/signal_latest.json
```

可以用 crontab 或任何调度器定时执行。

## 示例脚本

```python
#!/usr/bin/env python3
"""示例：简单的均线策略信号生成"""
import json
from datetime import date
from pathlib import Path

def generate_signal():
    # ... 你的策略逻辑 ...
    signal = {
        "strategy_id": "ma-crossover",
        "strategy_name": "均线交叉策略",
        "signal_date": str(date.today()),
        "holdings": [
            {"ticker": "510300.SH", "name": "沪深300", "weight": 0.8},
            {"ticker": "511010.SH", "name": "国债", "weight": 0.2},
        ],
        "signal_detail": {
            "ma5": 3900.5,
            "ma20": 3880.2,
            "signal": "金叉做多",
        },
    }
    out = Path("strategies/ma-crossover")
    out.mkdir(parents=True, exist_ok=True)
    (out / "signal_latest.json").write_text(
        json.dumps(signal, ensure_ascii=False, indent=2), encoding="utf-8"
    )

if __name__ == "__main__":
    generate_signal()
```

`strategies/_demo/generate_demo.py` 是生成完整 nav/history 契约数据的可运行参考。

## 目录结构总览

```
asset-monitor/
  strategies/                    ← STRATEGY_DIR
    ma-crossover/
      signal_latest.json         ← 必需
      signal_history.jsonl       ← 可选
    risk-parity/
      signal_latest.json
    momentum-timing/
      signal_latest.json
```

系统启动后自动扫描所有子目录，前端"策略信号"tab 动态显示所有已接入的策略。

## 窗口回测

策略详情页可选任意起止窗口重算指标（`GET /api/v1/signals/backtest/{id}?start_date=&end_date=`，end_date 可选默认到最后）。前端提供 全部/近3月/近1年/年初 预设与自定义日期。
