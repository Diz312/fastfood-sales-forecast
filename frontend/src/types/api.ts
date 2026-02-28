// Auto-generated from Pydantic schemas — do not edit manually

export type RunStatus = "pending" | "running" | "complete" | "failed";

export interface Restaurant {
  id: string;
  code: string;
  name: string;
  region: string | null;
  timezone: string;
  opened_on: string | null;
  is_active: boolean;
}

export interface SKU {
  id: string;
  code: string;
  name: string;
  product_group_id: string;
  is_active: boolean;
}

export interface DailySale {
  id: string;
  restaurant_id: string;
  sku_id: string;
  sale_date: string;
  quantity: number;
  revenue: string;
}

export interface ForecastRun {
  id: string;
  triggered_by: string;
  status: RunStatus;
  config: Record<string, unknown>;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  celery_task_id: string | null;
  created_at: string;
}

export interface ForecastValue {
  id: string;
  run_id: string;
  restaurant_id: string;
  sku_id: string;
  forecast_date: string;
  model_name: string;
  quantity_p50: string;
  quantity_p10: string | null;
  quantity_p90: string | null;
  is_reconciled: boolean;
}

export type AgentEventType =
  | "thinking"
  | "tool_call"
  | "tool_result"
  | "message"
  | "error"
  | "done";

export interface AgentEvent {
  event_type: AgentEventType;
  stream_id: string;
  data: Record<string, unknown>;
  timestamp: string;
}
