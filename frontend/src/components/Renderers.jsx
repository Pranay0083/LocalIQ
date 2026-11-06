import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ArrowSquareOut, MapPin, Quotes, Warning } from "@phosphor-icons/react";
import { useTheme } from "next-themes";
import { toneClass } from "@/lib/api";

const useChart = () => {
  const { resolvedTheme } = useTheme();
  const dark = resolvedTheme === "dark";
  return {
    axis: { fontSize: 10, fill: dark ? "#a1a1aa" : "#64748b", fontFamily: "IBM Plex Mono" },
    grid: dark ? "#27272a" : "#e2e8f0",
    stroke: dark ? "#818cf8" : "#4f46e5",
    muted: dark ? "#71717a" : "#94a3b8",
  };
};

const ChartTip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="panel rounded-md border border-zinc-800 bg-surface px-2.5 py-2">
      <p className="mono text-[10px] uppercase tracking-widest text-zinc-500">{label}</p>
      {payload.map((p) => (
        <p key={p.dataKey} className="mono text-xs text-zinc-100">
          {p.name}: <span style={{ color: p.color }}>{p.value}</span>
        </p>
      ))}
    </div>
  );
};

const Empty = ({ message }) => (
  <div
    data-testid="render-empty"
    className="flex items-center gap-2 border border-dashed border-zinc-800 px-3 py-4"
  >
    <Warning size={15} className="text-zinc-600" />
    <p className="text-xs text-zinc-500">{message}</p>
  </div>
);

const Gauge = ({ data }) => {
  const pct = Math.min(100, (data.value / (data.max || 500)) * 100);
  const tone =
    data.tone === "positive" ? "bg-emerald-500" : data.tone === "warning" ? "bg-amber-500" : "bg-red-500";
  return (
    <div data-testid="render-gauge">
      <div className="flex items-end gap-3">
        <span className="mono text-5xl font-semibold leading-none text-zinc-50">{data.value}</span>
        <div className="pb-1">
          <p className={`text-sm font-semibold ${toneClass[data.tone] || "text-zinc-300"}`}>{data.band}</p>
          <p className="mono text-[10px] text-zinc-500">{data.caption}</p>
        </div>
      </div>
      <div className="relative mt-3 h-2 w-full bg-zinc-900">
        <div className={`h-full ${tone}`} style={{ width: `${pct}%` }} />
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1">
        {(data.segments || []).map((s) => (
          <span
            key={s.label}
            className={`mono text-[9px] ${
              data.value >= s.from && data.value <= s.to ? "text-zinc-100" : "text-zinc-600"
            }`}
          >
            {s.label} {s.from}–{s.to}
          </span>
        ))}
      </div>
    </div>
  );
};

