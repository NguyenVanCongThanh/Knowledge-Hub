'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Server, Book, Plus, Activity, RefreshCw, Database, Terminal, GitBranch, Folder, Github, CheckCircle2, XCircle, AlertCircle, Cpu } from 'lucide-react';
import StatsGrid from '@/components/StatsGrid';
import UsageChart from '@/components/UsageChart';
import ModelDistribution from '@/components/ModelDistribution';
import KeysTable, { KeyItem } from '@/components/KeysTable';
import RecentLogs, { LogItem } from '@/components/RecentLogs';
import AddKeyModal from '@/components/AddKeyModal';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface IngestProgress {
  project_name: string;
  job_type: 'local_ingest' | 'github_ingest' | 'sync';
  status: 'running' | 'completed' | 'failed';
  stage: string;
  stage_text: string;
  total_files: number;
  processed_files: number;
  current_file?: string;
  total_chunks: number;
  processed_chunks: number;
  error_message?: string;
  progress_pct: number;
  started_at: number;
  updated_at: number;
  indexed_files_count?: number;
  chunks_count?: number;
  commits_indexed?: number;
}

export default function Dashboard() {
  // Navigation tabs state
  const [activeTab, setActiveTab] = useState<'gateway' | 'ingest'>('gateway');

  // Gateway state variables
  const [timeRange, setTimeRange] = useState<'24h' | '7d' | '30d'>('7d');
  const [totalKeys, setTotalKeys] = useState(0);
  const [activeKeys, setActiveKeys] = useState(0);
  const [totalTokens, setTotalTokens] = useState(0);
  const [dailyUsage, setDailyUsage] = useState<any[]>([]);
  const [modelUsage, setModelUsage] = useState<any[]>([]);
  const [recentLogs, setRecentLogs] = useState<LogItem[]>([]);
  const [keys, setKeys] = useState<KeyItem[]>([]);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Ingestion form state
  const [ingestType, setIngestType] = useState<'local' | 'github'>('local');
  const [projectName, setProjectName] = useState('');
  const [localPath, setLocalPath] = useState('');
  const [githubUrl, setGithubUrl] = useState('');
  const [githubBranch, setGithubBranch] = useState('main');
  const [githubToken, setGithubToken] = useState('');
  
  // Active progress tracking
  const [activeJob, setActiveJob] = useState<IngestProgress | null>(null);
  const [trackedProject, setTrackedProject] = useState<string>('');
  const [isSubmittingIngest, setIsSubmittingIngest] = useState(false);
  const [ingestError, setIngestError] = useState<string | null>(null);
  const [isCancelling, setIsCancelling] = useState(false);

  // Fetch Dashboard Stats and Charts
  const fetchSummaryStats = useCallback(async (range: string) => {
    try {
      const response = await fetch(`${API_URL}/api/groq/usage/summary?range=${range}`);
      if (!response.ok) throw new Error('Failed to fetch summary stats');
      const data = await response.json();
      
      setTotalKeys(data.total_keys);
      setActiveKeys(data.active_keys);
      setTotalTokens(data.total_tokens);
      setDailyUsage(data.daily_usage || []);
      setModelUsage(data.model_usage || []);
      setRecentLogs(data.recent_logs || []);
    } catch (error) {
      console.error('Error fetching summary stats:', error);
    }
  }, []);

  // Fetch Keys Table
  const fetchKeys = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/groq/keys`);
      if (!response.ok) throw new Error('Failed to fetch keys');
      const data = await response.json();
      setKeys(data || []);
    } catch (error) {
      console.error('Error fetching keys:', error);
    }
  }, []);

  // Combined Refresh Data
  const refreshData = useCallback(async () => {
    setIsRefreshing(true);
    await Promise.all([fetchSummaryStats(timeRange), fetchKeys()]);
    setIsRefreshing(false);
  }, [timeRange, fetchSummaryStats, fetchKeys]);

  // Load initial data and set up automatic pooling for gateway stats
  useEffect(() => {
    refreshData();
    const interval = setInterval(refreshData, 10000);
    return () => clearInterval(interval);
  }, [refreshData]);

  // Handle Add Key Submit
  const handleAddKey = async (name: string, apiKey: string) => {
    try {
      const response = await fetch(`${API_URL}/api/groq/keys`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, api_key: apiKey }),
      });
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Failed to add key');
      }
      setIsAddModalOpen(false);
      refreshData();
    } catch (error: any) {
      alert(`Lỗi khi thêm key: ${error.message}`);
    }
  };

  // Handle Edit Key Name
  const handleEditName = async (id: number, currentName: string) => {
    const newName = prompt('Nhập tên gợi nhớ mới cho Key:', currentName);
    if (!newName || newName.trim() === '' || newName === currentName) return;

    try {
      const response = await fetch(`${API_URL}/api/groq/keys/${id}/name`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newName.trim() }),
      });
      if (!response.ok) throw new Error('Failed to update name');
      refreshData();
    } catch (error: any) {
      alert(`Lỗi khi sửa tên key: ${error.message}`);
    }
  };

  // Handle Toggle Switch (Active/Inactive)
  const handleToggleStatus = async (id: number, currentStatus: string, checked: boolean) => {
    const newStatus = checked ? 'active' : 'inactive';
    try {
      const response = await fetch(`${API_URL}/api/groq/keys/${id}/status`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      });
      if (!response.ok) throw new Error('Failed to update status');
      refreshData();
    } catch (error: any) {
      alert(`Lỗi khi cập nhật trạng thái: ${error.message}`);
    }
  };

  // Handle Delete Key
  const handleDeleteKey = async (id: number) => {
    if (!confirm('Bạn có chắc chắn muốn xóa API Key này không? Thao tác này không thể hoàn tác.')) return;

    try {
      const response = await fetch(`${API_URL}/api/groq/keys/${id}`, {
        method: 'DELETE',
      });
      if (!response.ok) throw new Error('Failed to delete key');
      refreshData();
    } catch (error: any) {
      alert(`Lỗi khi xóa key: ${error.message}`);
    }
  };

  // Check progress of tracked project
  const fetchIngestProgress = useCallback(async (projName: string) => {
    if (!projName) return;
    try {
      const response = await fetch(`${API_URL}/ingest/status/${projName}`);
      if (!response.ok) {
        if (response.status === 404) {
          // No job found
          return;
        }
        throw new Error('Failed to fetch progress');
      }
      const data = await response.json();
      setActiveJob(data);
    } catch (err: any) {
      console.error('Error fetching progress:', err);
    }
  }, []);

  // Poll progress if job is running
  useEffect(() => {
    if (!trackedProject) return;
    
    // Fetch immediately
    fetchIngestProgress(trackedProject);
    
    const interval = setInterval(() => {
      fetchIngestProgress(trackedProject);
    }, 1500);

    // Stop polling if completed or failed
    if (activeJob && (activeJob.status === 'completed' || activeJob.status === 'failed')) {
      clearInterval(interval);
    }

    return () => clearInterval(interval);
  }, [trackedProject, fetchIngestProgress, activeJob?.status]);

  // Handle Ingestion Submit
  const handleIngestSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectName.trim()) {
      setIngestError('Vui lòng nhập tên định danh dự án');
      return;
    }

    setIsSubmittingIngest(true);
    setIngestError(null);
    setActiveJob(null);

    const endpoint = ingestType === 'local' ? `${API_URL}/ingest` : `${API_URL}/ingest/github`;
    const payload = ingestType === 'local' 
      ? { project_name: projectName.trim(), path: localPath.trim() }
      : { project_name: projectName.trim(), github_url: githubUrl.trim(), branch: githubBranch.trim(), token: githubToken.trim() || null };

    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Nạp dữ liệu thất bại');
      }

      setTrackedProject(projectName.trim());
      // Fetch status right away
      fetchIngestProgress(projectName.trim());
    } catch (err: any) {
      setIngestError(err.message);
    } finally {
      setIsSubmittingIngest(false);
    }
  };

  const handleCancelIngest = async (projName: string) => {
    if (!confirm(`Bạn có chắc chắn muốn hủy tiến trình nạp tri thức của dự án '${projName}' và khôi phục (dọn dẹp) dữ liệu dở dang không?`)) {
      return;
    }
    setIsCancelling(true);
    try {
      const response = await fetch(`${API_URL}/ingest/cancel/${projName}`, {
        method: 'POST',
      });
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Hủy tiến trình thất bại');
      }
      alert(`Đã gửi yêu cầu hủy cho dự án '${projName}'. Đang tiến hành dọn dẹp...`);
      fetchIngestProgress(projName);
    } catch (err: any) {
      alert(`Lỗi khi hủy: ${err.message}`);
    } finally {
      setIsCancelling(false);
    }
  };

  const isJobRunning = activeJob?.status === 'running';

  return (
    <div className="text-slate-100 min-h-screen flex flex-col">
      {/* Navigation */}
      <nav className="glass-nav sticky top-0 z-40 px-6 py-4 flex items-center justify-between shadow-md">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-gradient-to-tr from-violet-600 to-blue-600 rounded-xl shadow-lg shadow-violet-600/20">
            <Server className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-base font-semibold tracking-wide bg-gradient-to-r from-white via-slate-200 to-cyan-400 bg-clip-text text-transparent">
              SDLC Knowledge Hub
            </h1>
            <p className="text-xs text-slate-400">Groq Gateway & Knowledge Graph Ingestion</p>
          </div>
        </div>

        {/* Tab Switcher in Navbar */}
        <div className="flex bg-slate-900/80 p-1 rounded-xl border border-slate-800">
          <button
            onClick={() => setActiveTab('gateway')}
            className={`px-4 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all duration-200 ${
              activeTab === 'gateway' 
                ? 'bg-gradient-to-r from-violet-600 to-blue-600 text-white shadow-md' 
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            API Gateway
          </button>
          <button
            onClick={() => setActiveTab('ingest')}
            className={`px-4 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all duration-200 ${
              activeTab === 'ingest' 
                ? 'bg-gradient-to-r from-violet-600 to-blue-600 text-white shadow-md' 
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Database className="w-3.5 h-3.5" />
            Nạp Tri Thức / Ingestion
          </button>
        </div>

        <div className="flex items-center gap-4">
          <button 
            onClick={refreshData}
            className={`p-1.5 rounded-lg text-slate-400 hover:text-white transition-colors duration-150 ${isRefreshing ? 'animate-spin' : ''}`}
            title="Tải lại thủ công"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <span className="w-1.5 h-1.5 mr-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
            System Connected
          </span>
          <a
            href={`${API_URL}/docs`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-slate-400 hover:text-white transition-colors duration-200 flex items-center gap-1"
          >
            <Book className="w-3.5 h-3.5" /> API Docs
          </a>
        </div>
      </nav>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">
        {activeTab === 'gateway' ? (
          <>
            {/* Top Management Controls */}
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                  <Activity className="w-5 h-5 text-violet-500" />
                  Bảng quản trị hệ thống
                </h2>
                <p className="text-xs text-slate-400">Xem và phân tích hiệu suất Groq API Gateway</p>
              </div>
              <button
                onClick={() => setIsAddModalOpen(true)}
                className="px-4 py-2 bg-gradient-to-r from-violet-600 to-blue-600 hover:opacity-90 rounded-xl text-xs font-semibold flex items-center gap-1.5 shadow-lg shadow-violet-600/20 transition-all duration-200"
              >
                <Plus className="w-4 h-4" /> Thêm Key Mới
              </button>
            </div>

            {/* Stats Grid */}
            <StatsGrid
              totalKeys={totalKeys}
              activeKeys={activeKeys}
              totalTokens={totalTokens}
            />

            {/* Charts Section */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <UsageChart
                data={dailyUsage}
                timeRange={timeRange}
                onTimeRangeChange={(range) => {
                  setTimeRange(range);
                  fetchSummaryStats(range);
                }}
              />
              <ModelDistribution data={modelUsage} />
            </div>

            {/* Keys Management Table */}
            <KeysTable
              keys={keys}
              onToggleStatus={handleToggleStatus}
              onEditName={handleEditName}
              onDeleteKey={handleDeleteKey}
            />

            {/* Recent logs */}
            <RecentLogs logs={recentLogs} />
          </>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Ingest Form Panel */}
            <div className="lg:col-span-1 glass-panel p-6 rounded-2xl shadow-xl space-y-6 self-start">
              <div>
                <h2 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
                  <Cpu className="w-5 h-5 text-violet-500" />
                  Nạp Kho Tri Thức Mới
                </h2>
                <p className="text-xs text-slate-400">Đăng ký mã nguồn để xây dựng sơ đồ tri thức đồ thị</p>
              </div>

              {/* Form type tabs */}
              <div className="grid grid-cols-2 gap-2 bg-slate-900/60 p-1 rounded-xl border border-slate-800/80">
                <button
                  type="button"
                  disabled={isJobRunning}
                  onClick={() => setIngestType('local')}
                  className={`py-2 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-all duration-200 disabled:opacity-40 ${
                    ingestType === 'local' 
                      ? 'bg-slate-800 text-white shadow-sm' 
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  <Folder className="w-3.5 h-3.5" />
                  Local Path
                </button>
                <button
                  type="button"
                  disabled={isJobRunning}
                  onClick={() => setIngestType('github')}
                  className={`py-2 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-all duration-200 disabled:opacity-40 ${
                    ingestType === 'github' 
                      ? 'bg-slate-800 text-white shadow-sm' 
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  <Github className="w-3.5 h-3.5" />
                  GitHub Repository
                </button>
              </div>

              <form onSubmit={handleIngestSubmit} className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-300">Tên định danh Dự án (Project Name)</label>
                  <input
                    type="text"
                    required
                    disabled={isJobRunning}
                    placeholder={isJobRunning ? "Đang chạy một tiến trình..." : "ví dụ: my-fastapi-app"}
                    value={projectName}
                    onChange={(e) => setProjectName(e.target.value)}
                    className="w-full bg-slate-950 disabled:bg-slate-900/40 disabled:text-slate-500 border border-slate-800 focus:border-violet-500 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-600 outline-none transition-colors"
                  />
                </div>

                {ingestType === 'local' ? (
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-300">Đường dẫn thư mục tuyệt đối</label>
                    <input
                      type="text"
                      required
                      disabled={isJobRunning}
                      placeholder="ví dụ: /data/my-fastapi-app"
                      value={localPath}
                      onChange={(e) => setLocalPath(e.target.value)}
                      className="w-full bg-slate-950 disabled:bg-slate-900/40 disabled:text-slate-500 border border-slate-800 focus:border-violet-500 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-600 outline-none transition-colors"
                    />
                  </div>
                ) : (
                  <>
                     <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-slate-300">GitHub Repo URL</label>
                      <input
                        type="url"
                        required
                        disabled={isJobRunning}
                        placeholder="https://github.com/owner/repo"
                        value={githubUrl}
                        onChange={(e) => setGithubUrl(e.target.value)}
                        className="w-full bg-slate-950 disabled:bg-slate-900/40 disabled:text-slate-500 border border-slate-800 focus:border-violet-500 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-600 outline-none transition-colors"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-1.5">
                        <label className="text-xs font-semibold text-slate-300">Branch</label>
                        <input
                          type="text"
                          disabled={isJobRunning}
                          value={githubBranch}
                          onChange={(e) => setGithubBranch(e.target.value)}
                          className="w-full bg-slate-950 disabled:bg-slate-900/40 disabled:text-slate-500 border border-slate-800 focus:border-violet-500 rounded-xl px-3 py-2 text-xs text-white outline-none transition-colors"
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-xs font-semibold text-slate-300">Access Token (Tuỳ chọn)</label>
                        <input
                          type="password"
                          disabled={isJobRunning}
                          placeholder="ghp_..."
                          value={githubToken}
                          onChange={(e) => setGithubToken(e.target.value)}
                          className="w-full bg-slate-950 disabled:bg-slate-900/40 disabled:text-slate-500 border border-slate-800 focus:border-violet-500 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-600 outline-none transition-colors"
                        />
                      </div>
                    </div>
                  </>
                )}

                {ingestError && (
                  <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl text-xs flex items-start gap-2">
                    <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                    <span>{ingestError}</span>
                  </div>
                )}

                <button
                  type="submit"
                  disabled={isSubmittingIngest || isJobRunning}
                  className="w-full py-2.5 bg-gradient-to-r from-violet-600 to-blue-600 hover:opacity-90 disabled:from-slate-800 disabled:to-slate-800 disabled:text-slate-500 rounded-xl text-xs font-semibold text-white shadow-lg shadow-violet-600/10 transition-all duration-200"
                >
                  {isSubmittingIngest ? 'Đang gửi yêu cầu...' : isJobRunning ? 'Một tiến trình đang chạy...' : 'Bắt đầu nạp tri thức'}
                </button>
              </form>

              {/* Manual Job Monitor lookup */}
              <div className="border-t border-slate-800/80 pt-4 space-y-3">
                <h4 className="text-xs font-bold text-slate-400">Theo dõi Project đã tồn tại</h4>
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="Tên project..."
                    value={trackedProject}
                    onChange={(e) => setTrackedProject(e.target.value)}
                    className="flex-1 bg-slate-950 border border-slate-800 focus:border-violet-500 rounded-xl px-3 py-1.5 text-xs text-white placeholder-slate-600 outline-none"
                  />
                  <button
                    onClick={() => fetchIngestProgress(trackedProject)}
                    className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 rounded-xl text-xs font-semibold transition-colors"
                  >
                    Kiểm tra
                  </button>
                </div>
              </div>
            </div>

            {/* Progress / Status Panel */}
            <div className="lg:col-span-2 space-y-6">
              {activeJob ? (
                <div className="glass-panel p-6 rounded-2xl shadow-xl space-y-6">
                  {/* Job Header */}
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-lg font-bold text-white">Project: {activeJob.project_name}</h3>
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
                          activeJob.status === 'running' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' :
                          activeJob.status === 'completed' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' :
                          'bg-red-500/10 text-red-400 border border-red-500/20'
                        }`}>
                          {activeJob.status}
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 mt-1">
                        Kiểu job: {activeJob.job_type === 'github_ingest' ? 'Nạp từ GitHub' : activeJob.job_type === 'local_ingest' ? 'Nạp từ thư mục Local' : 'Đồng bộ tri thức'}
                      </p>
                    </div>

                    {/* Spinner/Status Icons */}
                    <div>
                      {activeJob.status === 'running' && (
                        <div className="flex items-center gap-3">
                          <div className="flex items-center gap-2 text-xs text-amber-400">
                            <RefreshCw className="w-4 h-4 animate-spin" />
                            <span>Đang cập nhật...</span>
                          </div>
                          <button
                            onClick={() => handleCancelIngest(activeJob.project_name)}
                            disabled={isCancelling}
                            className="px-2.5 py-1 bg-red-600/20 hover:bg-red-600/40 disabled:opacity-50 border border-red-500/30 rounded-lg text-[11px] font-semibold text-red-400 transition-colors"
                          >
                            {isCancelling ? 'Đang hủy...' : 'Hủy bỏ'}
                          </button>
                        </div>
                      )}
                      {activeJob.status === 'completed' && (
                        <div className="flex items-center gap-1.5 text-xs text-emerald-400">
                          <CheckCircle2 className="w-5 h-5" />
                          <span>Thành công</span>
                        </div>
                      )}
                      {activeJob.status === 'failed' && (
                        <div className="flex items-center gap-1.5 text-xs text-red-400">
                          <XCircle className="w-5 h-5" />
                          <span>Thất bại</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Main Progress Bar */}
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs">
                      <span className="font-semibold text-slate-300">Tiến độ tổng quát</span>
                      <span className="font-bold text-violet-400">{activeJob.progress_pct}%</span>
                    </div>
                    <div className="w-full bg-slate-900 rounded-full h-3 overflow-hidden border border-slate-800">
                      <div 
                        className="bg-gradient-to-r from-violet-600 via-blue-500 to-cyan-400 h-full rounded-full transition-all duration-500" 
                        style={{ width: `${activeJob.progress_pct}%` }}
                      ></div>
                    </div>
                  </div>

                  {/* Processing details log */}
                  <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2">
                    <div className="flex items-center gap-2 text-xs text-slate-400">
                      <Terminal className="w-3.5 h-3.5 text-cyan-500" />
                      <span className="font-semibold uppercase tracking-wider text-[10px]">Trạng thái hiện tại</span>
                    </div>
                    <p className="text-sm font-medium text-slate-200">{activeJob.stage_text}</p>
                    {activeJob.current_file && (
                      <p className="text-xs text-slate-500 truncate">
                        Tệp tin: <span className="text-slate-400 font-mono">{activeJob.current_file}</span>
                      </p>
                    )}
                  </div>

                  {/* Detail pipeline stats */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Files Processed Sub-bar */}
                    <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-800/60 space-y-3">
                      <div className="flex justify-between text-xs">
                        <span className="text-slate-400">Phân tích File (Source code / Docs)</span>
                        <span className="font-semibold text-white">
                          {activeJob.processed_files} / {activeJob.total_files}
                        </span>
                      </div>
                      <div className="w-full bg-slate-950 rounded-full h-2 overflow-hidden">
                        <div 
                          className="bg-blue-500 h-full rounded-full transition-all duration-300"
                          style={{ 
                            width: `${activeJob.total_files > 0 ? (activeJob.processed_files / activeJob.total_files) * 100 : 0}%` 
                          }}
                        ></div>
                      </div>
                    </div>

                    {/* Chunks Embedding Sub-bar */}
                    <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-800/60 space-y-3">
                      <div className="flex justify-between text-xs">
                        <span className="text-slate-400">Vector Chunks / Embeddings</span>
                        <span className="font-semibold text-white">
                          {activeJob.processed_chunks} / {activeJob.total_chunks || '?'}
                        </span>
                      </div>
                      <div className="w-full bg-slate-950 rounded-full h-2 overflow-hidden">
                        <div 
                          className="bg-cyan-500 h-full rounded-full transition-all duration-300"
                          style={{ 
                            width: `${activeJob.total_chunks > 0 ? (activeJob.processed_chunks / activeJob.total_chunks) * 100 : 0}%` 
                          }}
                        ></div>
                      </div>
                    </div>
                  </div>

                  {/* Final results summary (if completed) */}
                  {activeJob.status === 'completed' && (
                    <div className="p-4 bg-emerald-500/5 border border-emerald-500/10 rounded-xl space-y-3">
                      <h4 className="text-xs font-bold text-emerald-400 uppercase tracking-wider">Kết quả nạp tri thức</h4>
                      <div className="grid grid-cols-3 gap-2 text-center">
                        <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800">
                          <span className="block text-[10px] text-slate-500 uppercase">Tệp tin đã indexed</span>
                          <span className="text-lg font-bold text-slate-200">{activeJob.indexed_files_count || 0}</span>
                        </div>
                        <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800">
                          <span className="block text-[10px] text-slate-500 uppercase">Số lượng Chunks</span>
                          <span className="text-lg font-bold text-slate-200">{activeJob.chunks_count || 0}</span>
                        </div>
                        <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800">
                          <span className="block text-[10px] text-slate-500 uppercase">Commits Indexed</span>
                          <span className="text-lg font-bold text-slate-200">{activeJob.commits_indexed || 0}</span>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Error detail (if failed) */}
                  {activeJob.status === 'failed' && (
                    <div className="p-4 bg-red-500/5 border border-red-500/10 rounded-xl space-y-1.5 text-xs text-red-400">
                      <h4 className="font-bold uppercase tracking-wider text-[10px]">Chi tiết lỗi</h4>
                      <p className="font-mono bg-slate-950 p-3 rounded-lg border border-slate-900 mt-1 whitespace-pre-wrap">
                        {activeJob.error_message || 'Lỗi không xác định'}
                      </p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="glass-panel p-12 rounded-2xl shadow-xl text-center space-y-4">
                  <div className="w-16 h-16 bg-slate-900 rounded-2xl flex items-center justify-center mx-auto border border-slate-800">
                    <Database className="w-8 h-8 text-slate-600" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-slate-300">Chưa có Project nào được theo dõi</h3>
                    <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                      Hãy nhập thông tin dự án ở khung bên trái và bấm &quot;Bắt đầu nạp tri thức&quot; để theo dõi quá trình xây dựng sơ đồ tri thức thời gian thực.
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="mt-auto border-t border-slate-800/80 py-6 text-center text-xs text-slate-500 glass-panel">
        <p>© 2026 SDLC Knowledge Hub • Hệ thống quản lý Groq & Token sử dụng tích hợp</p>
      </footer>

      {/* Modals */}
      <AddKeyModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onSubmit={handleAddKey}
      />
    </div>
  );
}
