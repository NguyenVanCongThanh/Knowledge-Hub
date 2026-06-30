import React from 'react';

interface ModelUsageItem {
  model: string;
  tokens: number;
}

interface ModelDistributionProps {
  data: ModelUsageItem[];
}

export default function ModelDistribution({ data }: ModelDistributionProps) {
  const totalTokens = data.reduce((sum, item) => sum + item.tokens, 0);

  // Define a nice set of gradient/color classes for models
  const colorSchemes = [
    { bg: 'bg-violet-500', text: 'text-violet-400', border: 'border-violet-500/20' },
    { bg: 'bg-blue-500', text: 'text-blue-400', border: 'border-blue-500/20' },
    { bg: 'bg-cyan-500', text: 'text-cyan-400', border: 'border-cyan-500/20' },
    { bg: 'bg-emerald-500', text: 'text-emerald-400', border: 'border-emerald-500/20' },
    { bg: 'bg-amber-500', text: 'text-amber-400', border: 'border-amber-500/20' },
  ];

  return (
    <div className="glass-panel p-5 rounded-2xl space-y-5 shadow-xl">
      <h2 className="text-base font-semibold tracking-wide text-slate-200">
        Phân bổ Token theo Model
      </h2>

      {data.length === 0 ? (
        <div className="h-48 flex items-center justify-center text-slate-500 text-sm">
          Chưa có dữ liệu thống kê model.
        </div>
      ) : (
        <div className="space-y-4">
          {data.map((item, index) => {
            const percentage = totalTokens > 0 ? (item.tokens / totalTokens) * 100 : 0;
            const color = colorSchemes[index % colorSchemes.length];

            return (
              <div key={item.model} className="space-y-1.5">
                <div className="flex justify-between items-center text-xs">
                  <span className="font-semibold text-slate-300 font-mono truncate max-w-[200px]" title={item.model}>
                    {item.model}
                  </span>
                  <span className="text-slate-400 font-mono">
                    {item.tokens.toLocaleString()} ({percentage.toFixed(1)}%)
                  </span>
                </div>
                
                {/* Progress bar */}
                <div className="h-2 w-full bg-slate-950/60 rounded-full overflow-hidden border border-slate-900">
                  <div
                    className={`h-full ${color.bg} rounded-full transition-all duration-500`}
                    style={{ width: `${percentage}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
