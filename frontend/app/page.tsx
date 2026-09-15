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
      if (overview.status === "rejected" || health.status === "rejected") setError("Some dashboard data is unavailable. Check the backend and database, then refresh.");
      setLoading(false);
    });
    return () => controller.abort();
  }, [revision]);
  const latest = data?.recent_digests[0];
  const metrics = data ? [["Total Topics", data.total_topics], ["Enabled Topics", data.enabled_topics], ["Total Items", data.total_items], ["Relevant Items", data.relevant_items], ["Unanalyzed Items", data.unanalyzed_items]] : [];
  return <main id="main-content" className="mx-auto max-w-7xl px-5 py-8 sm:px-8">
    <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
      <div><p className="eyebrow">Personal Information Intelligence Platform</p><h1 className="mt-2 text-3xl font-bold tracking-tight">Dashboard</h1><p className="mt-2 text-slate-600">Your topics, collected signals, and latest intelligence.</p></div>
      <button disabled={loading} onClick={() => { setLoading(true); setError(null); setData(null); setStatus(null); setRevision(value => value + 1); }} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm">Refresh dashboard</button>
    </div>
    <div aria-live="polite">{loading && <p role="status">Loading dashboard...</p>}{error && <p role="alert" className="mb-5 text-sm text-red-700">{error}</p>}</div>
    <section aria-label="Overview counts" className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-5">
      {metrics.map(([label, value]) => <div key={label} className="panel"><p className="text-sm text-slate-500">{label}</p><p className="mt-2 text-3xl font-semibold tabular-nums">{value}</p></div>)}
    </section>
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(260px,1fr)]">
      <section className="panel border-t-4 border-t-blue-700">
        <p className="eyebrow">Latest Digest</p>
        {latest ? <><h2 className="mt-3 break-words text-2xl font-semibold">{latest.title}</h2><p className="mt-3 text-sm text-slate-500">{latest.topic_name} · {new Date(latest.generated_at).toLocaleString()} · {latest.item_count} items</p><span className="badge my-3">AI-generated Digest</span><p className="whitespace-pre-wrap break-words text-slate-700">{latest.summary}</p><Link className="mt-5 inline-block text-sm font-semibold text-blue-700 underline" href={`/topics#topic-${latest.topic_id}`}>Open Topic →</Link></> : <><h2 className="mt-3 text-xl font-semibold">Your next brief starts with a Topic.</h2><p className="my-3 text-slate-500">{data ? "No Digests yet. Scan and analyze your Items, then generate a Digest." : "Digest data is not available yet."}</p><Link href="/topics" className="text-sm font-semibold text-blue-700 underline">Manage Topics →</Link></>}
      </section>
      <section className="panel"><h2 className="text-lg font-semibold">Local runtime</h2><p className="mb-4 mt-1 text-sm text-slate-500">Dependency status at last refresh.</p><dl className="space-y-4">{["database", "ollama", "scheduler", "notifications"].map(key => <div key={key} className="flex flex-wrap justify-between gap-2 border-b border-slate-100 pb-3"><dt className="capitalize">{key === "ollama" ? "Ollama" : key}</dt><dd className="badge">{status?.[key as keyof Status] ?? (loading ? "Loading..." : "Unavailable")}</dd></div>)}</dl></section>
      <section className="panel"><h2 className="mb-4 text-lg font-semibold">Recently collected</h2>{data?.recent_items.length ? <ul className="divide-y divide-slate-100">{data.recent_items.map(item => <li key={item.id} className="py-3"><Link href={`/topics#topic-${item.topic_id}`} className="break-words font-medium text-slate-800 hover:underline">{item.title}</Link><p className="mt-1 text-xs text-slate-500">{item.topic_name} · {item.source} · {new Date(item.collected_at).toLocaleString()}</p></li>)}</ul> : <p className="text-sm text-slate-500">{data ? "No collected Items yet." : "Activity unavailable."}</p>}</section>
      <section className="panel"><h2 className="mb-4 text-lg font-semibold">Recent Digests</h2>{data?.recent_digests.length ? <ul className="space-y-4">{data.recent_digests.map(digest => <li key={digest.id}><Link href={`/topics#topic-${digest.topic_id}`} className="break-words text-sm font-medium hover:underline">{digest.title}</Link><p className="text-xs text-slate-500">{digest.topic_name} · {new Date(digest.generated_at).toLocaleString()}</p></li>)}</ul> : <p className="text-sm text-slate-500">{data ? "No Digests yet." : "History unavailable."}</p>}</section>
    </div>
  </main>;
}
