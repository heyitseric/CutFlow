import { useEffect, useState, useRef } from 'react';
import PageContainer from '../components/layout/PageContainer';
import {
  getDictionary,
  addDictionaryEntry,
  deleteDictionaryEntry,
  importDictionary,
  exportDictionary,
} from '../api/client';
import type { DictionaryEntry, DictionaryData } from '../api/types';

export default function DictionaryPage() {
  const [entries, setEntries] = useState<DictionaryEntry[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [newWrong, setNewWrong] = useState('');
  const [newCorrect, setNewCorrect] = useState('');
  const [newCategory, setNewCategory] = useState('general');
  const [adding, setAdding] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadDictionary();
  }, []);

  async function loadDictionary() {
    setLoading(true);
    try {
      const data = await getDictionary();
      setEntries(data.entries);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载词典失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleAdd() {
    if (!newWrong.trim() || !newCorrect.trim()) return;
    setAdding(true);
    try {
      const entry = await addDictionaryEntry({
        wrong: newWrong.trim(),
        correct: newCorrect.trim(),
        category: newCategory,
      });
      setEntries((prev) => [...prev, entry]);
      setNewWrong('');
      setNewCorrect('');
    } catch (err) {
      setError(err instanceof Error ? err.message : '添加失败');
    } finally {
      setAdding(false);
    }
  }

  async function handleDelete(wrong: string) {
    try {
      await deleteDictionaryEntry(wrong);
      setEntries((prev) => prev.filter((e) => e.wrong !== wrong));
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败');
    }
  }

  async function handleImport(file: File) {
    try {
      const text = await file.text();
      const data = JSON.parse(text) as DictionaryData;
      const result = await importDictionary(data);
      setEntries(result.entries);
    } catch (err) {
      setError(err instanceof Error ? err.message : '导入失败');
    }
  }

  async function handleExport() {
    try {
      const data = await exportDictionary();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `dictionary-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : '导出失败');
    }
  }

  const filtered = search
    ? entries.filter(
        (e) =>
          e.wrong.includes(search) ||
          e.correct.includes(search) ||
          e.category.includes(search),
      )
    : entries;

  return (
    <PageContainer>
      <div className="mb-8 animate-fade-in-up">
        <h1 className="font-display text-2xl font-bold tracking-tight text-text-primary">词典管理</h1>
        <p className="mt-2 text-sm text-text-muted">
          管理转录纠错词典，提高后续转录精度
        </p>
      </div>

      {/* Actions bar */}
      <div className="mb-5 flex items-center gap-3 animate-fade-in-up delay-1">
        <div className="relative flex-1">
          <svg className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8" />
            <path strokeLinecap="round" d="m21 21-4.35-4.35" />
          </svg>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索词条..."
            className="w-full rounded-xl border border-border bg-surface pl-10 pr-4 py-2.5 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-amber/40 focus:ring-1 focus:ring-amber/20 transition-colors transition-smooth"
          />
        </div>
        <button
          onClick={() => fileInputRef.current?.click()}
          className="rounded-xl border border-border bg-surface px-4 py-2.5 text-sm font-medium text-text-secondary hover:bg-elevated hover:text-text-primary transition-colors transition-smooth"
        >
          导入 JSON
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".json"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleImport(f);
          }}
        />
        <button
          onClick={handleExport}
          className="rounded-xl border border-border bg-surface px-4 py-2.5 text-sm font-medium text-text-secondary hover:bg-elevated hover:text-text-primary transition-colors transition-smooth"
        >
          导出 JSON
        </button>
      </div>

      {/* Add new entry */}
      <div className="mb-6 animate-fade-in-up delay-2 rounded-2xl border border-border bg-surface p-5">
        <h3 className="mb-4 font-display text-sm font-semibold text-text-secondary">添加新词条</h3>
        <div className="flex items-end gap-3">
          <div className="flex-1">
            <label className="mb-1.5 block text-xs text-text-muted">错误文字</label>
            <input
              type="text"
              value={newWrong}
              onChange={(e) => setNewWrong(e.target.value)}
              placeholder="如：生同"
              className="w-full rounded-lg border border-border bg-elevated px-3 py-2 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-amber/40"
            />
          </div>
          <div className="flex-1">
            <label className="mb-1.5 block text-xs text-text-muted">正确文字</label>
            <input
              type="text"
              value={newCorrect}
              onChange={(e) => setNewCorrect(e.target.value)}
              placeholder="如：生酮"
              className="w-full rounded-lg border border-border bg-elevated px-3 py-2 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-amber/40"
            />
          </div>
          <div className="w-32">
            <label className="mb-1.5 block text-xs text-text-muted">类别</label>
            <select
              value={newCategory}
              onChange={(e) => setNewCategory(e.target.value)}
              className="w-full rounded-lg border border-border bg-elevated px-2.5 py-2 text-sm text-text-secondary outline-none focus:border-amber/40"
            >
              <option value="general">通用</option>
              <option value="name">人名</option>
              <option value="technical">技术</option>
              <option value="brand">品牌</option>
            </select>
          </div>
          <button
            onClick={handleAdd}
            disabled={adding || !newWrong.trim() || !newCorrect.trim()}
            className="rounded-xl bg-amber px-6 py-2 text-sm font-medium text-deep hover:bg-amber/90 disabled:bg-elevated disabled:text-text-muted transition-colors transition-smooth"
          >
            {adding ? '添加中...' : '添加'}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 animate-slide-down rounded-xl border border-danger/20 bg-danger-surface p-3.5 text-sm text-danger flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ml-3 text-xs underline opacity-70 hover:opacity-100">
            关闭
          </button>
        </div>
      )}

      {/* Table */}
      <div className="animate-fade-in-up delay-3 overflow-hidden rounded-2xl border border-border bg-surface">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-border bg-elevated/50">
            <tr>
              <th className="px-5 py-3 font-display text-xs font-semibold text-text-muted">错误文字</th>
              <th className="px-5 py-3 font-display text-xs font-semibold text-text-muted">正确文字</th>
              <th className="px-5 py-3 font-display text-xs font-semibold text-text-muted">类别</th>
              <th className="px-5 py-3 font-display text-xs font-semibold text-text-muted">使用次数</th>
              <th className="px-5 py-3 font-display text-xs font-semibold text-text-muted">添加时间</th>
              <th className="px-5 py-3 font-display text-xs font-semibold text-text-muted w-20">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-subtle">
            {loading ? (
              <tr>
                <td colSpan={6} className="px-5 py-12 text-center text-text-muted animate-gentle-pulse">
                  加载中...
                </td>
              </tr>
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-5 py-12 text-center text-text-muted">
                  {search ? '没有匹配的词条' : '暂无词条，在上方添加'}
                </td>
              </tr>
            ) : (
              filtered.map((entry) => (
                <tr key={entry.wrong} className="hover:bg-elevated/30 transition-colors transition-smooth">
                  <td className="px-5 py-3">
                    <span className="rounded-md bg-danger-surface px-2 py-0.5 text-danger line-through">
                      {entry.wrong}
                    </span>
                  </td>
                  <td className="px-5 py-3">
                    <span className="rounded-md bg-success-surface px-2 py-0.5 text-success">
                      {entry.correct}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-text-muted">{entry.category}</td>
                  <td className="px-5 py-3 font-mono text-text-muted">{entry.frequency}</td>
                  <td className="px-5 py-3 font-mono text-xs text-text-faint">
                    {new Date(entry.addedAt).toLocaleDateString('zh-CN')}
                  </td>
                  <td className="px-5 py-3">
                    <button
                      onClick={() => handleDelete(entry.wrong)}
                      className="rounded-lg px-2.5 py-1 text-xs text-danger hover:bg-danger-surface transition-colors transition-smooth"
                    >
                      删除
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <p className="mt-3 font-mono text-xs text-text-faint">
        共 {filtered.length} 条{search && entries.length !== filtered.length && ` / 总计 ${entries.length} 条`}
      </p>
    </PageContainer>
  );
}
