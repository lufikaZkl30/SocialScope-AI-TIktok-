import { useMemo, useRef, useState } from 'react';
import { Download, FileUp } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { analyzeCsv } from '../api.js';
import { Alert, Badge, Card, ChartTooltipStyle, DataTable, SectionTitle, Spinner, Stat, Tabs } from '../components/ui.jsx';
import { COLORS, download, nf, pct } from '../utils.js';

const MAX_MB = 5;

function UploadPanel({ onResult, hasData }) {
  const [file, setFile] = useState(null);
  const [threshold, setThreshold] = useState(0.8);
  const [state, setState] = useState({ status: 'idle' });
  const [drag, setDrag] = useState(false);
  const input = useRef(null);

  function pick(f) {
    if (!f) return;
    if (!f.name.toLowerCase().endsWith('.csv')) return setState({ status: 'error', message: 'Only .csv files are supported.' });
    if (f.size > MAX_MB * 1024 * 1024) return setState({ status: 'error', message: `The file is larger than ${MAX_MB} MB.` });
    setFile(f); setState({ status: 'idle' });
  }
  async function run() {
    setState({ status: 'loading' });
    try { onResult(await analyzeCsv(file, threshold)); setState({ status: 'done' }); }
    catch (e) { setState({ status: 'error', message: e.message }); }
  }
  return (
    <Card>
      <SectionTitle title={hasData ? 'Analyze another file' : 'Upload a comments CSV'}
        hint="Required column: comment. Optional: timestamp, video_id, label (your own positive/neutral/negative labels, used only to measure the baseline). A username column is ignored and never returned."
        right={<button className="btn-ghost" onClick={() => download('comments_template.csv', 'comment,timestamp,video_id,label\r\n')}><Download className="h-4 w-4" />CSV template</button>} />
      <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files[0]); }}
        className={`flex flex-col items-center rounded-xl border-2 border-dashed px-4 py-8 text-center ${drag ? 'border-cyan-400 bg-cyan-400/5' : 'border-ink-600'}`}>
        <FileUp className="mb-2 h-7 w-7 text-violet-300" aria-hidden="true" />
        <p className="text-sm text-mist-300">{file ? <><strong>{file.name}</strong> ({(file.size / 1024).toFixed(1)} KB)</> : 'Drop a .csv file here, or'}</p>
        <input ref={input} type="file" accept=".csv,text/csv" className="sr-only" id="csv-file" onChange={(e) => pick(e.target.files[0])} />
        <label htmlFor="csv-file" className="btn-ghost mt-3 cursor-pointer focus-within:outline">Choose file</label>
      </div>
      <div className="mt-5 grid gap-4 sm:grid-cols-[1fr_auto] sm:items-end">
        <div>
          <label htmlFor="thr" className="text-sm font-medium">Similarity threshold: <span className="text-cyan-400">{threshold.toFixed(2)}</span></label>
          <input id="thr" type="range" min="0.6" max="0.95" step="0.01" value={threshold} onChange={(e) => setThreshold(+e.target.value)} className="mt-2 w-full accent-violet-500" />
          <p className="text-xs text-mist-500">Higher means only near-identical comments are grouped. Max {MAX_MB} MB per file.</p>
        </div>
        <button className="btn-primary" disabled={!file || state.status === 'loading'} onClick={run}>
          {state.status === 'loading' ? <Spinner label="Analyzing…" /> : 'Analyze comments'}
        </button>
      </div>
      {state.status === 'error' && <Alert tone="error" title="Could not analyze this file" className="mt-4">{state.message}</Alert>}
      {state.status === 'done' && <Alert tone="success" className="mt-4">Analysis complete. Results are shown below and on the other pages.</Alert>}
      <p className="mt-4 text-xs text-mist-500">Your file is analyzed in memory on the local backend and is not stored. Results stay in this browser tab only.</p>
    </Card>
  );
}

