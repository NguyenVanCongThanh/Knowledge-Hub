'use client';

import React from 'react';

interface UsageItem {
  date: string;
  tokens: number;
}

interface UsageChartProps {
  data: UsageItem[];
  timeRange: '24h' | '7d' | '30d';
  onTimeRangeChange: (range: '24h' | '7d' | '30d') => void;
}

export default function UsageChart({ data, timeRange, onTimeRangeChange }: UsageChartProps) {
  // Chart dimensions
  const width = 600;
  const height = 240;
  const paddingLeft = 60;
  const paddingRight = 20;
  const paddingTop = 20;
  const paddingBottom = 40;

  const chartWidth = width - paddingLeft - paddingRight;
  const chartHeight = height - paddingTop - paddingBottom;

  // Max value for scaling
  const maxTokens = Math.max(...data.map((d) => d.tokens), 1000);
  // Round max tokens to nice number
  const roundMax = Math.ceil(maxTokens / 1000) * 1000;

  // Generate points
  const points = data.map((d, index) => {
    const x = paddingLeft + (index / Math.max(data.length - 1, 1)) * chartWidth;
    const y = paddingTop + chartHeight - (d.tokens / roundMax) * chartHeight;
    return { x, y, ...d };
  });

  const pathD = points.length > 0 
    ? `M ${points[0].x} ${points[0].y} ` + points.slice(1).map(p => `L ${p.x} ${p.y}`).join(' ')
    : '';

  // Gradient area path
  const areaD = points.length > 0
    ? `${pathD} L ${points[points.length - 1].x} ${paddingTop + chartHeight} L ${points[0].x} ${paddingTop + chartHeight} Z`
    : '';

  // Get subset of x labels to display to avoid clutter
  const labelInterval = Math.ceil(data.length / 6);

  return (
    <div className="glass-panel p-5 rounded-2xl lg:col-span-2 space-y-4 shadow-xl">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold tracking-wide text-slate-200">
          {timeRange === '24h' && 'Xu hướng sử dụng Token (24 giờ qua)'}
          {timeRange === '7d' && 'Xu hướng sử dụng Token (7 ngày qua)'}
          {timeRange === '30d' && 'Xu hướng sử dụng Token (30 ngày qua)'}
        </h2>
        <div className="flex items-center gap-1 bg-slate-950/60 p-1 rounded-xl border border-slate-800 text-[11px] font-medium">
          {(['24h', '7d', '30d'] as const).map((range) => (
            <button
              key={range}
              onClick={() => onTimeRangeChange(range)}
              className={`px-3 py-1.5 rounded-lg transition-all duration-150 ${
                timeRange === range
                  ? 'bg-violet-600 text-white shadow-md shadow-violet-600/10'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              {range === '24h' ? '24 Giờ' : range === '7d' ? '7 Ngày' : '30 Ngày'}
            </button>
          ))}
        </div>
      </div>

      <div className="relative w-full overflow-hidden">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto overflow-visible">
          <defs>
            <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines (horizontal) */}
          {[0, 0.25, 0.5, 0.75, 1].map((ratio, i) => {
            const y = paddingTop + chartHeight * ratio;
            const val = Math.round(roundMax * (1 - ratio));
            return (
              <g key={i} className="opacity-40">
                <line
                  x1={paddingLeft}
                  y1={y}
                  x2={width - paddingRight}
                  y2={y}
                  stroke="#334155"
                  strokeWidth="1"
                  strokeDasharray="4 4"
                />
                <text
                  x={paddingLeft - 10}
                  y={y + 4}
                  fill="#94a3b8"
                  fontSize="10"
                  textAnchor="end"
                  className="font-mono"
                >
                  {val.toLocaleString()}
                </text>
              </g>
            );
          })}

          {/* Y Axis line */}
          <line
            x1={paddingLeft}
            y1={paddingTop}
            x2={paddingLeft}
            y2={paddingTop + chartHeight}
            stroke="#334155"
            strokeWidth="1.5"
          />

          {/* X Axis line */}
          <line
            x1={paddingLeft}
            y1={paddingTop + chartHeight}
            x2={width - paddingRight}
            y2={paddingTop + chartHeight}
            stroke="#334155"
            strokeWidth="1.5"
          />

          {/* Gradient area */}
          {areaD && <path d={areaD} fill="url(#chartGradient)" />}

          {/* Main stroke line */}
          {pathD && (
            <path
              d={pathD}
              fill="none"
              stroke="#8b5cf6"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* Data Points */}
          {points.map((p, i) => (
            <g key={i} className="group/point">
              <circle
                cx={p.x}
                cy={p.y}
                r="3"
                className="fill-violet-400 stroke-slate-950 stroke-[1.5px] transition-all duration-150 group-hover/point:r-5 group-hover/point:fill-white cursor-pointer"
              />
              <title>{`${p.date}: ${p.tokens.toLocaleString()} tokens`}</title>
            </g>
          ))}

          {/* X Axis labels */}
          {points.map((p, i) => {
            if (i % labelInterval !== 0 && i !== points.length - 1) return null;
            return (
              <text
                key={i}
                x={p.x}
                y={paddingTop + chartHeight + 20}
                fill="#94a3b8"
                fontSize="10"
                textAnchor="middle"
                className="font-mono opacity-80"
              >
                {timeRange === '24h' ? p.date : p.date.substring(5)}
              </text>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
