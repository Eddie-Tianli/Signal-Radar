import type { CollectedItem } from "./api";

type Props = {
  items: CollectedItem[];
  analyzing: Record<number, boolean>;
  errors: Record<number, string>;
  batchAnalyzing: boolean;
  onAnalyze: (id: number) => void;
};

export default function ItemList({ items, analyzing, errors, batchAnalyzing, onAnalyze }: Props) {
  if (!items.length) return <p className="text-sm text-slate-500">暂无已采集内容。</p>;
  return (
    <ul className="space-y-4">
      {items.map((item) => {
        const safeUrl = /^https?:\/\//i.test(item.url);
        return (
          <li key={item.id} className={`min-w-0 rounded-lg border border-slate-200 p-4 ${item.ai_analyzed_at && item.ai_relevant === false ? "bg-slate-50" : "bg-white"}`}>
            <p className="eyebrow mb-2">原始内容 · {item.source}</p>
            <h4 className="break-words font-semibold">
              {safeUrl ? <a href={item.url} target="_blank" rel="noopener noreferrer" className="text-blue-700 underline">{item.title}</a> : item.title}
            </h4>
            <p className="mt-2 text-sm text-slate-600">来源：{item.source} · 作者：{item.author || "未知"}</p>
            <p className="mt-1 text-sm text-slate-500">发布时间：{item.published_at ? <time dateTime={item.published_at}>{new Date(item.published_at).toLocaleString()}</time> : "未知"}</p>
            <p className="my-3 whitespace-pre-wrap break-words text-sm text-slate-600">{item.snippet || "暂无内容描述。"}</p>
            {safeUrl && <a href={item.url} target="_blank" rel="noopener noreferrer" className="break-all text-sm text-blue-700 underline">查看原文（新标签页）↗</a>}
            <section aria-label={`内容 AI 分析：${item.id}`} className="mt-4 rounded-lg border border-blue-100 bg-blue-50/50 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h5 className="font-semibold">AI 分析</h5>
                <button onClick={() => onAnalyze(item.id)} disabled={analyzing[item.id] || batchAnalyzing}
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:opacity-50">
                  {analyzing[item.id] ? "正在分析…" : "分析"}
                </button>
              </div>
              <div aria-live="polite" className="mt-2 space-y-2 text-sm">
                {errors[item.id] && <p role="alert" className="text-red-700">分析失败：{errors[item.id]}</p>}
                {item.ai_analyzed_at ? <>
                  <p className="badge">{item.ai_relevant ? "相关" : "不相关"}</p>
                  <p>相关性评分：{item.ai_relevance_score ?? "未知"} · 分类：{item.ai_category || "未知"}</p>
                  <p className="font-medium">AI 摘要（由 AI 生成）</p>
                  <p className="whitespace-pre-wrap break-words text-slate-600">{item.ai_summary}</p>
                  <p className="text-slate-500">分析时间：<time dateTime={item.ai_analyzed_at}>{new Date(item.ai_analyzed_at).toLocaleString()}</time></p>
                </> : <p className="text-slate-500">未分析</p>}
              </div>
            </section>
          </li>
        );
      })}
    </ul>
  );
}
