'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Server, Book, Plus, Activity, RefreshCw } from 'lucide-react';
import StatsGrid from '@/components/StatsGrid';
import UsageChart from '@/components/UsageChart';
import ModelDistribution from '@/components/ModelDistribution';
import KeysTable, { KeyItem } from '@/components/KeysTable';
import RecentLogs, { LogItem } from '@/components/RecentLogs';
import AddKeyModal from '@/components/AddKeyModal';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function Dashboard() {
  // State variables
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

  // Load initial data and set up automatic pooling
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
            <p className="text-xs text-slate-400">Groq Gateway & Usage Monitor</p>
          </div>
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
