"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import BriefCard from "./BriefCard";
import DigestArticle, { formatTime } from "./DigestArticle";
import { readDashboard, readStatus, readingOverview, type BriefCardData, type DashboardData, type RuntimeStatus } from "./topics/api";

const labels: Record<string, string> = { database: "数据库", ollama: "Ollama AI", scheduler: "自动更新", notifications: "系统通知" };
const states: Record<string, string> = { connected: "已连接", available: "可用", unavailable: "不可用", enabled: "已启用", disabled: "已关闭" };
export default function Dashboard() {
  const [reading,setReading]=useState<{recent_briefs:BriefCardData[];discovery:BriefCardData[];review_count:number;event_count:number;brief_count:number}|null>(null);
  const [data, setData] = useState<DashboardData | null>(null);
  const [status, setStatus] = useState<RuntimeStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    void Promise.allSettled([readDashboard(controller.signal), readStatus(controller.signal),readingOverview(controller.signal)]).then(([overview, health, news]) => {
      if (controller.signal.aborted) return;
      if (overview.status === "fulfilled") { setData(overview.value); setUpdatedAt(new Date().toISOString()); }
      if (health.status === "fulfilled") setStatus(health.value);
      if (news.status === "fulfilled") setReading(news.value);
      if (overview.status === "rejected" || health.status === "rejected" || news.status === "rejected") setError("部分数据暂时无法读取，请检查后端和数据库后刷新。已加载的内容仍可阅读。");
      setLoading(false);
    });
    return () => controller.abort();
  }, [revision]);
  const latest = data?.recent_digests[0];
  const metrics = [["关注主题", data?.total_topics], ["已采集内容", data?.total_items], ["已识别事件", reading?.event_count], ["事件简讯", reading?.brief_count]];
  return <main id="main-content" className="page">
    <header className="page-heading"><div><p className="eyebrow mb-2">YOUR INTELLIGENCE, ORGANIZED</p><h1 className="page-title">把信息变成值得关注的进展。</h1><p className="page-description">从关注的主题出发，让本地 AI 整理线索，留出时间阅读。</p></div><div className="flex gap-2"><button className="btn" disabled={loading} onClick={() => { setLoading(true); setError(null); setRevision(value => value + 1); }}>{loading ? "刷新中…" : "刷新总览"}</button><Link className="btn btn-primary" href="/topics">更新我的主题 →</Link></div></header>
    {error && <p role="alert" className="mb-5">{error}</p>}
    <section className="mb-8"><div className="mb-4 flex items-center justify-between"><h2 className="section-title">最新事件简讯</h2><Link className="text-link" href="/focus">阅读精准关注 →</Link></div>{reading?.recent_briefs.length?<div className="grid items-start gap-5 xl:grid-cols-2">{reading.recent_briefs.slice(0,2).map(brief=><BriefCard key={`${brief.id}-${brief.version}`} brief={brief} compact/>)}</div>:<p className="empty">{loading?"正在读取简讯…":"暂无事件简讯。更新主题后，已有进展会在这里呈现；服务失败不表示没有新闻。"}</p>}<p className="mt-4 text-xs text-muted">{reading?.review_count??"—"} 条匹配判断待复核 · <Link href="/discover" className="text-link">换个视角，开放发现 →</Link></p></section>
    <section aria-label="处理概况" className="mb-8 grid grid-cols-2 gap-3 lg:grid-cols-4">{metrics.map(([label, value]) => <div key={label} className="panel py-4"><p className="text-xs text-muted">{label}</p><p className="mt-2 text-xl font-semibold tabular-nums">{value ?? "—"}</p></div>)}</section>
    <div className="mb-4 flex flex-wrap items-center justify-between gap-2"><h2 className="section-title">你的情报速览</h2><p className="text-xs text-muted">{updatedAt ? `最近刷新 ${formatTime(updatedAt)}` : loading ? "正在读取工作空间…" : "尚未取得数据"}</p></div>
    <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1.7fr)_minmax(260px,1fr)]">
      <section className="panel border-t-[3px] border-t-accent sm:p-8">{latest ? <><DigestArticle digest={latest} topicName={latest.topic_name} compact/><Link className="text-link mt-6 inline-block" href={`/digests#digest-${latest.id}`}>阅读全文 →</Link></> : <div className="py-8"><p className="eyebrow mb-3">最新简报</p><h2 className="text-2xl font-semibold">下一份简报，从一个主题开始。</h2><p className="page-description mb-6">{loading ? "正在加载简报…" : data ? "还没有简报。在主题中执行一键更新，完成采集、分析和整理。" : "简报暂不可用，请检查后端连接。"}</p><Link className="btn btn-primary" href="/topics">前往我的主题</Link></div>}</section>
      <section className="panel"><div className="mb-5 flex items-center justify-between"><h2 className="section-title">主题动态</h2><Link href="/topics" className="text-link">管理</Link></div>{data?.topics.length ? <ul className="divide-y divide-line">{data.topics.slice(0, 6).map(topic => <li key={topic.id} className="py-3.5"><div className="flex items-center justify-between gap-3"><Link href={`/topics#topic-${topic.id}`} className="min-w-0 font-medium hover:text-accent">{topic.name}</Link><span className={`badge ${topic.enabled ? "badge-active" : ""}`}>{topic.enabled ? "已启用" : "已停用"}</span></div><p className="mt-1 text-xs text-muted">{topic.item_count} 条内容 · {topic.last_collected_at ? `最近采集 ${formatTime(topic.last_collected_at)}` : "尚未采集"}</p></li>)}</ul> : <p className="empty">{loading ? "正在加载主题…" : "暂无主题，创建第一个关注对象。"}</p>}<p className="mt-5 border-t border-line pt-4 text-xs leading-6 text-muted">一键更新顺序完成采集、规范化、主题匹配、事件识别和简讯整理。实际阶段及待处理数量请查看主题内的最近运行记录。</p></section>
      <section className="panel"><div className="mb-5 flex items-center justify-between"><h2 className="section-title">最近发现</h2><span className="eyebrow">RECENT SIGNALS</span></div>{data?.recent_items.length ? <ul className="divide-y divide-line">{data.recent_items.map(item => <li key={item.id} className="flex gap-4 py-4"><span className="mt-1 shrink-0 text-xs text-muted">{formatTime(item.collected_at).split(" ")[0]}</span><div className="min-w-0"><Link href={`/topics#topic-${item.topic_id}`} className="text-sm font-medium leading-6 hover:text-accent">{item.title}</Link><p className="mt-1 text-xs text-muted">{item.topic_name} · {item.source}</p></div></li>)}</ul> : <p className="empty">{loading ? "正在读取最新内容…" : data ? "还没有发现内容，先更新一个主题。" : "近期内容暂不可用。"}</p>}</section>
      <section id="system-status" className="panel scroll-mt-8"><h2 className="section-title">工作空间状态</h2><p className="page-description mb-5">本地依赖的实时探测快照</p><dl className="space-y-3">{Object.keys(labels).map(key => <div key={key} className="flex items-center justify-between gap-3"><dt className="text-sm text-muted">{labels[key]}</dt><dd className={`badge ${["connected", "available", "enabled"].includes(status?.[key as keyof RuntimeStatus] ?? "") ? "badge-active" : ""}`}>{status ? states[status[key as keyof RuntimeStatus]] ?? "未知" : loading ? "检测中" : "暂不可用"}</dd></div>)}</dl>{status?.ollama === "unavailable" && <p className="notice mt-5">AI 服务当前不可用。你仍可管理主题、采集和阅读已有内容。</p>}<p className="mt-5 border-t border-line pt-4 text-xs leading-6 text-muted">信息源连通性以实际扫描结果为准，此处不推测 YouTube API 配额或网络状态。</p></section>
    </div>
  </main>;
}
