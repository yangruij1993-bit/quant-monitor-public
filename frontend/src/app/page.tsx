"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import SummaryTable from "@/components/SummaryTable";
import CorrelationHeatmap from "@/components/CorrelationHeatmap";
import RollingTimeSeries from "@/components/RollingTimeSeries";
import AnomalySignals from "@/components/AnomalySignals";
import InsightsPanel from "@/components/InsightsPanel";
import ForwardTable, { AssetRow } from "@/components/ForwardTable";
import FrontierPlot from "@/components/FrontierPlot";
import CustomPortfolio from "@/components/CustomPortfolio";
import StrategySignals from "@/components/StrategySignals";

function filterMatrix(
  resp: MatrixResponse | null,
  tickers: string[]
): MatrixResponse | null {
  if (!resp) return null;
  const indexSet = new Set(tickers);
  const indices = resp.tickers
    .map((t, i) => (indexSet.has(t) ? i : -1))
    .filter(i => i >= 0);
  if (indices.length === 0) return null;
  return {
    tickers: indices.map(i => resp.tickers[i]),
    matrix: indices.map(i => indices.map(j => resp.matrix[i][j])),
  };
}
import { Activity, GitBranch, RefreshCcw, TrendingUp, Globe, BarChart3, Banknote, Package, Zap } from "lucide-react";
import clsx from "clsx";
import {
  fetchSummary, fetchRecentMatrix, fetchLongTermMatrix,
  fetchStaticRecentMatrix, fetchStaticAllMatrix,
  fetchRollingCorrelation, fetchRollingVolatility,
  fetchAnomalies, fetchInsights, refreshData, computeFrontier,
  fetchPortfolioStats,
  AssetGroup, Sensitivity
} from "@/lib/api";

async function withStartupTimeout<T>(promise: Promise<T>, timeoutMs = 60000): Promise<T> {
  let timeoutId: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<never>((_, reject) => {
    timeoutId = setTimeout(() => {
      reject(new Error("Backend startup timeout"));
    }, timeoutMs);
  });

  try {
    return await Promise.race([promise, timeout]);
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
  }
}

import {
  SummaryStat, MatrixResponse, RollingResponse,
  AnomalySignal, InsightResponse, FrontierResponse
} from "@/lib/types";

type Tab = "overview" | "rolling" | "signals";
type ViewMode = "monitor" | "frontier" | "signals";

interface GroupConfig {
  id: AssetGroup;
  label: string;
  icon: React.ReactNode;
}

const GROUPS: GroupConfig[] = [
  { id: "all" as AssetGroup, label: "All Assets", icon: <Globe size={16} /> },
  { id: "us_equities" as AssetGroup, label: "US Equities", icon: <TrendingUp size={16} /> },
  { id: "us_fixed_income" as AssetGroup, label: "US Fixed Income", icon: <Banknote size={16} /> },
  { id: "commodities_alts" as AssetGroup, label: "Commodities & Alts", icon: <Package size={16} /> },
  { id: "us_sectors" as AssetGroup, label: "US Sectors", icon: <BarChart3 size={16} /> },
  { id: "a_share_equities" as AssetGroup, label: "A-Share Equities", icon: <TrendingUp size={16} /> },
  { id: "a_share_industries" as AssetGroup, label: "A-Share Industries", icon: <BarChart3 size={16} /> },
  { id: "a_share_fixed_income" as AssetGroup, label: "A-Share Fixed Income", icon: <Banknote size={16} /> },
  { id: "china_commodities" as AssetGroup, label: "China Commodities", icon: <Package size={16} /> },
  { id: "cross_asset_macro" as AssetGroup, label: "Cross-Asset Macro", icon: <Globe size={16} /> },
];

