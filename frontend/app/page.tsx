"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import DigestArticle, { formatTime } from "./DigestArticle";
import { readDashboard, readStatus, type DashboardData, type RuntimeStatus } from "./topics/api";

const labels: Record<string, string> = { database: "数据库", ollama: "Ollama AI", scheduler: "自动更新", notifications: "系统通知" };
const states: Record<string, string> = { connected: "已连接", available: "可用", unavailable: "不可用", enabled: "已启用", disabled: "已关闭" };
export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [status, setStatus] = useState<RuntimeStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    void Promise.allSettled([readDashboard(controller.signal), readStatus(controller.signal)]).then(([overview, health]) => {
      if (controller.signal.aborted) return;
      if (overview.status === "fulfilled") { setData(overview.value); setUpdatedAt(new Date().toISOString()); }
      if (health.status === "fulfilled") setStatus(health.value);
      if (overview.status === "rejected" || health.status === "rejected") setError("部分数据暂时无法读取，请检查后端和数据库后刷新。已加载的内容仍可阅读。");
      setLoading(false);
    });
    return () => controller.abort();
  }, [revision]);
  const latest = data?.recent_digests[0];
  const metrics = [["关注主题", data?.total_topics], ["已采集内容", data?.total_items], ["已分析内容", data?.analyzed_items], ["有效内容", data?.relevant_items]];
  return <main id="main-content" className="page">
    <header className="page-heading"><div><p className="eyebrow mb-2">YOUR INTELLIGENCE, ORGANIZED</p><h1 className="page-title">把信息变成值得关注的进展。</h1><p className="page-description">从关注的主题出发，让本地 AI 整理线索，留出时间阅读。</p></div><div className="flex gap-2"><button className="btn" disabled={loading} onClick={() => { setLoading(true); setError(null); setRevision(value => value + 1); }}>{loading ? "刷新中…" : "刷新总览"}</button><Link className="btn btn-primary" href="/topics">更新我的主题 →</Link></div></header>
    {error && <p role="alert" className="mb-5">{error}</p>}
    <section aria-label="处理概况" className="mb-8 grid grid-cols-2 gap-3 lg:grid-cols-4">{metrics.map(([label, value]) => <div key={label} className="panel py-4"><p className="text-xs text-muted">{label}</p><p className="mt-2 text-3xl font-semibold tabular-nums">{value ?? "—"}</p></div>)}</section>
    <div className="mb-4 flex flex-wrap items-center justify-between gap-2"><h2 className="section-title">你的情报速览</h2><p className="text-xs text-muted">{updatedAt ? `最近刷新 ${formatTime(updatedAt)}` : loading ? "正在读取工作空间…" : "尚未取得数据"}</p></div>
    <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1.7fr)_minmax(260px,1fr)]">
      <section className="panel border-t-[3px] border-t-accent sm:p-8">{latest ? <><DigestArticle digest={latest} topicName={latest.topic_name} compact/><Link className="text-link mt-6 inline-block" href={`/digests#digest-${latest.id}`}>阅读全文 →</Link></> : <div className="py-8"><p className="eyebrow mb-3">最新简报</p><h2 className="text-2xl font-semibold">下一份简报，从一个主题开始。</h2><p className="page-description mb-6">{loading ? "正在加载简报…" : data ? "还没有简报。在主题中执行一键更新，完成采集、分析和整理。" : "简报暂不可用，请检查后端连接。"}</p><Link className="btn btn-primary" href="/topics">前往我的主题</Link></div>}</section>
      <section className="panel"><div className="mb-5 flex items-center justify-between"><h2 className="section-title">主题动态</h2><Link href="/topics" className="text-link">管理</Link></div>{data?.topics.length ? <ul className="divide-y divide-line">{data.topics.slice(0, 6).map(topic => <li key={topic.id} className="py-3.5"><div className="flex items-center justify-between gap-3"><Link href={`/topics#topic-${topic.id}`} className="min-w-0 font-medium hover:text-accent">{topic.name}</Link><span className={`badge ${topic.enabled ? "badge-active" : ""}`}>{topic.enabled ? "已启用" : "已停用"}</span></div><p className="mt-1 text-xs text-muted">{topic.item_count} 条内容 · {topic.last_collected_at ? `最近采集 ${formatTime(topic.last_collected_at)}` : "尚未采集"}</p></li>)}</ul> : <p className="empty">{loading ? "正在加载主题…" : "暂无主题，创建第一个关注对象。"}</p>}<p className="mt-5 border-t border-line pt-4 text-xs leading-6 text-muted">{data ? `${data.unanalyzed_items} 条内容等待分析` : "待分析数量暂不可用"}。一键更新会顺序处理，当前配置下已完成的分析不会重复执行；规则变更后会重新确认。</p></section>
      <section className="panel"><div className="mb-5 flex items-center justify-between"><h2 className="section-title">最近发现</h2><span className="eyebrow">RECENT SIGNALS</span></div>{data?.recent_items.length ? <ul className="divide-y divide-line">{data.recent_items.map(item => <li key={item.id} className="flex gap-4 py-4"><span className="mt-1 shrink-0 text-xs text-muted">{formatTime(item.collected_at).split(" ")[0]}</span><div className="min-w-0"><Link href={`/topics#topic-${item.topic_id}`} className="text-sm font-medium leading-6 hover:text-accent">{item.title}</Link><p className="mt-1 text-xs text-muted">{item.topic_name} · {item.source}</p></div></li>)}</ul> : <p className="empty">{loading ? "正在读取最新内容…" : data ? "还没有发现内容，先更新一个主题。" : "近期内容暂不可用。"}</p>}</section>
      <section id="system-status" className="panel scroll-mt-8"><h2 className="section-title">工作空间状态</h2><p className="page-description mb-5">本地依赖的实时探测快照</p><dl className="space-y-3">{Object.keys(labels).map(key => <div key={key} className="flex items-center justify-between gap-3"><dt className="text-sm text-muted">{labels[key]}</dt><dd className={`badge ${["connected", "available", "enabled"].includes(status?.[key as keyof RuntimeStatus] ?? "") ? "badge-active" : ""}`}>{status ? states[status[key as keyof RuntimeStatus]] ?? "未知" : loading ? "检测中" : "暂不可用"}</dd></div>)}</dl>{status?.ollama === "unavailable" && <p className="notice mt-5">AI 服务当前不可用。你仍可管理主题、采集和阅读已有内容。</p>}<p className="mt-5 border-t border-line pt-4 text-xs leading-6 text-muted">信息源连通性以实际扫描结果为准，此处不推测 YouTube API 配额或网络状态。</p></section>
    </div>
  </main>;
}