function SentimentTab({ a }) {
  const s = a.summary.sentiment;
  const data = ['positive', 'neutral', 'negative'].map((k) => ({ name: k[0].toUpperCase() + k.slice(1), key: k, value: s[k].count }));
  const terms = useMemo(() => {
    const t = {};
    a.comments.forEach((c) => c.matched_terms.forEach((m) => { const k = m.replace(' (negated)', ''); t[k] = (t[k] || 0) + 1; }));
    const list = Object.entries(t).map(([term, count]) => ({ term, count }));
    return { pos: list.filter((x) => x.term[0] === '+').sort((x, y) => y.count - x.count).slice(0, 8), neg: list.filter((x) => x.term[0] === '-').sort((x, y) => y.count - x.count).slice(0, 8) };
  }, [a]);
  const ev = a.sentiment.evaluation;
  return (
    <div className="space-y-6">
      <Alert tone="info" title={`Method: ${a.sentiment.method.name} (${a.sentiment.method.type})`}>
        Words from a small Indonesian lexicon are scored, with simple handling of negation and intensifiers. It is a transparent baseline and does not understand sarcasm or context. {a.sentiment.method.claims_accuracy ? '' : 'No accuracy is claimed.'}
      </Alert>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <SectionTitle title="Distribution" />
          <div className="h-56" role="img" aria-label={data.map((d) => `${d.name}: ${d.value}`).join(', ')}>
            <ResponsiveContainer>
              <PieChart>
                <Pie isAnimationActive={false} data={data} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={2} stroke="none">
                  {data.map((d) => <Cell key={d.key} fill={COLORS[d.key]} />)}
                </Pie>
                <Tooltip {...ChartTooltipStyle} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <ul className="mt-2 grid grid-cols-3 text-center text-sm">
            {data.map((d) => <li key={d.key}><span className="mr-1.5 inline-block h-2.5 w-2.5 rounded-sm" style={{ background: COLORS[d.key] }} />{d.name}<br /><strong>{nf.format(d.value)}</strong> <span className="text-mist-500">({pct(s[d.key].percent)})</span></li>)}
          </ul>
        </Card>
        <Card>
          <SectionTitle title="Most frequent matched words" hint="The lexicon words that drove the labels. A minus sign marks a word counted as negative, including positive words that were negated." />
          <div className="grid gap-4 sm:grid-cols-2 text-sm">
            {[['Positive', terms.pos, 'text-cyan-400'], ['Negative', terms.neg, 'text-neg']].map(([t, list, c]) => (
              <div key={t}><p className={`mb-2 font-semibold ${c}`}>{t}</p>
                {list.length ? <ul className="space-y-1">{list.map((x) => <li key={x.term} className="flex justify-between"><span>{x.term.slice(1)}</span><span className="text-mist-500">{x.count}</span></li>)}</ul> : <p className="text-mist-500">None matched</p>}
              </div>
            ))}
          </div>
        </Card>
      </div>
      <Card>
        <SectionTitle title="Evaluation against your labels" />
        {ev ? (
          <>
            <div className="grid gap-3 sm:grid-cols-3">
              <Stat label="Accuracy" value={pct(ev.accuracy * 100)} sub={`on ${ev.n_labeled} labelled comments`} />
              <Stat label="Macro F1" value={ev.macro_f1.toFixed(3)} />
              <Stat label="Labelled rows" value={ev.n_labeled} />
            </div>
            <div className="mt-4"><DataTable caption="Per-class metrics" rows={Object.entries(ev.per_class).map(([k, v]) => ({ cls: k, ...v }))}
              columns={[{ key: 'cls', label: 'Class' }, { key: 'precision', label: 'Precision' }, { key: 'recall', label: 'Recall' }, { key: 'f1', label: 'F1' }, { key: 'support', label: 'Support' }]} /></div>
            <p className="mt-3 text-xs text-mist-500">{ev.note}</p>
          </>
        ) : <p className="text-sm text-mist-500">{a.sentiment.evaluation_note} To measure the baseline, add a <code>label</code> column with positive, neutral or negative values you assigned yourself.</p>}
      </Card>
    </div>
  );
}

function CommentsTab({ a }) {
  const [f, setF] = useState({ sentiment: 'all', promo: false, repeated: false, q: '' });
  const rows = useMemo(() => a.comments.filter((c) =>
    (f.sentiment === 'all' || c.sentiment === f.sentiment) && (!f.promo || c.promo_signal) &&
    (!f.repeated || c.duplicate_group || c.similar_group) && (!f.q || c.text.toLowerCase().includes(f.q.toLowerCase()))), [a, f]);
  return (
    <Card>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <input className="input max-w-xs" placeholder="Search comments" aria-label="Search comments" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} />
        <select className="input w-auto" aria-label="Filter by sentiment" value={f.sentiment} onChange={(e) => setF({ ...f, sentiment: e.target.value })}>
          <option value="all">All sentiments</option><option value="positive">Positive</option><option value="neutral">Neutral</option><option value="negative">Negative</option>
        </select>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="accent-violet-500" checked={f.promo} onChange={(e) => setF({ ...f, promo: e.target.checked })} />Promotional signal</label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="accent-violet-500" checked={f.repeated} onChange={(e) => setF({ ...f, repeated: e.target.checked })} />Repeated wording</label>
        <span className="ml-auto text-sm text-mist-500">{nf.format(rows.length)} comments</span>
      </div>
      <DataTable caption="Analyzed comments" rows={rows} pageSize={20} empty="No comments match these filters."
        columns={[
          { key: 'row', label: 'Row', className: 'w-14 text-mist-500' },
          { key: 'text', label: 'Comment (personal identifiers masked)', render: (r) => <span className="break-words">{r.text}</span> },
          { key: 'sentiment', label: 'Sentiment', render: (r) => <div><Badge tone={r.sentiment}>{r.sentiment}</Badge><div className="mt-1 text-xs text-mist-500">score {r.score}</div></div> },
          { key: 'flags', label: 'Flags', render: (r) => <div className="flex flex-col items-start gap-1">
            {r.promo_signal && <Badge tone="violet">promo signal</Badge>}
            {(r.duplicate_group || r.similar_group) && <Badge tone="warn">repeated wording</Badge>}</div> },
        ]} />
    </Card>
  );
}

