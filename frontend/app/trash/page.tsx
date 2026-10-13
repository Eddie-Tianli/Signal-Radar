"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { readTrash, restoreContent, permanentlyDelete, type TrashContents, type ContentKind } from "../topics/api";
import { formatTime } from "../DigestArticle";

export default function TrashPage() {
  const [data, setData] = useState<TrashContents>({ items: [], digests: [] });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const active = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    void readTrash(controller.signal).then(result => { if (!controller.signal.aborted) setData(result); })
      .catch(error => { if (!controller.signal.aborted) setError(error.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [revision]);
  async function act(kind: ContentKind, id: number, permanent: boolean) {
    if (active.current) return;
    if (permanent && !window.confirm("永久删除后无法恢复。确定要删除这条内容吗？")) return;
    active.current = true; setBusy(`${kind}-${id}`); setError(null); setNotice(null);
    try {
      if (permanent) await permanentlyDelete(kind, id); else await restoreContent(kind, id);
      setData(previous => ({ ...previous, [kind]: previous[kind].filter(row => row.id !== id) }));
      setNotice(permanent ? "内容已永久删除，无法恢复。" : "内容已恢复，可返回主题或简报页面查看。");
    } catch (error) { setError(error instanceof Error ? error.message : "操作失败，请重试。"); }
    finally { active.current = false; setBusy(null); }
  }
  return <main id="main-content" className="page"><header className="page-heading"><div><h1 className="page-title">回收站</h1><p className="page-description">误删的采集内容、AI 分析和简报可以恢复。内容不会自动清理，永久删除后无法恢复。</p></div><button className="btn" disabled={loading || !!busy} onClick={() => { setLoading(true); setError(null); setRevision(value => value + 1); }}>刷新回收站</button></header>
    <p className="mb-5 text-sm text-muted">采集内容连同 AI 分析一起恢复。删除内容不会修改已经生成的简报快照；永久删除 Item 后，再次扫描可能重新采集它。删除整个主题会连同回收站内容一起永久删除。</p>
    <div aria-live="polite">{error && <p role="alert" className="mb-4">{error}</p>}{notice && <p className="notice mb-4">{notice}</p>}{loading && <p role="status">正在读取回收站…</p>}</div>
    {([['items', '采集内容与 AI 分析'], ['digests', '情报简报']] as const).map(([kind, label]) => <section key={kind} className="panel mb-6"><h2 className="section-title mb-4">{label} · {data[kind].length}</h2>{!loading && !data[kind].length && <p className="empty">暂无已删除内容。</p>}<ul className="space-y-4">{data[kind].map(row => <li key={row.id} className="rounded-xl border border-line p-4"><h3 className="font-semibold">{row.title}</h3><p className="my-2 text-xs text-muted">主题 #{row.topic_id} · 移入于 {formatTime(row.deleted_at)}</p><details className="mb-3"><summary className="text-sm text-muted">查看保留内容</summary><p className="mt-2 whitespace-pre-wrap text-sm leading-7">{'summary' in row ? row.summary : row.snippet || '无原始摘要'}</p>{'ai_summary' in row && row.ai_summary && <><p className="mt-3 text-xs font-medium text-accent">AI 生成摘要</p><p className="whitespace-pre-wrap text-sm leading-7">{row.ai_summary}</p></>}</details><div className="flex flex-wrap gap-2"><button className="btn" disabled={!!busy} onClick={() => void act(kind, row.id, false)}>{busy === `${kind}-${row.id}` ? '处理中…' : '恢复'}</button><button className="btn btn-quiet text-red-700" disabled={!!busy} onClick={() => void act(kind, row.id, true)}>永久删除</button><Link href={kind === 'items' ? `/topics#topic-${row.topic_id}` : '/digests'} className="btn btn-quiet">返回{kind === 'items' ? '主题' : '简报'}</Link></div></li>)}</ul></section>)}
  </main>;
}
