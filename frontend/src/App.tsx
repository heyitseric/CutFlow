import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Header from './components/layout/Header';
import UploadPage from './pages/UploadPage';
import ProcessingPage from './pages/ProcessingPage';
import ReviewPage from './pages/ReviewPage';
import ExportPage from './pages/ExportPage';
import DictionaryPage from './pages/DictionaryPage';

export default function App() {
  return (
    <BrowserRouter>
      <div className="bg-mesh min-h-screen font-body text-text-primary antialiased">
        <Header />
        <main className="relative">
          <Routes>
            <Route path="/" element={<UploadPage />} />
            <Route path="/processing/:id" element={<ProcessingPage />} />
            <Route path="/review/:id" element={<ReviewPage />} />
            <Route path="/export/:id" element={<ExportPage />} />
            <Route path="/dictionary" element={<DictionaryPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
