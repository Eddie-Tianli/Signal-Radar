"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { deleteTopic, listTopics, readDashboard, saveTopic, type Topic, type TopicInput, type TopicOverview } from "./api";
import TopicForm from "./TopicForm";
import TopicList from "./TopicList";
export default function TopicsPage() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [stats, setStats] = useState<TopicOverview[]>([]);
  const [editing, setEditing] = useState<Topic | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const saving = useRef(false);
  const followedHash = useRef("");
  const refreshStats = useCallback(() => { void readDashboard().then(data => setStats(data.topics)).catch(() => {}); }, []);
  useEffect(() => {
    const controller = new AbortController();
    void listTopics(controller.signal).then(data => { if (!controller.signal.aborted) setTopics(data); }).catch(error => { if (!controller.signal.aborted) setError(error.message); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    void readDashboard(controller.signal).then(data => { if (!controller.signal.aborted) setStats(data.topics); }).catch(() => {});
    return () => controller.abort();
  }, []);
  useEffect(() => {
    const hash = window.location.hash;
    if (!/^#topic-\d+$/.test(hash) || followedHash.current === hash) return;
    const target = document.getElementById(hash.slice(1));
    if (target) { target.scrollIntoView({ block: "start" }); followedHash.current = hash; }
  }, [topics]);
  async function refresh() {
    setLoading(true); setError(null);
    try { setTopics(await listTopics()); refreshStats(); }
    catch (error) { setError(error instanceof Error ? error.message : "主题列表读取失败。"); }
    finally { setLoading(false); }
  }
  async function save(data: TopicInput) {
    if (saving.current) return;
    saving.current = true; setBusy(true); setNotice(null);
    try {
      const saved = await saveTopic(data, editing?.id);
      setTopics(current => editing ? current.map(topic => topic.id === saved.id ? saved : topic) : [...current, saved]);
      setNotice(editing ? "主题已更新。" : "主题已创建，点击一键更新开始整理信息。");
      setEditing(null); setShowForm(false); refreshStats();
    } finally { saving.current = false; setBusy(false); }
  }
  async function remove(topic: Topic) {
    if (saving.current || !window.confirm(`确定删除“${topic.name}”吗？其内容和历史简报也会删除。`)) return;
    saving.current = true; setBusy(true); setNotice(null); setError(null);
    try { await deleteTopic(topic.id); setTopics(current => current.filter(item => item.id !== topic.id)); if (editing?.id === topic.id) { setEditing(null); setShowForm(false); } setNotice("主题已删除。"); refreshStats(); }
    catch (error) { setError(error instanceof Error ? error.message : "删除未完成。"); }
    finally { saving.current = false; setBusy(false); }
  }
  const visible = topics.filter(topic => `${topic.name} ${topic.description ?? ""}`.toLowerCase().includes(query.toLowerCase()) && (filter === "all" || topic.enabled === (filter === "enabled")));
  return <main id="main-content" className="page"><header className="page-heading"><div><p className="eyebrow mb-2">FOLLOW WHAT MATTERS</p><h1 className="page-title">我的主题</h1><p className="page-description">关注一个方向，一键完成采集、分析与简报整理。</p></div><button className="btn btn-primary" disabled={busy} onClick={() => { setEditing(null); setShowForm(true); }}>＋ 创建主题</button></header>
    <div aria-live="polite" className="mb-5 space-y-3">{notice && <p className="notice">{notice}</p>}{error && <p role="alert">{error}</p>}</div>
    {showForm && <TopicForm key={editing?.id ?? "new"} topic={editing} busy={busy} onSave={save} onCancel={() => { setShowForm(false); setEditing(null); }}/>}
    <section aria-label="主题管理"><div className="mb-5 flex flex-wrap items-center gap-3"><label className="sr-only" htmlFor="topic-query">查找主题</label><input id="topic-query" className="w-full sm:w-64" placeholder="查找主题名称或描述…" value={query} onChange={event => setQuery(event.target.value)}/><label className="sr-only" htmlFor="topic-filter">启用状态</label><select id="topic-filter" value={filter} onChange={event => setFilter(event.target.value)}><option value="all">全部状态</option><option value="enabled">已启用</option><option value="disabled">已停用</option></select><span className="mr-auto text-xs text-muted">{loading ? "读取中…" : error && !topics.length ? "数量暂不可用" : `${visible.length} 个主题`}</span><button className="btn btn-quiet" disabled={loading || busy} onClick={() => void refresh()}>{loading ? "加载中…" : "刷新列表"}</button></div>
    {loading && <p role="status" className="mb-4 text-sm text-muted">正在读取主题…</p>}
    {!loading && topics.length === 0 && !error ? <div className="empty"><h2 className="mb-2 text-lg font-medium text-ink">从你关心的事开始。</h2><p>创建一个主题，追踪人物、技术或行业的最新进展。</p><button className="btn btn-primary mt-4" onClick={() => setShowForm(true)}>创建第一个主题</button></div> : <TopicList topics={visible} stats={stats} busy={busy} onEdit={topic => { setEditing(topic); setShowForm(true); window.scrollTo({ top: 0, behavior: "instant" }); }} onDelete={topic => void remove(topic)} onDataChange={refreshStats}/>}
    {!loading && !!topics.length && !visible.length && <p className="empty">没有匹配的主题，请调整搜索或状态筛选。</p>}</section></main>;
}
