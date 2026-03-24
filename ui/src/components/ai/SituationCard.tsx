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
  const cleanText = (text || "").replace(/\*/g, "");
  const lines = cleanText.split("\n").map((l) => l.trim());

  const result = {
    status: "",
    reason: "",
    action: "",
  };

  let currentSection: keyof typeof result | null = null;
  const content = {
    status: [] as string[],
    reason: [] as string[],
    action: [] as string[],
  };

  for (const line of lines) {
    const l = line.toLowerCase();
    if (l.startsWith("status:")) {
      currentSection = "status";
      const [, rest] = line.split(/:(.+)/);
      if (rest && rest.trim()) content.status.push(rest.trim());
    } else if (l.startsWith("reason:")) {
      currentSection = "reason";
      const [, rest] = line.split(/:(.+)/);
      if (rest && rest.trim()) content.reason.push(rest.trim());
    } else if (l.startsWith("recommended action:") || l.startsWith("action:")) {
      currentSection = "action";
      const [, rest] = line.split(/:(.+)/);
      if (rest && rest.trim()) content.action.push(rest.trim());
    } else if (currentSection && line) {
      content[currentSection].push(line);
    }
  }

  return {
    status: content.status.join("\n").trim(),
    reason: content.reason.join("\n").trim(),
    action: content.action.join("\n").trim(),
  };
}

const SituationCard: React.FC<SituationCardProps> = ({ sessionId }) => {
  const [assessments, setAssessments] = useState<string[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!sessionId) {
      setAssessments([]);
      setCurrentIndex(0);
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
          const newAnalysis = res.data?.analysis || "";
          if (newAnalysis) {
            setAssessments(prev => {
              if (prev.length === 0 || prev[prev.length - 1] !== newAnalysis) {
                const nextArray = [...prev, newAnalysis];
                setCurrentIndex(nextArray.length - 1);
                return nextArray;
              }
              return prev;
            });
          }
        }
      } catch (err) {
        console.error("AI summary fetch failed", err);
        // Do nothing on error. Old assessments remain visible.
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

  const hasAnalysis = assessments.length > 0;
  const currentAnalysis = hasAnalysis ? assessments[currentIndex] : null;
  const parsed = currentAnalysis ? parseAnalysis(currentAnalysis) : null;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">System Assessment</h3>
        <div className="flex items-center gap-2">
          {hasAnalysis && assessments.length > 1 && (
            <div className="flex items-center gap-2 text-xs text-gray-500 mr-2 bg-gray-50 rounded-lg p-1 border border-gray-100">
              <button 
                onClick={() => setCurrentIndex(i => Math.max(0, i - 1))}
                disabled={currentIndex === 0}
                className="p-1 hover:bg-white rounded shadow-sm disabled:opacity-30 disabled:shadow-none transition-all"
                title="Previous Assessment"
              >
                ◀
              </button>
              <span className="w-8 text-center font-medium">{currentIndex + 1} / {assessments.length}</span>
              <button 
                onClick={() => setCurrentIndex(i => Math.min(assessments.length - 1, i + 1))}
                disabled={currentIndex === assessments.length - 1}
                className="p-1 hover:bg-white rounded shadow-sm disabled:opacity-30 disabled:shadow-none transition-all"
                title="Next Assessment"
              >
                ▶
              </button>
            </div>
          )}
          {loading && <Loader2 className="animate-spin text-gray-400" size={18} />}
        </div>
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

