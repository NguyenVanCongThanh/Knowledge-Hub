import React from 'react';

export interface LogItem {
  id: number;
  key_name: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  timestamp: string;
}

interface RecentLogsProps {
  logs: LogItem[];
}

export default function RecentLogs({ logs }: RecentLogsProps) {
  const formatDate = (isoString: string) => {
    try {
      const date = new Date(isoString);
      return date.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) + 
        ' ' + date.toLocaleDateString('vi-VN', { month: '2-digit', day: '2-digit' });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="glass-panel p-5 rounded-2xl space-y-4 shadow-xl">
      <h2 className="text-base font-semibold text-slate-200">Nhật ký cuộc gọi API gần đây</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-slate-800/80 text-xs text-slate-400 uppercase tracking-wider">
              <th className="py-3 px-4">Thời gian</th>
              <th className="py-3 px-4">Key sử dụng</th>
              <th className="py-3 px-4">Model</th>
              <th className="py-3 px-4 text-right">Prompt Tokens</th>
              <th className="py-3 px-4 text-right">Completion Tokens</th>
              <th className="py-3 px-4 text-right">Tổng Tokens</th>
            </tr>
          </thead>
          <tbody className="text-sm divide-y divide-slate-800/40">
            {logs.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-6 text-center text-slate-500">
                  Chưa có nhật ký hoạt động nào.
                </td>
              </tr>
            ) : (
              logs.map((log) => (
                <tr key={log.id} className="hover:bg-slate-900/10 transition-colors">
                  <td className="py-3.5 px-4 text-slate-400 font-mono text-xs">
                    {formatDate(log.timestamp)}
                  </td>
                  <td className="py-3.5 px-4 font-semibold text-slate-300">
                    {log.key_name || <span className="text-slate-500 italic">N/A</span>}
                  </td>
                  <td className="py-3.5 px-4 font-mono text-xs text-slate-400">
                    {log.model}
                  </td>
                  <td className="py-3.5 px-4 text-right font-mono text-xs text-slate-400">
                    {log.prompt_tokens.toLocaleString()}
                  </td>
                  <td className="py-3.5 px-4 text-right font-mono text-xs text-slate-400">
                    {log.completion_tokens.toLocaleString()}
                  </td>
                  <td className="py-3.5 px-4 text-right font-mono text-sm font-semibold text-violet-400">
                    {log.total_tokens.toLocaleString()}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
