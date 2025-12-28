import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  Upload, Play, Loader2, LayoutDashboard, History, Settings,
  Users, AlertTriangle, Shield, Clock, ChevronRight, Download,
  Activity, BarChart3, Info, TrendingUp, Video, FileVideo,
  Zap, Eye, CheckCircle2, XCircle, Trash2
} from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, BarChart, Bar, LineChart, Line, PieChart, Pie, Cell
} from 'recharts';

const API_BASE = "http://localhost:8000";
const WS_URL = "ws://localhost:8000/ws";

const COLORS = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6'];

function App() {
  const [file, setFile] = useState(null);
  const [processingStatus, setProcessingStatus] = useState('idle'); // idle, uploading, processing, completed
  const [fileId, setFileId] = useState(null);
  const [currentSession, setCurrentSession] = useState(null);
  const [realtimeData, setRealtimeData] = useState({
    count: 0,
    violations: 0,
    abnormal: false,
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

  const ws = useRef(null);

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
              setRealtimeData({
                count: msg.data.human_count || 0,
                violations: msg.data.violate_count || 0,
                abnormal: msg.data.abnormal || false,
                restricted: msg.data.restricted_entry || false,
                frame: msg.data.frame || 0,
                frameImage: msg.data.frame_image || null  // Base64 encoded frame image
              });
              
              // Track abnormal frames with Cloudinary URL
              if (msg.data.abnormal && msg.data.cloudinary_url) {
                setAbnormalFrames(prev => {
                  // Check if this frame already exists (avoid duplicates)
                  const exists = prev.some(f => f.frame === msg.data.frame);
                  if (!exists) {
                    return [...prev, {
                      frame: msg.data.frame || 0,
                      cloudinary_url: msg.data.cloudinary_url,
                      human_count: msg.data.human_count || 0,
                      violate_count: msg.data.violate_count || 0,
                      timestamp: new Date().toISOString()
                    }].sort((a, b) => a.frame - b.frame); // Sort by frame number
                  }
                  return prev;
                });
              }
              setChartData(prev => {
                const newData = [...prev.slice(-99), {
                  time: msg.data.frame || 0,
                  count: msg.data.human_count || 0,
                  violations: msg.data.violate_count || 0,
                  abnormal: msg.data.abnormal ? 1 : 0
                }];
                return newData;
              });
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
    setProcessingStatus('uploading');
    setChartData([]);
    setRealtimeData({ count: 0, violations: 0, abnormal: false, restricted: false, frame: 0, frameImage: null });
    setAbnormalFrames([]); // Reset abnormal frames
    setCurrentSession(null);

    const formData = new FormData();
    formData.append('file', file);

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
      setSessionDetails(res.data);
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
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 hover:shadow-md transition-all">
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
      violations: item.violations !== undefined ? item.violations : (item.violate_count || 0),
      abnormal: (item.abnormal !== undefined ? item.abnormal : item.abnormal_activity) ? 1 : 0
    }));
  };

  // Calculate statistics for pie chart
  const getAbnormalStats = (session) => {
    if (!session || !session.trends) return null;
    const total = session.trends.length;
    const abnormal = session.trends.filter(t => t.abnormal !== undefined ? t.abnormal : t.abnormal_activity).length;
    return [
      { name: 'Normal', value: total - abnormal },
      { name: 'Abnormal', value: abnormal }
    ];
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

                  <div className="flex flex-col justify-center">
                    <button
                      disabled={!file || processingStatus === 'processing' || processingStatus === 'uploading'}
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
                    <div className="relative bg-black rounded-lg overflow-hidden" style={{ aspectRatio: '16/9' }}>
                      {realtimeData.frameImage ? (
                        <img
                          src={`data:image/jpeg;base64,${realtimeData.frameImage}`}
                          alt="Processing frame"
                          className="w-full h-full object-contain"
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
                        <div className="absolute top-4 left-4 bg-black bg-opacity-70 text-white px-3 py-2 rounded-lg text-sm font-semibold">
                          Frame #{realtimeData.frame}
                        </div>
                      )}
                    </div>
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

                    <div className="bg-red-50 rounded-lg p-4 border border-red-200">
                      <div className="flex items-center gap-2 mb-2">
                        <Shield className="text-red-600" size={20} />
                        <span className="text-sm font-medium text-gray-700">SD Violations</span>
                      </div>
                      <p className="text-2xl font-bold text-red-600">{realtimeData.violations}</p>
                    </div>

                    <div className={`rounded-lg p-4 border ${realtimeData.abnormal ? 'bg-red-50 border-red-200' : 'bg-green-50 border-green-200'}`}>
                      <div className="flex items-center gap-2 mb-2">
                        <AlertTriangle className={realtimeData.abnormal ? 'text-red-600' : 'text-green-600'} size={20} />
                        <span className="text-sm font-medium text-gray-700">Anomaly Status</span>
                      </div>
                      <p className={`text-lg font-bold ${realtimeData.abnormal ? 'text-red-600' : 'text-green-600'}`}>
                        {realtimeData.abnormal ? 'Detected' : 'Normal'}
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
                title="SD Violations"
                value={realtimeData.violations}
                icon={Shield}
                color="red"
                subtitle="Social distancing"
              />
              <StatCard
                title="Anomaly Status"
                value={realtimeData.abnormal ? "Detected" : "Normal"}
                icon={AlertTriangle}
                color={realtimeData.abnormal ? "red" : "green"}
                subtitle="Unusual activity"
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

              {/* Violations Chart */}
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <div className="flex items-center justify-between mb-6">
                  <h3 className="text-lg font-semibold text-gray-900">Violations & Anomalies</h3>
                  <Activity size={20} className="text-gray-400" />
                </div>
                <div className="h-64">
                  {chartData.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={chartData}>
                        <defs>
                          <linearGradient id="colorViolations" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#ef4444" stopOpacity={0.8} />
                            <stop offset="95%" stopColor="#ef4444" stopOpacity={0.1} />
                          </linearGradient>
                          <linearGradient id="colorAbnormal" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.8} />
                            <stop offset="95%" stopColor="#f59e0b" stopOpacity={0.1} />
                          </linearGradient>
                        </defs>
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
                        <Area
                          type="monotone"
                          dataKey="violations"
                          stroke="#ef4444"
                          fillOpacity={1}
                          fill="url(#colorViolations)"
                          name="SD Violations"
                        />
                        <Area
                          type="monotone"
                          dataKey="abnormal"
                          stroke="#f59e0b"
                          fillOpacity={1}
                          fill="url(#colorAbnormal)"
                          name="Abnormal Activity"
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="h-full flex items-center justify-center text-gray-400">
                      <div className="text-center">
                        <Activity size={32} className="mx-auto mb-2" />
                        <p className="text-sm">No data yet. Start analysis to see real-time data.</p>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>

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
                    title="Abnormal"
                    value={sessionDetails.session?.summary?.total_abnormal_frames || 0}
                    icon={AlertTriangle}
                    color="red"
                    subtitle="Anomaly frames"
                  />
                  <StatCard
                    title="Violations"
                    value={sessionDetails.session?.summary?.total_violations || 0}
                    icon={Shield}
                    color="yellow"
                    subtitle="SD breaches"
                  />
                  <StatCard
                    title="Frame Rate"
                    value={sessionDetails.session?.video_meta?.VID_FPS?.toFixed(1) || sessionDetails.session?.video_meta?.fps?.toFixed(1) || '30.0'}
                    icon={Zap}
                    color="purple"
                    subtitle="FPS"
                  />
                </div>

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

                  {/* Abnormal Activity Distribution */}
                  <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-6">Activity Distribution</h3>
                    <div className="h-80">
                      {getAbnormalStats(sessionDetails) ? (
                        <ResponsiveContainer width="100%" height="100%">
                          <PieChart>
                            <Pie
                              data={getAbnormalStats(sessionDetails)}
                              cx="50%"
                              cy="50%"
                              labelLine={false}
                              label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                              outerRadius={100}
                              fill="#8884d8"
                              dataKey="value"
                            >
                              {getAbnormalStats(sessionDetails).map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                              ))}
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

                {/* Violations and Abnormal Activity Chart */}
                <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-6">Violations & Abnormal Activity</h3>
                  <div className="h-80">
                    {sessionDetails.trends && sessionDetails.trends.length > 0 ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={prepareChartData(sessionDetails.trends)}>
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
                          <Bar dataKey="violations" fill="#ef4444" name="SD Violations" />
                          <Bar dataKey="abnormal" fill="#f59e0b" name="Abnormal Activity" />
                        </BarChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="h-full flex items-center justify-center text-gray-400">
                        <p>No violation data available</p>
                      </div>
                    )}
                  </div>
                </div>

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

                {/* Abnormal Statistics */}
                {sessionDetails.abnormal_stats && (
                  <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                    <div className="flex items-center gap-3 mb-6">
                      <AlertTriangle className="text-red-500" size={24} />
                      <h3 className="text-lg font-semibold text-gray-900">Statistical Analysis</h3>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="space-y-4">
                        <h4 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Cleaned Statistics</h4>
                        <div className="space-y-3">
                          <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                            <span className="text-sm text-gray-600">Mean Energy</span>
                            <span className="text-sm font-semibold text-gray-900">
                              {sessionDetails.abnormal_stats.cleaned?.mean?.toFixed(4) || 'N/A'}
                            </span>
                          </div>
                          <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                            <span className="text-sm text-gray-600">Kurtosis</span>
                            <span className="text-sm font-semibold text-gray-900">
                              {sessionDetails.abnormal_stats.cleaned?.kurtosis?.toFixed(4) || 'N/A'}
                            </span>
                          </div>
                          <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                            <span className="text-sm text-gray-600">Skewness</span>
                            <span className="text-sm font-semibold text-gray-900">
                              {sessionDetails.abnormal_stats.cleaned?.skew?.toFixed(4) || 'N/A'}
                            </span>
                          </div>
                          <div className="flex justify-between items-center p-3 bg-red-50 rounded-lg">
                            <span className="text-sm text-gray-600">Outliers Removed</span>
                            <span className="text-sm font-semibold text-red-600">
                              {sessionDetails.abnormal_stats.cleaned?.outliers_removed || 0}
                            </span>
                          </div>
                        </div>
                      </div>
                      <div className="space-y-4">
                        <h4 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Original Statistics</h4>
                        <div className="space-y-3">
                          <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                            <span className="text-sm text-gray-600">Mean Energy</span>
                            <span className="text-sm font-semibold text-gray-900">
                              {sessionDetails.abnormal_stats.original?.mean?.toFixed(4) || 'N/A'}
                            </span>
                          </div>
                          <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                            <span className="text-sm text-gray-600">Kurtosis</span>
                            <span className="text-sm font-semibold text-gray-900">
                              {sessionDetails.abnormal_stats.original?.kurtosis?.toFixed(4) || 'N/A'}
                            </span>
                          </div>
                          <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                            <span className="text-sm text-gray-600">Skewness</span>
                            <span className="text-sm font-semibold text-gray-900">
                              {sessionDetails.abnormal_stats.original?.skew?.toFixed(4) || 'N/A'}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
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
    </div>
  );
}

export default App;