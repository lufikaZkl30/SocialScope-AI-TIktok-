import { useState } from 'react';
import { CheckCircle2, MinusCircle, Search, XCircle } from 'lucide-react';
import { analyzeUrl, searchResearchVideos } from '../api.js';
import { Alert, Card, SectionTitle, Spinner } from '../components/ui.jsx';

const EMPTY_QUERY = {
  keyword: '',
  region_codes: 'US, CA',
  start_date: '',
  end_date: '',
  max_count: '100',
};

const VIDEO_FIELDS = ['id', 'like_count', 'view_count', 'comment_count', 'share_count'];

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

function formattedCount(value) {
  return Number.isFinite(value) ? value.toLocaleString() : 'Not provided';
}

export default function UrlAnalyzer({ health, onNavigate }) {
  const [url, setUrl] = useState('');
  const [state, setState] = useState({ status: 'idle' });
  const [form, setForm] = useState(EMPTY_QUERY);
  const [queryState, setQueryState] = useState({ status: 'idle', videos: [], hasMore: false, cursor: 0 });
  const researchApi = health?.integrations?.tiktok_research_api;

  async function submitUrl(e) {
    e.preventDefault();
    setState({ status: 'loading' });
    try { setState({ status: 'done', data: await analyzeUrl(url) }); }
    catch (err) { setState({ status: 'error', message: err.message }); }
  }

  function makeQuery(cursor = 0) {
    return {
      keyword: form.keyword.trim(),
      region_codes: form.region_codes.split(',').map((code) => code.trim().toUpperCase()).filter(Boolean),
      start_date: form.start_date.replaceAll('-', ''),
      end_date: form.end_date.replaceAll('-', ''),
      max_count: Number(form.max_count),
      cursor,
    };
  }

  async function submitSearch(e) {
    e.preventDefault();
    const query = makeQuery();
    setQueryState({ status: 'loading', videos: [], hasMore: false, cursor: 0, query });
    try {
      const result = await searchResearchVideos(query);
      setQueryState({
        status: 'done',
        videos: Array.isArray(result.videos) ? result.videos : [],
        hasMore: result.has_more === true,
        cursor: result.cursor || 0,
        query,
      });
    } catch (err) {
      setQueryState({ status: 'error', message: err.message, videos: [], hasMore: false, cursor: 0, query });
    }
  }

  async function loadMore() {
    const query = { ...queryState.query, cursor: queryState.cursor };
    setQueryState({ ...queryState, loadingMore: true, message: null });
    try {
      const result = await searchResearchVideos(query);
      setQueryState({
        ...queryState,
        loadingMore: false,
        videos: [...queryState.videos, ...(Array.isArray(result.videos) ? result.videos : [])],
        hasMore: result.has_more === true,
        cursor: result.cursor || 0,
      });
    } catch (err) {
      setQueryState({ ...queryState, loadingMore: false, message: err.message });
    }
  }

  const d = state.data;
  const videos = queryState.videos;
  return (
    <div className="space-y-6">
      {health?.error && <Alert tone="error" title="Backend tidak tersambung">{health.error}</Alert>}
      <Alert tone="warn" title={researchApi?.configured ? 'Research API video search is enabled' : 'TikTok Research API is not configured'}>
        {researchApi?.message || 'Backend belum melaporkan status Research API. Pastikan backend berjalan, lalu muat ulang halaman.'}{' '}
        This feature returns public video metadata only, not comments. Use it only with approved Research API access.
      </Alert>

      <Card>
        <SectionTitle title="Search public video data" hint="Searches by description keyword and region, for the selected date range. Maximum 100 results per request." />
        <form onSubmit={submitSearch} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="text-sm text-mist-300">
              Description keyword
              <input className="input mt-1.5" value={form.keyword} maxLength={200} required
                placeholder="hello world" onChange={(e) => setForm({ ...form, keyword: e.target.value })} />
            </label>
            <label className="text-sm text-mist-300">
              Region codes (comma-separated)
              <input className="input mt-1.5" value={form.region_codes} required
                placeholder="US, CA" onChange={(e) => setForm({ ...form, region_codes: e.target.value })} />
            </label>
            <label className="text-sm text-mist-300">
              Start date
              <input className="input mt-1.5" type="date" value={form.start_date} required
                onChange={(e) => setForm({ ...form, start_date: e.target.value })} />
            </label>
            <label className="text-sm text-mist-300">
              End date
              <input className="input mt-1.5" type="date" value={form.end_date} required
                onChange={(e) => setForm({ ...form, end_date: e.target.value })} />
            </label>
            <label className="text-sm text-mist-300">
              Results per request
              <select className="input mt-1.5" value={form.max_count}
                onChange={(e) => setForm({ ...form, max_count: e.target.value })}>
                {[10, 25, 50, 100].map((count) => <option key={count} value={count}>{count}</option>)}
              </select>
            </label>
          </div>
          <p className="text-xs text-mist-500">Fields requested: {VIDEO_FIELDS.join(', ')}. The access token stays on the backend.</p>
          <button className="btn-primary" disabled={queryState.status === 'loading' || queryState.loadingMore}>
            {queryState.status === 'loading' ? <Spinner label="Searching TikTok…" /> : <><Search className="h-4 w-4" />Search videos</>}
          </button>
        </form>
        {queryState.status === 'error' && <Alert tone="error" title="Video search failed" className="mt-4">{queryState.message}</Alert>}
      </Card>

      {queryState.status === 'done' && (
        <Card>
          <SectionTitle title="Public video results" hint={`${videos.length} video${videos.length === 1 ? '' : 's'} returned by TikTok. This is metadata, not comment analysis.`} />
          {queryState.message && <Alert tone="error" title="Could not load more videos" className="mb-4">{queryState.message}</Alert>}
          {videos.length ? (
            <div className="overflow-x-auto rounded-lg border border-ink-600/60">
              <table className="w-full min-w-[700px] border-collapse text-left text-sm">
                <thead className="bg-ink-900/60">
                  <tr>{VIDEO_FIELDS.map((field) => <th key={field} scope="col" className="px-4 py-3 font-semibold text-mist-300">{field}</th>)}</tr>
                </thead>
                <tbody className="divide-y divide-ink-600/40">
                  {videos.map((video, index) => (
                    <tr key={`${video.id || 'video'}-${index}`} className="hover:bg-ink-700/30">
                      {VIDEO_FIELDS.map((field) => (
                        <td key={field} className="px-4 py-3 text-mist-300">
                          {field === 'id' ? String(video[field] ?? 'Not provided') : formattedCount(video[field])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="rounded-lg border border-dashed border-ink-600 p-6 text-center text-sm text-mist-500">TikTok returned no videos for this query.</p>}
          {queryState.hasMore && (
            <button className="btn-ghost mt-4" onClick={loadMore} disabled={queryState.loadingMore}>
              {queryState.loadingMore ? <Spinner label="Loading more…" /> : 'Load more'}
            </button>
          )}
        </Card>
      )}

      <Card>
        <SectionTitle title="Check a TikTok video URL" hint="This check validates the URL format only; it does not fetch comments or video data." />
        <form onSubmit={submitUrl} className="flex flex-col gap-3 sm:flex-row">
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
          <SectionTitle title="URL validation result" hint={d.message} />
          <ul className="space-y-4">
            <Step ok={d.url_valid} title="URL format validated" detail={`Recognised as a TikTok ${d.url.url_type === 'video' ? 'video link' : 'short link'}.`} />
            <Step ok={d.comments_retrieved > 0} title="Comments retrieved" detail="No comments were fetched from this URL." />
            <Step ok={d.content_analyzed} title="Content analyzed" detail="No comment analysis was run because no comment data was retrieved." />
            <Step ok={d.integration.configured} title="Comment connector" detail={d.integration.message} />
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
