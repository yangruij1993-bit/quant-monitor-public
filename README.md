# 资产配置监控

宏观经济资产配置与动态相关性监控平台。跟踪 **60+ 资产**（美股 ETF、美债、A股 ETF、大宗商品），使用 GARCH + Kalman Filter 计算动态相关性，检测异常信号（Z-Score），辅助组合配置决策。

## 技术架构

*   **后端**: Python, FastAPI, Pandas, Tushare, yfinance, PostgreSQL
*   **前端**: Next.js 14, React, Tailwind CSS, Recharts, Plotly.js（静态导出）
*   **数据**: A股 ETF 通过 Tushare，美股 ETF 通过 Oracle/yfinance，PostgreSQL 持久化，CSV 兜底

## 功能

*   **分组导航**: 两级 Tab — 4 个宏观资产分组，每组包含概览 / 时序图 / 洞察
*   **动态相关性（Kalman Filter）**: 用 GARCH(1,1) + 一维 Kalman Filter（随机游走）替代标准滚动窗口，消除"残影效应"，提供 3 档灵敏度（Fast / Standard / Smooth）
*   **有效前沿优化器**: 基于最新 Kalman 协方差矩阵的 Markowitz 均值-方差优化，支持最大夏普、最小波动、可编辑的前瞻预期，localStorage 持久化
*   **概览仪表盘**: 汇总统计（年化收益、波动率、最大回撤）和相关性热力图（Fast vs Smooth），按历史波动率排序
*   **滚动相关性时序图**: 选择一个基准资产，同时查看它与所有其他资产的动态相关性曲线
*   **异常信号**: 基于Z-Score的 ETF 配对偏离历史均值预警
*   **策略信号插件**: 在 `strategies/` 目录放一个 JSON 文件即可接入任意策略的信号、持仓和净值曲线，无需改后端代码。详见 [STRATEGIES.md](STRATEGIES.md)
*   **洞察面板**: 基于当前相关性自动生成市场状态分析和配置建议
*   **自定义提示框**: 悬停 ticker 显示完整资产名称（如 "BTC" → "Bitcoin (USD)"）

## 本地部署

### 1. 后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env  # 填入 TUSHARE_TOKEN 和 DATABASE_URL
```

PostgreSQL 初始化：

```sql
CREATE DATABASE asset_monitor;
CREATE USER assetmon WITH PASSWORD 'assetmon';
GRANT ALL PRIVILEGES ON DATABASE asset_monitor TO assetmon;
```

### 2. 前端

```bash
cd frontend
npm install
```

## 启动

同时启动前后端：

```bash
chmod +x start.sh
./start.sh
```

或分别启动：

**后端：**
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --port 8012
```

**前端：**
```bash
cd frontend
npm run dev -- -p 3012
```

打开 [http://localhost:3012](http://localhost:3012)。

## ngrok 分享

只需一个隧道 — 后端同时提供 API 和前端静态文件：

```bash
ngrok http 8012
# 获取 URL 如 https://xxxx.ngrok-free.app
cd frontend
NEXT_PUBLIC_API_URL=https://xxxx.ngrok-free.app/api/v1/analysis npx next build
# 重启后端即可 — 自动托管 frontend/out/ 静态文件
```
