import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { TooltipProvider } from '@/components/ui/tooltip';
import { Toaster } from '@/components/ui/sonner';
import Header from './components/layout/Header';
import Sidebar from './components/layout/Sidebar';
import SystemMonitor from './components/layout/SystemMonitor';
import UploadPage from './pages/UploadPage';
import ProcessingPage from './pages/ProcessingPage';
import ReviewPage from './pages/ReviewPage';
import ExportPage from './pages/ExportPage';
import DictionaryPage from './pages/DictionaryPage';
import StoragePage from './pages/StoragePage';
import SettingsPage from './pages/SettingsPage';

export default function App() {
  return (
    <BrowserRouter>
      <TooltipProvider>
        <div className="flex min-h-screen flex-col bg-background font-body text-foreground antialiased">
          <Header />
          <div className="flex flex-1 overflow-hidden">
            <Sidebar />
            <main className="relative flex-1 overflow-y-auto">
              <Routes>
                <Route path="/" element={<UploadPage />} />
                <Route path="/processing/:id" element={<ProcessingPage />} />
                <Route path="/review/:id" element={<ReviewPage />} />
                <Route path="/export/:id" element={<ExportPage />} />
                <Route path="/dictionary" element={<DictionaryPage />} />
                <Route path="/storage" element={<StoragePage />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Routes>
            </main>
          </div>
        </div>
        <Toaster />
        <SystemMonitor />
      </TooltipProvider>
    </BrowserRouter>
  );
}
