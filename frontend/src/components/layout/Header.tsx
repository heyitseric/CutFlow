import { Link, useLocation } from 'react-router-dom';

export default function Header() {
  const location = useLocation();
  const isDictionary = location.pathname === '/dictionary';

  return (
    <header className="glass-panel sticky top-0 z-50 border-b border-border-subtle">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-6">
        <Link
          to="/"
          className="group flex items-center gap-3 transition-colors"
        >
          {/* Film reel icon */}
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber/10">
            <svg className="h-4.5 w-4.5 text-amber" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <circle cx="12" cy="12" r="10" />
              <circle cx="12" cy="12" r="3" />
              <circle cx="12" cy="5" r="1" fill="currentColor" stroke="none" />
              <circle cx="12" cy="19" r="1" fill="currentColor" stroke="none" />
              <circle cx="5" cy="12" r="1" fill="currentColor" stroke="none" />
              <circle cx="19" cy="12" r="1" fill="currentColor" stroke="none" />
            </svg>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="font-display text-lg font-semibold tracking-tight text-text-primary group-hover:text-amber transition-colors">
              A-Roll
            </span>
            <span className="text-sm text-text-muted">粗剪工具</span>
          </div>
        </Link>

        <nav className="flex items-center gap-2">
          <Link
            to="/dictionary"
            className={`flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-sm font-medium transition-all ${
              isDictionary
                ? 'bg-amber/10 text-amber'
                : 'text-text-secondary hover:bg-elevated hover:text-text-primary'
            }`}
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
            词典管理
          </Link>
        </nav>
      </div>
    </header>
  );
}
