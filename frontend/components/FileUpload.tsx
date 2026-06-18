"use client";

import { useCallback, useRef, useState, type DragEvent } from "react";
import { cn } from "@/lib/utils";

const ALLOWED = ["image/jpeg", "image/png", "image/webp", "application/pdf"];
const MAX_MB = 20;

interface Props {
  file: File | null;
  onSelect: (file: File | null) => void;
}

export function FileUpload({ file, onSelect }: Props) {
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validate = useCallback((f: File): boolean => {
    if (!ALLOWED.includes(f.type)) {
      setError("Format tidak didukung (gunakan JPG, PNG, WEBP, atau PDF).");
      return false;
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      setError(`Ukuran berkas melebihi ${MAX_MB}MB.`);
      return false;
    }
    setError(null);
    return true;
  }, []);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) return;
      const f = files[0];
      if (validate(f)) onSelect(f);
    },
    [validate, onSelect],
  );

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    handleFiles(e.dataTransfer.files);
  }

  function onDragOver(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(true);
  }

  return (
    <div>
      <div
        onClick={() => inputRef.current?.click()}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={() => setDragging(false)}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 text-center transition",
          dragging
            ? "border-indigo-500 bg-indigo-50"
            : "border-slate-300 bg-slate-50 hover:border-indigo-400",
        )}
      >
        <p className="text-sm font-medium text-slate-700">
          {file ? file.name : "Klik atau seret berkas ke sini"}
        </p>
        <p className="mt-1 text-xs text-slate-500">
          JPG, PNG, WEBP, atau PDF \u00b7 maks {MAX_MB}MB
        </p>
        <input
          ref={inputRef}
          type="file"
          accept={ALLOWED.join(",")}
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      {file && (
        <button
          type="button"
          onClick={() => onSelect(null)}
          className="mt-2 text-xs text-slate-500 transition hover:text-red-600"
        >
          Hapus berkas
        </button>
      )}
    </div>
  );
}
