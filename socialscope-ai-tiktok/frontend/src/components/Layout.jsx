import { useState } from 'react';
import { BarChart3, FileText, Info, Link2, Menu, Network, UploadCloud, X } from 'lucide-react';

export const NAV = [
  { id: 'overview', label: 'Overview', icon: BarChart3 },
  { id: 'url', label: 'TikTok Data Search', icon: Link2 },
  { id: 'comments', label: 'Comment Analysis', icon: UploadCloud },
  { id: 'coordination', label: 'Coordination Signals', icon: Network },
  { id: 'reports', label: 'Reports', icon: FileText },
  { id: 'about', label: 'About & Methodology', icon: Info },
];

const Logo = () => (
  <svg viewBox="0 0 32 32" className="h-8 w-8" aria-hidden="true">
    <circle cx="16" cy="16" r="9" fill="none" stroke="#22D3EE" strokeWidth="2.5" />
    <circle cx="16" cy="16" r="2.8" fill="#A78BFA" />
    <path d="M16 3v6M16 23v6M3 16h6M23 16h6" stroke="#A78BFA" strokeWidth="2" strokeLinecap="round" />
  </svg>
);

function NavList({ page, onNavigate }) {
  return (
    <nav aria-label="Main" className="flex flex-col gap-1">
      {NAV.map(({ id, label, icon: Icon }) => (
        <button key={id} onClick={() => onNavigate(id)} aria-current={page === id ? 'page' : undefined}
          className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium transition-colors ${page === id ? 'bg-violet-500/20 text-violet-300' : 'text-mist-300 hover:bg-ink-700/70 hover:text-mist-100'}`}>
          <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />{label}
        </button>
      ))}
    </nav>
  );
}

function Brand() {
  return (
    <div className="flex items-center gap-3">
      <Logo />
      <div>
        <p className="text-lg font-extrabold leading-tight tracking-tight">SocialScope AI</p>
        <p className="text-xs leading-tight text-cyan-400">TikTok Analytics</p>
      </div>
    </div>
  );
}

export default function Layout({ page, onNavigate, health, dataSource, children }) {
  const [open, setOpen] = useState(false);
  const status = health === null ? ['Checking backend…', 'bg-mist-500'] : health.error ? ['Backend offline', 'bg-neg'] : ['Backend connected', 'bg-cyan-400'];
  const go = (id) => { onNavigate(id); setOpen(false); };
  return (
    <div className="min-h-screen bg-[radial-gradient(ellipse_at_top_right,rgba(139,92,246,0.14),transparent_55%),radial-gradient(ellipse_at_top_left,rgba(34,211,238,0.07),transparent_45%)]">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded focus:bg-cyan-400 focus:px-3 focus:py-2 focus:text-ink-950">Skip to content</a>
      <aside className="fixed inset-y-0 left-0 hidden w-64 flex-col border-r border-ink-600/50 bg-ink-900/80 p-5 lg:flex">
        <Brand />
        <p className="mt-2 text-xs text-mist-500">TikTok Social Intelligence Platform</p>
        <div className="mt-8 flex-1"><NavList page={page} onNavigate={go} /></div>
        <div className="space-y-3 text-xs text-mist-500">
          <p className="flex items-center gap-2"><span className={`h-2 w-2 rounded-full ${status[1]}`} />{status[0]}</p>
          <p className="leading-relaxed">Independent, unofficial educational project. Not affiliated with or endorsed by TikTok.</p>
        </div>
      </aside>

      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-ink-600/50 bg-ink-900/90 px-4 py-3 backdrop-blur lg:hidden">
        <Brand />
        <button className="btn-ghost !px-2.5" onClick={() => setOpen(!open)} aria-expanded={open} aria-label="Toggle navigation">
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </header>
      {open && <div className="border-b border-ink-600/50 bg-ink-900 p-4 lg:hidden"><NavList page={page} onNavigate={go} /></div>}

      <div className="lg:pl-64">
        <div className="mx-auto max-w-6xl px-4 py-6 sm:px-8 sm:py-8">
          <div className="mb-6 flex flex-wrap items-center justify-between gap-2">
            <h1 className="text-2xl font-extrabold tracking-tight">{NAV.find((n) => n.id === page)?.label}</h1>
            <p className="rounded-full border border-ink-600 bg-ink-800/60 px-3 py-1 text-xs text-mist-300">
              Data source: {dataSource ? `CSV upload (${dataSource})` : 'none loaded'}
            </p>
          </div>
          <main id="main" tabIndex={-1}>{children}</main>
          <footer className="mt-12 border-t border-ink-600/40 pt-4 text-xs text-mist-500 lg:hidden">Independent, unofficial educational project. Not affiliated with TikTok.</footer>
        </div>
      </div>
    </div>
  );
}
