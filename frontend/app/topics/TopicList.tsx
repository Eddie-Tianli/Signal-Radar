"use client";
import { useState } from "react";
import type { Topic, TopicOverview } from "./api";
import { formatTime } from "../DigestArticle";
import TopicContent from "./TopicContent";
type Props = { topics: Topic[]; stats: TopicOverview[]; busy: boolean; onEdit: (topic: Topic) => void; onDelete: (topic: Topic) => void; onDataChange: () => void };
function TopicCard({ topic, stats, busy, onEdit, onDelete, onDataChange }: Omit<Props, "topics" | "stats"> & { topic: Topic; stats?: TopicOverview }) {
  const [working, setWorking] = useState(false);
  return <li id={`topic-${topic.id}`} className="panel min-w-0 scroll-mt-8 sm:p-7"><header className="flex flex-wrap items-start justify-between gap-4"><div className="min-w-0 flex-1"><div className="mb-2 flex flex-wrap items-center gap-2"><span className={`badge ${topic.enabled ? "badge-active" : ""}`}>{topic.enabled ? "已启用" : "已停用"}</span><span className="text-[11px] text-muted">TOPIC {topic.id}</span></div><h2 className="text-xl font-semibold">{topic.name}</h2><p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-muted">{topic.description || "暂无关注方向，编辑主题可帮助 AI 更准确判断相关性。"}</p>{stats && <p className="mt-3 text-xs text-muted">{stats.item_count} 条内容 · {stats.last_collected_at ? `最近采集 ${formatTime(stats.last_collected_at)}` : "尚未采集"}</p>}</div><div className="flex gap-1"><button className="btn btn-quiet" disabled={busy || working} onClick={() => onEdit(topic)} aria-label={`编辑 ${topic.name}`}>编辑</button><button className="btn btn-quiet text-red-700" disabled={busy || working} onClick={() => onDelete(topic)} aria-label={`删除 ${topic.name}`}>删除</button></div></header><TopicContent topicId={topic.id} topicName={topic.name} onBusyChange={setWorking} onDataChange={onDataChange}/></li>;
}
export default function TopicList({ topics, stats, ...props }: Props) {
  return <ul className="space-y-6">{topics.map(topic => <TopicCard key={topic.id} topic={topic} stats={stats.find(row => row.id === topic.id)} {...props}/>)}</ul>;
}
