import type {
  DailySale,
  ForecastRun,
  ForecastValue,
  Restaurant,
  SKU,
} from "@/types/api";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  restaurants: {
    list: () => apiFetch<Restaurant[]>("/restaurants"),
    skus: (restaurantId: string) =>
      apiFetch<SKU[]>(`/restaurants/${restaurantId}/skus`),
    sales: (restaurantId: string) =>
      apiFetch<DailySale[]>(`/restaurants/${restaurantId}/sales`),
  },

  forecasts: {
    create: (triggeredBy = "manual") =>
      apiFetch<ForecastRun>("/forecasts", {
        method: "POST",
        body: JSON.stringify({ triggered_by: triggeredBy }),
      }),
    get: (runId: string) => apiFetch<ForecastRun>(`/forecasts/${runId}`),
    values: (runId: string) =>
      apiFetch<ForecastValue[]>(`/forecasts/${runId}/values`),
  },

  agents: {
    run: (prompt: string) =>
      apiFetch<{ stream_id: string }>("/agents/run", {
        method: "POST",
        body: JSON.stringify({ prompt }),
      }),
    streamUrl: (streamId: string) =>
      `${API_URL}/agents/stream/${streamId}`,
  },
};
