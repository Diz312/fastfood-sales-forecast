"use client";

import { useEffect, useState, useCallback } from "react";
import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { api } from "@/lib/api";
import type { DailySale, ForecastRun, ForecastValue, Restaurant, SKU } from "@/types/api";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function statusColor(status: ForecastRun["status"]) {
  return {
    pending: "text-yellow-400",
    running: "text-blue-400",
    complete: "text-green-400",
    failed: "text-red-400",
  }[status];
}

function buildChartData(
  sales: DailySale[],
  forecast: ForecastValue[],
  skuId: string
) {
  const salesBySku = sales.filter((s) => s.sku_id === skuId);
  const forecastBySku = forecast.filter((f) => f.sku_id === skuId);

  const map = new Map<string, { date: string; actual?: number; p50?: number; p10?: number; p90?: number }>();

  for (const s of salesBySku) {
    map.set(s.sale_date, { date: s.sale_date, actual: s.quantity });
  }
  for (const f of forecastBySku) {
    const existing = map.get(f.forecast_date) ?? { date: f.forecast_date };
    map.set(f.forecast_date, {
      ...existing,
      p50: parseFloat(f.quantity_p50),
      p10: f.quantity_p10 ? parseFloat(f.quantity_p10) : undefined,
      p90: f.quantity_p90 ? parseFloat(f.quantity_p90) : undefined,
    });
  }

  return Array.from(map.values()).sort((a, b) => a.date.localeCompare(b.date));
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  const [restaurants, setRestaurants] = useState<Restaurant[]>([]);
  const [skus, setSkus] = useState<SKU[]>([]);
  const [sales, setSales] = useState<DailySale[]>([]);
  const [runs, setRuns] = useState<ForecastRun[]>([]);
  const [forecastValues, setForecastValues] = useState<ForecastValue[]>([]);
  const [selectedRestaurant, setSelectedRestaurant] = useState<string>("");
  const [selectedSku, setSelectedSku] = useState<string>("");
  const [selectedRun, setSelectedRun] = useState<string>("");
  const [triggering, setTriggering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);

  // Load restaurants on mount
  useEffect(() => {
    api.restaurants.list().then((r) => {
      setRestaurants(r);
      if (r.length > 0) setSelectedRestaurant(r[0].id);
    });
  }, []);

  // Load SKUs + sales when restaurant changes
  useEffect(() => {
    if (!selectedRestaurant) return;
    Promise.all([
      api.restaurants.skus(selectedRestaurant),
      api.restaurants.sales(selectedRestaurant),
    ]).then(([s, sa]) => {
      setSkus(s);
      setSales(sa);
      if (s.length > 0) setSelectedSku(s[0].id);
    });
  }, [selectedRestaurant]);

  const loadRun = useCallback(async (runId: string) => {
    const [run, values] = await Promise.all([
      api.forecasts.get(runId),
      api.forecasts.values(runId),
    ]);
    setRuns((prev) => {
      const idx = prev.findIndex((r) => r.id === runId);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = run;
        return next;
      }
      return [run, ...prev];
    });
    if (run.status === "complete") {
      setForecastValues(values);
      setPolling(false);
    }
    return run;
  }, []);

  // Poll until complete
  useEffect(() => {
    if (!polling || !selectedRun) return;
    const interval = setInterval(async () => {
      const run = await loadRun(selectedRun);
      if (run.status === "complete" || run.status === "failed") {
        clearInterval(interval);
        setPolling(false);
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [polling, selectedRun, loadRun]);

  const triggerForecast = async () => {
    setTriggering(true);
    setError(null);
    try {
      const run = await api.forecasts.create("manual");
      setRuns((prev) => [run, ...prev]);
      setSelectedRun(run.id);
      setPolling(true);
    } catch (e) {
      setError(String(e));
    } finally {
      setTriggering(false);
    }
  };

  const currentRun = runs.find((r) => r.id === selectedRun);
  const chartData = selectedSku ? buildChartData(sales, forecastValues, selectedSku) : [];
  const currentSkuName = skus.find((s) => s.id === selectedSku)?.name ?? "";

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Sales Forecast Dashboard</h1>
        <button
          onClick={triggerForecast}
          disabled={triggering || polling}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded text-sm font-medium transition-colors"
        >
          {triggering ? "Queuing..." : polling ? "Training..." : "Run Forecast"}
        </button>
      </div>

      {error && (
        <div className="bg-red-900/40 border border-red-700 rounded p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Controls */}
      <div className="flex gap-4 flex-wrap">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500">Restaurant</label>
          <select
            value={selectedRestaurant}
            onChange={(e) => setSelectedRestaurant(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm"
          >
            {restaurants.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500">SKU</label>
          <select
            value={selectedSku}
            onChange={(e) => setSelectedSku(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm"
          >
            {skus.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </div>
        {runs.length > 0 && (
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500">Forecast Run</label>
            <select
              value={selectedRun}
              onChange={async (e) => {
                setSelectedRun(e.target.value);
                await loadRun(e.target.value);
              }}
              className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm"
            >
              {runs.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.id.slice(0, 8)} — {r.status}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Status card */}
      {currentRun && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex gap-6 text-sm">
          <div>
            <span className="text-gray-500">Status </span>
            <span className={`font-medium ${statusColor(currentRun.status)}`}>
              {currentRun.status}
            </span>
          </div>
          <div>
            <span className="text-gray-500">Triggered by </span>
            <span>{currentRun.triggered_by}</span>
          </div>
          {currentRun.completed_at && (
            <div>
              <span className="text-gray-500">Completed </span>
              <span>{new Date(currentRun.completed_at).toLocaleString()}</span>
            </div>
          )}
          {currentRun.error_message && (
            <div className="text-red-400">{currentRun.error_message}</div>
          )}
        </div>
      )}

      {/* Chart */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h2 className="text-sm font-medium text-gray-400 mb-4">
          {currentSkuName || "Select a SKU"} — Historical & Forecast
        </h2>
        {chartData.length === 0 ? (
          <div className="h-64 flex items-center justify-center text-gray-600 text-sm">
            {sales.length === 0
              ? "No sales data — run make seed first"
              : forecastValues.length === 0
              ? "No forecast yet — click Run Forecast"
              : "No data for this selection"}
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={360}>
            <ComposedChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10, fill: "#9ca3af" }}
                tickFormatter={(v) => v.slice(5)}
                interval="preserveStartEnd"
              />
              <YAxis tick={{ fontSize: 10, fill: "#9ca3af" }} />
              <Tooltip
                contentStyle={{ background: "#111827", border: "1px solid #374151", fontSize: 12 }}
                labelStyle={{ color: "#e5e7eb" }}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="actual" name="Actual" fill="#4b5563" maxBarSize={4} />
              <Line
                type="monotone"
                dataKey="p50"
                name="Forecast P50"
                stroke="#3b82f6"
                dot={false}
                strokeWidth={2}
              />
              <Line
                type="monotone"
                dataKey="p10"
                name="P10"
                stroke="#6b7280"
                dot={false}
                strokeDasharray="3 3"
                strokeWidth={1}
              />
              <Line
                type="monotone"
                dataKey="p90"
                name="P90"
                stroke="#6b7280"
                dot={false}
                strokeDasharray="3 3"
                strokeWidth={1}
              />
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Stats */}
      {sales.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { label: "Historical Days", value: new Set(sales.map((s) => s.sale_date)).size },
            { label: "SKUs", value: skus.length },
            { label: "Forecast Values", value: forecastValues.length },
            {
              label: "Avg Daily Qty",
              value: sales.length
                ? Math.round(sales.reduce((a, s) => a + s.quantity, 0) / sales.length)
                : 0,
            },
          ].map((card) => (
            <div
              key={card.label}
              className="bg-gray-900 border border-gray-800 rounded-lg p-4"
            >
              <div className="text-2xl font-bold">{card.value}</div>
              <div className="text-xs text-gray-500 mt-1">{card.label}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