function PromoTab({ a }) {
  const flagged = a.comments.filter((c) => c.promo_signal);
  return (
    <div className="space-y-6">
      <Alert tone="warn" title="Signals, not verdicts">{a.promotional.disclaimer} Many people recommend products, share links or mention discounts without being paid.</Alert>
      <Card>
        <SectionTitle title={`Flagged comments (${flagged.length})`} hint="'Stronger' means more than one kind of signal matched. 'Weak' means one." />
        <DataTable caption="Comments with promotional signals" rows={flagged} empty="No promotional signals were found in this file."
          columns={[{ key: 'row', label: 'Row', className: 'w-14 text-mist-500' },
            { key: 'text', label: 'Comment', render: (r) => <span className="break-words">{r.text}</span> },
            { key: 'promo_reason', label: 'Why it was flagged', render: (r) => r.promo_reason },
            { key: 'promo_signal', label: 'Signal', render: (r) => <Badge tone={r.promo_signal === 'stronger' ? 'stronger' : 'weak'}>{r.promo_signal} signal</Badge> }]} />
      </Card>
    </div>
  );
}

function SimilarTab({ a }) {
  const s = a.similarity, c = s.counts;
  return (
    <div className="space-y-6">
      <Alert tone="info" title="How to read this">{s.note} Similarity uses TF-IDF on character n-grams with cosine similarity (threshold {s.threshold.toFixed(2)}).</Alert>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Exact duplicate groups" value={c.exact_duplicate_groups} sub={`${c.comments_in_exact_duplicates} comments`} />
        <Stat label="Normalized duplicate groups" value={c.normalized_duplicate_groups} sub="same after cleaning text" />
        <Stat label="Similar-text groups" value={c.similar_groups} sub={`${c.comments_in_similar_groups} comments`} />
        <Stat label="Comments in any group" value={pct(c.share_in_any_repeat * 100)} />
      </div>
      <Card>
        <SectionTitle title="Exact and normalized duplicates" />
        <DataTable caption="Duplicate groups" rows={[...s.exact_duplicate_groups, ...s.normalized_duplicate_groups]} empty="No duplicate comments found."
          columns={[{ key: 'text', label: 'Comment', render: (r) => <span className="break-words">{r.text}</span> },
            { key: 'size', label: 'Copies', className: 'w-20' },
            { key: 'kind', label: 'Type', render: (r) => <Badge tone={r.kind === 'exact' ? 'violet' : 'warn'}>{r.kind === 'exact' ? 'exact' : 'after cleaning'}</Badge> },
            { key: 'rows', label: 'Rows', render: (r) => <span className="text-mist-500">{r.rows.slice(0, 8).join(', ')}{r.rows.length > 8 ? '…' : ''}</span> }]} />
      </Card>
      <Card>
        <SectionTitle title="Similar (not identical) comment groups" hint="Comments with different wording but high text similarity." />
        <DataTable caption="Similar comment groups" rows={s.similar_groups} pageSize={10} empty="No similar-text groups at this threshold."
          columns={[{ key: 'examples', label: 'Example wording', render: (r) => <ul className="space-y-1">{r.examples.slice(0, 3).map((t, i) => <li key={i} className="break-words">{t}</li>)}</ul> },
            { key: 'size', label: 'Comments', className: 'w-24' },
            { key: 'avg_similarity', label: 'Avg. similarity', render: (r) => `${r.avg_similarity} (min ${r.min_similarity})` }]} />
      </Card>
      <Card>
        <SectionTitle title="Repeated phrases" hint="Three- and four-word phrases that appear in at least three different comments." />
        <DataTable caption="Repeated phrases" rows={s.repeated_phrases} empty="No phrase is repeated across enough comments."
          columns={[{ key: 'phrase', label: 'Phrase' }, { key: 'comments', label: 'Comments', className: 'w-24' }, { key: 'share', label: 'Share', render: (r) => pct(r.share * 100) }]} />
      </Card>
    </div>
  );
}

export default function CommentAnalysis({ analysis, setAnalysis }) {
  const [tab, setTab] = useState('sentiment');
  return (
    <div className="space-y-6">
      <UploadPanel hasData={!!analysis} onResult={(r) => { setAnalysis(r); setTab('sentiment'); }} />
      {analysis && (
        <>
          <Tabs value={tab} onChange={setTab} tabs={[{ id: 'sentiment', label: 'Sentiment' }, { id: 'comments', label: 'Comments' }, { id: 'promo', label: 'Promotional signals' }, { id: 'similar', label: 'Similar wording' }]} />
          {tab === 'sentiment' && <SentimentTab a={analysis} />}
          {tab === 'comments' && <CommentsTab a={analysis} />}
          {tab === 'promo' && <PromoTab a={analysis} />}
          {tab === 'similar' && <SimilarTab a={analysis} />}
        </>
      )}
    </div>
  );
}
