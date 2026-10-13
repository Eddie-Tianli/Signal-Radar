import type { Digest } from "./topics/api";
export function formatTime(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString("zh-CN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "暂无记录";
}
export default function DigestArticle({ digest, topicName, compact = false }: { digest: Digest; topicName: string; compact?: boolean }) {
  return <article className="min-w-0" aria-label={`简报：${digest.title}`}>
    <div className="mb-4 flex flex-wrap items-center gap-2"><span className="badge badge-active">AI 生成简报</span><span className="text-xs text-muted">{topicName}</span></div>
    <h2 className={`${compact ? "text-xl" : "text-2xl sm:text-3xl"} font-semibold leading-snug tracking-tight`}>{digest.title}</h2>
    <p className="mb-6 mt-3 text-xs text-muted"><time dateTime={digest.generated_at}>{formatTime(digest.generated_at)}</time><span className="mx-2">·</span>整合 {digest.item_count} 条内容</p>
    <div className={`space-y-4 ${compact ? "line-clamp-6" : ""}`}>{digest.summary.split(/\n\s*\n/).filter(Boolean).map((paragraph, index) => <p key={index} className="reader">{paragraph}</p>)}</div>
    {!compact && <p className="mt-8 border-t border-line pt-4 text-xs leading-6 text-muted">由本地 AI 基于已分析摘要生成，可能存在遗漏或错误。请结合主题中的原始内容核实。</p>}
  </article>;
}
