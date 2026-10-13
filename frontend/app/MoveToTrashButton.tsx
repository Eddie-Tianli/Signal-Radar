"use client";
import { useRef, useState } from "react";
import { moveToTrash, type ContentKind } from "./topics/api";

export default function MoveToTrashButton({ kind, id, disabled, onDeleted }: {
  kind: ContentKind; id: number; disabled?: boolean; onDeleted: () => void;
}) {
  const working = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function remove() {
    if (working.current) return;
    working.current = true; setBusy(true); setError(null);
    try { await moveToTrash(kind, id); onDeleted(); }
    catch (error) { setError(error instanceof Error ? error.message : "移入回收站失败，请重试。"); }
    finally { working.current = false; setBusy(false); }
  }
  return <div><button className="btn btn-quiet text-xs text-red-700" disabled={disabled || busy} onClick={() => void remove()}>{busy ? "正在移入…" : "移入回收站"}</button>{error && <p role="alert" className="mt-2 text-sm">{error}</p>}</div>;
}
