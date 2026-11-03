import { useState } from 'react';
import { AlertTriangle, CheckCircle2, Info, Loader2, XCircle, ChevronLeft, ChevronRight } from 'lucide-react';

export const Card = ({ className = '', children, ...p }) => <section className={`card p-5 ${className}`} {...p}>{children}</section>;

export const SectionTitle = ({ title, hint, right }) => (
  <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
    <div>
      <h2 className="text-base font-semibold text-mist-100">{title}</h2>
      {hint && <p className="mt-1 max-w-2xl text-sm leading-relaxed text-mist-500">{hint}</p>}
    </div>
    {right}
  </div>
);

export const Stat = ({ label, value, sub, tone = 'text-mist-100' }) => (
  <div className="card p-4">
    <p className="text-sm text-mist-500">{label}</p>
    <p className={`mt-1 text-2xl font-bold ${tone}`}>{value}</p>
    {sub && <p className="mt-1 text-xs text-mist-500">{sub}</p>}
  </div>
);

const BADGE = {
  positive: 'bg-cyan-400/15 text-cyan-400', neutral: 'bg-mist-500/20 text-mist-300', negative: 'bg-neg/15 text-neg',
  violet: 'bg-violet-500/20 text-violet-300', warn: 'bg-warn/15 text-warn', none: 'bg-ink-700 text-mist-500',
  strong: 'bg-neg/15 text-neg', moderate: 'bg-warn/15 text-warn', weak: 'bg-cyan-400/15 text-cyan-400',
  unavailable: 'bg-ink-700 text-mist-500', stronger: 'bg-violet-500/25 text-violet-300',
};
export const Badge = ({ tone = 'neutral', children }) => (
  <span className={`inline-block whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ${BADGE[tone] || BADGE.neutral}`}>{children}</span>
);

const ALERT = {
  info: ['border-cyan-400/30 bg-cyan-400/10 text-cyan-100', Info],
  warn: ['border-warn/30 bg-warn/10 text-amber-100', AlertTriangle],
  error: ['border-neg/40 bg-neg/10 text-rose-100', XCircle],
  success: ['border-cyan-400/30 bg-cyan-400/10 text-cyan-100', CheckCircle2],
};
export function Alert({ tone = 'info', title, children, className = '' }) {
  const [cls, Icon] = ALERT[tone];
  return (
    <div role={tone === 'error' ? 'alert' : 'note'} className={`flex gap-3 rounded-lg border p-4 text-sm leading-relaxed ${cls} ${className}`}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <div>{title && <p className="font-semibold">{title}</p>}<div className={title ? 'mt-0.5 opacity-90' : ''}>{children}</div></div>
    </div>
  );
}

export const Spinner = ({ label = 'Working…' }) => (
  <span className="inline-flex items-center gap-2 text-sm" role="status"><Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />{label}</span>
);

export function EmptyState({ icon: Icon, title, children, actions }) {
  return (
    <div className="card flex flex-col items-center px-6 py-14 text-center">
      <div className="mb-4 rounded-full bg-ink-700 p-3 text-violet-300"><Icon className="h-6 w-6" aria-hidden="true" /></div>
      <h2 className="text-lg font-semibold">{title}</h2>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-mist-500">{children}</p>
      {actions && <div className="mt-6 flex flex-wrap justify-center gap-3">{actions}</div>}
    </div>
  );
}

export function Tabs({ tabs, value, onChange }) {
  return (
    <div role="tablist" className="mb-5 flex gap-1 overflow-x-auto border-b border-ink-600/60">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)}
          className={`whitespace-nowrap border-b-2 px-4 py-2.5 text-sm font-semibold transition-colors ${value === t.id ? 'border-violet-400 text-violet-300' : 'border-transparent text-mist-500 hover:text-mist-100'}`}>
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function DataTable({ columns, rows, pageSize = 20, empty = 'Nothing to show.', caption }) {
  const [page, setPage] = useState(0);
  const pages = Math.max(1, Math.ceil(rows.length / pageSize));
  const p = Math.min(page, pages - 1);
  const slice = rows.slice(p * pageSize, p * pageSize + pageSize);
  if (!rows.length) return <p className="rounded-lg border border-dashed border-ink-600 p-6 text-center text-sm text-mist-500">{empty}</p>;
  return (
    <div>
      <div className="overflow-x-auto rounded-lg border border-ink-600/60">
        <table className="w-full min-w-[560px] border-collapse">
          {caption && <caption className="sr-only">{caption}</caption>}
          <thead className="bg-ink-900/60"><tr>{columns.map((c) => <th key={c.key} scope="col" className={`th ${c.className || ''}`}>{c.label}</th>)}</tr></thead>
          <tbody className="divide-y divide-ink-600/40">
            {slice.map((r, i) => (
              <tr key={i} className="hover:bg-ink-700/30">
                {columns.map((c) => <td key={c.key} className={`td ${c.className || ''}`}>{c.render ? c.render(r) : r[c.key]}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <div className="mt-3 flex items-center justify-between text-sm text-mist-500">
          <span>{p * pageSize + 1}–{Math.min(rows.length, (p + 1) * pageSize)} of {rows.length}</span>
          <div className="flex gap-2">
            <button className="btn-ghost !px-2.5 !py-1.5" disabled={p === 0} onClick={() => setPage(p - 1)} aria-label="Previous page"><ChevronLeft className="h-4 w-4" /></button>
            <button className="btn-ghost !px-2.5 !py-1.5" disabled={p >= pages - 1} onClick={() => setPage(p + 1)} aria-label="Next page"><ChevronRight className="h-4 w-4" /></button>
          </div>
        </div>
      )}
    </div>
  );
}

export const ChartTooltipStyle = { contentStyle: { background: '#0B1120', border: '1px solid #26345E', borderRadius: 8, color: '#E8ECF8', fontSize: 12 }, itemStyle: { color: '#E8ECF8' }, cursor: { fill: 'rgba(139,92,246,0.12)' } };
