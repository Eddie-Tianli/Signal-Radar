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
      if (!request.signal.aborted) setError(error instanceof Error ? error.message : "简报加载失败，请重试。");
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
      if (!request.signal.aborted) setError(error instanceof Error ? error.message : "简报操作失败，请重试。");
    } finally {
      controller.current = null;
      if (!request.signal.aborted) setBusy(null);
    }
  }

  return <section aria-label={`主题简报：${topicId}`} className="rounded-xl border border-blue-100 bg-slate-50 p-4 sm:p-5">
    <p className="eyebrow">情报简报</p>
    <h3 className="mt-1 text-lg font-semibold">最新简报</h3>
    <div className="my-3 flex flex-wrap gap-3">
      <button disabled={!!busy || initialLoading} onClick={() => void load("generate")} className="rounded-lg bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50">
        {busy === "generate" ? "正在生成简报…" : "生成简报"}
      </button>
      <button disabled={!!busy || initialLoading} onClick={() => history ? setHistory(false) : void load("history")} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm disabled:opacity-50">
        {busy === "history" ? "正在加载历史记录…" : history ? "收起历史简报" : "查看历史简报"}
      </button>
    </div>
    <div aria-live="polite" className="space-y-3">
      {error && <p role="alert" className="text-sm text-red-700">简报操作失败：{error}</p>}
      {initialLoading && <p role="status">正在加载简报…</p>}
      {!initialLoading && !digests.length && <p className="text-sm text-slate-500">暂无简报。请先分析内容，存在相关内容后即可生成简报。</p>}
      {(history ? digests : digests.slice(0, 1)).map((digest) => <article key={digest.id} className="rounded-lg border border-slate-200 border-t-4 border-t-blue-700 bg-white p-5">
        <h4 className="break-words font-semibold">{digest.title}</h4>
        <p className="mt-2 text-sm font-medium">AI 生成的简报</p>
        <p className="text-sm text-slate-500">主题：{topicName}</p>
        <p className="text-sm text-slate-500">生成时间：<time dateTime={digest.generated_at}>{new Date(digest.generated_at).toLocaleString()}</time></p>
        <p className="text-sm text-slate-500">引用内容数：{digest.item_count}</p>
        <p className="mt-3 whitespace-pre-wrap break-words text-slate-700">{digest.summary}</p>
      </article>)}
    </div>
  </section>;
}
