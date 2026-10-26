import { useMemo, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Download,
  FileUp,
  Link2,
  MessageSquareText,
  ShieldAlert,
  Sparkles,
  TrendingUp,
  Upload,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

const initialState = {
  source: null,
  summary: {
    total_comments: 0,
    positive: 0,
    neutral: 0,
    negative: 0,
    promotional_comments: 0,
    repeated_text_groups: 0,
    similar_pairs: 0,
    timestamps_available: 0,
    unique_videos: 0,
  },
  sentiment: {
    positive: 0,
    neutral: 0,
    negative: 0,
    unknown: 0,
  },
  repeated_comments: [],
  similar_pairs: [],
  hourly_activity: [],
  coordination_signals: [],
  findings: [],
  method_notes: [],
  analysis_status: 'idle',
  message: '',
};

const navItems = [
  'Overview',
  'TikTok URL Analyzer',
  'Comment Analysis',
  'Coordination Signals',
  'Reports',
  'About & Methodology',
];

const supportDomains = ['tiktok.com', 'vm.tiktok.com', 'vt.tiktok.com', 'm.tiktok.com'];

function isValidTikTokUrl(value) {
  if (!value) return false;
  try {
    const url = new URL(value);
    const host = url.hostname.toLowerCase();
    return supportDomains.includes(host) || host.endsWith('.tiktok.com');
  } catch {
    return false;
  }
}

function getStatusBadge(status) {
  const variants = {
    idle: 'border-slate-700 text-slate-200 bg-slate-800/80',
    completed: 'border-emerald-500/50 bg-emerald-500/10 text-emerald-300',
    validation_only: 'border-cyan-500/50 bg-cyan-500/10 text-cyan-300',
    unavailable: 'border-amber-500/50 bg-amber-500/10 text-amber-300',
    error: 'border-rose-500/50 bg-rose-500/10 text-rose-300',
  };
  return variants[status] || variants.idle;
}

function StatCard({ icon: Icon, label, value, accentClass = 'text-cyan-300', helper }) {
  return (
    <div className="metric-card">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{label}</p>
          <p className="mt-4 text-3xl font-semibold text-white">{value}</p>
          {helper ? <p className="mt-2 text-sm text-slate-400">{helper}</p> : null}
        </div>
        <div className={`rounded-xl border border-slate-700 bg-slate-800/80 p-3 ${accentClass}`}>
          <Icon size={20} />
        </div>
      </div>
    </div>
  );
}

function App() {
  const [nav, setNav] = useState('Overview');
  const [urlInput, setUrlInput] = useState('');
  const [urlStatus, setUrlStatus] = useState(null);
  const [urlLoading, setUrlLoading] = useState(false);
  const [csvLoading, setCsvLoading] = useState(false);
  const [csvError, setCsvError] = useState('');
  const [result, setResult] = useState(initialState);
  const [fileName, setFileName] = useState('');

  const sentimentData = useMemo(
    () => [
      { name: 'Positive', value: result.sentiment.positive, fill: '#22d3ee' },
      { name: 'Neutral', value: result.sentiment.neutral, fill: '#a78bfa' },
      { name: 'Negative', value: result.sentiment.negative, fill: '#f97316' },
    ],
    [result.sentiment]
  );

  const activityData = useMemo(
    () => {
      if (!result.hourly_activity || result.hourly_activity.length === 0) {
        return [];
      }
      return result.hourly_activity.map((point) => ({
        name: new Date(point.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        comments: point.count,
      }));
    },
    [result.hourly_activity]
  );

  const handleUrlSubmit = async (event) => {
    event.preventDefault();
    const trimmed = urlInput.trim();
    const isValid = isValidTikTokUrl(trimmed);
    setUrlStatus({
      status: isValid ? 'validation_only' : 'error',
      message: isValid
        ? 'URL format is valid, but content has not been analyzed because no approved integration is configured.'
        : 'Please enter a valid TikTok URL beginning with http(s).',
      valid: isValid,
    });

    if (!isValid) {
      return;
    }

    setUrlLoading(true);
    try {
      const response = await fetch('http://127.0.0.1:5000/api/analyze-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: trimmed }),
      });
      const payload = await response.json();
      setUrlStatus({
        status: response.ok ? payload.status || 'validation_only' : 'error',
        message: payload.message || payload.error || 'The URL could not be analyzed.',
        valid: payload.is_valid_url ?? true,
      });
    } catch (error) {
      setUrlStatus({
        status: 'error',
        message: 'Unable to reach the backend. Confirm the Flask API is running on port 5000.',
        valid: false,
      });
    } finally {
      setUrlLoading(false);
    }
  };

  const handleCsvUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    setCsvError('');
    setCsvLoading(true);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('http://127.0.0.1:5000/api/analyze-csv', {
        method: 'POST',
        body: formData,
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || 'CSV analysis failed.');
      }
      setResult({
        source: payload.source || 'uploaded_csv',
        summary: payload.summary || initialState.summary,
        sentiment: payload.sentiment || initialState.sentiment,
        repeated_comments: payload.repeated_comments || [],
        similar_pairs: payload.similar_pairs || [],
        hourly_activity: payload.hourly_activity || [],
        coordination_signals: payload.coordination_signals || [],
        findings: payload.findings || [],
        method_notes: payload.method_notes || [],
        analysis_status: payload.analysis_status || 'completed',
        message: payload.message || 'Analysis complete.',
      });
      setNav('Overview');
    } catch (error) {
      setCsvError(error.message || 'An unexpected error occurred during CSV analysis.');
      setResult(initialState);
    } finally {
      setCsvLoading(false);
      event.target.value = '';
    }
  };

  const exportCsv = () => {
    if (!result.summary || result.summary.total_comments === 0) {
      return;
    }

    const rows = [
      ['Metric', 'Value'],
      ['Total comments', result.summary.total_comments],
      ['Positive', result.summary.positive],
      ['Neutral', result.summary.neutral],
      ['Negative', result.summary.negative],
      ['Promotional comments', result.summary.promotional_comments],
      ['Repeated text groups', result.summary.repeated_text_groups],
      ['Similar pairs', result.summary.similar_pairs],
    ];

    const csv = rows.map((row) => row.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'socialscope-ai-summary.csv';
    link.click();
    URL.revokeObjectURL(url);
  };

  const isDataLoaded = result.summary.total_comments > 0;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4">
          <div>
            <p className="text-xs uppercase tracking-[0.32em] text-cyan-300">SocialScope AI</p>
            <h1 className="mt-1 text-2xl font-semibold text-white">TikTok Analytics</h1>
          </div>
          <nav className="hidden gap-2 md:flex">
            {navItems.map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setNav(item)}
                className={`rounded-full px-3 py-2 text-sm transition ${
                  nav === item ? 'bg-cyan-500/15 text-cyan-200 ring-1 ring-cyan-500/40' : 'text-slate-300 hover:bg-slate-800'
                }`}
              >
                {item}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-8">
        <section className="grid gap-6 lg:grid-cols-[1.5fr_0.8fr]">
          <div className="panel">
            <div className="flex items-center gap-3">
              <div className="rounded-2xl bg-cyan-500/10 p-3 text-cyan-300">
                <Sparkles size={20} />
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.28em] text-slate-400">Platform</p>
                <h2 className="text-3xl font-semibold text-white">SocialScope AI</h2>
              </div>
            </div>
            <p className="mt-4 max-w-2xl text-slate-300">
              TikTok Social Intelligence Platform
            </p>
            <p className="mt-3 max-w-2xl text-sm text-slate-400">
              An AI-powered platform for exploring TikTok comment sentiment, promotional patterns,
              and potential coordinated activity through data-driven analysis.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <span className="badge border-emerald-500/30 bg-emerald-500/10 text-emerald-200">Status: Ready</span>
              <span className="badge border-violet-500/30 bg-violet-500/10 text-violet-200">Baseline NLP</span>
              <span className="badge border-cyan-500/30 bg-cyan-500/10 text-cyan-200">Explainable</span>
            </div>
          </div>

          <div className="panel">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Analysis status</p>
                <h3 className="mt-2 text-xl font-semibold text-white">{isDataLoaded ? 'Dataset loaded' : 'Waiting for data'}</h3>
              </div>
              <span className={`badge ${getStatusBadge(isDataLoaded ? 'completed' : 'idle')}`}>
                {isDataLoaded ? 'Completed' : 'Idle'}
              </span>
            </div>
            <p className="mt-4 text-sm text-slate-300">
              {isDataLoaded
                ? 'The current dataset has been analyzed with transparent baseline metrics.'
                : 'Upload CSV comments or validate a TikTok URL to begin analysis.'}
            </p>
          </div>
        </section>

        <section className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <StatCard icon={MessageSquareText} label="Total comments" value={result.summary.total_comments} helper="Across uploaded data" accentClass="text-cyan-300" />
          <StatCard icon={TrendingUp} label="Positive" value={result.summary.positive} helper="Positive sentiment" accentClass="text-emerald-300" />
          <StatCard icon={Activity} label="Neutral" value={result.summary.neutral} helper="Neutral sentiment" accentClass="text-violet-300" />
          <StatCard icon={AlertTriangle} label="Negative" value={result.summary.negative} helper="Negative sentiment" accentClass="text-amber-300" />
        </section>

        <section className="mt-8 grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
          <div className="panel">
            <div className="mb-4 flex items-center gap-3">
              <Link2 className="text-cyan-300" size={20} />
              <h3 className="text-xl font-semibold text-white">TikTok URL Analyzer</h3>
            </div>
            <form onSubmit={handleUrlSubmit} className="space-y-4">
              <label className="block">
                <span className="mb-2 block text-sm text-slate-300">TikTok video URL</span>
                <input
                  type="url"
                  value={urlInput}
                  onChange={(event) => setUrlInput(event.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-slate-100 outline-none ring-0 placeholder:text-slate-500 focus:border-cyan-400"
                  placeholder="https://www.tiktok.com/@user/video/1234567890"
                />
              </label>
              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="submit"
                  disabled={urlLoading}
                  className="rounded-xl bg-cyan-500 px-4 py-2.5 font-medium text-slate-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {urlLoading ? 'Validating URL...' : 'Validate URL'}
                </button>
                <span className="text-xs text-slate-400">Supported domains: {supportDomains.join(', ')}</span>
              </div>
            </form>
            {urlStatus ? (
              <div className={`mt-5 rounded-2xl border p-4 ${getStatusBadge(urlStatus.status)}`}>
                <div className="flex items-center gap-2 text-sm font-medium">
                  {urlStatus.valid ? <CheckCircle2 size={16} /> : <ShieldAlert size={16} />}
                  <span>{urlStatus.valid ? 'Validated' : 'Not available'}</span>
                </div>
                <p className="mt-2 text-sm opacity-90">{urlStatus.message}</p>
              </div>
            ) : null}
          </div>

          <div className="panel">
            <div className="mb-4 flex items-center gap-3">
              <Upload className="text-violet-300" size={20} />
              <h3 className="text-xl font-semibold text-white">CSV Comment Analysis</h3>
            </div>
            <label className="flex cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed border-slate-700 bg-slate-950/80 p-7 text-center transition hover:border-cyan-400 hover:bg-slate-900">
              <FileUp className="mb-3 text-cyan-300" size={30} />
              <span className="text-sm text-slate-300">Upload CSV with comment data</span>
              <span className="mt-1 text-xs text-slate-500">Required column: comment, comments, text, content, or komentar</span>
              <input type="file" accept=".csv" className="hidden" onChange={handleCsvUpload} />
            </label>
            {fileName ? <p className="mt-4 text-sm text-slate-300">Loaded file: {fileName}</p> : null}
            {csvError ? <p className="mt-4 text-sm text-rose-300">{csvError}</p> : null}
            {csvLoading ? <p className="mt-4 text-sm text-cyan-300">Analyzing uploaded comments...</p> : null}
          </div>
        </section>

        <section className="mt-8 grid gap-6 lg:grid-cols-2">
          <div className="panel">
            <div className="mb-5 flex items-center justify-between">
              <h3 className="text-xl font-semibold text-white">Sentiment distribution</h3>
              <span className="badge border-cyan-500/30 bg-cyan-500/10 text-cyan-200">Baseline</span>
            </div>
            {isDataLoaded ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie dataKey="value" data={sentimentData} innerRadius={45} outerRadius={85} paddingAngle={3}>
                      {sentimentData.map((entry) => (
                        <Bar key={entry.name} fill={entry.fill} dataKey="value" />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="flex h-64 items-center justify-center rounded-2xl border border-dashed border-slate-700 bg-slate-950/40 text-slate-400">
                No sentiment chart available until a CSV is uploaded.
              </div>
            )}
          </div>

          <div className="panel">
            <div className="mb-5 flex items-center justify-between">
              <h3 className="text-xl font-semibold text-white">Comment activity</h3>
              <span className="badge border-violet-500/30 bg-violet-500/10 text-violet-200">Time-based</span>
            </div>
            {activityData.length ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={activityData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="name" stroke="#94a3b8" />
                    <YAxis stroke="#94a3b8" />
                    <Tooltip />
                    <Line type="monotone" dataKey="comments" stroke="#22d3ee" strokeWidth={3} dot={{ r: 3 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="flex h-64 items-center justify-center rounded-2xl border border-dashed border-slate-700 bg-slate-950/40 text-slate-400">
                No time-series data available without valid timestamps.
              </div>
            )}
          </div>
        </section>

        <section className="mt-8 grid gap-6 lg:grid-cols-2">
          <div className="panel">
            <div className="mb-5 flex items-center gap-3">
              <BarChart3 className="text-emerald-300" size={20} />
              <h3 className="text-xl font-semibold text-white">Promotional indicators</h3>
            </div>
            {result.summary.promotional_comments ? (
              <div className="space-y-3">
                {result.examples?.slice(0, 5).map((example, index) => (
                  <div key={`${example.comment}-${index}`} className="rounded-xl border border-slate-700 bg-slate-950/70 p-3">
                    <p className="text-sm text-slate-200">{example.comment}</p>
                    <p className="mt-2 text-xs uppercase tracking-[0.18em] text-amber-300">
                      {example.promotional_language_detected ? 'Promotional signal' : 'No keyword match'}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/40 p-6 text-sm text-slate-400">
                No promotional keyword matches were detected in the current dataset.
              </div>
            )}
          </div>

          <div className="panel">
            <div className="mb-5 flex items-center gap-3">
              <ShieldAlert className="text-amber-300" size={20} />
              <h3 className="text-xl font-semibold text-white">Potential coordination indicators</h3>
            </div>
            {result.coordination_signals?.length ? (
              <div className="space-y-3">
                {result.coordination_signals.map((signal, index) => (
                  <div key={`${signal.type}-${index}`} className="rounded-xl border border-slate-700 bg-slate-950/70 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-sm font-medium text-slate-200">{signal.type.replace(/_/g, ' ')}</span>
                      <span className="badge border-amber-500/30 bg-amber-500/10 text-amber-200">{signal.status}</span>
                    </div>
                    <p className="mt-2 text-sm text-slate-300">{signal.detail}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/40 p-6 text-sm text-slate-400">
                No coordination signal exceeds the current review threshold.
              </div>
            )}
          </div>
        </section>

        <section className="mt-8 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="panel">
            <div className="mb-5 flex items-center justify-between">
              <h3 className="text-xl font-semibold text-white">Findings and validation notes</h3>
              <button type="button" onClick={exportCsv} className="inline-flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 hover:border-cyan-400">
                <Download size={16} />
                Export CSV
              </button>
            </div>
            {result.findings?.length ? (
              <div className="space-y-3">
                {result.findings.map((finding, index) => (
                  <div key={`${finding.title}-${index}`} className="rounded-xl border border-slate-700 bg-slate-950/70 p-3">
                    <p className="text-sm font-medium text-slate-200">{finding.title}</p>
                    <p className="mt-2 text-sm text-slate-300">{finding.detail}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/40 p-6 text-sm text-slate-400">
                No findings available until a dataset is uploaded and analyzed.
              </div>
            )}
          </div>

          <div className="panel">
            <div className="mb-5 flex items-center gap-3">
              <CheckCircle2 className="text-emerald-300" size={20} />
              <h3 className="text-xl font-semibold text-white">Methodology</h3>
            </div>
            <ul className="space-y-3 text-sm text-slate-300">
              {result.method_notes?.length ? (
                result.method_notes.map((note, index) => (
                  <li key={`${note}-${index}`} className="rounded-xl border border-slate-700 bg-slate-950/70 p-3">
                    {note}
                  </li>
                ))
              ) : (
                <li className="rounded-xl border border-dashed border-slate-700 bg-slate-950/40 p-3 text-slate-400">
                  Method notes will appear after analysis.
                </li>
              )}
            </ul>
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
