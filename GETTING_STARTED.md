# 上手指南

这个项目是资产监控和策略信号展示框架，不内置假策略、假净值或示例行情数据。拿到仓库后，需要接入自己的行情数据源和策略输出。

## 1. 准备环境

需要本地具备：

- Python 3.11 或 3.12
- Node.js 18+
- PostgreSQL
- Tushare token，用于 A 股 ETF 行情

美股 ETF 可以通过 `yfinance` 拉取。Oracle 和 Doris 是可选数据源，未配置时不会阻塞基础运行。

## 2. 初始化数据库

```sql
CREATE DATABASE asset_monitor;
CREATE USER assetmon WITH PASSWORD 'assetmon';
GRANT ALL PRIVILEGES ON DATABASE asset_monitor TO assetmon;
```

如果你使用自己的数据库用户或云数据库，把连接串写入 `backend/.env` 的 `DATABASE_URL`。

## 3. 配置后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
```

编辑 `backend/.env`：

```bash
TUSHARE_TOKEN=你的_tushare_token
DATABASE_URL=postgresql://assetmon:assetmon@localhost:5432/asset_monitor
STRATEGY_DIR=../strategies
CORS_ORIGINS=*
```

第一次启动时，后端会按资产配置拉取行情，写入 PostgreSQL，并生成本地 CSV 缓存。没有配置 Tushare 时，A 股相关资产不会有完整数据。

## 4. 安装前端

```bash
cd ../frontend
npm install
```

## 5. 启动系统

在项目根目录运行：

```bash
chmod +x start.sh
./start.sh
```

默认地址：

- 前端：`http://localhost:3012`
- 后端：`http://localhost:8012`
- 健康检查：`http://localhost:8012/api/v1/health`

策略信号页默认会显示一个 `_demo` 示例策略（带 Demo 徽章）让你看到 UI 长什么样。删除 `strategies/_demo/` 后页面就空了——这是正常的，系统不会生成假策略数据。

## 6. 接入自己的策略

你的策略脚本只需要在运行结束后写出一个 JSON 文件：

```text
strategies/                  ← 项目根目录
  your-strategy-id/
    signal_latest.json
```

`signal_latest.json` 的最小格式：

```json
{
  "strategy_id": "your-strategy-id",
  "strategy_name": "Your Strategy Name",
  "signal_date": "2026-06-13",
  "holdings": [
    {"ticker": "SPY", "name": "S&P 500 ETF", "weight": 0.6},
    {"ticker": "TLT", "name": "20+ Year Treasury ETF", "weight": 0.4}
  ],
  "signal_detail": {
    "signal": "hold",
    "reason": "your strategy output"
  }
}
```

可选字段包括 `nav`、`metrics` 和 `signal_history.jsonl`，详见 [STRATEGIES.md](STRATEGIES.md)。

## 7. 自动更新

本项目不假设你的策略如何生成信号。常见做法是：

```bash
python your_strategy.py
```

让你的脚本把最新结果写到：

```text
strategies/your-strategy-id/signal_latest.json
```

然后用 crontab、GitHub Actions、Airflow 或你自己的调度器定时运行策略脚本。前端刷新后会读取最新 JSON。

## 8. 常见检查

后端是否可用：

```bash
curl http://localhost:8012/api/v1/health
```

策略是否被识别：

```bash
curl http://localhost:8012/api/v1/signals/overview
```

行情数据是否拉取成功：

```bash
ls backend/cache/prices.csv
```

如果 `prices.csv` 不存在，先检查 `TUSHARE_TOKEN`、网络、PostgreSQL 连接，以及后端启动日志。
