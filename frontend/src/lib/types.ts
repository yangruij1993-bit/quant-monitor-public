export interface RefreshResponse {
  status: string;
  message: string;
  last_date: string;
}

export interface SummaryStat {
  ticker: string;
  cagr_ytd: number | null;
  cagr_1y: number | null;
  cagr_3y: number | null;
  cagr_5y: number | null;
  cagr_all: number | null;
  vol_all: number | null;
  max_dd_all: number | null;
}

export interface TimeSeriesPoint {
  date: string;
  value: number;
}

export interface RollingResponse {
  sensitivity: string;
  data: Record<string, TimeSeriesPoint[]>;
}

export interface MatrixResponse {
  tickers: string[];
  matrix: number[][];
}

export interface AnomalySignal {
  pair: string;
  current_corr: number;
  mean_corr: number;
  std_corr: number;
  z_score: number;
  signal: string;
}

export interface InsightResponse {
  regime_notes: string[];
  allocation_suggestions: string[];
}

export interface FrontierRequest {
  tickers: string[];
  mu: number[];
  sigma: number[];
  rf?: number;
  allowShort?: boolean;
  nPoints?: number;
}

export interface PortfolioPoint {
  weights: number[];
  ret: number;
  vol: number;
  sharpe: number;
}

export interface AssetPoints {
  tickers: string[];
  vol: number[];
  ret: number[];
}

export interface FrontierResponse {
  efPoints: PortfolioPoint[];
  maxSharpe: PortfolioPoint | null;
  minVol: PortfolioPoint | null;
  assetPoints: AssetPoints;
  warnings: string[];
}

export interface PortfolioStatsRequest {
  tickers: string[];
  mu: number[];
  sigma: number[];
  weights: number[];
  rf: number;
}

// Strategy Signal types
export interface HoldingsItem {
  ticker: string;
  name: string;
  weight: number;
}

export interface SignalOverview {
  strategy_id: string;
  strategy_name: string;
  signal_date: string;
  holdings: HoldingsItem[];
  signal_detail: Record<string, unknown>;
  updated_at: string | null;
}

export interface BacktestMetrics {
  annual_return: number;
  max_drawdown: number;
  sharpe_ratio: number;
  win_rate: number;
  annual_volatility: number | null;
  turnover: number | null;
  period_start: string;
  period_end: string;
  absolute_return?: number | null;
  // ── PMS extended metrics (populated when nav/benchmark data allows) ──
  relative_return?: number | null;
  relative_return_geometric?: number | null;
  weekly_return?: number | null;
  monthly_return?: number | null;
  quarterly_return?: number | null;
  ytd_return?: number | null;
  alpha?: number | null;
  beta?: number | null;
  tracking_error?: number | null;
  annual_tracking_error?: number | null;
  information_ratio?: number | null;
  daily_win_rate?: number | null;
  weekly_win_rate?: number | null;
  monthly_win_rate?: number | null;
  calmar?: number | null;
  avg_holding_days?: number | null;
}

export interface SignalDetail {
  strategy_id: string;
  strategy_name: string;
  signal_date: string;
  holdings: HoldingsItem[];
  signal_detail: Record<string, unknown>;
  nav_latest: number | null;
  metrics: BacktestMetrics | null;
  updated_at: string | null;
}

export interface NavCurve {
  strategy_id: string;
  dates: string[];
  nav: number[];
  benchmark_nav: number[] | null;
  benchmark_name: string | null;
  excess_nav: number[] | null;
  excess_name: string | null;
}

export interface SignalHistoryItem {
  date: string;
  action: string;
  detail: Record<string, unknown>;
}
