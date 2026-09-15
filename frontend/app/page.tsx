"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import type { Digest } from "./topics/api";

type Overview = {
  total_topics: number; enabled_topics: number; total_items: number; relevant_items: number; unanalyzed_items: number;
  recent_items: { id: number; topic_id: number; topic_name: string; title: string; source: string; collected_at: string }[];
  recent_digests: (Digest & { topic_name: string })[];
};
type Status = { database: string; ollama: string; scheduler: string; notifications: string };

const runtimeLabels: Record<string, string> = { database: "数据库", ollama: "Ollama", scheduler: "自动任务", notifications: "系统通知" };
const runtimeStates: Record<string, string> = { connected: "已连接", available: "可用", unavailable: "暂不可用", enabled: "已启用", disabled: "已停用" };

export default function Dashboard() {
  const [data, setData] = useState<Overview | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    async function read(path: string) {
      const response = await fetch(`http://127.0.0.1:8000/api/${path}`, { cache: "no-store", signal: AbortSignal.any([controller.signal, AbortSignal.timeout(12000)]) });
      if (!response.ok) throw new Error("Request failed");
      return response.json();
    }
    void Promise.allSettled([read("dashboard"), read("status")]).then(([overview, health]) => {
      if (controller.signal.aborted) return;
      if (overview.status === "fulfilled") setData(overview.value);
      if (health.status === "fulfilled") setStatus(health.value);
      if (overview.status === "rejected" || health.status === "rejected") setError("部分概览数据暂不可用，请检查后端和数据库后刷新。");
      setLoading(false);
    });
    return () => controller.abort();
  }, [revision]);
  const latest = data?.recent_digests[0];
  const metrics = data ? [["主题总数", data.total_topics], ["已启用主题", data.enabled_topics], ["内容总数", data.total_items], ["相关内容", data.relevant_items], ["待分析内容", data.unanalyzed_items]] : [];
  return <main id="main-content" className="mx-auto max-w-7xl px-5 py-8 sm:px-8">
    <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
      <div><p className="eyebrow">个人信息情报平台</p><h1 className="mt-2 text-3xl font-bold tracking-tight">概览</h1><p className="mt-2 text-slate-600">查看关注的主题、已采集内容与最新简报。</p></div>
      <button disabled={loading} onClick={() => { setLoading(true); setError(null); setData(null); setStatus(null); setRevision(value => value + 1); }} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm">刷新概览</button>
    </div>
    <div aria-live="polite">{loading && <p role="status">正在加载概览…</p>}{error && <p role="alert" className="mb-5 text-sm text-red-700">{error}</p>}</div>
    <section aria-label="数据概览" className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-5">
      {metrics.map(([label, value]) => <div key={label} className="panel"><p className="text-sm text-slate-500">{label}</p><p className="mt-2 text-3xl font-semibold tabular-nums">{value}</p></div>)}
    </section>
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(260px,1fr)]">
      <section className="panel border-t-4 border-t-blue-700">
        <p className="eyebrow">最新简报</p>
        {latest ? <><h2 className="mt-3 break-words text-2xl font-semibold">{latest.title}</h2><p className="mt-3 text-sm text-slate-500">{latest.topic_name} · {new Date(latest.generated_at).toLocaleString()} · {latest.item_count} 条内容</p><span className="badge my-3">AI 生成的简报</span><p className="whitespace-pre-wrap break-words text-slate-700">{latest.summary}</p><Link className="mt-5 inline-block text-sm font-semibold text-blue-700 underline" href={`/topics#topic-${latest.topic_id}`}>查看主题 →</Link></> : <><h2 className="mt-3 text-xl font-semibold">从一个关注的主题开始。</h2><p className="my-3 text-slate-500">{data ? "暂无简报。请先扫描并分析内容，再生成简报。" : "简报数据暂不可用。"}</p><Link href="/topics" className="text-sm font-semibold text-blue-700 underline">管理主题 →</Link></>}
      </section>
      <section className="panel"><h2 className="text-lg font-semibold">本地运行状态</h2><p className="mb-4 mt-1 text-sm text-slate-500">以下为最近一次刷新时的依赖状态。</p><dl className="space-y-4">{["database", "ollama", "scheduler", "notifications"].map(key => <div key={key} className="flex flex-wrap justify-between gap-2 border-b border-slate-100 pb-3"><dt className="capitalize">{runtimeLabels[key]}</dt><dd className="badge">{(status ? runtimeStates[status[key as keyof Status]] : undefined) ?? (loading ? "加载中…" : "暂不可用")}</dd></div>)}</dl></section>
      <section className="panel"><h2 className="mb-4 text-lg font-semibold">最近采集</h2>{data?.recent_items.length ? <ul className="divide-y divide-slate-100">{data.recent_items.map(item => <li key={item.id} className="py-3"><Link href={`/topics#topic-${item.topic_id}`} className="break-words font-medium text-slate-800 hover:underline">{item.title}</Link><p className="mt-1 text-xs text-slate-500">{item.topic_name} · {item.source} · {new Date(item.collected_at).toLocaleString()}</p></li>)}</ul> : <p className="text-sm text-slate-500">{data ? "暂无已采集内容。" : "近期内容暂不可用。"}</p>}</section>
      <section className="panel"><h2 className="mb-4 text-lg font-semibold">最近生成的简报</h2>{data?.recent_digests.length ? <ul className="space-y-4">{data.recent_digests.map(digest => <li key={digest.id}><Link href={`/topics#topic-${digest.topic_id}`} className="break-words text-sm font-medium hover:underline">{digest.title}</Link><p className="text-xs text-slate-500">{digest.topic_name} · {new Date(digest.generated_at).toLocaleString()}</p></li>)}</ul> : <p className="text-sm text-slate-500">{data ? "暂无简报。" : "历史记录暂不可用。"}</p>}</section>
    </div>
  </main>;
}