const TrendLine = ({ data }) => {
  const c = useChart();
  if (!data.series?.length) return <Empty message="No time series available." />;
  return (
    <div className="h-[190px] w-full" data-testid="render-trend-line">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data.series} margin={{ top: 6, right: 6, left: -22, bottom: 0 }}>
          <defs>
            <linearGradient id="aqiFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={c.stroke} stopOpacity={0.45} />
              <stop offset="100%" stopColor={c.stroke} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={c.grid} strokeDasharray="2 4" vertical={false} />
          <XAxis dataKey="label" tick={c.axis} interval={Math.ceil(data.series.length / 6)} tickLine={false} axisLine={{ stroke: c.grid }} />
          <YAxis tick={c.axis} tickLine={false} axisLine={false} width={44} />
          <Tooltip content={<ChartTip />} />
          <Area type="monotone" dataKey="aqi" name="CPCB AQI" stroke={c.stroke} strokeWidth={2} fill="url(#aqiFill)" />
          <Line type="monotone" dataKey="pm25" name="PM2.5" stroke={c.muted} strokeWidth={1.4} dot={false} strokeDasharray="3 3" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

const StatGrid = ({ data }) => {
  const stats = (data.stats || []).filter((s) => s.value !== null && s.value !== undefined && s.value !== "");
  if (!stats.length) return <Empty message="No measurements available for this module." />;
  return (
    <div className="grid-skeleton grid grid-cols-2 sm:grid-cols-3" data-testid="render-stat-grid">
      {stats.map((s, i) => (
        <div key={i} className="px-3 py-2.5" data-testid={`stat-${i}`}>
          <p className="overline text-zinc-600">{s.label}</p>
          <p className="mono mt-1 text-lg text-zinc-100">
            {String(s.value)}
            {s.unit ? <span className="ml-1 text-[10px] text-zinc-500">{s.unit}</span> : null}
          </p>
        </div>
      ))}
    </div>
  );
};

const DistanceList = ({ data }) => {
  if (!data.items?.length) return <Empty message={data.empty_message} />;
  return (
    <ul className="divide-y divide-zinc-900 border border-zinc-900" data-testid="render-distance-list">
      {data.items.map((item, i) => (
        <li key={i} className="flex items-center justify-between gap-3 px-3 py-2" data-testid={`distance-item-${i}`}>
          <div className="flex min-w-0 items-center gap-2">
            <MapPin size={13} weight="duotone" className="shrink-0 text-indigo-400" />
            <span className="truncate text-xs text-zinc-200">{item.name}</span>
            <span className="overline shrink-0 text-zinc-600">{item.kind}</span>
          </div>
          <span className="mono shrink-0 text-xs text-zinc-400">
            {item.distance_m >= 1000 ? `${(item.distance_m / 1000).toFixed(1)} km` : `${Math.round(item.distance_m)} m`}
            <span className="text-zinc-600"> · {item.walk_min}m walk</span>
          </span>
        </li>
      ))}
    </ul>
  );
};

const statusTone = {
  under_construction: "border-amber-500/40 text-amber-300",
  approved: "border-blue-500/40 text-blue-300",
  announced: "border-zinc-600 text-zinc-400",
  completed: "border-emerald-500/40 text-emerald-300",
  stalled: "border-red-500/40 text-red-300",
  reported: "border-amber-500/40 text-amber-300",
};

const Timeline = ({ data }) => {
  if (!data.events?.length) return <Empty message={data.empty_message} />;
  return (
    <ol className="relative border-l border-zinc-800 pl-4" data-testid="render-timeline">
      {data.events.map((e, i) => (
        <li key={i} className="relative pb-4 last:pb-0" data-testid={`timeline-event-${i}`}>
          <span className="absolute -left-[21px] top-1.5 h-2 w-2 border border-indigo-400 bg-zinc-950" />
          <div className="flex flex-wrap items-center gap-2">
            <span className="mono text-[11px] text-indigo-300">{e.date}</span>
            {e.status ? (
              <span className={`overline border px-1.5 py-[2px] ${statusTone[e.status] || "border-zinc-700 text-zinc-400"}`}>
                {String(e.status).replace(/_/g, " ")}
              </span>
            ) : null}
            {e.impact ? <span className="overline text-zinc-600">impact: {e.impact}</span> : null}
          </div>
          <p className="mt-1 text-sm text-zinc-100">{e.title}</p>
          {e.description ? <p className="mt-0.5 text-xs leading-snug text-zinc-500">{e.description}</p> : null}
          {e.source_url ? (
            <a href={e.source_url} target="_blank" rel="noreferrer" className="mono mt-1 inline-flex items-center gap-1 text-[10px] text-indigo-400 hover:underline">
              <ArrowSquareOut size={10} /> {e.source_name || "source"}
            </a>
          ) : null}
        </li>
      ))}
    </ol>
  );
};

const IncidentList = ({ data }) => (
  <div data-testid="render-incident-list">
    <p className="mb-2.5 border-l-2 border-amber-500/60 bg-amber-500/5 px-3 py-2 text-[11px] leading-snug text-amber-200/80">
      {data.caption}
    </p>
    {!data.items?.length ? (
      <Empty message={data.empty_message} />
    ) : (
      <ul className="divide-y divide-zinc-900 border border-zinc-900">
        {data.items.map((inc, i) => (
          <li key={i} className="px-3 py-2.5" data-testid={`incident-${i}`}>
            <div className="flex flex-wrap items-center gap-2">
              <span className="mono text-[11px] text-zinc-400">{inc.date || "undated"}</span>
              {inc.category ? (
                <span className="overline border border-zinc-700 px-1.5 py-[2px] text-zinc-400">{inc.category}</span>
              ) : null}
              {inc.location_hint ? <span className="text-[10px] text-zinc-600">{inc.location_hint}</span> : null}
            </div>
            <p className="mt-1 text-xs leading-snug text-zinc-200">{inc.headline}</p>
            {inc.source_url ? (
              <a href={inc.source_url} target="_blank" rel="noreferrer" className="mono mt-1 inline-flex items-center gap-1 text-[10px] text-indigo-400 hover:underline">
                <ArrowSquareOut size={10} /> {inc.source_name || "source"}
              </a>
            ) : null}
          </li>
        ))}
      </ul>
    )}
  </div>
);

const QuoteList = ({ data }) => (
  <div data-testid="render-quote-list">
    {data.caption ? <p className="mb-2 text-[11px] text-zinc-500">{data.caption}</p> : null}
    <div className="space-y-2">
      {(data.items || []).map((q, i) => (
        <div key={i} className="border-l-2 border-zinc-800 pl-3" data-testid={`quote-${i}`}>
          <Quotes size={12} className="text-zinc-700" weight="fill" />
          <p className="text-xs italic leading-snug text-zinc-300">{q.quote}</p>
          <div className="mt-1 flex items-center gap-2">
            <span className="mono text-[10px] text-zinc-600">{q.source_name}</span>
            {q.source_url ? (
              <a href={q.source_url} target="_blank" rel="noreferrer" className="mono text-[10px] text-indigo-400 hover:underline">
                source
              </a>
            ) : null}
          </div>
        </div>
      ))}
    </div>
  </div>
);

const TextBlock = ({ data }) => (
  <div data-testid="render-text-block">
    {data.heading ? <p className="overline mb-1 text-zinc-600">{data.heading}</p> : null}
    <p className="text-sm leading-relaxed text-zinc-300">{data.body}</p>
  </div>
);

const BarCompare = ({ data }) => {
  const c = useChart();
  return (
  <div className="h-[220px] w-full" data-testid="render-bar-compare">
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data.items} margin={{ top: 6, right: 6, left: -24, bottom: 0 }}>
        <CartesianGrid stroke={c.grid} strokeDasharray="2 4" vertical={false} />
        <XAxis dataKey="label" tick={c.axis} tickLine={false} axisLine={{ stroke: c.grid }} />
        <YAxis domain={[0, 100]} tick={c.axis} tickLine={false} axisLine={false} width={40} />
        <Tooltip content={<ChartTip />} cursor={{ fill: "rgb(99 102 241 / 0.08)" }} />
        <Legend wrapperStyle={{ fontSize: 10, fontFamily: "IBM Plex Mono" }} />
        {(data.keys || []).map((k) => (
          <Bar key={k.key} dataKey={k.key} name={k.label} fill={k.color} radius={[3, 3, 0, 0]} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  </div>
  );
};

export const RENDERERS = {
  gauge: Gauge,
  trend_line: TrendLine,
  stat_grid: StatGrid,
  distance_list: DistanceList,
  timeline: Timeline,
  incident_list: IncidentList,
  quote_list: QuoteList,
  text_block: TextBlock,
  bar_compare: BarCompare,
};

export const Render = ({ block }) => {
  const Component = RENDERERS[block.type];
  if (!Component) {
    return <Empty message={`No renderer registered for block type "${block.type}".`} />;
  }
  return (
    <div className="space-y-1.5">
      {block.title ? <p className="overline text-zinc-600">{block.title}</p> : null}
      <Component data={block.data || {}} />
    </div>
  );
};
