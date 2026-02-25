import React, { useEffect, useState } from "react";
import axios from "axios";
import { Loader2 } from "lucide-react";

const API_BASE =
  (import.meta as any).env?.VITE_API_BASE_URL || "http://localhost:8000";

type SituationCardProps = {
  sessionId?: string | null;
};

type ParsedSummary = {
  status: string;
  reason: string;
  action: string;
};

function parseAnalysis(text: string): ParsedSummary {
  const lines = (text || "").split("\n").map((l) => l.trim());

  const getValue = (label: string) => {
    const line = lines.find((l) =>
      l.toLowerCase().startsWith(label.toLowerCase() + ":")
    );
    if (!line) return "";
    const [, rest] = line.split(/:(.+)/);
    return (rest || "").trim();
  };

  return {
    status: getValue("Status"),
    reason: getValue("Reason"),
    action: getValue("Recommended Action"),
  };
}

const SituationCard: React.FC<SituationCardProps> = ({ sessionId }) => {
  const [analysis, setAnalysis] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!sessionId) {
      setAnalysis(null);
      return;
    }

    let cancelled = false;

    const fetchSummary = async () => {
      if (!sessionId) return;
      setLoading(true);
      try {
        const res = await axios.get<{ analysis: string }>(
          `${API_BASE}/ai/${sessionId}/summary`,
          { timeout: 6000 }
        );
        if (!cancelled) {
          setAnalysis(res.data?.analysis || "");
        }
      } catch (err) {
        console.error("AI summary fetch failed", err);
        if (!cancelled) {
          // Keep last good value; if none, show safe fallback in UI
          if (!analysis) {
            setAnalysis(null);
          }
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    fetchSummary();
    const id = setInterval(fetchSummary, 12000);

    return () => {
      cancelled = true;
      clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const hasAnalysis = !!analysis;
  const parsed = hasAnalysis ? parseAnalysis(analysis || "") : null;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
      <div className="flex items-center justify-between mb  -4">
        <h3 className="text-lg font-semibold text-gray-900">System Assessment</h3>
        {loading && <Loader2 className="animate-spin text-gray-400" size={18} />}
      </div>

      {!sessionId && (
        <p className="mt-2 text-sm text-gray-500">
          Waiting for an active session to start.
        </p>
      )}

      {sessionId && hasAnalysis && parsed && (
        <div className="mt-3 space-y-2">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase">
              Status
            </p>
            <p className="text-sm text-gray-900">
              {parsed.status || "Not specified"}
            </p>
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase">
              Reason
            </p>
            <p className="text-sm text-gray-900 whitespace-pre-line">
              {parsed.reason || "No specific reason provided."}
            </p>
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase">
              Recommended Action
            </p>
            <p className="text-sm text-gray-900 whitespace-pre-line">
              {parsed.action || "No action required at this time."}
            </p>
          </div>
        </div>
      )}

      {sessionId && !hasAnalysis && !loading && (
        <p className="mt-2 text-sm text-gray-500">
          No active risk detected.
        </p>
      )}
    </div>
  );
};

export default SituationCard;

