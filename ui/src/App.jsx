import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  Upload, Play, Loader2, LayoutDashboard, History, Settings,
  Users, AlertTriangle, Shield, Clock, ChevronRight, Download,
  Activity, BarChart3, Info, TrendingUp, Video, FileVideo,
  Zap, Eye, CheckCircle2, XCircle, Trash2, Layers
} from 'lucide-react';
import SituationCard from './components/ai/SituationCard';
import AlertExplanationDrawer from './components/ai/AlertExplanationDrawer';
import AskAssistant from './components/ai/AskAssistant';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  RadialBarChart, RadialBar
} from 'recharts';

const API_BASE = import.meta.env?.VITE_API_BASE_URL || "http://localhost:8000";
const WS_URL = "ws://localhost:8000/ws";

const COLORS = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6'];

const riskMapping = {
  'NORMAL': 0.25,
  'BUSY': 0.5,
  'WARNING': 0.75,
  'CRITICAL': 1.0
};

const getRiskLabel = (score) => {
  if (score <= 0.25) return 'NORMAL';
  if (score <= 0.5) return 'BUSY';
  if (score <= 0.75) return 'WARNING';
  return 'CRITICAL';
};

const riskScaleMapping = {
  'NORMAL': 0,
  'BUSY': 1,
  'WARNING': 2,
  'CRITICAL': 3
};

const getRiskColor = (level) => {
  switch (level) {
    case 'NORMAL': return '#22c55e';
    case 'BUSY': return '#facc15';
    case 'WARNING': return '#fb923c';
    case 'CRITICAL': return '#ef4444';
    default: return '#22c55e';
  }
};

const CustomYAxisTick = ({ x, y, payload }) => {
  const labels = ['NORMAL', 'BUSY', 'WARNING', 'CRITICAL'];
  const label = labels[payload.value];
  return (
    <g transform={`translate(${x},${y})`}>
      <text
        x={0}
        y={0}
        dy={4}
        textAnchor="end"
        fill={getRiskColor(label)}
        fontSize={10}
        fontWeight="bold"
      >
        {label}
      </text>
    </g>
  );
};

const CustomDot = (props) => {
  const { cx, cy, payload } = props;
  if (!cx || !cy) return null;
  return (
    <circle
      cx={cx}
      cy={cy}
      r={6}
      fill={getRiskColor(payload.level)}
      stroke="#fff"
      strokeWidth={2}
    />
  );
};

const RADIAN = Math.PI / 180;
const needle = (value, cx, cy, iR, oR, color) => {
  const ang = 180.0 * (1 - value);
  const length = (iR + 2 * oR) / 3;
  const sin = Math.sin(-RADIAN * ang);
  const cos = Math.cos(-RADIAN * ang);
  const r = 5;
  const x0 = cx;
  const y0 = cy;
  const xba = x0 + r * sin;
  const yba = y0 - r * cos;
  const xbb = x0 - r * sin;
  const ybb = y0 + r * cos;
  const xp = x0 + length * cos;
  const yp = y0 + length * sin;

  return (
    <g>
      <circle cx={x0} cy={y0} r={r} fill={color} stroke="none" />
      <path
        d={`M${xba} ${yba}L${xbb} ${ybb}L${xp} ${yp}L${xba} ${yba}`}
        stroke="none"
        fill={color}
        style={{ transition: 'all 0.5s ease-out' }}
      />
    </g>
  );
};

const RiskGauge = ({ level, score }) => {
  const needleValue = score !== undefined ? score : (riskMapping[level] || 0);
  const gaugeData = [{ value: 100 }]; // Single segment for the gradient arc

  const cx = 150;
  const cy = 150;
  const iR = 60;
  const oR = 100;

  return (
    <div className="h-48 w-full relative flex flex-col items-center justify-center overflow-hidden">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <defs>
            <linearGradient id="riskGaugeGradient" x1="0" y1="0" x2="100%" y2="0">
              <stop offset="0%" stopColor="#22c55e" />
              <stop offset="33%" stopColor="#facc15" />
              <stop offset="66%" stopColor="#fb923c" />
              <stop offset="100%" stopColor="#ef4444" />
            </linearGradient>
          </defs>
          <Pie
            dataKey="value"
            startAngle={180}
            endAngle={0}
            data={gaugeData}
            cx={cx}
            cy={cy}
            innerRadius={iR}
            outerRadius={oR}
            stroke="none"
            fill="url(#riskGaugeGradient)"
          />
          {needle(needleValue, cx, cy, iR, oR, '#334155')}
        </PieChart>
      </ResponsiveContainer>
      <div className="absolute top-[160px] flex flex-col items-center">
        <span className="text-xl font-black uppercase tracking-tighter" style={{ color: getRiskColor(level) }}>
          {level || 'NORMAL'}
        </span>
        <span className="text-[9px] text-gray-400 font-bold uppercase tracking-widest -mt-1">Status</span>
      </div>
    </div>
  );
};

const RiskTimelineChart = ({ data }) => {
  const chartData = data.map(r => {
    const level = r.risk_level || getRiskLabel(r.risk_score || 0.25);
    return {
      time: r.timestamp ? (typeof r.timestamp === 'string' ? new Date(r.timestamp).toLocaleTimeString() : new Date(r.timestamp).toLocaleTimeString()) : 'N/A',
      score: riskScaleMapping[level],
      level: level,
      count: r.avg_human_count || 0
    };
  });



  return (
    <div className="bg-white rounded-xl shadow-lg border border-gray-100 p-6 overflow-hidden">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-xl font-bold text-gray-900 leading-tight tracking-tight">Crowd Risk Timeline</h3>
          <p className="text-sm text-gray-500 mt-1 font-medium">Real-time risk evolution from Context Engine</p>
        </div>
        <div className="p-2.5 bg-blue-50 text-blue-600 rounded-xl shadow-inner">
          <TrendingUp size={24} />
        </div>
      </div>
      <div className="h-80 w-full mt-4">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 20, right: 30, left: 50, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
            <XAxis
              dataKey="time"
              stroke="#94a3b8"
              tick={{ fontSize: 10, fontWeight: 600 }}
              axisLine={false}
              tickLine={false}
              dy={10}
            />
            <YAxis
              domain={[0, 3]}
              ticks={[0, 1, 2, 3]}
              stroke="#94a3b8"
              axisLine={false}
              tickLine={false}
              tick={<CustomYAxisTick />}
              dx={-10}
            />
            <Tooltip
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const d = payload[0].payload;
                  return (
                    <div className="bg-white/95 backdrop-blur-sm p-4 border border-gray-100 shadow-2xl rounded-2xl ring-1 ring-black/5">
                      <p className="text-[10px] text-gray-400 font-black mb-3 uppercase tracking-widest border-b border-gray-50 pb-2">{d.time}</p>
                      <div className="flex items-center gap-2 mb-3">
                        <div className="w-3 h-3 rounded-full shadow-sm" style={{ backgroundColor: getRiskColor(d.level) }}></div>
                        <p className="font-black text-base italic" style={{ color: getRiskColor(d.level) }}>{d.level}</p>
                      </div>
                      <div className="space-y-2">
                        <div className="flex items-center justify-between gap-6">
                          <span className="text-xs text-gray-500 font-bold">Avg People:</span>
                          <span className="font-black text-gray-900">{d.count.toFixed(1)}</span>
                        </div>
                      </div>
                    </div>
                  );
                }
                return null;
              }}
            />
            <Line
              type="monotone"
              dataKey="score"
              stroke="#cbd5e1"
              strokeWidth={3}
              dot={<CustomDot />}
              activeDot={{ r: 8, strokeWidth: 0, fill: '#64748b' }}
              isAnimationActive={true}
              animationDuration={800}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

