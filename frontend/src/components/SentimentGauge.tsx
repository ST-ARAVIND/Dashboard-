// Simple semicircular composite sentiment gauge (0-100).
export function SentimentGauge({
  score,
  label,
}: {
  score: number;
  label: string;
}) {
  const clamped = Math.max(0, Math.min(100, score));
  // Map 0..100 to 180..0 degrees.
  const angle = 180 - (clamped / 100) * 180;
  const r = 70;
  const cx = 90;
  const cy = 90;
  const rad = (angle * Math.PI) / 180;
  const nx = cx + r * Math.cos(rad);
  const ny = cy - r * Math.sin(rad);
  const color = label === "bullish" ? "#15803D" : label === "bearish" ? "#C0392B" : "#eab308";

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 180 110" className="w-44">
        <defs>
          <linearGradient id="g" x1="0" x2="1">
            <stop offset="0%" stopColor="#C0392B" />
            <stop offset="50%" stopColor="#eab308" />
            <stop offset="100%" stopColor="#15803D" />
          </linearGradient>
        </defs>
        <path
          d={`M 20 90 A ${r} ${r} 0 0 1 160 90`}
          fill="none"
          stroke="url(#g)"
          strokeWidth="12"
          strokeLinecap="round"
        />
        <line x1={cx} y1={cy} x2={nx} y2={ny} stroke="#2A2620" strokeWidth="3" />
        <circle cx={cx} cy={cy} r="5" fill="#2A2620" />
      </svg>
      <div className="text-center -mt-2">
        <div className="text-2xl font-mono" style={{ color }}>
          {clamped.toFixed(0)}
        </div>
        <div className="text-[11px] uppercase tracking-wide" style={{ color }}>
          {label}
        </div>
      </div>
    </div>
  );
}
