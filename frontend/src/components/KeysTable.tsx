'use client';

import React, { useState, useEffect } from 'react';
import { Pencil, Trash2, ShieldAlert } from 'lucide-react';

export interface KeyItem {
  id: number;
  name: string;
  api_key: string;
  status: 'active' | 'inactive' | 'rate_limited';
  remaining_requests: number | null;
  remaining_tokens: number | null;
  limit_requests: number | null;
  limit_tokens: number | null;
  cooldown_until: string | null;
}

interface KeysTableProps {
  keys: KeyItem[];
  onToggleStatus: (id: number, currentStatus: string, checked: boolean) => void;
  onEditName: (id: number, currentName: string) => void;
  onDeleteKey: (id: number) => void;
}

export default function KeysTable({ keys, onToggleStatus, onEditName, onDeleteKey }: KeysTableProps) {
  const [cooldowns, setCooldowns] = useState<Record<number, string>>({});

  useEffect(() => {
    // Timer to update cooldowns every second
    const interval = setInterval(() => {
      const newCooldowns: Record<number, string> = {};
      const now = new Date().getTime();

      keys.forEach((k) => {
        if (k.status === 'rate_limited' && k.cooldown_until) {
          const target = new Date(k.cooldown_until).getTime();
          const diff = target - now;

          if (diff > 0) {
            const minutes = Math.floor(diff / 60000);
            const seconds = Math.floor((diff % 60000) / 1000);
            newCooldowns[k.id] = `${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;
          }
        }
      });
      setCooldowns(newCooldowns);
    }, 1000);

    return () => clearInterval(interval);
  }, [keys]);

  return (
    <div className="glass-panel p-5 rounded-2xl space-y-4 shadow-xl">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-slate-200">Quản lý API Keys</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-slate-800/80 text-xs text-slate-400 uppercase tracking-wider">
              <th className="py-3 px-4">Tên gợi nhớ</th>
              <th className="py-3 px-4">API Key</th>
              <th className="py-3 px-4">Requests còn lại</th>
              <th className="py-3 px-4">Tokens còn lại</th>
              <th className="py-3 px-4">Trạng thái (Kích hoạt)</th>
              <th className="py-3 px-4 text-right">Hành động</th>
            </tr>
          </thead>
          <tbody className="text-sm divide-y divide-slate-800/40">
            {keys.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-slate-500">
                  Chưa có API Key nào được thêm. Hãy nhấn Thêm Key Mới!
                </td>
              </tr>
            ) : (
              keys.map((k) => {
                const isChecked = k.status === 'active';
                const cooldownText = cooldowns[k.id];

                return (
                  <tr key={k.id} className="hover:bg-slate-900/10 transition-colors">
                    <td className="py-4 px-4 font-semibold text-slate-200">
                      <div className="flex items-center gap-2">
                        <span>{k.name}</span>
                        <button
                          onClick={() => onEditName(k.id, k.name)}
                          className="text-slate-500 hover:text-violet-400 transition-colors text-xs"
                          title="Chỉnh sửa tên"
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                    <td className="py-4 px-4 font-mono text-xs text-slate-400">
                      {k.api_key}
                    </td>
                    <td className="py-4 px-4 font-semibold text-slate-300">
                      {k.remaining_requests !== null ? (
                        k.remaining_requests.toLocaleString()
                      ) : (
                        <span className="text-xs text-slate-500 italic">Chưa gọi</span>
                      )}
                    </td>
                    <td className="py-4 px-4 font-semibold text-slate-300">
                      {k.remaining_tokens !== null ? (
                        k.remaining_tokens.toLocaleString()
                      ) : (
                        <span className="text-xs text-slate-500 italic">Chưa gọi</span>
                      )}
                    </td>
                    <td className="py-4 px-4">
                      <div className="flex items-center gap-3">
                        <label className="relative inline-flex items-center cursor-pointer">
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={(e) => onToggleStatus(k.id, k.status, e.target.checked)}
                            className="sr-only peer"
                            disabled={k.status === 'rate_limited'}
                          />
                          <div className="w-9 h-5 bg-slate-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-500 after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-emerald-500 peer-checked:after:bg-white disabled:opacity-50" />
                        </label>
                        <span
                          className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                            k.status === 'active'
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                              : k.status === 'rate_limited'
                              ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                              : 'bg-slate-800 text-slate-400 border border-slate-700'
                          }`}
                        >
                          {k.status === 'rate_limited' && cooldownText ? (
                            <span className="flex items-center gap-1">
                              <ShieldAlert className="w-3.5 h-3.5 animate-pulse" />
                              cooldown ({cooldownText})
                            </span>
                          ) : (
                            k.status
                          )}
                        </span>
                      </div>
                    </td>
                    <td className="py-4 px-4 text-right">
                      <button
                        onClick={() => onDeleteKey(k.id)}
                        className="text-xs p-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded-xl transition-colors"
                        title="Xóa Key"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