function App() {
  const [file, setFile] = useState(null);
  const [processingStatus, setProcessingStatus] = useState('idle'); // idle, uploading, processing, completed
  const [fileId, setFileId] = useState(null);
  const [currentSession, setCurrentSession] = useState(null);
  const [realtimeData, setRealtimeData] = useState({
    count: 0,
    violations: 0,
    restricted: false,
    frame: 0,
    frameImage: null  // Base64 encoded frame image
  });
  const [chartData, setChartData] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [selectedSession, setSelectedSession] = useState(null);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [sessionDetails, setSessionDetails] = useState(null);
  const [abnormalFrames, setAbnormalFrames] = useState([]); // For real-time abnormal frames
  const [remarks, setRemarks] = useState([]); // For real-time remarks
  const [alertDrawerOpen, setAlertDrawerOpen] = useState(false);
  const [sessionContext, setSessionContext] = useState({
    flow_type: '',
    capacity: '',
    sensitivity: '',
    clustering: '',
    goal: ''
  });
  const [automationAlert, setAutomationAlert] = useState(null);

  const ws = useRef(null);
  const lastRenderedFrameRef = useRef(0);
  const [historicalTab, setHistoricalTab] = useState('video');
  const realtimeFrameSrc = realtimeData.frameImage
    ? `data:image/jpeg;base64,${realtimeData.frameImage}`
    : null;

  useEffect(() => {
    fetchSessions();
    // Auto-refresh sessions every 30 seconds
    const interval = setInterval(fetchSessions, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const connectWS = () => {
      try {
        ws.current = new WebSocket(WS_URL);
        ws.current.onopen = () => {
          console.log("WebSocket connected");
        };
        ws.current.onmessage = (event) => {
          const msg = JSON.parse(event.data);
          if (msg.file_id === fileId || !fileId) {
            if (msg.status === 'completed') {
              setProcessingStatus('completed');
              fetchSessions();
              if (msg.analysis) {
                setCurrentSession({
                  file_id: msg.file_id,
                  analysis: msg.analysis,
                  status: 'completed'
                });
              }
            } else if (msg.status === 'failed') {
              setProcessingStatus('idle');
              alert(`Processing failed: ${msg.error || 'Unknown error'}`);
            } else if (msg.type === 'realtime') {
              const nextFrame = msg.data.frame || 0;
              if (nextFrame <= lastRenderedFrameRef.current) {
                return;
              }

              lastRenderedFrameRef.current = nextFrame;
              setRealtimeData({
                count: msg.data.human_count || 0,
                violations: msg.data.violate_count || 0,
                restricted: msg.data.restricted_entry || false,
                frame: nextFrame,
                frameImage: msg.data.frame_image || null
              });

              setChartData(prev => {
                const newData = [...prev.slice(-99), {
                  time: nextFrame,
                  count: msg.data.human_count || 0,
                  violations: msg.data.violate_count || 0
                }];
                return newData;
              });
            } else if (msg.type === 'remark') {
              // Add new remark to the list
              setRemarks(prev => {
                const newRemark = {
                  ...msg.data,
                  timestamp: msg.data.window_end || new Date().toISOString()
                };
                // Check if remark already exists (avoid duplicates)
                const exists = prev.some(r => r.window_start === msg.data.window_start);
                if (!exists) {
                  return [...prev, newRemark].sort((a, b) =>
                    new Date(a.timestamp) - new Date(b.timestamp)
                  );
                }
                return prev;
              });
            } else if (msg.type === 'automation_alert_sent') {
              setAutomationAlert({
                risk_level: msg.risk_level,
                timestamp: new Date().toLocaleTimeString()
              });
              // Auto-dismiss after 8 seconds
              setTimeout(() => {
                setAutomationAlert(null);
              }, 8000);
            }
          }
        };
        ws.current.onclose = () => {
          console.log("WebSocket closed, retrying...");
          setTimeout(connectWS, 3000);
        };
        ws.current.onerror = (err) => {
          console.error("WebSocket error", err);
        };
      } catch (e) {
        console.error("Failed to connect WebSocket", e);
      }
    };
    connectWS();
    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [fileId]);

  const fetchSessions = async () => {
    setLoadingSessions(true);
    try {
      const res = await axios.get(`${API_BASE}/sessions`);
      setSessions(res.data || []);
    } catch (err) {
      console.error("Fetch sessions failed", err);
    } finally {
      setLoadingSessions(false);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    if (!sessionContext.flow_type || !sessionContext.capacity || !sessionContext.sensitivity || !sessionContext.clustering || !sessionContext.goal) {
      alert("Please fill in all Scene Context Configuration fields.");
      return;
    }

    setProcessingStatus('uploading');
    setChartData([]);
    lastRenderedFrameRef.current = 0;
    setRealtimeData({ count: 0, violations: 0, restricted: false, frame: 0, frameImage: null });
    setAbnormalFrames([]); // Reset abnormal frames
    setRemarks([]); // Reset remarks
    setCurrentSession(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('flow_type', sessionContext.flow_type);
    formData.append('capacity', sessionContext.capacity);
    formData.append('sensitivity', sessionContext.sensitivity);
    formData.append('clustering', sessionContext.clustering);
    formData.append('goal', sessionContext.goal);

    try {
      const res = await axios.post(`${API_BASE}/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setFileId(res.data.file_id);
      setProcessingStatus('processing');
      setCurrentSession({
        file_id: res.data.file_id,
        filename: res.data.filename,
        status: 'processing'
      });
    } catch (err) {
      console.error(err);
      setProcessingStatus('idle');
      alert("Error starting analysis. Please check if the API server is running.");
    }
  };

  const loadSessionDetails = async (sessionId) => {
    try {
      const res = await axios.get(`${API_BASE}/sessions/${sessionId}`);
      // Ensure aggregated_windows is included
      const sessionData = {
        ...res.data,
        aggregated_windows: res.data.aggregated_windows || []
      };

      // If aggregated_windows is empty, try fetching separately
      if (!sessionData.aggregated_windows || sessionData.aggregated_windows.length === 0) {
        try {
          const aggregatedRes = await axios.get(`${API_BASE}/sessions/${sessionId}/aggregated`);
          sessionData.aggregated_windows = aggregatedRes.data || [];
        } catch (e) {
          console.log("No aggregated data available yet");
        }
      }

      setSessionDetails(sessionData);
      setSelectedSession(sessionId);
    } catch (err) {
      console.error("Load session details failed", err);
      alert("Failed to load session details");
    }
  };

  const handleDeleteSession = async (e, sessionId) => {
    e.stopPropagation(); // Prevent opening session details
    if (!window.confirm("Are you sure you want to delete this session and all its data?")) return;

    try {
      await axios.delete(`${API_BASE}/sessions/${sessionId}`);
      // Refresh sessions list
      fetchSessions();
      // If the deleted session was selected, clear details
      if (selectedSession === sessionId) {
        setSelectedSession(null);
        setSessionDetails(null);
      }
    } catch (err) {
      console.error("Delete session failed", err);
      alert("Failed to delete session");
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const StatCard = ({ title, value, icon: Icon, color = "blue", subtitle, trend }) => {
    const colorClasses = {
      blue: "bg-blue-50 text-blue-600",
      red: "bg-red-50 text-red-600",
      green: "bg-green-50 text-green-600",
      yellow: "bg-yellow-50 text-yellow-600",
      purple: "bg-purple-50 text-purple-600"
    };

    return (
      <div className="bg-white rounded-xl shadow-md border border-gray-100 p-6 hover:shadow-lg transition-all transform hover:-translate-y-1">
        <div className="flex items-center justify-between mb-4">
          <div className={`p-3 rounded-lg ${colorClasses[color]}`}>
            <Icon size={24} />
          </div>
          {trend && (
            <div className={`flex items-center gap-1 text-xs font-semibold ${trend > 0 ? 'text-green-600' : 'text-red-600'}`}>
              <TrendingUp size={14} className={trend < 0 ? 'rotate-180' : ''} />
              {Math.abs(trend)}%
            </div>
          )}
        </div>
        <div>
          <h3 className="text-3xl font-bold text-gray-900 mb-1">{value}</h3>
          <p className="text-sm font-medium text-gray-600 mb-1">{title}</p>
          {subtitle && <p className="text-xs text-gray-500">{subtitle}</p>}
        </div>
      </div>
    );
  };

  // Prepare chart data for completed sessions
  const prepareChartData = (trends) => {
    if (!trends || trends.length === 0) return [];
    return trends.map((item, index) => ({
      frame: item.frame || index,
      count: item.count !== undefined ? item.count : (item.human_count || 0),
      violations: item.violations !== undefined ? item.violations : (item.violate_count || 0)
    }));
  };

  // Calculate statistics for pie chart using risk_level instead of abnormal trends
  const getRiskStats = (session) => {
    if (!session || !session.aggregated_windows || session.aggregated_windows.length === 0) return null;
    const totals = { NORMAL: 0, BUSY: 0, WARNING: 0, CRITICAL: 0 };
    session.aggregated_windows.forEach(w => {
      if (w.risk_level) totals[w.risk_level]++;
      else if (w.severity === 'LOW') totals.NORMAL++;
      else if (w.severity === 'MEDIUM') totals.WARNING++;
      else if (w.severity === 'HIGH') totals.CRITICAL++;
    });
    return [
      { name: 'Normal', value: totals.NORMAL },
      { name: 'Busy', value: totals.BUSY },
      { name: 'Warning', value: totals.WARNING },
      { name: 'Critical', value: totals.CRITICAL }
    ].filter(item => item.value > 0);
  };

  return (
    <div className="flex min-h-screen bg-gray-50">
      {/* Sidebar with Previous Sessions */}
      <aside className="w-80 bg-white border-r border-gray-200 flex flex-col fixed h-screen z-20 left-0 top-0">
        {/* Header */}
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-purple-600 rounded-lg flex items-center justify-center">
              <Eye className="text-white" size={20} />
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">Dhrishti</h1>
              <p className="text-xs text-gray-500">Crowd Analysis</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="p-4 border-b border-gray-200">
          <button
            onClick={() => {
              setSelectedSession(null);
              setSessionDetails(null);
            }}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-100 transition-colors"
          >
            <LayoutDashboard size={18} />
            Dashboard
          </button>
        </nav>

        {/* Previous Sessions List */}
        <div className="flex-1 overflow-y-auto">
          <div className="p-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Previous Sessions</h2>
              <button
                onClick={fetchSessions}
                className="text-xs text-blue-600 hover:text-blue-700 font-medium"
                disabled={loadingSessions}
              >
                {loadingSessions ? <Loader2 size={14} className="animate-spin" /> : 'Refresh'}
              </button>
            </div>

            {loadingSessions && sessions.length === 0 ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="animate-spin text-gray-400" size={24} />
              </div>
            ) : sessions.length === 0 ? (
              <div className="text-center py-12">
                <FileVideo className="mx-auto text-gray-300 mb-3" size={32} />
                <p className="text-sm text-gray-500">No sessions yet</p>
              </div>
            ) : (
              <div className="space-y-2">
                {sessions.map(session => (
                  <div
                    key={session.session_id}
                    onClick={() => loadSessionDetails(session.session_id)}
                    className={`p-4 rounded-lg border cursor-pointer transition-all ${selectedSession === session.session_id
                      ? 'border-blue-500 bg-blue-50 shadow-sm'
                      : 'border-gray-200 hover:border-gray-300 hover:shadow-sm bg-white'
                      }`}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-gray-900 truncate mb-1">
                          {session.filename || 'Untitled'}
                        </p>
                        <p className="text-xs text-gray-500 flex items-center gap-1">
                          <Clock size={12} />
                          {formatDate(session.start_time)}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 ml-2">
                        {session.status === 'completed' ? (
                          <CheckCircle2 size={16} className="text-green-500" />
                        ) : session.status === 'processing' ? (
                          <Loader2 size={16} className="text-blue-500 animate-spin" />
                        ) : (
                          <XCircle size={16} className="text-red-500" />
                        )}
                        <button
                          onClick={(e) => handleDeleteSession(e, session.session_id)}
                          className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors"
                          title="Delete Session"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                    {session.summary && (
                      <div className="flex items-center gap-4 mt-3 pt-3 border-t border-gray-100">
                        <div className="flex items-center gap-1">
                          <Users size={12} className="text-gray-400" />
                          <span className="text-xs text-gray-600">
                            {session.summary.peak_count || 0}
                          </span>
                        </div>
                        <div className="flex items-center gap-1">
                          <AlertTriangle size={12} className="text-red-400" />
                          <span className="text-xs text-gray-600">
                            {session.summary.total_abnormal_frames || 0}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-gray-200 bg-gray-50">
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <span>API Connected</span>
          </div>
        </div>
      </aside>

      {/* Automation Alert Toast */}
      {automationAlert && (
        <div className="fixed top-6 right-6 z-50 animate-bounce">
          <div className="bg-red-500 border border-red-600 shadow-xl rounded-lg p-4 max-w-sm flex items-start gap-4 text-white">
            <div className="p-2 bg-red-600 rounded-full">
              <AlertTriangle size={24} className="text-white" />
            </div>
            <div className="flex-1">
              <h4 className="font-bold text-lg mb-1">🚨 Automation Alert Sent</h4>
              <p className="text-sm text-red-100">
                Critical crowd surge detected. Authorities notified through automation workflow.
              </p>
              <div className="mt-2 text-xs font-semibold px-2 py-1 bg-red-600 rounded inline-block">
                Risk Level: {automationAlert.risk_level}
              </div>
            </div>
            <button
              onClick={() => setAutomationAlert(null)}
              className="text-red-200 hover:text-white"
            >
              <XCircle size={20} />
            </button>
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="flex-1 ml-80 p-8 min-h-screen">
        {!selectedSession ? (
          /* Dashboard View */
          <div className="max-w-7xl mx-auto space-y-8">
            {/* Header */}
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-3xl font-bold text-gray-900 mb-2">Real-time Analysis Dashboard</h2>
                <p className="text-gray-600">Monitor crowd density, detect anomalies, and analyze behavior patterns</p>
              </div>
              <div className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium ${processingStatus === 'processing'
                ? 'bg-green-100 text-green-700'
                : processingStatus === 'completed'
                  ? 'bg-blue-100 text-blue-700'
                  : 'bg-gray-100 text-gray-600'
                }`}>
                <div className={`w-2 h-2 rounded-full ${processingStatus === 'processing' ? 'bg-green-500 animate-pulse' : 'bg-gray-400'
                  }`}></div>
                {processingStatus === 'processing' ? 'Processing' :
                  processingStatus === 'completed' ? 'Completed' : 'Idle'}
              </div>
            </div>

            {/* Upload Section - Hidden when processing */}
            {processingStatus !== 'processing' && processingStatus !== 'uploading' && (
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Upload Video</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div
                    className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${file
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-300 hover:border-gray-400 bg-gray-50'
                      }`}
                    onClick={() => document.getElementById('fileInput').click()}
                  >
                    <input
                      type="file"
                      id="fileInput"
                      className="hidden"
                      accept="video/*"
                      onChange={(e) => setFile(e.target.files[0])}
                    />
                    <Upload className={`mx-auto mb-4 ${file ? 'text-blue-600' : 'text-gray-400'}`} size={32} />
                    <p className="text-sm font-medium text-gray-700 mb-1">
                      {file ? file.name : 'Click to select video'}
                    </p>
                    <p className="text-xs text-gray-500">MP4, AVI, MOV supported</p>
                  </div>

                  <div className="flex flex-col justify-center space-y-4">
                    {/* Scene Context Form */}
                    <div className="bg-gray-50 p-4 rounded-lg border border-gray-200 space-y-3">
                      <h4 className="text-sm font-semibold text-gray-700">Scene Context Configuration</h4>
                      <div className="grid grid-cols-2 gap-3 text-sm">
                        <div>
                          <label className="block text-xs font-medium text-gray-500 mb-1">Flow Type</label>
                          <select
                            value={sessionContext.flow_type}
                            onChange={(e) => setSessionContext({ ...sessionContext, flow_type: e.target.value })}
                            className="w-full rounded border-gray-300 shadow-sm p-1.5 focus:ring-blue-500 focus:border-blue-500"
                          >
                            <option value="" disabled>Select Flow Type</option>
                            <option value="STATIC">Static</option>
                            <option value="SLOW">Slow</option>
                            <option value="NORMAL">Normal</option>
                            <option value="FAST_FLOW">Fast Flow</option>
                            <option value="TRANSIT_RUSH">Transit Rush</option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-500 mb-1">Target Capacity</label>
                          <input
                            type="number"
                            value={sessionContext.capacity}
                            onChange={(e) => setSessionContext({ ...sessionContext, capacity: e.target.value })}
                            placeholder="e.g. 120"
                            className="w-full rounded border-gray-300 shadow-sm p-1.5 focus:ring-blue-500 focus:border-blue-500"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-500 mb-1">Sensitivity</label>
                          <select
                            value={sessionContext.sensitivity}
                            onChange={(e) => setSessionContext({ ...sessionContext, sensitivity: e.target.value })}
                            className="w-full rounded border-gray-300 shadow-sm p-1.5 focus:ring-blue-500 focus:border-blue-500"
                          >
                            <option value="" disabled>Select Sensitivity</option>
                            <option value="LOW">Low</option>
                            <option value="MEDIUM">Medium</option>
                            <option value="HIGH">High</option>
                            <option value="PARANOID">Paranoid</option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-500 mb-1">Clustering</label>
                          <select
                            value={sessionContext.clustering}
                            onChange={(e) => setSessionContext({ ...sessionContext, clustering: e.target.value })}
                            className="w-full rounded border-gray-300 shadow-sm p-1.5 focus:ring-blue-500 focus:border-blue-500"
                          >
                            <option value="" disabled>Select Clustering</option>
                            <option value="ALLOWED">Allowed</option>
                            <option value="LIMITED">Limited</option>
                            <option value="DISCOURAGED">Discouraged</option>
                            <option value="NOT_ALLOWED">Not Allowed</option>
                          </select>
                        </div>
                        <div className="col-span-2">
                          <label className="block text-xs font-medium text-gray-500 mb-1">Goal</label>
                          <select
                            value={sessionContext.goal}
                            onChange={(e) => setSessionContext({ ...sessionContext, goal: e.target.value })}
                            className="w-full rounded border-gray-300 shadow-sm p-1.5 focus:ring-blue-500 focus:border-blue-500"
                          >
                            <option value="" disabled>Select Goal</option>
                            <option value="FLOW">Flow</option>
                            <option value="STAY">Stay</option>
                            <option value="QUEUE">Queue</option>
                            <option value="SECURITY">Security</option>
                            <option value="RESTRICTED">Restricted</option>
                            <option value="MONITORING">Monitoring</option>
                          </select>
                        </div>
                      </div>
                    </div>

                    <button
                      disabled={!file || processingStatus === 'processing' || processingStatus === 'uploading' || !sessionContext.flow_type || !sessionContext.capacity || !sessionContext.sensitivity || !sessionContext.clustering || !sessionContext.goal}
                      onClick={handleUpload}
                      className="w-full py-3 px-6 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                    >
                      {processingStatus === 'processing' || processingStatus === 'uploading' ? (
                        <>
                          <Loader2 className="animate-spin" size={18} />
                          Processing...
                        </>
                      ) : (
                        <>
                          <Play size={18} />
                          Start Analysis
                        </>
                      )}
                    </button>
                    {file && (
                      <p className="text-xs text-gray-500 mt-2 text-center">
                        File size: {(file.size / (1024 * 1024)).toFixed(2)} MB
                      </p>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Situation Assessment (AI summary) */}
            {fileId && (
              <SituationCard sessionId={fileId} />
            )}

            {/* Real-time Frame Display - Shown when processing */}
            {processingStatus === 'processing' && (
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-gray-900">Processing Frame</h3>
                  <div className="flex items-center gap-2 text-sm text-gray-600">
                    <Video size={18} />
                    <span>Frame: {realtimeData.frame}</span>
                  </div>
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  {/* Video Frame Display */}
                  <div className="lg:col-span-2">
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="text-sm font-semibold text-gray-700">Live Video Feed</h4>
                    </div>
                    <div className="relative bg-black rounded-lg overflow-hidden flex items-center justify-center" style={{ aspectRatio: '16/9' }}>
                      {realtimeData.frameImage ? (
                        <img
                          key={realtimeData.frame}
                          src={realtimeFrameSrc}
                          alt="Processing frame"
                          className="w-full h-full object-contain relative z-10"
                          id="live-video-img"
                          loading="eager"
                          decoding="sync"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-gray-400">
                          <div className="text-center">
                            <Loader2 className="animate-spin mx-auto mb-2" size={32} />
                            <p className="text-sm">Waiting for frame data...</p>
                          </div>
                        </div>
                      )}
                      {/* Overlay with frame info */}
                      {realtimeData.frameImage && (
                        <div className="absolute top-4 left-4 bg-black bg-opacity-70 text-white px-3 py-2 rounded-lg text-sm font-semibold z-30">
                          Frame #{realtimeData.frame}
                        </div>
                      )}
                    </div>

                    {/* Real-time Remarks Section - Below video frame */}
                    {remarks.length > 0 && (
                      <div className="mt-4 bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg border border-blue-200 p-4">
                        <div className="flex items-center gap-2 mb-3">
                          <Activity className="text-blue-600" size={20} />
                          <h4 className="text-sm font-semibold text-gray-900">Recent Remarks</h4>
                        </div>
                        <div className="space-y-2 max-h-48 overflow-y-auto">
                          {remarks.slice(-5).reverse().map((remark, idx) => (
                            <div key={idx} className={`p-3 rounded-lg border-l-4 ${remark.severity === 'CRITICAL' ? 'bg-red-50 border-red-500' :
                              remark.severity === 'HIGH' ? 'bg-orange-50 border-orange-500' :
                                remark.severity === 'MEDIUM' ? 'bg-yellow-50 border-yellow-500' :
                                  'bg-green-50 border-green-500'
                              }`}>
                              <div className="flex items-start justify-between mb-1">
                                <span className={`text-xs font-semibold px-2 py-0.5 rounded ${remark.severity === 'CRITICAL' ? 'bg-red-200 text-red-800' :
                                  remark.severity === 'HIGH' ? 'bg-orange-200 text-orange-800' :
                                    remark.severity === 'MEDIUM' ? 'bg-yellow-200 text-yellow-800' :
                                      'bg-green-200 text-green-800'
                                  }`}>
                                  {remark.severity}
                                </span>
                                <span className="text-xs text-gray-500">
                                  {new Date(remark.timestamp).toLocaleTimeString()}
                                </span>
                              </div>
                              <p className="text-sm text-gray-800 font-medium">{remark.remark}</p>
                              <div className="flex items-center gap-4 mt-2 text-xs text-gray-600">
                                <span>👥 {remark.avg_human_count?.toFixed(1) || 0}</span>
                                <span>📈 {remark.crowd_growth_rate ? (remark.crowd_growth_rate * 100).toFixed(1) + '%' : '0%'}</span>
                                <span>⚡ {remark.avg_fast_motion_ratio ? (remark.avg_fast_motion_ratio * 100).toFixed(0) + '%' : '0%'}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Frame Data Stats */}
                  <div className="space-y-4">
                    <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
                      <div className="flex items-center gap-2 mb-2">
                        <Users className="text-blue-600" size={20} />
                        <span className="text-sm font-medium text-gray-700">People Count</span>
                      </div>
                      <p className="text-2xl font-bold text-blue-600">{realtimeData.count}</p>
                    </div>

                    <div className="bg-white rounded-lg p-5 border border-gray-100 shadow-sm flex flex-col items-center justify-center">
                      <h4 className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-2">Live Risk Indicator</h4>
                      <RiskGauge
                        level={remarks.length > 0 ? remarks[remarks.length - 1].risk_level : 'NORMAL'}
                        score={remarks.length > 0 ? remarks[remarks.length - 1].risk_score : 0.25}
                      />
                    </div>

                    <div className={`rounded-lg p-4 border ${remarks.length > 0 && ['WARNING', 'CRITICAL'].includes(remarks[remarks.length - 1]?.risk_level) ? 'bg-red-50 border-red-200' : 'bg-green-50 border-green-200'}`}>
                      <div className="flex items-center gap-2 mb-2">
                        <AlertTriangle className={remarks.length > 0 && ['WARNING', 'CRITICAL'].includes(remarks[remarks.length - 1]?.risk_level) ? 'text-red-600' : 'text-green-600'} size={20} />
                        <span className="text-sm font-medium text-gray-700">Current Risk</span>
                      </div>
                      <p className={`text-lg font-bold ${remarks.length > 0 && ['WARNING', 'CRITICAL'].includes(remarks[remarks.length - 1]?.risk_level) ? 'text-red-600' : 'text-green-600'}`}>
                        {remarks.length > 0 ? remarks[remarks.length - 1].risk_level : 'NORMAL'}
                      </p>
                    </div>

                    {realtimeData.restricted && (
                      <div className="bg-yellow-50 rounded-lg p-4 border border-yellow-200">
                        <div className="flex items-center gap-2 mb-2">
                          <Shield className="text-yellow-600" size={20} />
                          <span className="text-sm font-medium text-gray-700">Restricted Entry</span>
                        </div>
                        <p className="text-lg font-bold text-yellow-600">Active</p>
                      </div>
                    )}
                  </div>
                </div>

                {/* Abnormal Frames Gallery - Below video frame */}
                {abnormalFrames.length > 0 && (
                  <div className="mt-6">
                    <div className="flex items-center gap-2 mb-4">
                      <AlertTriangle className="text-red-600" size={20} />
                      <h3 className="text-lg font-semibold text-gray-900">Abnormal Activity Detected</h3>
                      <span className="ml-auto text-sm text-gray-600 bg-red-100 text-red-700 px-3 py-1 rounded-full font-medium">
                        {abnormalFrames.length} {abnormalFrames.length === 1 ? 'Frame' : 'Frames'}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                      {abnormalFrames.map((abnormalFrame, idx) => (
                        <div key={idx} className="bg-red-50 border-2 border-red-200 rounded-lg overflow-hidden hover:shadow-lg transition-shadow">
                          <div className="relative aspect-video bg-black">
                            <img
                              src={abnormalFrame.cloudinary_url}
                              alt={`Abnormal frame ${abnormalFrame.frame}`}
                              className="w-full h-full object-cover"
                              onError={(e) => {
                                e.target.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="100" height="100"%3E%3Crect fill="%23ccc" width="100" height="100"/%3E%3Ctext fill="%23999" x="50%25" y="50%25" text-anchor="middle" dy=".3em"%3EImage not available%3C/text%3E%3C/svg%3E';
                              }}
                            />
                            <div className="absolute top-2 left-2 bg-red-600 text-white px-2 py-1 rounded text-xs font-semibold">
                              Frame #{abnormalFrame.frame}
                            </div>
                          </div>
                          <div className="p-3">
                            <div className="flex items-center justify-between text-xs mb-1">
                              <span className="text-gray-600">People: <span className="font-semibold text-gray-900">{abnormalFrame.human_count}</span></span>
                              <span className="text-gray-600">Violations: <span className="font-semibold text-red-600">{abnormalFrame.violate_count}</span></span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Remarks Analytics Graphs - Below remarks */}
                {remarks.length > 0 && (
                  <div className="mt-6">
                    <div className="flex items-center gap-2 mb-4">
                      <BarChart3 className="text-blue-600" size={20} />
                      <h3 className="text-lg font-semibold text-gray-900">Remarks Analytics</h3>
                      <span className="ml-auto text-sm text-gray-600 bg-blue-100 text-blue-700 px-3 py-1 rounded-full font-medium">
                        {remarks.length} {remarks.length === 1 ? 'Window' : 'Windows'}
                      </span>
                    </div>
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                      {/* Crowd Count Trend from Remarks */}
                      <div className="bg-white rounded-lg border border-gray-200 p-4">
                        <h4 className="text-sm font-semibold text-gray-700 mb-4">Crowd Count Trend</h4>
                        <div className="h-64">
                          <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={remarks.map((r, idx) => ({
                              time: r.timestamp ? (typeof r.timestamp === 'string' ? new Date(r.timestamp).toLocaleTimeString() : new Date(r.timestamp).toLocaleTimeString()) : `Window ${idx + 1}`,
                              avg: r.avg_human_count || 0,
                              max: r.max_human_count || 0
                            }))}>
                              <defs>
                                <linearGradient id="colorAvgReal" x1="0" y1="0" x2="0" y2="1">
                                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                                </linearGradient>
                                <linearGradient id="colorMaxReal" x1="0" y1="0" x2="0" y2="1">
                                  <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                                </linearGradient>
                              </defs>
                              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                              <XAxis
                                dataKey="time"
                                stroke="#6b7280"
                                tick={{ fontSize: 10 }}
                                angle={-45}
                                textAnchor="end"
                                height={60}
                              />
                              <YAxis stroke="#6b7280" tick={{ fontSize: 12 }} />
                              <Tooltip />
                              <Legend />
                              <Area type="monotone" dataKey="avg" stroke="#3b82f6" fillOpacity={1} fill="url(#colorAvgReal)" name="Avg Count" />
                              <Area type="monotone" dataKey="max" stroke="#ef4444" fillOpacity={1} fill="url(#colorMaxReal)" name="Max Count" />
                            </AreaChart>
                          </ResponsiveContainer>
                        </div>
                      </div>

                      {/* Motion & Growth Analysis */}
                      <div className="bg-white rounded-lg border border-gray-200 p-4">
                        <h4 className="text-sm font-semibold text-gray-700 mb-4">Motion & Growth Analysis</h4>
                        <div className="h-64">
                          <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={remarks.map((r, idx) => ({
                              time: r.timestamp ? (typeof r.timestamp === 'string' ? new Date(r.timestamp).toLocaleTimeString() : new Date(r.timestamp).toLocaleTimeString()) : `Window ${idx + 1}`,
                              speed: r.avg_motion_speed || 0,
                              growth: r.crowd_growth_rate ? (r.crowd_growth_rate * 100) : 0,
                              fastRatio: r.avg_fast_motion_ratio ? (r.avg_fast_motion_ratio * 100) : 0
                            }))}>
                              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                              <XAxis
                                dataKey="time"
                                stroke="#6b7280"
                                tick={{ fontSize: 10 }}
                                angle={-45}
                                textAnchor="end"
                                height={60}
                              />
                              <YAxis yAxisId="left" stroke="#6b7280" tick={{ fontSize: 12 }} />
                              <YAxis yAxisId="right" orientation="right" stroke="#f59e0b" tick={{ fontSize: 12 }} />
                              <Tooltip />
                              <Legend />
                              <Line yAxisId="left" type="monotone" dataKey="speed" stroke="#3b82f6" strokeWidth={2} name="Avg Speed" />
                              <Line yAxisId="right" type="monotone" dataKey="growth" stroke="#10b981" strokeWidth={2} name="Growth %" />
                              <Line yAxisId="right" type="monotone" dataKey="fastRatio" stroke="#f59e0b" strokeWidth={2} name="Fast Motion %" />
                            </LineChart>
                          </ResponsiveContainer>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              <StatCard
                title="People Count"
                value={realtimeData.count}
                icon={Users}
                color="blue"
                subtitle="Current detection"
              />
              <StatCard
                title="Restricted Access"
                value={realtimeData.restricted ? "ACTIVE" : "NONE"}
                icon={Shield}
                color={realtimeData.restricted ? "yellow" : "blue"}
                subtitle="Zone security status"
              />
              <StatCard
                title="Current Risk"
                value={remarks.length > 0 ? remarks[remarks.length - 1].risk_level || 'NORMAL' : 'NORMAL'}
                icon={AlertTriangle}
                color={remarks.length > 0 && ['WARNING', 'CRITICAL'].includes(remarks[remarks.length - 1]?.risk_level) ? "red" : "green"}
                subtitle="Context engine status"
              />
              <StatCard
                title="Frame"
                value={realtimeData.frame}
                icon={Video}
                color="purple"
                subtitle="Processing progress"
              />
            </div>

            {/* Charts Section */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Real-time People Count Chart */}
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <div className="flex items-center justify-between mb-6">
                  <h3 className="text-lg font-semibold text-gray-900">People Count Over Time</h3>
                  <BarChart3 size={20} className="text-gray-400" />
                </div>
                <div className="h-64">
                  {chartData.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                        <XAxis
                          dataKey="time"
                          stroke="#6b7280"
                          tick={{ fontSize: 12 }}
                          label={{ value: 'Frame', position: 'insideBottom', offset: -5 }}
                        />
                        <YAxis
                          stroke="#6b7280"
                          tick={{ fontSize: 12 }}
                          label={{ value: 'Count', angle: -90, position: 'insideLeft' }}
                        />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: 'white',
                            border: '1px solid #e5e7eb',
                            borderRadius: '8px'
                          }}
                        />
                        <Legend />
                        <Line
                          type="monotone"
                          dataKey="count"
                          stroke="#3b82f6"
                          strokeWidth={2}
                          dot={false}
                          name="People Count"
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="h-full flex items-center justify-center text-gray-400">
                      <div className="text-center">
                        <BarChart3 size={32} className="mx-auto mb-2" />
                        <p className="text-sm">No data yet. Start analysis to see real-time data.</p>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Risk Meter Gauge Card */}
              <div className="bg-white rounded-xl shadow-lg border border-gray-100 p-6 flex flex-col items-center justify-center relative overflow-hidden">
                <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-green-500 via-yellow-400 to-red-500"></div>
                <div className="w-full flex items-center justify-between mb-8">
                  <h3 className="text-lg font-bold text-gray-900">Crowd Risk Level</h3>
                  <Zap size={20} className="text-yellow-500" />
                </div>
                <div className="w-full py-4">
                  <RiskGauge level={remarks.length > 0 ? remarks[remarks.length - 1].risk_level : 'NORMAL'} />
                </div>
                <p className="text-xs text-gray-500 text-center mt-2 max-w-[200px]">
                  Visual assessment of the current crowd scenario risk score (0-100%)
                </p>
              </div>
            </div>

            {/* Risk Timeline Section - Added under analytics graphs */}
            {remarks.length > 0 && (
              <div className="mt-8">
                <RiskTimelineChart data={remarks} />
              </div>
            )}

            {/* Current Session Info */}
            {currentSession && (
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Current Session</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <p className="text-xs text-gray-500 mb-1">File ID</p>
                    <p className="text-sm font-mono text-gray-900">{currentSession.file_id}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 mb-1">Filename</p>
                    <p className="text-sm font-medium text-gray-900">{currentSession.filename}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 mb-1">Status</p>
                    <p className="text-sm font-medium text-gray-900 capitalize">{currentSession.status}</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        ) : (
          /* Session Details View */
          <div className="max-w-7xl mx-auto space-y-8">
            {sessionDetails ? (
              <>
                {/* Header */}
                <div className="flex items-center justify-between">
                  <div>
                    <button
                      onClick={() => {
                        setSelectedSession(null);
                        setSessionDetails(null);
                      }}
                      className="text-sm text-gray-600 hover:text-gray-900 mb-2 flex items-center gap-2"
                    >
                      <ChevronRight size={16} className="rotate-180" />
                      Back to Dashboard
                    </button>
                    <h2 className="text-3xl font-bold text-gray-900 mb-2">
                      {sessionDetails.session?.filename || 'Session Details'}
                    </h2>
                    <p className="text-gray-600">
                      Analysis completed on {formatDate(sessionDetails.session?.end_time || sessionDetails.session?.start_time)}
                    </p>
                  </div>
                  <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2">
                    <Download size={18} />
                    Export Results
                  </button>
                </div>

                {/* Summary Stats */}
                <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
                  <StatCard
                    title="Avg Count"
                    value={sessionDetails.session?.summary?.avg_count || 0}
                    icon={Users}
                    color="blue"
                    subtitle="Average density"
                  />
                  <StatCard
                    title="Peak Count"
                    value={sessionDetails.session?.summary?.peak_count || 0}
                    icon={TrendingUp}
                    color="green"
                    subtitle="Maximum detected"
                  />
                  <StatCard
                    title="Risk Alerts"
                    value={sessionDetails.aggregated_windows ? sessionDetails.aggregated_windows.filter(w => ['WARNING', 'CRITICAL'].includes(w.risk_level || w.severity)).length : 0}
                    icon={AlertTriangle}
                    color="red"
                    subtitle="High risk windows"
                  />
                  <StatCard
                    title="Risk Score"
                    value={sessionDetails.session?.summary?.risk_score?.toFixed(2) || "0.25"}
                    icon={Zap}
                    color="yellow"
                    subtitle="Context assessment"
                  />
                  <StatCard
                    title="Frame Rate"
                    value={sessionDetails.session?.video_meta?.VID_FPS?.toFixed(1) || sessionDetails.session?.video_meta?.fps?.toFixed(1) || '30.0'}
                    icon={Zap}
                    color="purple"
                    subtitle="FPS"
                  />
                </div>

                <div className="flex border-b border-gray-200 mt-6 mb-6">
                  <button
                    onClick={() => setHistoricalTab('video')}
                    className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${historicalTab === 'video' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}`}
                  >
                    Analysis / Data
                  </button>
                  <button
                    onClick={() => setHistoricalTab('heatmap')}
                    className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${historicalTab === 'heatmap' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}`}
                  >
                    Final Heatmap
                  </button>
                </div>

                {historicalTab === 'heatmap' ? (
                  <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-6">Final Historical Heatmap</h3>
                    {sessionDetails.heatmap_url ? (
                      <div className="relative bg-black rounded-lg overflow-hidden flex items-center justify-center" style={{ aspectRatio: '16/9' }}>
                        <img src={sessionDetails.heatmap_url} alt="Heatmap" className="w-full h-full object-contain" />
                      </div>
                    ) : (
                      <div className="flex flex-col items-center justify-center py-12 text-gray-400">
                        <Layers size={48} className="mx-auto mb-4 text-gray-300" />
                        <p>No heatmap generated for this session.</p>
                      </div>
                    )}
                  </div>
                ) : (
                  <>
                    {/* Charts */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                      {/* People Count Trend */}
                      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                        <h3 className="text-lg font-semibold text-gray-900 mb-6">People Count Trend</h3>
                        <div className="h-80">
                          {sessionDetails.trends && sessionDetails.trends.length > 0 ? (
                            <ResponsiveContainer width="100%" height="100%">
                              <AreaChart data={prepareChartData(sessionDetails.trends)}>
                                <defs>
                                  <linearGradient id="colorCountDetail" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                                  </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                                <XAxis
                                  dataKey="frame"
                                  stroke="#6b7280"
                                  tick={{ fontSize: 12 }}
                                  label={{ value: 'Frame', position: 'insideBottom', offset: -5 }}
                                />
                                <YAxis
                                  stroke="#6b7280"
                                  tick={{ fontSize: 12 }}
                                  label={{ value: 'People Count', angle: -90, position: 'insideLeft' }}
                                />
                                <Tooltip
                                  contentStyle={{
                                    backgroundColor: 'white',
                                    border: '1px solid #e5e7eb',
                                    borderRadius: '8px'
                                  }}
                                />
                                <Area
                                  type="monotone"
                                  dataKey="count"
                                  stroke="#3b82f6"
                                  strokeWidth={2}
                                  fillOpacity={1}
                                  fill="url(#colorCountDetail)"
                                />
                              </AreaChart>
                            </ResponsiveContainer>
                          ) : (
                            <div className="h-full flex items-center justify-center text-gray-400">
                              <p>No trend data available</p>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Risk Level Distribution */}
                      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                        <h3 className="text-lg font-semibold text-gray-900 mb-6">Risk Level Distribution</h3>
                        <div className="h-80">
                          {getRiskStats(sessionDetails) ? (
                            <ResponsiveContainer width="100%" height="100%">
                              <PieChart>
                                <Pie
                                  data={getRiskStats(sessionDetails)}
                                  cx="50%"
                                  cy="50%"
                                  labelLine={false}
                                  label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                                  outerRadius={100}
                                  dataKey="value"
                                >
                                  {getRiskStats(sessionDetails).map((entry, index) => {
                                    // Dynamic colors for risk
                                    const colors = {
                                      "Normal": "#10b981",
                                      "Busy": "#f59e0b",
                                      "Warning": "#f50b0bff",
                                      "Critical": "#ef4444"
                                    };
                                    return <Cell key={`cell-${index}`} fill={colors[entry.name] || COLORS[index % COLORS.length]} />;
                                  })}
                                </Pie>
                                <Tooltip />
                                <Legend />
                              </PieChart>
                            </ResponsiveContainer>
                          ) : (
                            <div className="h-full flex items-center justify-center text-gray-400">
                              <p>No distribution data available</p>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Violations Chart */}
                    {/* Risk Evolution Timeline (Session View) */}
                    {sessionDetails.aggregated_windows && sessionDetails.aggregated_windows.length > 0 && (
                      <div className="mt-8">
                        <RiskTimelineChart data={sessionDetails.aggregated_windows} />
                      </div>
                    )}

                    {/* Abnormal Frames Gallery */}
                    {sessionDetails.abnormal_frames && sessionDetails.abnormal_frames.length > 0 && (
                      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                        <div className="flex items-center justify-between mb-6">
                          <div className="flex items-center gap-3">
                            <AlertTriangle className="text-red-500" size={24} />
                            <h3 className="text-lg font-semibold text-gray-900">Abnormal Activity Frames</h3>
                          </div>
                          <span className="text-sm text-gray-600 bg-red-100 text-red-700 px-3 py-1 rounded-full font-medium">
                            {sessionDetails.abnormal_frames.length} {sessionDetails.abnormal_frames.length === 1 ? 'Frame' : 'Frames'}
                          </span>
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                          {sessionDetails.abnormal_frames.map((frame, idx) => (
                            <div key={idx} className="bg-red-50 border-2 border-red-200 rounded-lg overflow-hidden hover:shadow-lg transition-all cursor-pointer group">
                              <div className="relative aspect-video bg-black">
                                <img
                                  src={frame.cloudinary_url}
                                  alt={`Abnormal frame ${frame.frame}`}
                                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200"
                                  onError={(e) => {
                                    e.target.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="100" height="100"%3E%3Crect fill="%23ccc" width="100" height="100"/%3E%3Ctext fill="%23999" x="50%25" y="50%25" text-anchor="middle" dy=".3em"%3EImage not available%3C/text%3E%3C/svg%3E';
                                  }}
                                />
                                <div className="absolute top-2 left-2 bg-red-600 text-white px-2 py-1 rounded text-xs font-semibold">
                                  Frame #{frame.frame}
                                </div>
                              </div>
                              <div className="p-3">
                                <div className="space-y-2">
                                  <div className="flex items-center justify-between text-xs">
                                    <span className="text-gray-600">People Count</span>
                                    <span className="font-semibold text-gray-900">{frame.human_count || 0}</span>
                                  </div>
                                  <div className="flex items-center justify-between text-xs">
                                    <span className="text-gray-600">SD Violations</span>
                                    <span className="font-semibold text-red-600">{frame.violate_count || 0}</span>
                                  </div>
                                  {frame.restricted_entry && (
                                    <div className="flex items-center gap-1 text-xs text-yellow-600">
                                      <Shield size={12} />
                                      <span>Restricted Entry</span>
                                    </div>
                                  )}
                                  {frame.timestamp && (
                                    <div className="text-xs text-gray-500 pt-1 border-t border-gray-200">
                                      {new Date(frame.timestamp).toLocaleString()}
                                    </div>
                                  )}
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Remark History Section */}
                    {sessionDetails && (
                      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                        <div className="flex items-center gap-3 mb-6">
                          <Activity className="text-blue-600" size={24} />
                          <h3 className="text-lg font-semibold text-gray-900">Remark History & Analytics</h3>
                          {sessionDetails.aggregated_windows && sessionDetails.aggregated_windows.length > 0 && (
                            <span className="ml-auto text-sm text-gray-600 bg-blue-100 text-blue-700 px-3 py-1 rounded-full font-medium">
                              {sessionDetails.aggregated_windows.length} Windows
                            </span>
                          )}
                        </div>

                        {sessionDetails.aggregated_windows && sessionDetails.aggregated_windows.length > 0 ? (
                          <>

                            {/* Remarks Timeline */}
                            <div className="mb-6">
                              <h4 className="text-sm font-semibold text-gray-700 mb-3">Remarks Timeline</h4>
                              <div className="space-y-2 max-h-64 overflow-y-auto">
                                {sessionDetails.aggregated_windows.map((window, idx) => (
                                  <div key={idx} className={`p-3 rounded-lg border-l-4 ${window.severity === 'CRITICAL' ? 'bg-red-50 border-red-500' :
                                    window.severity === 'HIGH' ? 'bg-orange-50 border-orange-500' :
                                      window.severity === 'MEDIUM' ? 'bg-yellow-50 border-yellow-500' :
                                        'bg-green-50 border-green-500'
                                    }`} onClick={() => setAlertDrawerOpen(true)}>
                                    <div className="flex items-start justify-between mb-2">
                                      <div className="flex items-center gap-2">
                                        <span className={`text-xs font-semibold px-2 py-0.5 rounded ${window.severity === 'CRITICAL' ? 'bg-red-200 text-red-800' :
                                          window.severity === 'HIGH' ? 'bg-orange-200 text-orange-800' :
                                            window.severity === 'MEDIUM' ? 'bg-yellow-200 text-yellow-800' :
                                              'bg-green-200 text-green-800'
                                          }`}>
                                          {window.severity}
                                        </span>
                                        <span className="text-xs text-gray-500">
                                          {window.window_start ? (typeof window.window_start === 'string' ? new Date(window.window_start).toLocaleTimeString() : new Date(window.window_start).toLocaleTimeString()) : 'N/A'} - {window.window_end ? (typeof window.window_end === 'string' ? new Date(window.window_end).toLocaleTimeString() : new Date(window.window_end).toLocaleTimeString()) : 'N/A'}
                                        </span>
                                      </div>
                                    </div>
                                    <p className="text-sm text-gray-800 font-medium mb-2">{window.remark}</p>
                                    <div className="flex items-center gap-4 text-xs text-gray-600">
                                      <span>👥 Avg: {window.avg_human_count?.toFixed(1) || 0} | Max: {window.max_human_count || 0}</span>
                                      <span>📈 Growth: {window.crowd_growth_rate ? (window.crowd_growth_rate * 100).toFixed(1) + '%' : '0%'}</span>
                                      <span>⚡ Fast Motion: {window.avg_fast_motion_ratio ? (window.avg_fast_motion_ratio * 100).toFixed(0) + '%' : '0%'}</span>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>

                            {/* Numerical Data Graphs */}
                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                              {/* Crowd Count Over Time */}
                              <div>
                                <h4 className="text-sm font-semibold text-gray-700 mb-4">Crowd Count Trend</h4>
                                <div className="h-64">
                                  <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={sessionDetails.aggregated_windows.map((w, idx) => ({
                                      time: w.window_end ? (typeof w.window_end === 'string' ? new Date(w.window_end).toLocaleTimeString() : new Date(w.window_end).toLocaleTimeString()) : `Window ${idx + 1}`,
                                      avg: w.avg_human_count || 0,
                                      max: w.max_human_count || 0
                                    }))}>
                                      <defs>
                                        <linearGradient id="colorAvg" x1="0" y1="0" x2="0" y2="1">
                                          <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                                          <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                                        </linearGradient>
                                        <linearGradient id="colorMax" x1="0" y1="0" x2="0" y2="1">
                                          <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                                          <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                                        </linearGradient>
                                      </defs>
                                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                                      <XAxis
                                        dataKey="time"
                                        stroke="#6b7280"
                                        tick={{ fontSize: 10 }}
                                        angle={-45}
                                        textAnchor="end"
                                        height={60}
                                      />
                                      <YAxis stroke="#6b7280" tick={{ fontSize: 12 }} />
                                      <Tooltip />
                                      <Legend />
                                      <Area type="monotone" dataKey="avg" stroke="#3b82f6" fillOpacity={1} fill="url(#colorAvg)" name="Avg Count" />
                                      <Area type="monotone" dataKey="max" stroke="#ef4444" fillOpacity={1} fill="url(#colorMax)" name="Max Count" />
                                    </AreaChart>
                                  </ResponsiveContainer>
                                </div>
                              </div>

                              {/* Motion Speed & Fast Motion Ratio */}
                              <div>
                                <h4 className="text-sm font-semibold text-gray-700 mb-4">Motion Analysis</h4>
                                <div className="h-64">
                                  <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={sessionDetails.aggregated_windows.map((w, idx) => ({
                                      time: w.window_end ? (typeof w.window_end === 'string' ? new Date(w.window_end).toLocaleTimeString() : new Date(w.window_end).toLocaleTimeString()) : `Window ${idx + 1}`,
                                      speed: w.avg_motion_speed || 0,
                                      fastRatio: (w.avg_fast_motion_ratio || 0) * 100
                                    }))}>
                                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                                      <XAxis
                                        dataKey="time"
                                        stroke="#6b7280"
                                        tick={{ fontSize: 10 }}
                                        angle={-45}
                                        textAnchor="end"
                                        height={60}
                                      />
                                      <YAxis yAxisId="left" stroke="#6b7280" tick={{ fontSize: 12 }} />
                                      <YAxis yAxisId="right" orientation="right" stroke="#f59e0b" tick={{ fontSize: 12 }} />
                                      <Tooltip />
                                      <Legend />
                                      <Line yAxisId="left" type="monotone" dataKey="speed" stroke="#3b82f6" strokeWidth={2} name="Avg Speed" />
                                      <Line yAxisId="right" type="monotone" dataKey="fastRatio" stroke="#f59e0b" strokeWidth={2} name="Fast Motion %" />
                                    </LineChart>
                                  </ResponsiveContainer>
                                </div>
                              </div>

                              {/* Density Score */}
                              <div>
                                <h4 className="text-sm font-semibold text-gray-700 mb-4">Crowd Density Score</h4>
                                <div className="h-64">
                                  <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={sessionDetails.aggregated_windows.map((w, idx) => ({
                                      time: w.window_end ? (typeof w.window_end === 'string' ? new Date(w.window_end).toLocaleTimeString() : new Date(w.window_end).toLocaleTimeString()) : `Window ${idx + 1}`,
                                      density: w.max_density_score || 0
                                    }))}>
                                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                                      <XAxis
                                        dataKey="time"
                                        stroke="#6b7280"
                                        tick={{ fontSize: 10 }}
                                        angle={-45}
                                        textAnchor="end"
                                        height={60}
                                      />
                                      <YAxis stroke="#6b7280" tick={{ fontSize: 12 }} />
                                      <Tooltip />
                                      <Bar dataKey="density" fill="#8b5cf6" name="Max Density" />
                                    </BarChart>
                                  </ResponsiveContainer>
                                </div>
                              </div>

                              {/* Crowd Growth Rate */}
                              <div>
                                <h4 className="text-sm font-semibold text-gray-700 mb-4">Crowd Growth Rate</h4>
                                <div className="h-64">
                                  <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={sessionDetails.aggregated_windows.map((w, idx) => ({
                                      time: w.window_end ? (typeof w.window_end === 'string' ? new Date(w.window_end).toLocaleTimeString() : new Date(w.window_end).toLocaleTimeString()) : `Window ${idx + 1}`,
                                      growth: (w.crowd_growth_rate || 0) * 100
                                    }))}>
                                      <defs>
                                        <linearGradient id="colorGrowth" x1="0" y1="0" x2="0" y2="1">
                                          <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                                          <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                                        </linearGradient>
                                      </defs>
                                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                                      <XAxis
                                        dataKey="time"
                                        stroke="#6b7280"
                                        tick={{ fontSize: 10 }}
                                        angle={-45}
                                        textAnchor="end"
                                        height={60}
                                      />
                                      <YAxis stroke="#6b7280" tick={{ fontSize: 12 }} />
                                      <Tooltip formatter={(value) => `${value.toFixed(1)}%`} />
                                      <Area type="monotone" dataKey="growth" stroke="#10b981" fillOpacity={1} fill="url(#colorGrowth)" name="Growth Rate %" />
                                    </AreaChart>
                                  </ResponsiveContainer>
                                </div>
                              </div>
                            </div>
                          </>
                        ) : (
                          <div className="text-center py-12">
                            <Activity className="mx-auto text-gray-300 mb-3" size={48} />
                            <p className="text-sm text-gray-500 mb-2">No aggregated data available yet</p>
                            <p className="text-xs text-gray-400">Aggregation runs every 5 seconds. Data will appear here once windows are processed.</p>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Ask Drishti assistant (session mode) */}
                    <AskAssistant sessionId={selectedSession} mode="session" />

                    {/* No Abnormal Statistics block */}
                  </>
                )}
              </>
            ) : (
              <div className="flex items-center justify-center h-96">
                <Loader2 className="animate-spin text-gray-400" size={32} />
              </div>
            )}
          </div>
        )}
      </main>

      {/* Global AI helpers */}
      <AlertExplanationDrawer
        sessionId={selectedSession || (currentSession?.file_id ?? null)}
        open={alertDrawerOpen}
        onClose={() => setAlertDrawerOpen(false)}
      />
      <AskAssistant sessionId={selectedSession || fileId || (currentSession?.file_id ?? null)} mode="dashboard" />
    </div>
  );
}

export default App;
