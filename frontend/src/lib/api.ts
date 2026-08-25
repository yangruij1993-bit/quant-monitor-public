import {
  RefreshResponse, SummaryStat, RollingResponse,
  MatrixResponse, AnomalySignal, InsightResponse,
  FrontierRequest, FrontierResponse, PortfolioPoint,
  PortfolioStatsRequest, SignalOverview, SignalDetail,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8012/api/v1/analysis";
const FRONTIER_BASE = API_BASE.replace("/analysis", "/frontier");
const SIGNALS_BASE = API_BASE.replace("/analysis", "/signals");

export type AssetGroup =
  | "all" | "us_equities" | "us_fixed_income" | "commodities_alts"
  | "us_sectors" | "a_share_equities" | "a_share_industries"
  | "a_share_fixed_income" | "china_commodities" | "cross_asset_macro";
export type Sensitivity = "fast" | "standard" | "smooth";

export async function refreshData(): Promise<RefreshResponse> {
  const res = await fetch(`${API_BASE}/refresh`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to refresh data");
  return res.json();
}

export async function fetchSummary(group: AssetGroup = "all"): Promise<SummaryStat[]> {
  const res = await fetch(`${API_BASE}/summary?group=${group}`);
  if (!res.ok) throw new Error("Failed to fetch summary");
  return res.json();
}

export async function fetchRollingCorrelation(sensitivity: Sensitivity = "standard", group: AssetGroup = "all"): Promise<RollingResponse> {
  const res = await fetch(`${API_BASE}/rolling/correlation?sensitivity=${sensitivity}&group=${group}`);
  if (!res.ok) throw new Error("Failed to fetch rolling correlation");
  return res.json();
}

export async function fetchRollingVolatility(sensitivity: Sensitivity = "standard", group: AssetGroup = "all"): Promise<RollingResponse> {
  const res = await fetch(`${API_BASE}/rolling/volatility?sensitivity=${sensitivity}&group=${group}`);
  if (!res.ok) throw new Error("Failed to fetch rolling volatility");
  return res.json();
}

export async function fetchRecentMatrix(sensitivity: Sensitivity = "standard", group: AssetGroup = "all"): Promise<MatrixResponse> {
  const res = await fetch(`${API_BASE}/correlation/matrix/recent?sensitivity=${sensitivity}&group=${group}`);
  if (!res.ok) throw new Error("Failed to fetch recent matrix");
  return res.json();
}

export async function fetchLongTermMatrix(sensitivity: Sensitivity = "standard", group: AssetGroup = "all"): Promise<MatrixResponse> {
  const res = await fetch(`${API_BASE}/correlation/matrix/long-term?sensitivity=${sensitivity}&group=${group}`);
  if (!res.ok) throw new Error("Failed to fetch long term matrix");
  return res.json();
}

export async function fetchStaticRecentMatrix(group: AssetGroup = "all"): Promise<MatrixResponse> {
  const res = await fetch(`${API_BASE}/correlation/matrix/static-recent?group=${group}`);
  if (!res.ok) throw new Error("Failed to fetch static recent matrix");
  return res.json();
}

export async function fetchStaticAllMatrix(group: AssetGroup = "all"): Promise<MatrixResponse> {
  const res = await fetch(`${API_BASE}/correlation/matrix/static-all?group=${group}`);
  if (!res.ok) throw new Error("Failed to fetch static all matrix");
  return res.json();
}

export async function fetchAnomalies(sensitivity: Sensitivity = "standard", group: AssetGroup = "all"): Promise<AnomalySignal[]> {
  const res = await fetch(`${API_BASE}/anomalies?sensitivity=${sensitivity}&group=${group}`);
  if (!res.ok) throw new Error("Failed to fetch anomalies");
  return res.json();
}

export async function fetchInsights(sensitivity: Sensitivity = "standard", group: AssetGroup = "all"): Promise<InsightResponse> {
  const res = await fetch(`${API_BASE}/insights?sensitivity=${sensitivity}&group=${group}`);
  if (!res.ok) throw new Error("Failed to fetch insights");
  return res.json();
}

export async function computeFrontier(req: FrontierRequest): Promise<FrontierResponse> {
  const res = await fetch(`${FRONTIER_BASE}/compute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req)
  });
  if (!res.ok) throw new Error("Failed to compute efficient frontier");
  return res.json();
}

export async function fetchPortfolioStats(req: PortfolioStatsRequest): Promise<PortfolioPoint> {
  const res = await fetch(`${FRONTIER_BASE}/portfolio-stats`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req)
  });
  if (!res.ok) throw new Error("Failed to compute portfolio stats");
  return res.json();
}

// Strategy Signals API
export async function fetchSignalOverviews(): Promise<SignalOverview[]> {
  const res = await fetch(`${SIGNALS_BASE}/overview`);
  if (!res.ok) throw new Error("Failed to fetch signal overviews");
  return res.json();
}

export async function fetchSignalDetail(strategyId: string): Promise<SignalDetail> {
  const res = await fetch(`${SIGNALS_BASE}/detail/${strategyId}`);
  if (!res.ok) throw new Error(`Failed to fetch signal detail for ${strategyId}`);
  return res.json();
}

export async function fetchSignalOverview(strategyId: string): Promise<SignalOverview> {
  const res = await fetch(`${SIGNALS_BASE}/overview/${strategyId}`);
  if (!res.ok) throw new Error(`Failed to fetch signal overview for ${strategyId}`);
  return res.json();
}

export async function fetchNavCurve(strategyId: string): Promise<import("./types").NavCurve> {
  const res = await fetch(`${SIGNALS_BASE}/nav/${strategyId}`);
  if (!res.ok) {
    let message = `Failed to fetch NAV curve for ${strategyId}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string" && body.detail) message = body.detail;
    } catch { /* keep generic message */ }
    throw new Error(message);
  }
  return res.json();
}

export async function fetchSignalMetrics(strategyId: string): Promise<import("./types").BacktestMetrics> {
  const res = await fetch(`${SIGNALS_BASE}/metrics/${strategyId}`);
  if (!res.ok) throw new Error(`Failed to fetch metrics for ${strategyId}`);
  return res.json();
}

export async function fetchSignalHistory(strategyId: string, limit = 30): Promise<import("./types").SignalHistoryItem[]> {
  const res = await fetch(`${SIGNALS_BASE}/history/${strategyId}?limit=${limit}`);
  if (!res.ok) throw new Error(`Failed to fetch signal history for ${strategyId}`);
  return res.json();
}

export async function fetchWindowBacktest(
  strategyId: string, startDate: string, endDate?: string
): Promise<{ metrics: import("./types").BacktestMetrics; nav: import("./types").NavCurve }> {
  const params = new URLSearchParams({ start_date: startDate });
  if (endDate) params.set("end_date", endDate);
  const res = await fetch(`${SIGNALS_BASE}/backtest/${strategyId}?${params}`);
  if (!res.ok) {
    let message = `Failed to fetch window backtest for ${strategyId}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string" && body.detail) message = body.detail;
    } catch { /* keep generic message */ }
    throw new Error(message);
  }
  return res.json();
}