export default function Dashboard() {
  const [viewMode, setViewMode] = useState<ViewMode>("monitor");
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [activeGroup, setActiveGroup] = useState<AssetGroup>("all");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [sensitivity, setSensitivity] = useState<Sensitivity>("standard");
  const [selectedTickers, setSelectedTickers] = useState<string[]>([]);

  const [rfRate, setRfRate] = useState(4.5);
  const [allowShort, setAllowShort] = useState(false);
  const [forwardRows, setForwardRows] = useState<AssetRow[]>([]);
  const [frontierData, setFrontierData] = useState<FrontierResponse | null>(null);
  const [computingFrontier, setComputingFrontier] = useState(false);
  const [usingSavedDefaults, setUsingSavedDefaults] = useState(false);
  const [customPortfolio, setCustomPortfolio] = useState<{
    ret: number; vol: number; sharpe: number; weights: Record<string, number>;
  } | null>(null);
  const [computingCustom, setComputingCustom] = useState(false);

  const [loadError, setLoadError] = useState<string | null>(null);

  const [data, setData] = useState<{
    summary: SummaryStat[];
    recentMatrix: MatrixResponse | null;
    longTermMatrix: MatrixResponse | null;
    staticRecentMatrix: MatrixResponse | null;
    staticAllMatrix: MatrixResponse | null;
    rollingCorr: RollingResponse | null;
    rollingVol: RollingResponse | null;
    anomalies: AnomalySignal[];
    insights: InsightResponse | null;
  }>({
    summary: [],
    recentMatrix: null,
    longTermMatrix: null,
    staticRecentMatrix: null,
    staticAllMatrix: null,
    rollingCorr: null,
    rollingVol: null,
    anomalies: [],
    insights: null
  });

  // Track the latest params to ignore stale Promise resolves
  const loadedRef = useRef({ group: activeGroup, sensitivity });

  const loadData = useCallback(async () => {
    const group = activeGroup;
    const sens = sensitivity;
    loadedRef.current = { group, sensitivity: sens };
    setLoading(true);
    setLoadError(null);
    try {
      const [sum, rec, lng, sRec, sAll, rCorr, rVol, anom, ins] = await withStartupTimeout(Promise.all([
        fetchSummary(group),
        fetchRecentMatrix("fast", group),
        fetchLongTermMatrix("smooth", group),
        fetchStaticRecentMatrix(group),
        fetchStaticAllMatrix(group),
        fetchRollingCorrelation(sens, group),
        fetchRollingVolatility(sens, group),
        fetchAnomalies(sens, group),
        fetchInsights(sens, group)
      ]));

      // Ignore stale responses from previous group/sensitivity
      const current = loadedRef.current;
      if (current.group !== group || current.sensitivity !== sens) return;

      // Reset ticker selection when group changes
      const groupTickers = sum.map(s => s.ticker);
      setSelectedTickers(prev => {
        const prevSet = new Set(prev);
        const allMatch = groupTickers.length === prev.length && groupTickers.every(t => prevSet.has(t));
        return allMatch ? prev : groupTickers;
      });

      setData({
        summary: sum,
        recentMatrix: rec,
        longTermMatrix: lng,
        staticRecentMatrix: sRec,
        staticAllMatrix: sAll,
        rollingCorr: rCorr,
        rollingVol: rVol,
        anomalies: anom,
        insights: ins
      });
    } catch (error) {
      console.error("Failed to load data:", error);
      setLoadError("后端正在启动或暂时不可用");
    } finally {
      const current = loadedRef.current;
      if (current.group === group && current.sensitivity === sens) {
        setLoading(false);
      }
    }
  }, [activeGroup, sensitivity]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Sync forward rows when summary changes
  useEffect(() => {
    if (data.summary.length > 0 && viewMode === "frontier") {
      const savedDefaults = localStorage.getItem("frontierDefaults");
      if (savedDefaults) {
        try {
          const parsed = JSON.parse(savedDefaults);
          // Only use if the tickers match
          if (Array.isArray(parsed) && parsed.length === data.summary.length) {
            setForwardRows(parsed.map((r: AssetRow) => ({ ...r, include: false })));
            setUsingSavedDefaults(true);
            setFrontierData(null);
            return;
          }
        } catch (e) {
          console.error("Failed to parse saved defaults", e);
        }
      }

      setForwardRows(data.summary.map(s => ({
        ticker: s.ticker,
        name: s.ticker,
        include: false,
        mu: s.cagr_all !== null ? parseFloat((s.cagr_all * 100).toFixed(2)) : 5.0,
        sigma: s.vol_all !== null ? parseFloat((s.vol_all * 100).toFixed(2)) : 15.0,
      })));
      setUsingSavedDefaults(false);
      setFrontierData(null);
    }
  }, [data.summary, viewMode]);

  const handleSaveDefaults = () => {
    localStorage.setItem("frontierDefaults", JSON.stringify(forwardRows));
    setUsingSavedDefaults(true);
  };

  const handleAutoFill = () => {
    if (data.summary.length > 0) {
      setForwardRows(rows => rows.map(r => {
        const s = data.summary.find(x => x.ticker === r.ticker);
        return {
          ...r,
          mu: s?.cagr_all !== null && s?.cagr_all !== undefined ? parseFloat((s.cagr_all * 100).toFixed(2)) : r.mu,
          sigma: s?.vol_all !== null && s?.vol_all !== undefined ? parseFloat((s.vol_all * 100).toFixed(2)) : r.sigma,
        };
      }));
      setUsingSavedDefaults(false);
    }
  };

  const handleViewModeChange = (mode: ViewMode) => {
    setViewMode(mode);
    if (mode === "frontier") {
      setActiveGroup("all");
    } else if (mode === "signals") {
      // no group needed for signals
    } else {
      if (activeGroup === "all") setActiveGroup("us_equities");
    }
  };

  const handleComputeFrontier = async () => {
    const included = forwardRows.filter(r => r.include);
    if (included.length < 2) return;
    
    setComputingFrontier(true);
    setCustomPortfolio(null);
    try {
      const res = await computeFrontier({
        tickers: included.map(r => r.ticker),
        mu: included.map(r => r.mu / 100.0),
        sigma: included.map(r => r.sigma / 100.0),
        rf: rfRate / 100.0,
        allowShort,
        nPoints: 100
      });
      setFrontierData(res);
      
    } catch (error) {
      console.error("Failed to compute frontier:", error);
    } finally {
      setComputingFrontier(false);
    }
  };

  const handlePlotCustomPortfolio = async (weights: Record<string, number>) => {
    const included = forwardRows.filter(r => r.include);
    if (included.length < 2 || !frontierData) return;

    setComputingCustom(true);
    try {
      const tickers = included.map(r => r.ticker);
      const res = await fetchPortfolioStats({
        tickers,
        mu: included.map(r => r.mu / 100.0),
        sigma: included.map(r => r.sigma / 100.0),
        weights: tickers.map(t => weights[t] ?? 0),
        rf: rfRate / 100.0,
      });
      const weightsMap: Record<string, number> = {};
      tickers.forEach((t, i) => { weightsMap[t] = res.weights[i]; });
      setCustomPortfolio({ ...res, weights: weightsMap });
    } catch (error) {
      console.error("Failed to compute portfolio stats:", error);
    } finally {
      setComputingCustom(false);
    }
  };

  const handleGroupChange = (group: AssetGroup) => {
    if (group !== activeGroup) {
      setActiveGroup(group);
      setActiveTab("overview");
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await refreshData();
      await loadData();
    } catch (error) {
      console.error("Refresh failed:", error);
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Top Nav Bar — Vercel style */}
      <nav className="sticky top-0 z-50 border-b border-border bg-background/80 backdrop-blur-md">
        <div className="max-w-[1400px] mx-auto flex items-center justify-between h-14 px-6">
          <div className="flex items-center gap-6">
            <h1 className="text-sm font-semibold tracking-tight text-ink flex items-center gap-2">
              <Activity size={16} className="text-accent" />
              Asset Monitor
            </h1>
            <div className="flex items-center gap-1">
              {[
                { id: "monitor", label: "Market Monitor", icon: Globe },
                { id: "frontier", label: "Efficient Frontier", icon: BarChart3 },
                { id: "signals", label: "Strategy Signals", icon: Zap },
              ].map((nav) => (
                <button
                  key={nav.id}
                  onClick={() => handleViewModeChange(nav.id as ViewMode)}
                  className={clsx(
                    "flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
                    viewMode === nav.id
                      ? "bg-surface-light text-ink"
                      : "text-body hover:text-ink"
                  )}
                >
                  <nav.icon size={13} />
                  {nav.label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 caption-mono text-mute">
              <span className="text-[11px]">Sensitivity</span>
              <select
                className="bg-surface border border-border rounded-sm text-ink text-xs py-1 px-2 outline-none cursor-pointer"
                value={sensitivity}
                onChange={(e) => setSensitivity(e.target.value as Sensitivity)}
              >
                <option value="fast">Fast</option>
                <option value="standard">Standard</option>
                <option value="smooth">Smooth</option>
              </select>
            </div>
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-ink text-background hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              <RefreshCcw size={12} className={clsx(refreshing && "animate-spin")} />
              {refreshing ? "Syncing" : "Update"}
            </button>
          </div>
        </div>
      </nav>

      <div className="max-w-[1400px] mx-auto px-6 py-6 space-y-6">
      {viewMode === "monitor" && (
        <>
          {/* Group pills */}
          <div className="flex items-center gap-1 overflow-x-auto pb-2">
            {GROUPS.map((g) => (
              <button
                key={g.id}
                onClick={() => handleGroupChange(g.id as AssetGroup)}
                className={clsx(
                  "flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-pill-sm whitespace-nowrap transition-colors",
                  activeGroup === g.id
                    ? "bg-surface-light text-ink border border-border"
                    : "text-body hover:text-ink"
                )}
              >
                {g.icon}
                {g.label}
              </button>
            ))}
          </div>

          {/* Sub tabs */}
          <div className="flex items-center gap-1 border-b border-border">
            {[
              { id: "overview", label: "Overview", icon: Activity },
              { id: "rolling", label: "Time Series", icon: TrendingUp },
              { id: "signals", label: "Insights & Signals", icon: GitBranch },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as Tab)}
                className={clsx(
                  "flex items-center gap-1.5 px-4 py-2.5 text-xs font-medium border-b-2 transition-colors -mb-px",
                  activeTab === tab.id
                    ? "border-accent text-ink"
                    : "border-transparent text-body hover:text-ink"
                )}
              >
                <tab.icon size={14} />
                {tab.label}
              </button>
            ))}
          </div>
        </>
      )}

      {/* Content */}
      <div className="min-h-[500px]">
        {loadError ? (
          <div className="flex flex-col items-center justify-center h-[300px] gap-4 text-center">
            <div>
              <h2 className="text-sm font-semibold text-white">{loadError}</h2>
              <p className="mt-2 text-xs text-gray-500">
                后端可能正在预热计算缓存。稍等片刻后重试。
              </p>
            </div>
            <button
              onClick={loadData}
              className="px-3 py-1.5 text-xs font-medium rounded-md bg-white text-gray-900 hover:opacity-90 transition-opacity"
            >
              重试
            </button>
          </div>
        ) : loading ? (
          <div className="flex justify-center items-center h-[300px]">
            <RefreshCcw className="animate-spin text-accent" size={32} />
          </div>
        ) : (
          <>
            {viewMode === "monitor" && activeTab === "overview" && (
              <div className="space-y-6">
                <SummaryTable
                  data={data.summary}
                  selected={selectedTickers}
                  onSelectionChange={setSelectedTickers}
                />
                <CorrelationHeatmap
                  recent={filterMatrix(data.recentMatrix, selectedTickers)}
                  longTerm={filterMatrix(data.longTermMatrix, selectedTickers)}
                  staticRecent={filterMatrix(data.staticRecentMatrix, selectedTickers)}
                  staticAll={filterMatrix(data.staticAllMatrix, selectedTickers)}
                />
              </div>
            )}

            {viewMode === "monitor" && activeTab === "rolling" && (
              <div className="space-y-6">
                <RollingTimeSeries
                  key={activeGroup}
                  corrData={data.rollingCorr}
                  volData={data.rollingVol}
                  tickers={selectedTickers.length > 0 ? selectedTickers : data.summary.map(s => s.ticker)}
                />
              </div>
            )}

            {viewMode === "monitor" && activeTab === "signals" && (
              <div className="space-y-6">
                <InsightsPanel insights={data.insights} />
                <AnomalySignals signals={data.anomalies} />
              </div>
            )}

            {viewMode === "frontier" && (
              <div className="space-y-6 mt-4">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  <div className="lg:col-span-1 space-y-6">
                    <ForwardTable
                      rows={forwardRows}
                      rfRate={rfRate}
                      allowShort={allowShort}
                      onRowsChange={setForwardRows}
                      onRfChange={setRfRate}
                      onAllowShortChange={setAllowShort}
                      onAutoFill={handleAutoFill}
                      onSaveDefaults={handleSaveDefaults}
                      onCompute={handleComputeFrontier}
                      computing={computingFrontier}
                      usingSavedDefaults={usingSavedDefaults}
                    />
                  </div>

                  <div className="lg:col-span-2 space-y-6">
                    <FrontierPlot
                      data={frontierData}
                      customPortfolio={customPortfolio}
                    />
                    {frontierData && (
                      <CustomPortfolio
                        tickers={forwardRows.filter(r => r.include).map(r => r.ticker)}
                        onPlot={handlePlotCustomPortfolio}
                        computing={computingCustom}
                      />
                    )}
                  </div>
                </div>
              </div>
            )}

            {viewMode === "signals" && (
              <StrategySignals />
            )}
          </>
        )}
      </div>
      </div>
    </div>
  );
}
