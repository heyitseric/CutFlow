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
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/components/ui/select';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Search, Upload, Download, Plus, Trash2, X, AlertCircle } from 'lucide-react';

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
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight text-foreground">词典管理</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          管理转录纠错词典，提高后续转录精度
        </p>
      </div>

      {/* Actions bar */}
      <div className="mb-5 flex items-center gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索词条..."
            className="pl-10"
          />
        </div>
        <Button
          variant="outline"
          onClick={() => fileInputRef.current?.click()}
        >
          <Upload className="size-4" />
          导入 JSON
        </Button>
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
        <Button variant="outline" onClick={handleExport}>
          <Download className="size-4" />
          导出 JSON
        </Button>
      </div>

      {/* Add new entry */}
      <Card className="mb-6">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold text-muted-foreground">添加新词条</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-end gap-3">
            <div className="flex-1">
              <Label className="mb-1.5">错误文字</Label>
              <Input
                type="text"
                value={newWrong}
                onChange={(e) => setNewWrong(e.target.value)}
                placeholder="如：生同"
              />
            </div>
            <div className="flex-1">
              <Label className="mb-1.5">正确文字</Label>
              <Input
                type="text"
                value={newCorrect}
                onChange={(e) => setNewCorrect(e.target.value)}
                placeholder="如：生酮"
              />
            </div>
            <div className="w-32">
              <Label className="mb-1.5">类别</Label>
              <Select value={newCategory} onValueChange={setNewCategory}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="general">通用</SelectItem>
                  <SelectItem value="name">人名</SelectItem>
                  <SelectItem value="technical">技术</SelectItem>
                  <SelectItem value="brand">品牌</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button
              onClick={handleAdd}
              disabled={adding || !newWrong.trim() || !newCorrect.trim()}
            >
              <Plus className="size-4" />
              {adding ? '添加中...' : '添加'}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Error */}
      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertCircle className="size-4" />
          <AlertDescription className="flex items-center justify-between">
            <span>{error}</span>
            <Button variant="ghost" size="icon-xs" onClick={() => setError(null)}>
              <X className="size-3.5" />
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {/* Table */}
      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>错误文字</TableHead>
              <TableHead>正确文字</TableHead>
              <TableHead>类别</TableHead>
              <TableHead>使用次数</TableHead>
              <TableHead>添加时间</TableHead>
              <TableHead className="w-20">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={6} className="py-12 text-center text-muted-foreground">
                  加载中...
                </TableCell>
              </TableRow>
            ) : filtered.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="py-12 text-center text-muted-foreground">
                  {search ? '没有匹配的词条' : '暂无词条，在上方添加'}
                </TableCell>
              </TableRow>
            ) : (
              filtered.map((entry) => (
                <TableRow key={entry.wrong}>
                  <TableCell>
                    <Badge variant="destructive" className="line-through">
                      {entry.wrong}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge className="bg-success/10 text-success border-transparent">
                      {entry.correct}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{entry.category}</TableCell>
                  <TableCell className="font-mono text-muted-foreground">{entry.frequency}</TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground/50">
                    {new Date(entry.addedAt).toLocaleDateString('zh-CN')}
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      onClick={() => handleDelete(entry.wrong)}
                      className="text-destructive hover:text-destructive hover:bg-destructive/10"
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Card>

      <p className="mt-3 font-mono text-xs text-muted-foreground/50">
        共 {filtered.length} 条{search && entries.length !== filtered.length && ` / 总计 ${entries.length} 条`}
      </p>
    </PageContainer>
  );
}
