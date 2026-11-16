import Link from "next/link";
import type { Digest } from "./topics/api";
export function formatTime(value: string | null | undefined) {
  if(!value)return "暂无记录";
  const parsed=new Date(/(?:Z|[+-]\d{2}:\d{2})$/i.test(value)?value:`${value}Z`);
  return Number.isNaN(parsed.getTime())?"时间未知":parsed.toLocaleString("zh-CN",{timeZone:"Asia/Shanghai",month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"});
}
export default function DigestArticle({ digest, topicName, compact = false }: { digest: Digest; topicName: string; compact?: boolean }) {
  const kind=digest.result_kind??"legacy";
  const label=kind==="digest"?"AI 综合简报":kind==="brief_collection"?"简讯集合 · 程序整理":kind==="no_updates"?"无更新报告":"历史 AI 简报";
  return <article className="min-w-0" aria-label={`简报：${digest.title}`}>
    <div className="mb-4 flex flex-wrap items-center gap-2"><span className="badge badge-active">{label}</span><span className="text-xs text-muted">{topicName}</span></div>
    <h2 className={`${compact ? "text-xl" : "text-2xl sm:text-3xl"} break-words font-semibold leading-snug tracking-tight`}>{digest.title}</h2>
    <p className="mb-6 mt-3 text-xs text-muted"><time dateTime={digest.generated_at}>{formatTime(digest.generated_at)}</time><span className="mx-2">·</span>{kind==="no_updates"?"无新增事件":digest.briefs?.length?`收录 ${digest.briefs.length} 个事件 · ${digest.item_count} 条来源`:`整合 ${digest.item_count} 条内容`}</p>
    {digest.generation_error&&<p className="notice mb-5">{digest.generation_error}</p>}
    {kind==="no_updates"&&digest.run_stats&&<p className="notice mb-5 text-sm leading-7">{digest.run_stats.scan_performed?`成功采集于 ${formatTime(String(digest.run_stats.scan_time??""))} · 获取 ${digest.run_stats.fetched??0} · 有效 ${digest.run_stats.valid_items??0} · 重复 ${digest.run_stats.duplicates??0} · 本次发现仍待复核 ${digest.run_stats.review??0}`:"本报告未执行采集，仅检查当前尚未收录的事件。"}</p>}
    <div className={`space-y-4 ${compact ? "line-clamp-6" : ""}`}>{(kind==="brief_collection"&&!compact?["以下直接展示已保存的事件简讯，未进行 AI 综合。"]:digest.summary.split(/\n\s*\n/).filter(Boolean)).map((paragraph, index) => ["核心动态","主要事件","值得关注"].includes(paragraph.split("\n")[0])?<section key={index}><h3 className="section-title mb-3">{paragraph.split("\n")[0]}</h3><p className="reader whitespace-pre-wrap">{paragraph.split("\n").slice(1).join("\n")}</p></section>:<p key={index} className="reader whitespace-pre-wrap">{paragraph}</p>)}</div>
    {!compact&&!!digest.briefs?.length&&<section className="mt-6 space-y-4 border-t border-line pt-5"><h3 className="section-title">收录事件简讯</h3>{digest.briefs.map(brief=><article key={brief.event_id} className="rounded-lg border border-line p-4"><Link className="text-link font-medium" href={`/events#event-${brief.event_id}`}>{brief.title} →</Link><p className="mt-2 whitespace-pre-wrap text-sm leading-7">{brief.summary}</p><p className="mt-2 text-xs text-muted">{brief.generation_status==="completed"?"AI 事件简讯":"程序资料摘要"} · {brief.verification_status==="conflicting"?"存在冲突":"未独立核验"} · 版本 {brief.version}</p></article>)}</section>}
    {!compact && <section className="mt-7 border-t border-line pt-5" aria-label="简报信息来源"><h3 className="section-title mb-3">信息来源</h3>{digest.sources?.length ? <ul className="space-y-3">{digest.sources.map(source => <li key={`${source.unit_id}-${source.item_id}`} className="break-words text-xs leading-6"><span className="badge mr-2">{source.unit_id}</span>{/^https?:\/\//i.test(source.url) ? <a className="text-link" href={source.url} target="_blank" rel="noopener noreferrer">{source.title} ↗</a> : source.title}<p className="text-muted">Item #{source.item_id} · {source.source} · {source.author || "作者未知"} · {formatTime(source.published_at)}</p></li>)}</ul> : <p className="text-xs text-muted">{kind==="no_updates"?"本报告未收录新事件，无新增来源清单。":kind==="legacy"?"旧版简报未保存来源快照，请结合主题中的原始内容核实。":"暂无可显示来源，请核对事件资料。"}</p>}</section>}
    {!compact && <p className="mt-8 border-t border-line pt-4 text-xs leading-6 text-muted">{kind==="digest"?"由本地 AI 基于事件 Brief 综合，可能存在遗漏或错误。":kind==="legacy"?"历史生成路径，未必保存事件 Brief 关联。":"程序整理或无更新报告，不是 AI 综合成功结果。"} 请结合原始来源核实。</p>}
  </article>;
}
