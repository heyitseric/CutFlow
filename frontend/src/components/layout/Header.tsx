import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { getHealthStatus } from '../../api/client';
import { useTheme } from '../../hooks/useTheme';
import { Package, BookOpen, Settings, Sun, Moon } from 'lucide-react';
import { Button } from '@/components/ui/button';

type ConfigStatus = 'none' | 'partial' | 'full';

export default function Header() {
  const location = useLocation();
  const isDictionary = location.pathname === '/dictionary';
  const isStorage = location.pathname === '/storage';
  const isSettings = location.pathname === '/settings';

  const [configStatus, setConfigStatus] = useState<ConfigStatus>('none');
  const { theme, toggleTheme } = useTheme();

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
    <header className="sticky top-0 z-50 bg-background border-b border-border">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-6">
        <Link
          to="/"
          className="group flex items-center gap-3 transition-colors"
        >
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
            <Package className="h-4.5 w-4.5 text-foreground" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="font-display text-lg font-semibold tracking-tight text-foreground group-hover:text-primary transition-colors">
              A-Roll
            </span>
            <span className="text-sm text-muted-foreground">粗剪工具</span>
          </div>
        </Link>

        <nav className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleTheme}
            className="text-muted-foreground hover:text-foreground"
            aria-label={theme === 'light' ? '切换暗色模式' : '切换亮色模式'}
          >
            {theme === 'light' ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
          </Button>
          <div className="mx-1 h-4 w-px bg-border" />
          <Button
            variant="ghost"
            size="sm"
            asChild
            className={
              isStorage
                ? 'bg-accent text-foreground'
                : 'text-muted-foreground hover:text-foreground'
            }
          >
            <Link to="/storage">
              <Package className="h-4 w-4" />
              存储管理
            </Link>
          </Button>
          <Button
            variant="ghost"
            size="sm"
            asChild
            className={
              isDictionary
                ? 'bg-accent text-foreground'
                : 'text-muted-foreground hover:text-foreground'
            }
          >
            <Link to="/dictionary">
              <BookOpen className="h-4 w-4" />
              词典管理
            </Link>
          </Button>
          <Button
            variant="ghost"
            size="sm"
            asChild
            className={
              isSettings
                ? 'bg-accent text-foreground'
                : 'text-muted-foreground hover:text-foreground'
            }
          >
            <Link to="/settings">
              <Settings className="h-4 w-4" />
              服务配置
              {configStatus !== 'none' && (
                <span
                  className={`h-2 w-2 rounded-full ${
                    configStatus === 'full' ? 'bg-success' : 'bg-warning'
                  }`}
                />
              )}
            </Link>
          </Button>
        </nav>
      </div>
    </header>
  );
}
