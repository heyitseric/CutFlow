import { useCallback, useRef, useState, type DragEvent } from 'react';
import { CheckCircle2, RefreshCw } from 'lucide-react';
import { Card } from '@/components/ui/card';

interface FileDropZoneProps {
  accept: string;
  label: string;
  icon: React.ReactNode;
  file: File | null;
  onFile: (file: File) => void;
}

export default function FileDropZone({ accept, label, icon, file, onFile }: FileDropZoneProps) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback(
    (e: DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const f = e.dataTransfer.files[0];
      if (f) onFile(f);
    },
    [onFile],
  );

  const handleDragOver = useCallback((e: DragEvent) => {
    e.preventDefault();
    setDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setDragging(false);
  }, []);

  function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  return (
    <Card
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onClick={() => inputRef.current?.click()}
      className={`
        group flex cursor-pointer flex-col items-center justify-center
        border-2 border-dashed p-10 transition-all duration-300
        ${dragging
          ? 'border-primary bg-primary/5 scale-[1.02]'
          : file
            ? 'border-success/30 bg-success/5'
            : 'border-border hover:border-muted-foreground/30 hover:bg-accent'
        }
      `}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
        }}
      />

      {file ? (
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-success/10 text-success">
            <CheckCircle2 className="h-7 w-7" />
          </div>
          <div>
            <p className="text-sm font-medium text-foreground">{file.name}</p>
            <p className="mt-1 font-mono text-xs text-muted-foreground">{formatSize(file.size)}</p>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-muted px-3 py-1 text-xs text-muted-foreground transition-colors group-hover:bg-accent group-hover:text-foreground">
            <RefreshCw className="h-3 w-3" />
            点击更换文件
          </span>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-4 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-muted text-muted-foreground transition-colors group-hover:bg-primary/5 group-hover:text-foreground">
            {icon}
          </div>
          <div>
            <p className="text-sm font-medium text-foreground">{label}</p>
            <p className="mt-1.5 text-xs text-muted-foreground">
              拖拽文件到此处，或点击选择
            </p>
          </div>
        </div>
      )}
    </Card>
  );
}
