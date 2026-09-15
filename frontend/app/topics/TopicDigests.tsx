"use client";

import { useEffect, useRef, useState } from "react";
import { generateDigest, listDigests, type Digest } from "./api";

export default function TopicDigests({ topicId }: { topicId: number }) {
  const [digests, setDigests] = useState<Digest[]>([]);
  const [history, setHistory] = useState(false);
  const [busy, setBusy] = useState<"generate" | "history" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);

  async function load(action: "generate" | "history") {
    if (controller.current) return;
    const request = new AbortController();
    controller.current = request;
    setBusy(action);
    setError(null);
    try {
      if (action === "generate") {
        const digest = await generateDigest(topicId, request.signal);
        if (!request.signal.aborted) {
          setDigests((previous) => [digest, ...previous.filter((item) => item.id !== digest.id)]);
          setHistory(false);
        }
      } else {
        const results = await listDigests(topicId, request.signal);
        if (!request.signal.aborted) {
          setDigests(results);
          setHistory(true);
        }
      }
    } catch (error) {
      if (!request.signal.aborted) setError(error instanceof Error ? error.message : "Could not load Digest.");
    } finally {
      controller.current = null;
      if (!request.signal.aborted) setBusy(null);
    }
  }

  return <section aria-label={`Digests for Topic ${topicId}`} className="mt-6 border-t border-slate-200 pt-4">
    <h3 className="font-semibold">Topic Digests</h3>
    <div className="my-3 flex flex-wrap gap-3">
      <button disabled={!!busy} onClick={() => void load("generate")} className="rounded-lg bg-slate-900 px-3 py-2 text-white disabled:opacity-50">
        {busy === "generate" ? "Generating..." : "Generate Digest"}
      </button>
      <button disabled={!!busy} onClick={() => void load("history")} className="rounded-lg border border-slate-300 px-3 py-2 disabled:opacity-50">
        {busy === "history" ? "Loading history..." : "View Digest History"}
      </button>
    </div>
    <div aria-live="polite" className="space-y-3">
      {error && <p role="alert" className="text-sm text-red-700">Digest failed: {error}</p>}
      {history && !digests.length && <p className="text-sm text-slate-500">No Digests yet.</p>}
      {(history ? digests : digests.slice(0, 1)).map((digest) => <article key={digest.id} className="rounded-lg border border-slate-200 p-4">
        <h4 className="break-words font-semibold">{digest.title}</h4>
        <p className="mt-2 text-sm font-medium">AI-generated Digest</p>
        <p className="text-sm text-slate-500">Generated: <time dateTime={digest.generated_at}>{digest.generated_at}</time></p>
        <p className="text-sm text-slate-500">Items used: {digest.item_count}</p>
        <p className="mt-3 whitespace-pre-wrap break-words text-slate-700">{digest.summary}</p>
      </article>)}
    </div>
  </section>;
}
