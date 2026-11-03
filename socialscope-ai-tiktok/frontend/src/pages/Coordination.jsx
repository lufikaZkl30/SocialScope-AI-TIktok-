import { Network, UploadCloud } from 'lucide-react';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Alert, Badge, Card, ChartTooltipStyle, DataTable, EmptyState, SectionTitle } from '../components/ui.jsx';
import { COLORS, fmtDate, pct } from '../utils.js';

const STRENGTH_TEXT = { none: 'not observed', weak: 'weak signal', moderate: 'moderate signal', strong: 'strong signal', unavailable: 'unavailable' };

export default function Coordination({ analysis, onNavigate }) {
  if (!analysis) {
    return <EmptyState icon={Network} title="No data for coordination analysis"
      actions={<button className="btn-primary" onClick={() => onNavigate('comments')}><UploadCloud className="h-4 w-4" />Upload a CSV</button>}>
      Potential coordination indicators are computed from repeated text, similarity, posting times and video IDs in a CSV you upload.
    </EmptyState>;
  }
  const c = analysis.coordination, t = c.time;
  return (
    <div className="space-y-6">
      <Alert tone="warn" title="Indicators, not proof">{c.disclaimer}</Alert>
      {c.summary.sample_size_warning && <Alert tone="info" title="Small sample">Fewer than 50 comments were analyzed, so these indicators are unstable.</Alert>}
      <p className="text-sm text-mist-300">{c.summary.headline}</p>
      <div className="grid gap-4 md:grid-cols-2">
        {c.indicators.map((i) => (
          <Card key={i.id} className={i.available ? '' : 'opacity-70'}>
            <div className="flex items-start justify-between gap-3">
              <h2 className="text-base font-semibold">{i.title}</h2>
              <Badge tone={i.strength}>{STRENGTH_TEXT[i.strength]}</Badge>
            </div>
            <p className="mt-3 text-lg font-bold">{i.value_label}</p>
            <p className="mt-2 text-sm leading-relaxed text-mist-500">{i.explanation}</p>
          </Card>
        ))}
      </div>

      <Card>
        <SectionTitle title="Comment activity over time" hint={t ? `${t.dated_comments} dated comments, ${fmtDate(t.first)} to ${fmtDate(t.last)}. Counts ${t.bucket}.` : undefined} />
        {t ? (
          <>
            <div className="h-64" role="img" aria-label="Area chart of comment counts over time">
              <ResponsiveContainer>
                <AreaChart data={t.series} margin={{ left: 0, right: 12 }}>
                  <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#8B5CF6" stopOpacity={0.5} /><stop offset="100%" stopColor="#8B5CF6" stopOpacity={0} /></linearGradient></defs>
                  <CartesianGrid stroke={COLORS.grid} vertical={false} />
                  <XAxis dataKey="t" tickFormatter={(v) => new Date(v).toISOString().slice(5, 16).replace('T', ' ')} stroke="#8794BA" fontSize={11} minTickGap={40} />
                  <YAxis allowDecimals={false} stroke="#8794BA" fontSize={12} width={36} />
                  <Tooltip {...ChartTooltipStyle} labelFormatter={fmtDate} />
                  <Area isAnimationActive={false} type="monotone" dataKey="count" name="Comments" stroke="#22D3EE" fill="url(#g)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            {t.chart_note && <p className="mt-2 text-xs text-mist-500">{t.chart_note}</p>}
            <h3 className="mb-2 mt-5 text-sm font-semibold">Burst windows</h3>
            <DataTable caption="Burst windows" rows={t.bursts} empty="No window exceeds the dataset's average by 3 standard deviations."
              columns={[{ key: 'bucket_start', label: 'Window start', render: (r) => fmtDate(r.bucket_start) },
                { key: 'comments', label: 'Comments' },
                { key: 'share_of_dated_comments', label: 'Share of dated comments', render: (r) => pct(r.share_of_dated_comments * 100) },
                { key: 'share_also_repeated_text', label: 'Also repeated text', render: (r) => pct(r.share_also_repeated_text * 100) }]} />
          </>
        ) : <p className="rounded-lg border border-dashed border-ink-600 p-6 text-center text-sm text-mist-500">No chart: the file needs a timestamp column with at least 20 parseable values ({analysis.quality.timestamps_parsed} found).</p>}
      </Card>

      <Card>
        <SectionTitle title="Same text across videos" />
        {c.cross_video ? (
          <DataTable caption="Texts repeated across videos" rows={c.cross_video.examples} empty="No text appears under more than one video."
            columns={[{ key: 'text', label: 'Comment text', render: (r) => <span className="break-words">{r.text}</span> }, { key: 'videos', label: 'Videos' }, { key: 'comments', label: 'Comments' }]} />
        ) : <p className="rounded-lg border border-dashed border-ink-600 p-6 text-center text-sm text-mist-500">Unavailable: needs a video_id column with at least two different videos.</p>}
      </Card>
    </div>
  );
}
