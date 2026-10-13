"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { listDigests, listTopics, type Digest } from "../topics/api";
import DigestArticle, { formatTime } from "../DigestArticle";
type Brief = Digest & { topic_name: string };
export default function DigestsPage() {
  const [digests, setDigests] = useState<Brief[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      try {
        const topics = await listTopics(controller.signal);
        const results = await Promise.allSettled(topics.map(async topic => (await listDigests(topic.id, controller.signal)).map(digest => ({ ...digest, topic_name: topic.name }))));
        if (controller.signal.aborted) return;
        const rows = results.flatMap(result => result.status === "fulfilled" ? result.value : []).sort((a, b) => new Date(b.generated_at).getTime() - new Date(a.generated_at).getTime() || b.id - a.id);
        setDigests(rows);
        const requested = Number(window.location.hash.replace("#digest-", ""));
        setSelected(rows.find(row => row.id === requested)?.id ?? rows[0]?.id ?? null);
        if (results.some(result => result.status === "rejected")) setError("部分主题的历史简报暂不可用，已读取的简报仍可阅读。请刷新重试。");
      } catch (error) { if (!controller.signal.aborted) setError(error instanceof Error ? error.message : "简报读取失败。"); }
      finally { if (!controller.signal.aborted) setLoading(false); }
    })();
    return () => controller.abort();
  }, [revision]);
  const visible = digests.filter(digest => filter === "all" || String(digest.topic_id) === filter);
  const current = visible.find(digest => digest.id === selected) ?? visible[0];
  const topics = Array.from(new Map(digests.map(digest => [digest.topic_id, digest.topic_name])).entries());
  return <main id="main-content" className="page"><header className="page-heading"><div><p className="eyebrow mb-2">LESS NOISE, MORE SIGNAL</p><h1 className="page-title">情报简报</h1><p className="page-description">读重要进展，也回看每一次整理留下的快照。</p></div><button className="btn" disabled={loading} onClick={() => { setLoading(true); setError(null); setRevision(value => value + 1); }}>{loading ? "读取中…" : "刷新历史"}</button></header>{error && <p role="alert" className="mb-5">{error}</p>}{loading && <p role="status" className="mb-4 text-sm text-muted">正在读取各主题的简报历史…</p>}{!loading && !digests.length ? <section className="empty"><h2 className="mb-2 text-lg font-medium text-ink">{error ? "简报暂时无法读取。" : "还没有可阅读的简报。"}</h2><p>{error ? "请检查本地后端和数据库，再刷新历史。" : "更新一个主题，AI 会在有相关摘要时生成简报。"}</p><Link className="btn btn-primary mt-4" href="/topics">前往我的主题</Link></section> : <div className="grid items-start gap-6 xl:grid-cols-[280px_minmax(0,1fr)]"><section className="panel p-3"><label className="field-label px-2" htmlFor="brief-topic">主题</label><select className="mb-4 w-full" id="brief-topic" value={filter} onChange={event => setFilter(event.target.value)}><option value="all">全部主题</option>{topics.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select><ul className="max-h-[65vh] space-y-1 overflow-y-auto">{visible.map(digest => <li key={digest.id}><button aria-pressed={current?.id === digest.id} onClick={() => setSelected(digest.id)} className={`w-full rounded-lg p-3 text-left ${current?.id === digest.id ? "bg-accent-soft text-accent" : "hover:bg-canvas"}`}><p className="mb-2 text-[11px] text-muted">{digest.topic_name} · {formatTime(digest.generated_at)}</p><p className="line-clamp-2 text-sm font-medium leading-6">{digest.title}</p></button></li>)}</ul></section><section className="panel min-w-0 sm:p-9 lg:p-10">{current && <><DigestArticle digest={current} topicName={current.topic_name}/><Link className="text-link mt-5 inline-block" href={`/topics#topic-${current.topic_id}`}>查看主题与原始内容 →</Link></>}</section></div>}</main>;
}
