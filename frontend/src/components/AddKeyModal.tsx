'use client';

import React, { useState } from 'react';
import { X, PlusCircle } from 'lucide-react';

interface AddKeyModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (name: string, apiKey: string) => void;
}

export default function AddKeyModal({ isOpen, onClose, onSubmit }: AddKeyModalProps) {
  const [name, setName] = useState('');
  const [apiKey, setApiKey] = useState('');

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !apiKey.trim()) return;
    onSubmit(name, apiKey);
    setName('');
    setApiKey('');
  };

  return (
    <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center z-50 transition-all duration-300">
      <div className="glass-panel max-w-md w-full p-6 rounded-2xl space-y-5 shadow-2xl border border-slate-850 animate-in fade-in zoom-in duration-200">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
            <PlusCircle className="w-5 h-5 text-violet-500" />
            Thêm Groq API Key
          </h3>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white transition-colors duration-150"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-400" htmlFor="key-name">
              Tên Gợi Nhớ
            </label>
            <input
              type="text"
              id="key-name"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Ví dụ: Key Dự Án Chatbot chính"
              className="w-full bg-slate-950/90 border border-slate-800 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-violet-500 text-slate-200"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-400" htmlFor="api-key-val">
              Groq API Key
            </label>
            <input
              type="password"
              id="api-key-val"
              required
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="gsk_xxxxxxxxxxxxxxxxxxxx"
              className="w-full bg-slate-950/90 border border-slate-800 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-violet-500 text-slate-200"
            />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 transition-colors text-xs font-semibold rounded-xl text-slate-300"
            >
              Hủy
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-gradient-to-r from-violet-600 to-blue-600 hover:opacity-90 transition-opacity text-xs font-semibold rounded-xl text-white shadow-md shadow-violet-600/10"
            >
              Lưu Key
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
