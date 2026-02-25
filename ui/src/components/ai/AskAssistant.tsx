import React, { useState } from "react";
import axios from "axios";
import { MessageCircle, Send, Loader2, X } from "lucide-react";

const API_BASE =
  (import.meta as any).env?.VITE_API_BASE_URL || "http://localhost:8000";

type AskAssistantProps = {
  sessionId?: string | null;
  mode?: "dashboard" | "session";
};

const AskAssistant: React.FC<AskAssistantProps> = ({
  sessionId,
  mode = "dashboard",
}) => {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false); // dashboard floating panel

  const canAsk = !!sessionId && question.trim().length > 0 && !loading;

  const sendQuestion = async () => {
    if (!sessionId || !question.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post<{ analysis: string }>(
        `${API_BASE}/ai/${sessionId}/ask`,
        { question: question.trim() },
        { timeout: 8000 }
      );
      setAnswer(res.data?.analysis || "");
    } catch (err) {
      console.error("AI ask failed", err);
      setError("Unable to get AI response. Please try again.");
      setAnswer(null);
    } finally {
      setLoading(false);
    }
  };

  const content = (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <MessageCircle className="text-blue-600" size={18} />
          <span className="text-sm font-semibold text-gray-900">
            Ask Drishti assistant
          </span>
        </div>
        {mode === "dashboard" && (
          <button
            onClick={() => setOpen(false)}
            className="p-1 rounded-full text-gray-400 hover:text-gray-600 hover:bg-gray-100"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        )}
      </div>

      <p className="text-xs text-gray-500 mb-3">
        {mode === "dashboard"
          ? "Ask about the current crowd situation. Short operational answers."
          : "Investigate this session using the stored analytics data."}
      </p>

      {!sessionId && (
        <p className="text-xs text-gray-500 mb-3">
          Select or start a session to ask questions.
        </p>
      )}

      <div className="flex items-center gap-2 mb-3">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={
            mode === "dashboard"
              ? "Ask about current crowd situation..."
              : "Investigate this session..."
          }
          className="flex-1 text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
        <button
          onClick={sendQuestion}
          disabled={!canAsk}
          className="inline-flex items-center justify-center px-3 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed hover:bg-blue-700 transition-colors"
        >
          {loading ? (
            <Loader2 className="animate-spin" size={16} />
          ) : (
            <Send size={16} />
          )}
        </button>
      </div>

      {error && (
        <p className="text-xs text-red-600 mb-2">{error}</p>
      )}

      {answer && (
        <div className="mt-1 flex-1 overflow-y-auto border border-gray-100 rounded-lg bg-gray-50 p-3">
          <p className="text-sm text-gray-900 whitespace-pre-line">
            {answer}
          </p>
        </div>
      )}
    </div>
  );

  if (mode === "session") {
    // Full-width box for session result page
    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5 mt-6">
        {content}
      </div>
    );
  }

  // Dashboard floating button + compact panel
  return (
    <>
      {/* Floating button */}
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-30 inline-flex items-center gap-2 px-4 py-2 rounded-full shadow-lg bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700"
      >
        <MessageCircle size={16} />
        Ask Drishti
      </button>

      {/* Floating panel */}
      {open && (
        <div className="fixed bottom-20 right-6 z-30 w-80 bg-white rounded-xl shadow-xl border border-gray-200 p-4">
          {content}
        </div>
      )}
    </>
  );
};

export default AskAssistant;

