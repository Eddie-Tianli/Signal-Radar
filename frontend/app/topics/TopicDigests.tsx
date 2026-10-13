"use client";
import { useEffect, useState } from "react";
import { listDigests, type Digest } from "./api";
import DigestArticle, { formatTime } from "../DigestArticle";
export default function TopicDigests({ topicId, topicName, revision }: { topicId: number; topicName: string; revision: number }) {
  const [digests, setDigests] = useState<Digest[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    void listDigests(topicId, controller.signal).then(data => { if (!controller.signal.aborted) { setDigests(data); setSelected(data[0]?.id ?? null); setError(null); } }).catch(error => { if (!controller.signal.aborted) setError(error.message); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [topicId, revision]);
  const digest = digests.find(item => item.id === selected) ?? digests[0];
  return <section className="mt-5 rounded-xl border border-line bg-canvas/50 p-5 sm:p-7" aria-label={`${topicName} 的简报`}><div className="mb-5 flex flex-wrap items-center justify-between gap-3"><p className="eyebrow">TOPIC BRIEF / 主题简报</p>{!!digests.length && <><label className="sr-only" htmlFor={`history-${topicId}`}>选择历史简报</label><select id={`history-${topicId}`} className="max-w-full text-xs" value={digest?.id ?? ""} onChange={event => setSelected(Number(event.target.value))}>{digests.map((item, index) => <option key={item.id} value={item.id}>{index === 0 ? "最新" : "历史"} · {formatTime(item.generated_at)} · {item.item_count} 条内容</option>)}</select></>}</div>{error && <p role="alert" className="mb-4">简报读取失败：{error}</p>}{loading ? <p role="status" className="text-sm text-muted">正在读取简报…</p> : digest ? <><DigestArticle digest={digest} topicName={topicName} compact/><a href={`/digests#digest-${digest.id}`} className="text-link mt-5 inline-block">展开阅读 →</a></> : <div className="py-4"><h3 className="text-lg font-medium">这里将汇集值得关注的进展。</h3><p className="page-description">还没有简报。一键更新会在存在新的相关摘要时生成；无相关内容时会明确跳过。</p></div>}</section>;
}
