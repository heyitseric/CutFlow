import { useCallback, useRef, useState, type DragEvent } from 'react';

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
    <div
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onClick={() => inputRef.current?.click()}
      className={`
        group relative flex cursor-pointer flex-col items-center justify-center
        rounded-2xl border-2 border-dashed p-10 transition-all duration-300 transition-cinematic
        ${dragging
          ? 'border-amber bg-amber-glow scale-[1.02]'
          : file
            ? 'border-success/30 bg-success-surface'
            : 'border-border hover:border-amber-dim hover:bg-amber-glow/50'
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
            <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <div>
            <p className="font-display text-sm font-medium text-text-primary">{file.name}</p>
            <p className="mt-1 font-mono text-xs text-text-muted">{formatSize(file.size)}</p>
          </div>
          <span className="rounded-full bg-elevated px-3 py-1 text-xs text-text-secondary transition-colors transition-smooth group-hover:bg-hover group-hover:text-amber">
            点击更换文件
          </span>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-4 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-elevated text-text-muted transition-colors transition-smooth group-hover:bg-amber/10 group-hover:text-amber">
            {icon}
          </div>
          <div>
            <p className="font-display text-sm font-medium text-text-primary">{label}</p>
            <p className="mt-1.5 text-xs text-text-muted">
              拖拽文件到此处，或点击选择
            </p>
          </div>
        </div>
      )}

      {/* Decorative corner marks */}
      {!file && (
        <>
          <div className="absolute left-3 top-3 h-4 w-4 border-l-2 border-t-2 border-border/50 rounded-tl transition-colors transition-smooth group-hover:border-amber/30" />
          <div className="absolute right-3 top-3 h-4 w-4 border-r-2 border-t-2 border-border/50 rounded-tr transition-colors transition-smooth group-hover:border-amber/30" />
          <div className="absolute bottom-3 left-3 h-4 w-4 border-b-2 border-l-2 border-border/50 rounded-bl transition-colors transition-smooth group-hover:border-amber/30" />
          <div className="absolute bottom-3 right-3 h-4 w-4 border-b-2 border-r-2 border-border/50 rounded-br transition-colors transition-smooth group-hover:border-amber/30" />
        </>
      )}
    </div>
  );
}
