"use client";

import { useEffect, useRef, useState } from "react";
import { generateDigest, listDigests, type Digest } from "./api";

export default function TopicDigests({ topicId, topicName }: { topicId: number; topicName: string }) {
  const [digests, setDigests] = useState<Digest[]>([]);
  const [history, setHistory] = useState(false);
  const [busy, setBusy] = useState<"generate" | "history" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    const request = new AbortController();
    void listDigests(topicId, request.signal).then(results => {
      if (!request.signal.aborted) setDigests(results);
    }).catch(error => {
      if (!request.signal.aborted) setError(error instanceof Error ? error.message : "Could not load Digests.");
    }).finally(() => { if (!request.signal.aborted) setInitialLoading(false); });
    return () => request.abort();
  }, [topicId]);

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

  return <section aria-label={`Digests for Topic ${topicId}`} className="rounded-xl border border-blue-100 bg-slate-50 p-4 sm:p-5">
    <p className="eyebrow">Intelligence brief</p>
    <h3 className="mt-1 text-lg font-semibold">Latest Digest</h3>
    <div className="my-3 flex flex-wrap gap-3">
      <button disabled={!!busy || initialLoading} onClick={() => void load("generate")} className="rounded-lg bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50">
        {busy === "generate" ? "Generating..." : "Generate Digest"}
      </button>
      <button disabled={!!busy || initialLoading} onClick={() => history ? setHistory(false) : void load("history")} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm disabled:opacity-50">
        {busy === "history" ? "Loading history..." : history ? "Hide Digest History" : "View Digest History"}
      </button>
    </div>
    <div aria-live="polite" className="space-y-3">
      {error && <p role="alert" className="text-sm text-red-700">Digest failed: {error}</p>}
      {initialLoading && <p role="status">Loading Digests...</p>}
      {!initialLoading && !digests.length && <p className="text-sm text-slate-500">No Digests yet. Analyze relevant Items, then generate your first brief.</p>}
      {(history ? digests : digests.slice(0, 1)).map((digest) => <article key={digest.id} className="rounded-lg border border-slate-200 border-t-4 border-t-blue-700 bg-white p-5">
        <h4 className="break-words font-semibold">{digest.title}</h4>
        <p className="mt-2 text-sm font-medium">AI-generated Digest</p>
        <p className="text-sm text-slate-500">Topic: {topicName}</p>
        <p className="text-sm text-slate-500">Generated: <time dateTime={digest.generated_at}>{new Date(digest.generated_at).toLocaleString()}</time></p>
        <p className="text-sm text-slate-500">Items used: {digest.item_count}</p>
        <p className="mt-3 whitespace-pre-wrap break-words text-slate-700">{digest.summary}</p>
      </article>)}
    </div>
  </section>;
}
