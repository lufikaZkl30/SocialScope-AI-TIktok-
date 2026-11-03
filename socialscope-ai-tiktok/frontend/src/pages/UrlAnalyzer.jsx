import { useState } from 'react';
import { CheckCircle2, MinusCircle, Search, XCircle } from 'lucide-react';
import { analyzeUrl } from '../api.js';
import { Alert, Card, SectionTitle, Spinner } from '../components/ui.jsx';

function Step({ ok, title, detail }) {
  const Icon = ok === true ? CheckCircle2 : ok === false ? XCircle : MinusCircle;
  const color = ok === true ? 'text-cyan-400' : ok === false ? 'text-neg' : 'text-mist-500';
  return (
    <li className="flex gap-3">
      <Icon className={`mt-0.5 h-5 w-5 shrink-0 ${color}`} aria-hidden="true" />
      <div><p className="text-sm font-semibold">{title}</p><p className="text-sm text-mist-500">{detail}</p></div>
    </li>
  );
}

export default function UrlAnalyzer({ health, onNavigate }) {
  const [url, setUrl] = useState('');
  const [state, setState] = useState({ status: 'idle' });
  const connector = health?.integrations?.tiktok_api;

  async function submit(e) {
    e.preventDefault();
    setState({ status: 'loading' });
    try { setState({ status: 'done', data: await analyzeUrl(url) }); }
    catch (err) { setState({ status: 'error', message: err.message }); }
  }
  const d = state.data;
  return (
    <div className="space-y-6">
      <Alert tone="warn" title="Automatic comment retrieval is not available">
        {connector?.message || 'This app has no authorized TikTok API connector, so it cannot fetch comments from a URL.'}{' '}
        It never scrapes TikTok or bypasses access restrictions. The URL check below validates the link format only.
      </Alert>
      <Card>
        <SectionTitle title="Check a TikTok video URL" hint="Supported domains: tiktok.com, www.tiktok.com, m.tiktok.com, vm.tiktok.com and vt.tiktok.com." />
        <form onSubmit={submit} className="flex flex-col gap-3 sm:flex-row">
          <label className="sr-only" htmlFor="tt-url">TikTok video URL</label>
          <input id="tt-url" className="input" inputMode="url" autoComplete="off" placeholder="https://www.tiktok.com/@username/video/1234567890123456789"
            value={url} onChange={(e) => setUrl(e.target.value)} required />
          <button className="btn-primary sm:w-44" disabled={state.status === 'loading' || !url.trim()}>
            {state.status === 'loading' ? <Spinner label="Checking…" /> : <><Search className="h-4 w-4" />Validate URL</>}
          </button>
        </form>
        {state.status === 'error' && <Alert tone="error" title="URL not accepted" className="mt-4">{state.message}</Alert>}
      </Card>

      {d && (
        <Card>
          <SectionTitle title="Result" hint={d.message} />
          <ul className="space-y-4">
            <Step ok={d.url_valid} title="URL format validated" detail={`Recognised as a TikTok ${d.url.url_type === 'video' ? 'video link' : 'short link'}.`} />
            <Step ok={d.comments_retrieved > 0} title="Comments retrieved" detail={`${d.comments_retrieved} comments retrieved. Nothing was fetched from TikTok.`} />
            <Step ok={d.content_analyzed} title="Content analyzed" detail="No analysis was run on this URL because there is no comment data." />
            <Step ok={d.integration.configured} title="Authorized API connector" detail={d.integration.message} />
          </ul>
          <dl className="mt-5 grid gap-3 rounded-lg bg-ink-900/60 p-4 text-sm sm:grid-cols-2">
            <div><dt className="text-xs text-mist-500">Normalized URL</dt><dd className="break-all font-medium">{d.url.normalized_url}</dd></div>
            <div><dt className="text-xs text-mist-500">Video ID</dt><dd className="font-medium">{d.url.video_id || 'Unknown'}</dd></div>
            {d.url.note && <div className="sm:col-span-2 text-mist-500">{d.url.note}</div>}
          </dl>
          <div className="mt-5"><p className="mb-3 text-sm text-mist-300">{d.next_step}</p>
            <button className="btn-primary" onClick={() => onNavigate('comments')}>Go to Comment Analysis</button></div>
        </Card>
      )}
    </div>
  );
}
