import React, { useEffect, useState } from "react";
import axios from "axios";
import { Loader2, X } from "lucide-react";

const API_BASE =
  (import.meta as any).env?.VITE_API_BASE_URL || "http://localhost:8000";

type AlertExplanationDrawerProps = {
  sessionId?: string | null;
  open: boolean;
  onClose: () => void;
};

const AlertExplanationDrawer: React.FC<AlertExplanationDrawerProps> = ({
  sessionId,
  open,
  onClose,
}) => {
  const [analysis, setAnalysis] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !sessionId) return;

    let cancelled = false;

    const fetchExplain = async () => {
      setLoading(true);
      try {
        const res = await axios.get<{ analysis: string }>(
          `${API_BASE}/ai/${sessionId}/explain`,
          { timeout: 6000 }
        );
        if (!cancelled) {
          setAnalysis(res.data?.analysis || "");
        }
      } catch (err) {
        console.error("AI explain fetch failed", err);
        // Keep last explanation cached; if none, show fallback text
        if (!cancelled && !analysis) {
          setAnalysis(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    fetchExplain();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, sessionId]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40 flex">
      {/* Backdrop */}
      <div
        className="flex-1 bg-black bg-opacity-40"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer */}
      <aside className="w-full max-w-md bg-white shadow-xl border-l border-gray-200 flex flex-col">
        <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-900">
            Alert Justification
          </h2>
          <button
            onClick={onClose}
            className="p-1 rounded-full text-gray-400 hover:text-gray-600 hover:bg-gray-100"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 p-5 overflow-y-auto">
          {!sessionId && (
            <p className="text-sm text-gray-500">
              Select a session to view alert justification.
            </p>
          )}

          {sessionId && loading && (
            <div className="flex items-center justify-center py-8 text-gray-500">
              <Loader2 className="animate-spin mr-2" size={18} />
              <span>Analyzing alert conditions...</span>
            </div>
          )}

          {sessionId && !loading && analysis && (
            <p className="whitespace-pre-line text-sm text-gray-900">
              {analysis}
            </p>
          )}

          {sessionId && !loading && !analysis && (
            <p className="text-sm text-gray-500">
              No detailed justification available for this alert yet.
            </p>
          )}
        </div>
      </aside>
    </div>
  );
};

export default AlertExplanationDrawer;

