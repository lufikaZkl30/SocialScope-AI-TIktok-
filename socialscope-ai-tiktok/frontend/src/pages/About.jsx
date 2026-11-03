import { useEffect, useState } from 'react';
import { getMethodology } from '../api.js';
import { Alert, Badge, Card, SectionTitle, Spinner } from '../components/ui.jsx';

const FUTURE = [
  'Connect an authorized TikTok data source by implementing the CommentSource interface in backend/integrations/tiktok.py.',
  'Evaluate and compare an Indonesian transformer model (for example IndoBERT) against the lexicon baseline on labelled data.',
  'Add a labelled Indonesian test set and a repeatable evaluation report.',
  'Add language detection for mixed Indonesian, English and regional-language comments.',
  'Add background jobs so larger files can be analyzed without a row limit.',
];

export default function About() {
  const [m, setM] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { getMethodology().then(setM).catch((e) => setErr(e.message)); }, []);
  return (
    <div className="space-y-6">
      <Card>
        <SectionTitle title="SocialScope AI — TikTok Social Intelligence Platform" />
        <p className="max-w-3xl text-sm leading-relaxed text-mist-300">An AI-powered platform for exploring TikTok comment sentiment, promotional patterns, and potential coordinated activity through data-driven analysis.</p>
        <Alert tone="warn" className="mt-4" title="Independent, unofficial project">Built as an educational AI engineering portfolio project. It is not affiliated with, endorsed by or connected to TikTok or ByteDance.</Alert>
      </Card>
      {err && <Alert tone="error" title="Methodology unavailable">{err}</Alert>}
      {!m && !err && <Spinner label="Loading methodology…" />}
      {m && (
        <>
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <SectionTitle title="Sentiment" />
              <p className="mb-2"><Badge tone="violet">baseline</Badge></p>
              <p className="text-sm leading-relaxed text-mist-300">{m.sentiment.name}: {m.sentiment.type}. Language: {m.sentiment.language}. Handles simple negation and intensifiers; cannot detect sarcasm. Accuracy is never assumed; it is computed only when you supply labels.</p>
            </Card>
            <Card>
              <SectionTitle title="Similar and repeated comments" />
              <p className="text-sm leading-relaxed text-mist-300">{m.similarity.method}, default threshold {m.similarity.default_threshold}. Exact and normalized duplicates are grouped first; repeated 3–4 word phrases are counted across comments.</p>
            </Card>
          </div>
          <Card>
            <SectionTitle title="Promotional keyword categories" hint="Configurable in the backend (PROMO_KEYWORDS_PATH). A match is a signal, not confirmed advertising." />
            <div className="grid gap-4 md:grid-cols-2">
              {Object.entries(m.promotional_categories).map(([k, v]) => (
                <div key={k}><p className="mb-1.5 text-sm font-semibold">{v.label}</p>
                  <p className="flex flex-wrap gap-1.5">{v.keywords.map((w) => <span key={w} className="rounded bg-ink-900 px-2 py-0.5 text-xs text-mist-300">{w}</span>)}</p></div>
              ))}
            </div>
            <p className="mt-4 text-sm text-mist-500">Links and Indonesian phone numbers are also treated as signals.</p>
          </Card>
          <div className="grid gap-6 lg:grid-cols-2">
            <Card><SectionTitle title="Privacy" /><ul className="list-disc space-y-2 pl-5 text-sm leading-relaxed text-mist-300">
              <li>Usernames are not needed and are ignored if present.</li><li>Emails, phone numbers and @mentions are masked in results and exports.</li>
              <li>Files are processed in memory and are not saved by the backend.</li><li>No account or person is labelled a bot or buzzer.</li></ul></Card>
            <Card><SectionTitle title="Limitations" /><ul className="list-disc space-y-2 pl-5 text-sm leading-relaxed text-mist-300">{m.limitations.map((l) => <li key={l}>{l}</li>)}</ul></Card>
          </div>
        </>
      )}
      <Card><SectionTitle title="Future improvements" /><ul className="list-disc space-y-2 pl-5 text-sm leading-relaxed text-mist-300">{FUTURE.map((f) => <li key={f}>{f}</li>)}</ul></Card>
    </div>
  );
}
