"use client";
import { useEffect, useState } from "react";
import { getItemNormalization, normalizeItem, type ItemNormalization as Normalization } from "./api";
import { formatTime } from "../DigestArticle";

const claimStatus = { reported: "来源声称（未核验）", unconfirmed: "尚未确认", conflicting: "存在冲突", unknown: "无法确定" };
export default function ItemNormalization({ itemId, disabled }: { itemId: number; disabled: boolean }) {
  const [result, setResult] = useState<Normalization | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    getItemNormalization(itemId, controller.signal).then(value => {
      if (!controller.signal.aborted) setResult(value);
    }).catch(reason => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "简讯读取失败，请重试。");
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [itemId]);
  async function generate(force = false) {
    setBusy(true); setError("");
    try { setResult(await normalizeItem(itemId, force)); }
    catch (reason) {
      setError(reason instanceof Error ? reason.message : "简讯生成失败，请重试。");
      try { setResult(await getItemNormalization(itemId)); } catch { /* keep the last visible result */ }
    } finally { setBusy(false); }
  }
  const completed = result?.normalization_status === "completed";
  return <section className="border-t border-line bg-canvas/40 p-5" aria-label={`内容 ${itemId} 的规范化简讯`}>
    <div className="flex flex-wrap items-center justify-between gap-3"><h5 className="font-semibold">AI 规范化简讯</h5>
      <span className="badge">{busy ? "处理中" : loading ? "加载中" : completed ? "已完成" : result?.normalization_status === "failed" ? "失败 · 可重试" : result?.normalization_status === "processing" ? "处理中或上次任务中断" : "待处理"}</span>
    </div>
    <p className="mt-2 text-xs text-muted">单条来源整理，与上方 Topic 相关性分析独立；AI 生成，不代表事实已核实。</p>
    {(error || result?.error) && <p className="notice mt-3" role="alert">{error || result?.error}</p>}
    {completed && <div className="mt-4 space-y-3 break-words">
      <h6 className="text-base font-semibold">{result.headline}</h6>
      <p className="whitespace-pre-wrap text-sm leading-7">{result.summary}</p>
      <div className="space-y-2 text-xs text-muted"><div>人物与机构：{result.entities?.join("、") || "未提取到"}</div><div>关键词：{result.keywords?.join("、") || "未提取到"}</div><div>事件类型：{result.event_type || "未知"} · 事件时间：{result.event_date || "未确定（不是平台发布时间）"}</div></div>
      {!!result.claims?.length && <div><p className="mb-2 text-xs font-medium">事实与来源声称</p><ul className="space-y-2 text-sm">{result.claims.map((claim,index) => <li key={index}><span className="badge mr-2">{claimStatus[claim.status]}</span>{claim.text}</li>)}</ul></div>}
      {!!result.warnings.length && <div className="notice"><p className="font-medium">注意事项</p><ul className="mt-2 list-disc space-y-1 pl-4 text-xs">{result.warnings.map((warning,index) => <li key={index}>{warning}</li>)}</ul></div>}
      <p className="text-xs text-muted">内容覆盖：{result.content_coverage === "metadata_only" ? "YouTube metadata，未读取视频或字幕" : "已有标题与 snippet，完整性未知"}</p>
      {/^https?:\/\//i.test(result.source_reference.url) && <a className="text-link text-xs" href={result.source_reference.url} target="_blank" rel="noopener noreferrer">原始来源 · Item #{result.source_reference.item_id}（新标签页）↗</a>}
      <p className="text-xs text-muted">生成于 {formatTime(result.normalized_at)} · {result.model_name} · schema {result.schema_version} / 修订 {result.revision}</p>
    </div>}
    {!loading && !completed && !busy && <p className="mt-3 text-sm text-muted">{result?.normalization_status === "failed" ? "本次未保存简讯正文，原始信息仍保留。" : "生成一条独立中文简讯，提取人物、机构、关键词及来源声称。"}</p>}
    <div className="mt-4 flex flex-wrap gap-2"><button className="btn btn-quiet text-xs" disabled={disabled || loading || busy} onClick={() => void generate()}>{busy ? "正在生成简讯…" : completed ? "读取已有简讯（不调用模型）" : result ? "重试生成简讯" : "生成简讯"}</button>
    {completed && <button className="btn btn-quiet text-xs" disabled={disabled || busy} onClick={() => void generate(true)}>重新生成（保留旧版本）</button>}</div>
  </section>;
}
