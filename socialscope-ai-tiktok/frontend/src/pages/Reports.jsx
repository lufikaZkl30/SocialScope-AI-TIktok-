import { Download, FileText, UploadCloud } from 'lucide-react';
import { Alert, Card, DataTable, EmptyState, SectionTitle } from '../components/ui.jsx';
import { download, nf, pct, toCsv } from '../utils.js';

export default function Reports({ analysis: a, onNavigate }) {
  if (!a) {
    return <EmptyState icon={FileText} title="No report available"
      actions={<button className="btn-primary" onClick={() => onNavigate('comments')}><UploadCloud className="h-4 w-4" />Upload a CSV</button>}>
      Reports are generated from the CSV you analyze. Upload a file first.
    </EmptyState>;
  }
  const q = a.quality, s = a.summary;
  const stamp = new Date().toISOString().slice(0, 10);
  const exportComments = () => download(`socialscope_comment_results_${stamp}.csv`, toCsv([
    ['row', 'comment', 'sentiment', 'sentiment_score', 'matched_terms', 'promotional_signal', 'promotional_reason', 'in_duplicate_group', 'in_similar_group'],
    ...a.comments.map((c) => [c.row, c.text, c.sentiment, c.score, c.matched_terms.join(' '), c.promo_signal || '', c.promo_reason || '', c.duplicate_group ? 'yes' : 'no', c.similar_group ? 'yes' : 'no'])]));
  const exportSummary = () => download(`socialscope_summary_${stamp}.csv`, toCsv([
    ['metric', 'value'], ['source_file', a.data_source.filename], ['comments_analyzed', s.total_comments],
    ['positive', s.sentiment.positive.count], ['neutral', s.sentiment.neutral.count], ['negative', s.sentiment.negative.count],
    ['sentiment_method', a.sentiment.method.id], ['promotional_signals', s.promotional_signals],
    ['comments_in_repeated_groups', s.comments_in_repeated_groups],
    ...a.coordination.indicators.map((i) => [`indicator_${i.id}`, `${i.strength}: ${i.value_label}`]),
    ['note', 'Potential indicators only; not proof of coordinated behaviour.']]));
  const quality = [
    ['Rows received', q.rows_received], ['Comments analyzed', q.rows_analyzed], ['Empty comments removed', q.empty_comments_removed],
    ['Malformed rows skipped', q.malformed_rows_skipped], ['Very short comments (under 2 words)', q.very_short_comments],
    ['Timestamps parsed', q.timestamps_parsed], ['Timestamps unparseable', q.timestamps_unparseable],
    ['Rows with a video ID', q.video_ids_present], ['Distinct video IDs', q.distinct_video_ids],
    ['Username column', q.username_column_ignored ? 'Present, ignored' : 'Not present'],
    ['Columns used', Object.entries(q.columns_detected).filter(([, v]) => v).map(([k, v]) => `${k} (${v})`).join(', ')],
  ].map(([metric, value]) => ({ metric, value: typeof value === 'number' ? nf.format(value) : value }));
  const share = [['Positive', s.sentiment.positive], ['Neutral', s.sentiment.neutral], ['Negative', s.sentiment.negative]]
    .map(([k, v]) => ({ k, n: nf.format(v.count), p: pct(v.percent) }));
  return (
    <div className="space-y-6">
      <Card>
        <SectionTitle title="Export results" hint="Exports contain comment text with emails, phone numbers and @mentions masked. They never include usernames. Cells that start with a formula character are escaped." />
        <div className="flex flex-wrap gap-3">
          <button className="btn-primary" onClick={exportComments}><Download className="h-4 w-4" />Comment results (CSV)</button>
          <button className="btn-ghost" onClick={exportSummary}><Download className="h-4 w-4" />Summary (CSV)</button>
        </div>
      </Card>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card><SectionTitle title="Dataset quality" /><DataTable caption="Dataset quality" rows={quality} pageSize={20} columns={[{ key: 'metric', label: 'Measure' }, { key: 'value', label: 'Value' }]} /></Card>
        <Card><SectionTitle title="Sentiment summary" hint={`Method: ${a.sentiment.method.name}.`} />
          <DataTable caption="Sentiment summary" rows={share} columns={[{ key: 'k', label: 'Sentiment' }, { key: 'n', label: 'Comments' }, { key: 'p', label: 'Share' }]} />
          <p className="mt-3 text-sm text-mist-500">{a.sentiment.evaluation ? `Baseline accuracy on ${a.sentiment.evaluation.n_labeled} of your labelled rows: ${pct(a.sentiment.evaluation.accuracy * 100)}.` : a.sentiment.evaluation_note}</p>
        </Card>
      </div>
      <Card>
        <SectionTitle title="Limitations of this analysis" />
        <ul className="list-disc space-y-2 pl-5 text-sm leading-relaxed text-mist-300">{a.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
      </Card>
      {q.rows_analyzed < 50 && <Alert tone="warn" title="Small dataset">With fewer than 50 comments, percentages and indicators can change a lot from one comment.</Alert>}
    </div>
  );
}
