import { useState, useEffect, useRef } from 'react';
import { addDictionaryEntry } from '../../api/client';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';

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
      className="fixed z-50 w-72 animate-slide-down rounded-xl border border-border bg-card p-4 shadow-lg"
      style={{
        left: Math.min(position.x, window.innerWidth - 300),
        top: position.y + 8,
      }}
    >
      <p className="mb-2.5 text-xs font-semibold text-muted-foreground">修正文字</p>
      <div className="mb-3 rounded-lg bg-danger-light px-2.5 py-1.5">
        <Badge variant="destructive" className="text-sm line-through">
          {selectedText}
        </Badge>
      </div>
      <Input
        ref={inputRef}
        type="text"
        value={correctText}
        onChange={(e) => setCorrectText(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && handleSave()}
        placeholder="输入正确文字…"
        className="mb-2.5"
      />
      <Select value={category} onValueChange={setCategory}>
        <SelectTrigger className="mb-3 text-xs">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="general">通用</SelectItem>
          <SelectItem value="name">人名</SelectItem>
          <SelectItem value="technical">技术术语</SelectItem>
          <SelectItem value="brand">品牌</SelectItem>
        </SelectContent>
      </Select>
      <div className="flex justify-end gap-2">
        <Button variant="ghost" size="sm" onClick={onClose}>
          取消
        </Button>
        <Button
          size="sm"
          onClick={handleSave}
          disabled={!correctText.trim() || saving}
        >
          {saving ? '保存中…' : '保存到词典'}
        </Button>
      </div>
    </div>
  );
}
