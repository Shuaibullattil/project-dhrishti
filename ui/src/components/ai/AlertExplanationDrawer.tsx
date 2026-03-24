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

const renderWithBold = (text: string) => {
  if (!text) return null;
  const parts = text.split(/(\*\*.*?\*\*)/g);
  return parts.map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    return part;
  });
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal Popup */}
      <div className="relative w-full max-w-lg bg-white rounded-xl shadow-2xl flex flex-col max-h-[85vh] overflow-hidden transform transition-all animate-in fade-in zoom-in-95 duration-200">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between bg-gray-50">
          <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
            AI Alert Justification
          </h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-full text-gray-400 hover:text-gray-700 hover:bg-gray-200 transition-colors"
            aria-label="Close"
            title="Close"
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 p-6 overflow-y-auto">
          {!sessionId && (
            <p className="text-sm text-gray-500 text-center">
              Select a session to view alert justification.
            </p>
          )}

          {sessionId && loading && (
            <div className="flex flex-col items-center justify-center py-10 text-gray-500">
              <Loader2 className="animate-spin mb-3 text-blue-500" size={28} />
              <span className="text-sm font-medium">Analyzing alert conditions...</span>
            </div>
          )}

          {sessionId && !loading && analysis && (
            <div className="bg-blue-50/50 p-4 rounded-lg border border-blue-100">
              <p className="whitespace-pre-line text-sm text-gray-800 leading-relaxed">
                {renderWithBold(analysis)}
              </p>
            </div>
          )}

          {sessionId && !loading && !analysis && (
            <p className="text-sm text-gray-500 text-center py-8">
              No detailed justification available for this alert yet.
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

export default AlertExplanationDrawer;

