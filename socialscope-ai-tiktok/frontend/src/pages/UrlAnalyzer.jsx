import { useEffect, useState } from 'react';
import { Link2, LogOut, RefreshCw, Video } from 'lucide-react';
import { analyzeUrl, disconnectTikTok, getTikTokStatus, getTikTokVideos } from '../api.js';
import { Alert, Card, SectionTitle, Spinner } from '../components/ui.jsx';

function createdAt(value) {
  if (!Number.isFinite(value)) return 'Not provided';
  return new Date(value * 1000).toLocaleString();
}

function count(value) {
  return Number.isFinite(value) ? value.toLocaleString() : '—';
}

export default function UrlAnalyzer({ onNavigate }) {
  const [account, setAccount] = useState(null);
  const [accountError, setAccountError] = useState(null);
  const [videos, setVideos] = useState([]);
  const [cursor, setCursor] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loadingVideos, setLoadingVideos] = useState(false);
  const [authNotice, setAuthNotice] = useState(null);
  const [url, setUrl] = useState('');
  const [urlState, setUrlState] = useState({ status: 'idle' });

  async function loadVideos(nextCursor = 0, append = false) {
    setLoadingVideos(true);
    setAccountError(null);
    try {
      const result = await getTikTokVideos(nextCursor);
      setVideos((current) => append ? [...current, ...result.videos] : result.videos);
      setCursor(result.cursor || 0);
      setHasMore(result.has_more === true);
    } catch (error) {
      setAccountError(error.message);
    } finally {
      setLoadingVideos(false);
    }
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const result = params.get('tiktok');
    if (result === 'connected') {
      setAuthNotice({ tone: 'success', message: 'Akun TikTok berhasil dihubungkan.' });
    } else if (result === 'error') {
      const reasons = {
        authorization_denied: 'Izin TikTok tidak diberikan.',
        invalid_state: 'Pemeriksaan keamanan login gagal. Silakan coba hubungkan ulang.',
        missing_authorization_code: 'TikTok tidak mengirim kode otorisasi.',
        token_exchange_failed: 'TikTok gagal memberikan token. Periksa konfigurasi aplikasi dan scope video.list.',
      };
      setAuthNotice({ tone: 'error', message: reasons[params.get('reason')] || 'Login TikTok gagal.' });
    }
    if (result) window.history.replaceState({}, '', window.location.pathname);

    getTikTokStatus()
      .then((status) => {
        setAccount(status);
        if (status.connected) loadVideos();
      })
      .catch((error) => setAccountError(error.message));
  }, []);

  async function disconnect() {
    try {
      await disconnectTikTok();
      setAccount((current) => ({ ...current, connected: false }));
      setVideos([]);
      setHasMore(false);
      setCursor(0);
      setAccountError(null);
    } catch (error) {
      setAccountError(error.message);
    }
  }

  async function submitUrl(event) {
    event.preventDefault();
    setUrlState({ status: 'loading' });
    try {
      setUrlState({ status: 'done', data: await analyzeUrl(url) });
    } catch (error) {
      setUrlState({ status: 'error', message: error.message });
    }
  }

  const result = urlState.data;
  return (
    <div className="space-y-6">
      {authNotice && <Alert tone={authNotice.tone} title="TikTok Login">{authNotice.message}</Alert>}
      {accountError && <Alert tone="error" title="TikTok request failed">{accountError}</Alert>}

      <Card>
        <SectionTitle
          title="Video akun TikTok saya"
          hint="Hubungkan akun TikTok untuk melihat video yang diizinkan oleh akun tersebut, termasuk tanggal publikasinya. Gunakan Muat video lainnya untuk menelusuri riwayat."
        />
        {!account ? (
          <Spinner label="Memeriksa status TikTok…" />
        ) : !account.configured ? (
          <div className="space-y-4">
            <Alert tone="warn" title="Aplikasi Login Kit belum dikonfigurasi">{account.message}</Alert>
            <ol className="list-decimal space-y-2 pl-5 text-sm text-mist-300">
              <li>Buat aplikasi di TikTok for Developers dan aktifkan Login Kit.</li>
              <li>Tambahkan produk/API yang menyediakan daftar video, lalu minta scope <code>video.list</code>.</li>
              <li>Daftarkan redirect URL persis seperti nilai <code>TIKTOK_REDIRECT_URI</code> di backend <code>.env</code>.</li>
              <li>Isi Client Key dan Client Secret di backend <code>.env</code>, lalu restart backend.</li>
            </ol>
          </div>
        ) : !account.connected ? (
          <div className="space-y-4">
            <Alert tone="info" title="Izin akun diperlukan">
              Setelah menekan tombol, masuk ke TikTok dan setujui scope <code>video.list</code>. Token ditukar dan disimpan di backend; token tidak dikirim ke browser.
            </Alert>
            <a className="btn-primary inline-flex" href="/api/tiktok/login">
              <Video className="h-4 w-4" /> Hubungkan akun TikTok
            </a>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-cyan-300">Akun terhubung dengan scope: {account.scopes.join(', ')}</p>
              <div className="flex gap-2">
                <button className="btn-ghost" onClick={() => loadVideos()} disabled={loadingVideos}>
                  {loadingVideos ? <Spinner label="Memuat…" /> : <><RefreshCw className="h-4 w-4" />Muat ulang</>}
                </button>
                <button className="btn-ghost" onClick={disconnect} disabled={loadingVideos}>
                  <LogOut className="h-4 w-4" />Putuskan
                </button>
              </div>
            </div>
            {videos.length ? (
              <>
                <div className="overflow-x-auto rounded-lg border border-ink-600/60">
                  <table className="w-full min-w-[820px] border-collapse text-left text-sm">
                    <thead className="bg-ink-900/60">
                      <tr>
                        {['Video', 'Dipublikasikan', 'Views', 'Likes', 'Komentar', 'Shares'].map((label) => (
                          <th key={label} scope="col" className="px-4 py-3 font-semibold text-mist-300">{label}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-ink-600/40">
                      {videos.map((video) => (
                        <tr key={video.id} className="hover:bg-ink-700/30">
                          <td className="max-w-md px-4 py-3">
                            {video.share_url ? (
                              <a className="text-cyan-300 hover:underline" href={video.share_url} target="_blank" rel="noreferrer">
                                {video.video_description || video.id}
                              </a>
                            ) : (video.video_description || video.id)}
                          </td>
                          <td className="whitespace-nowrap px-4 py-3 text-mist-300">{createdAt(video.create_time)}</td>
                          <td className="px-4 py-3 text-mist-300">{count(video.view_count)}</td>
                          <td className="px-4 py-3 text-mist-300">{count(video.like_count)}</td>
                          <td className="px-4 py-3 text-mist-300">{count(video.comment_count)}</td>
                          <td className="px-4 py-3 text-mist-300">{count(video.share_count)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {hasMore && (
                  <button className="btn-ghost" onClick={() => loadVideos(cursor, true)} disabled={loadingVideos}>
                    {loadingVideos ? <Spinner label="Memuat video…" /> : 'Muat video lainnya'}
                  </button>
                )}
                {!hasMore && <p className="text-sm text-mist-500">Semua video yang tersedia untuk akun ini sudah dimuat.</p>}
              </>
            ) : loadingVideos ? (
              <Spinner label="Mengambil video dari TikTok…" />
            ) : (
              <p className="rounded-lg border border-dashed border-ink-600 p-6 text-center text-sm text-mist-500">
                Belum ada video yang dikembalikan untuk akun ini.
              </p>
            )}
          </div>
        )}
      </Card>

      <Card>
        <SectionTitle title="Validasi tautan video" hint="Hanya memeriksa format URL; tidak mengambil komentar atau data video." />
        <form onSubmit={submitUrl} className="flex flex-col gap-3 sm:flex-row">
          <label className="sr-only" htmlFor="tt-url">TikTok video URL</label>
          <input id="tt-url" className="input" inputMode="url" autoComplete="off"
            placeholder="https://www.tiktok.com/@username/video/1234567890123456789"
            value={url} onChange={(event) => setUrl(event.target.value)} required />
          <button className="btn-primary sm:w-44" disabled={urlState.status === 'loading' || !url.trim()}>
            {urlState.status === 'loading' ? <Spinner label="Memeriksa…" /> : <><Link2 className="h-4 w-4" />Validasi URL</>}
          </button>
        </form>
        {urlState.status === 'error' && <Alert tone="error" title="URL tidak valid" className="mt-4">{urlState.message}</Alert>}
        {result && (
          <Alert tone="success" title="URL TikTok valid" className="mt-4">
            {result.url.normalized_url} — video ID: {result.url.video_id || 'tidak diketahui'}. Komentar tidak diambil.
          </Alert>
        )}
        {result && <button className="btn-ghost mt-3" onClick={() => onNavigate('comments')}>Buka analisis komentar CSV</button>}
      </Card>
    </div>
  );
}
