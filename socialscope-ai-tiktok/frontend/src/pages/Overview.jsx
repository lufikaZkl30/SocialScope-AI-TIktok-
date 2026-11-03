import { BarChart3, Link2, UploadCloud } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Alert, Card, ChartTooltipStyle, EmptyState, SectionTitle, Stat } from '../components/ui.jsx';
import { COLORS, fmtDate, nf, pct } from '../utils.js';

function StatusRow({ health, analysis }) {
  const api = health?.integrations?.tiktok_research_api;
  const rows = [
    ['Backend', health === null ? 'Checking…' : health.error ? 'Offline' : `Connected (v${health.version})`],
    ['Analysis status', analysis ? 'Analyzed from uploaded CSV' : 'Waiting for data'],
    ['Data source', analysis ? `CSV upload: ${analysis.data_source.filename}` : 'None loaded'],
    ['TikTok Research API', api ? (api.configured ? 'Configured' : 'Not configured') : 'Unknown'],
  ];
  return (
    <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {rows.map(([k, v]) => (
        <div key={k} className="card p-4"><dt className="text-xs text-mist-500">{k}</dt><dd className="mt-1 text-sm font-semibold">{v}</dd></div>
      ))}
    </dl>
  );
}

function Spectrum({ s }) {
  const seg = [['positive', 'Positive', COLORS.positive], ['neutral', 'Neutral', COLORS.neutral], ['negative', 'Negative', COLORS.negative]];
  return (
    <Card>
      <SectionTitle title="Sentiment across all comments"
        hint="Lexicon baseline labels. This is a rule-based estimate, not a measured accuracy figure." />
      <div role="img" aria-label={seg.map(([k, l]) => `${l} ${s.sentiment[k].percent}%`).join(', ')} className="flex h-9 w-full overflow-hidden rounded-lg bg-ink-900">
        {seg.map(([k, , c]) => s.sentiment[k].count > 0 && <div key={k} style={{ width: `${s.sentiment[k].percent}%`, background: c }} />)}
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        {seg.map(([k, l, c]) => (
          <div key={k} className="flex items-baseline gap-3">
            <span className="h-3 w-3 shrink-0 rounded-sm" style={{ background: c }} aria-hidden="true" />
            <span className="text-sm text-mist-300">{l}</span>
            <span className="ml-auto text-lg font-bold">{nf.format(s.sentiment[k].count)}</span>
            <span className="w-14 text-right text-sm text-mist-500">{pct(s.sentiment[k].percent)}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

export default function Overview({ analysis, health, onNavigate }) {
  if (!analysis) {
    return (
      <div className="space-y-6">
        <StatusRow health={health} analysis={null} />
        <EmptyState icon={BarChart3} title="No comments analyzed yet"
          actions={<>
            <button className="btn-primary" onClick={() => onNavigate('comments')}><UploadCloud className="h-4 w-4" />Upload a CSV</button>
            <button className="btn-ghost" onClick={() => onNavigate('url')}><Link2 className="h-4 w-4" />Search TikTok videos</button>
          </>}>
          Upload a CSV of TikTok comments to see sentiment, promotional signals, repeated wording and potential coordination indicators.
          Every number in this dashboard comes from data you upload; nothing here is sample or placeholder data.
        </EmptyState>
        {health?.error && <Alert tone="error" title="The backend is not reachable">{health.error}</Alert>}
      </div>
    );
  }
  const s = analysis.summary;
  const promoData = analysis.promotional.category_counts;
  return (
    <div className="space-y-6">
      <StatusRow health={health} analysis={analysis} />
      <Spectrum s={s} />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Comments analyzed" value={nf.format(s.total_comments)} sub={`of ${nf.format(analysis.quality.rows_received)} rows received`} />
        <Stat label="Promotional signals" value={nf.format(s.promotional_signals)} sub={`${pct(s.promotional_signals_percent)} of comments, not confirmed ads`} tone="text-violet-300" />
        <Stat label="In repeated or similar groups" value={nf.format(s.comments_in_repeated_groups)} sub={`${pct(s.repeated_percent)} of comments`} />
        <Stat label="Coordination indicators" value={`${s.notable_coordination_indicators} of ${s.available_coordination_indicators}`} sub="moderate or strong; potential only" />
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <SectionTitle title="Promotional signals by type" hint="A comment can match more than one type." />
          {promoData.length ? (
            <div className="h-60" role="img" aria-label="Bar chart of promotional signals by type">
              <ResponsiveContainer>
                <BarChart data={promoData} layout="vertical" margin={{ left: 10, right: 16 }}>
                  <CartesianGrid stroke={COLORS.grid} horizontal={false} />
                  <XAxis type="number" allowDecimals={false} stroke="#8794BA" fontSize={12} />
                  <YAxis type="category" dataKey="label" width={150} stroke="#8794BA" fontSize={12} />
                  <Tooltip {...ChartTooltipStyle} />
                  <Bar dataKey="count" name="Comments" isAnimationActive={false} fill={COLORS.promo} radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : <p className="rounded-lg border border-dashed border-ink-600 p-6 text-center text-sm text-mist-500">No promotional signals were found in this file.</p>}
        </Card>
        <Card>
          <SectionTitle title="Dataset at a glance" />
          <dl className="space-y-2 text-sm">
            {[['Analyzed', fmtDate(analysis.data_source.analyzed_at)],
              ['Empty comments removed', analysis.quality.empty_comments_removed],
              ['Malformed rows skipped', analysis.quality.malformed_rows_skipped],
              ['Timestamps usable', analysis.quality.timestamps_parsed ? `${analysis.quality.timestamps_parsed} rows` : 'none'],
              ['Distinct video IDs', analysis.quality.distinct_video_ids || 'none']].map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4 border-b border-ink-600/40 pb-2"><dt className="text-mist-500">{k}</dt><dd className="font-semibold">{v}</dd></div>
            ))}
          </dl>
          <button className="btn-ghost mt-4" onClick={() => onNavigate('coordination')}>View coordination signals</button>
        </Card>
      </div>
    </div>
  );
}
