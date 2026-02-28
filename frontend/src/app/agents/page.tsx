"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { AgentEventType } from "@/types/api";

interface StreamEvent {
  id: number;
  type: AgentEventType;
  data: Record<string, unknown>;
  timestamp: string;
}

const EVENT_COLORS: Record<AgentEventType, string> = {
  thinking: "text-purple-400",
  tool_call: "text-yellow-400",
  tool_result: "text-green-400",
  message: "text-blue-300",
  error: "text-red-400",
  done: "text-gray-400",
};

const EVENT_LABELS: Record<AgentEventType, string> = {
  thinking: "Thinking",
  tool_call: "Tool Call",
  tool_result: "Tool Result",
  message: "Message",
  error: "Error",
  done: "Done",
};

export default function AgentsPage() {
  const [prompt, setPrompt] = useState(
    "Summarize the current sales data and check if there are any completed forecast runs."
  );
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const eventSourceRef = useRef<EventSource | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const counterRef = useRef(0);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  const runAgent = async () => {
    if (!prompt.trim()) return;
    setRunning(true);
    setError(null);
    setEvents([]);
    setExpanded(new Set());

    // Close any existing stream
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    try {
      const { stream_id } = await api.agents.run(prompt);
      const url = api.agents.streamUrl(stream_id);
      const es = new EventSource(url);
      eventSourceRef.current = es;

      const eventTypes: AgentEventType[] = [
        "thinking",
        "tool_call",
        "tool_result",
        "message",
        "error",
        "done",
      ];

      for (const type of eventTypes) {
        es.addEventListener(type, (e: MessageEvent) => {
          const data = JSON.parse(e.data) as Record<string, unknown>;
          const id = ++counterRef.current;
          setEvents((prev) => [
            ...prev,
            { id, type, data, timestamp: new Date().toISOString() },
          ]);
          if (type === "done" || type === "error") {
            es.close();
            setRunning(false);
          }
        });
      }

      es.onerror = () => {
        es.close();
        setRunning(false);
      };
    } catch (e) {
      setError(String(e));
      setRunning(false);
    }
  };

  const toggleExpanded = (id: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <h1 className="text-2xl font-bold">Agent Console</h1>
      <p className="text-sm text-gray-500">
        The orchestrator uses claude-opus-4-6 with adaptive thinking and ML
        tools to analyze forecasts.
      </p>

      {/* Input */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-3">
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={3}
          placeholder="Ask the agent something..."
          className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm resize-none focus:outline-none focus:border-blue-500"
        />
        <div className="flex gap-2">
          <button
            onClick={runAgent}
            disabled={running || !prompt.trim()}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded text-sm font-medium transition-colors"
          >
            {running ? "Running..." : "Run Agent"}
          </button>
          {events.length > 0 && (
            <button
              onClick={() => setEvents([])}
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm transition-colors"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="bg-red-900/40 border border-red-700 rounded p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Event stream */}
      {events.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg divide-y divide-gray-800 max-h-[600px] overflow-y-auto">
          {events.map((event) => (
            <div key={event.id} className="p-3">
              <div
                className="flex items-center gap-2 cursor-pointer select-none"
                onClick={() => toggleExpanded(event.id)}
              >
                <span
                  className={`text-xs font-mono font-medium ${EVENT_COLORS[event.type]}`}
                >
                  {EVENT_LABELS[event.type]}
                </span>
                <span className="text-xs text-gray-600">
                  {new Date(event.timestamp).toLocaleTimeString()}
                </span>
                {event.type === "tool_call" && (
                  <span className="text-xs text-gray-400">
                    {String(event.data.name ?? "")}
                  </span>
                )}
                {event.type === "message" && (
                  <span className="text-xs text-gray-300 truncate max-w-sm">
                    {String(event.data.text ?? "").slice(0, 100)}
                  </span>
                )}
                <span className="ml-auto text-gray-600 text-xs">
                  {expanded.has(event.id) ? "▲" : "▼"}
                </span>
              </div>

              {expanded.has(event.id) && (
                <pre className="mt-2 text-xs text-gray-400 bg-gray-950 rounded p-3 overflow-auto max-h-64 whitespace-pre-wrap">
                  {JSON.stringify(event.data, null, 2)}
                </pre>
              )}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      )}

      {events.length === 0 && !running && (
        <div className="text-sm text-gray-600 text-center py-8">
          Events will appear here when the agent runs.
        </div>
      )}
    </div>
  );
}
