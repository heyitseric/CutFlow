import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { getHealthStatus } from '../../api/client';

type ConfigStatus = 'none' | 'partial' | 'full';

export default function Header() {
  const location = useLocation();
  const isDictionary = location.pathname === '/dictionary';
  const isStorage = location.pathname === '/storage';
  const isSettings = location.pathname === '/settings';

  const [configStatus, setConfigStatus] = useState<ConfigStatus>('none');

  useEffect(() => {
    getHealthStatus()
      .then((health) => {
        if (health.has_api_key && health.has_caption_keys) {
          setConfigStatus('full');
        } else if (health.has_api_key || health.has_caption_keys) {
          setConfigStatus('partial');
        } else {
          setConfigStatus('none');
        }
      })
      .catch(() => {
        // Silently fail — status dot just won't show
      });
  }, [location.pathname]); // Re-check when navigating (user may have just saved settings)

  return (
    <header className="glass-panel sticky top-0 z-50 border-b border-border-subtle">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-6">
        <Link
          to="/"
          className="group flex items-center gap-3 transition-colors transition-smooth"
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
            <span className="font-display text-lg font-semibold tracking-tight text-text-primary group-hover:text-amber transition-colors transition-smooth">
              A-Roll
            </span>
            <span className="text-sm text-text-muted">粗剪工具</span>
          </div>
        </Link>

        <nav className="flex items-center gap-2">
          <Link
            to="/storage"
            className={`flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-sm font-medium transition-all transition-smooth ${
              isStorage
                ? 'bg-amber/10 text-amber'
                : 'text-text-secondary hover:bg-elevated hover:text-text-primary'
            }`}
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path strokeLinecap="round" strokeLinejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
            </svg>
            存储管理
          </Link>
          <Link
            to="/dictionary"
            className={`flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-sm font-medium transition-all transition-smooth ${
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
          <Link
            to="/settings"
            className={`flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-sm font-medium transition-all transition-smooth ${
              isSettings
                ? 'bg-amber/10 text-amber'
                : 'text-text-secondary hover:bg-elevated hover:text-text-primary'
            }`}
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            服务配置
            {configStatus !== 'none' && (
              <span
                className={`h-2 w-2 rounded-full ${
                  configStatus === 'full' ? 'bg-success' : 'bg-warning'
                }`}
              />
            )}
          </Link>
        </nav>
      </div>
    </header>
  );
}
