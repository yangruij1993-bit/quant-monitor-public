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
    "values": [1.0, 1.005, 0.998]
  }
  ```
- `metrics` — 回测指标：
  ```json
  "metrics": {
    "annual_return": 0.12,
    "max_drawdown": -0.08,
    "sharpe_ratio": 1.5,
    "win_rate": 0.55,
    "annual_volatility": 0.15,
    "turnover": 3.2,
    "period_start": "2024-01-02",
    "period_end": "2026-06-12"
  }
  ```

### 3. 可选：历史记录

放一个 `signal_history.jsonl`（每行一个 JSON）：

```
{"date": "2026-06-10", "action": "买入", "detail": {"reason": "突破均线"}}
{"date": "2026-06-11", "action": "持有", "detail": {"reason": "趋势延续"}}
{"date": "2026-06-12", "action": "卖出", "detail": {"reason": "跌破均线"}}
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
