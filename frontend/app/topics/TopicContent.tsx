"use client";
import { useEffect, useRef, useState } from "react";
import { analyzeItem, analyzeTopic, generateDigest, listItems, scanTopic, updateTopic, type CollectedItem, type UpdateProgress } from "./api";
import ItemList from "./ItemList";
import TopicDigests from "./TopicDigests";
import UpdateStatus from "./UpdateStatus";
export default function TopicContent({ topicId, topicName, onBusyChange, onDataChange }: { topicId: number; topicName: string; onBusyChange: (busy: boolean) => void; onDataChange: () => void }) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<CollectedItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [progress, setProgress] = useState<UpdateProgress | null>(null);
  const [itemErrors, setItemErrors] = useState<Record<number, string>>({});
  const [revision, setRevision] = useState(0);
  const active = useRef<AbortController | null>(null);
  useEffect(() => () => active.current?.abort(), []);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    void listItems(topicId, controller.signal).then(data => { if (!controller.signal.aborted) setItems(data); }).catch(error => { if (!controller.signal.aborted) setError(error.message); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [open, revision, topicId]);
  function refresh() { setLoading(true); setOpen(true); setRevision(value => value + 1); }
  async function run(action: string, id?: number) {
    if (active.current) return;
    const controller = new AbortController();
    active.current = controller; setBusy(action); onBusyChange(true); setError(null); setNotice(null);
    if (action === "update") setProgress(null);
    if (id !== undefined) setItemErrors(previous => ({ ...previous, [id]: "" }));
    try {
      if (action === "update") await updateTopic(topicId, controller.signal, value => { if (!controller.signal.aborted) setProgress(value); });
      else if (action === "scan") { const result = await scanTopic(topicId, controller.signal); if (!controller.signal.aborted) setNotice(`扫描完成：获取 ${result.fetched}，新增 ${result.created}，重复 ${result.duplicates}。`); }
      else if (action === "analyze") { const result = await analyzeTopic(topicId, controller.signal); if (!controller.signal.aborted) { if (result.failed) setError(`部分分析未完成：成功 ${result.processed} 条，失败 ${result.failed} 条。已完成结果已保存，请检查 Ollama 或单独重试。`); else setNotice(`分析完成 ${result.processed} 条，相关 ${result.relevant}，不相关 ${result.irrelevant}。`); } }
      else if (action === "digest") { await generateDigest(topicId, controller.signal); if (!controller.signal.aborted) setNotice("新简报已生成并保存。"); }
      else if (id !== undefined) { const updated = await analyzeItem(id, controller.signal); if (!controller.signal.aborted) setItems(previous => previous.map(item => item.id === id ? updated : item)); }
    } catch (error) {
      if (!controller.signal.aborted) { const message = error instanceof Error ? error.message : "请求未完成，请检查本地服务后重试。"; if (id !== undefined) setItemErrors(previous => ({ ...previous, [id]: message })); else setError(message); }
    } finally {
      active.current = null;
      if (!controller.signal.aborted) { setBusy(null); onBusyChange(false); if (id === undefined) { refresh(); onDataChange(); } }
    }
  }
  const eligible = items.filter(item => item.ai_analyzed_at && item.ai_relevant && item.ai_summary?.trim()).length;
  return <section className="mt-5" aria-label={`${topicName} 的工作空间`}><div className="flex flex-wrap items-center gap-2"><button className="btn btn-primary" disabled={!!busy} onClick={() => void run("update")}>{busy === "update" ? "正在更新…" : "↻ 一键更新"}</button><button className="btn" disabled={loading} onClick={refresh}>{loading ? "加载中…" : open ? "刷新内容" : "查看内容"}</button><details className="relative"><summary className="btn btn-quiet list-none">高级操作 ▾</summary><div className="absolute left-0 z-10 mt-2 flex w-44 flex-col gap-1 rounded-xl border border-line bg-surface p-2 shadow-lg"><button className="btn btn-quiet justify-start" disabled={!!busy} onClick={() => void run("scan")}>{busy === "scan" ? "正在采集…" : "仅扫描"}</button><button className="btn btn-quiet justify-start" disabled={!!busy} onClick={() => void run("analyze")}>{busy === "analyze" ? "正在分析…" : "仅分析未处理内容"}</button><button className="btn btn-quiet justify-start" disabled={!!busy} onClick={() => void run("digest")}>{busy === "digest" ? "正在生成…" : "仅生成简报"}</button></div></details><span className="ml-auto text-xs text-muted">采集 → 分析 → 简报</span></div>
    <UpdateStatus progress={progress} updating={busy === "update"}/><div aria-live="polite" className="my-4 space-y-3">{error && <p role="alert">{error}</p>}{notice && <p className="notice">{notice}</p>}{busy && busy !== "update" && !busy.startsWith("item-") && <p role="status" className="text-sm text-muted">{busy === "scan" ? "正在采集和去重…" : busy === "analyze" ? "正在逐条分析，可能需要几分钟…" : "正在生成中文简报…"}</p>}</div>
    <TopicDigests topicId={topicId} topicName={topicName} revision={revision} disabled={!!busy} onDeleted={onDataChange}/>
    {open && <section className="mt-7 border-t border-line pt-6" aria-label="采集内容"><div className="mb-4 flex flex-wrap items-center justify-between gap-2"><h3 className="section-title">内容线索 <span className="ml-2 text-sm font-normal text-muted">{items.length} 条</span></h3><span className="text-xs text-muted">保留原始内容，AI 判断仅供参考</span></div>{loading ? <p role="status" className="text-sm text-muted">正在加载内容…</p> : <><p className="mb-4 text-xs leading-6 text-muted">{!items.length ? "暂无内容，点击一键更新或仅扫描开始采集。" : !items.some(item => item.ai_analyzed_at) ? "这些内容尚未分析，执行一键更新或仅分析以判断相关性。" : !eligible ? "暂无可生成简报的相关摘要。不相关内容仍保留，可查看原文并重新分析。" : `${eligible} 条相关摘要可用于生成简报。`}</p><ItemList items={items} analyzing={busy?.startsWith("item-") ? { [Number(busy.slice(5))]: true } : {}} errors={itemErrors} batchAnalyzing={!!busy} onAnalyze={id => void run(`item-${id}`, id)} onDeleted={id => { setItems(previous => previous.filter(item => item.id !== id)); setNotice("内容已移入回收站，可前往回收站恢复。"); onDataChange(); }}/></>}</section>}
  </section>;
}
