import React from 'react';
import { Key, CheckCircle, BarChart3 } from 'lucide-react';

interface StatsGridProps {
  totalKeys: number;
  activeKeys: number;
  totalTokens: number;
}

export default function StatsGrid({ totalKeys, activeKeys, totalTokens }: StatsGridProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
      {/* Total Keys Card */}
      <div className="glass-panel p-5 rounded-2xl flex items-center justify-between shadow-xl">
        <div className="space-y-1">
          <span className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Tổng số Keys</span>
          <h3 className="text-3xl font-bold tracking-tight">{totalKeys}</h3>
        </div>
        <div className="p-3 bg-violet-500/10 text-violet-400 rounded-xl">
          <Key className="w-6 h-6" />
        </div>
      </div>

      {/* Active Keys Card */}
      <div className="glass-panel p-5 rounded-2xl flex items-center justify-between shadow-xl">
        <div className="space-y-1">
          <span className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Keys Đang Hoạt Động</span>
          <h3 className="text-3xl font-bold tracking-tight text-emerald-400">{activeKeys}</h3>
        </div>
        <div className="p-3 bg-emerald-500/10 text-emerald-400 rounded-xl">
          <CheckCircle className="w-6 h-6" />
        </div>
      </div>

      {/* Token Usage Card */}
      <div className="glass-panel p-5 rounded-2xl flex items-center justify-between shadow-xl">
        <div className="space-y-1">
          <span className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Lượng Token Đã Dùng</span>
          <h3 className="text-3xl font-bold tracking-tight text-blue-400">
            {totalTokens.toLocaleString()}
          </h3>
        </div>
        <div className="p-3 bg-blue-500/10 text-blue-400 rounded-xl">
          <BarChart3 className="w-6 h-6" />
        </div>
      </div>
    </div>
  );
}
