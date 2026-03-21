import { useState, useEffect, useRef } from 'react';
import { addDictionaryEntry } from '../../api/client';

interface TextCorrectionPopoverProps {
  selectedText: string;
  position: { x: number; y: number };
  onClose: () => void;
  onSaved: (wrong: string, correct: string) => void;
}

export default function TextCorrectionPopover({
  selectedText,
  position,
  onClose,
  onSaved,
}: TextCorrectionPopoverProps) {
  const [correctText, setCorrectText] = useState('');
  const [category, setCategory] = useState('general');
  const [saving, setSaving] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose();
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [onClose]);

  async function handleSave() {
    if (!correctText.trim()) return;
    setSaving(true);
    try {
      await addDictionaryEntry({
        wrong: selectedText,
        correct: correctText.trim(),
        category,
      });
      onSaved(selectedText, correctText.trim());
      onClose();
    } catch {
      // silently fail
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      ref={ref}
      className="fixed z-50 w-72 animate-slide-down rounded-xl border border-border bg-surface p-4 shadow-2xl shadow-black/40"
      style={{
        left: Math.min(position.x, window.innerWidth - 300),
        top: position.y + 8,
      }}
    >
      <p className="mb-2.5 font-display text-xs font-semibold text-text-muted">修正文字</p>
      <div className="mb-3 rounded-lg bg-danger-surface px-2.5 py-1.5 text-sm text-danger line-through">
        {selectedText}
      </div>
      <input
        ref={inputRef}
        type="text"
        value={correctText}
        onChange={(e) => setCorrectText(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && handleSave()}
        placeholder="输入正确文字..."
        className="mb-2.5 w-full rounded-lg border border-border bg-elevated px-3 py-2 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-amber/50 focus:ring-1 focus:ring-amber/20"
      />
      <select
        value={category}
        onChange={(e) => setCategory(e.target.value)}
        className="mb-3 w-full rounded-lg border border-border bg-elevated px-2.5 py-1.5 text-xs text-text-secondary outline-none focus:border-amber/50"
      >
        <option value="general">通用</option>
        <option value="name">人名</option>
        <option value="technical">技术术语</option>
        <option value="brand">品牌</option>
      </select>
      <div className="flex justify-end gap-2">
        <button
          onClick={onClose}
          className="rounded-lg px-3 py-1.5 text-xs text-text-secondary hover:bg-elevated transition-colors"
        >
          取消
        </button>
        <button
          onClick={handleSave}
          disabled={!correctText.trim() || saving}
          className="rounded-lg bg-amber px-4 py-1.5 text-xs font-medium text-deep hover:bg-amber/90 disabled:bg-elevated disabled:text-text-muted transition-colors"
        >
          {saving ? '保存中...' : '保存到词典'}
        </button>
      </div>
    </div>
  );
}
