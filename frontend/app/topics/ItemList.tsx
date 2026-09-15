import type { CollectedItem } from "./api";

type Props = {
  items: CollectedItem[];
  analyzing: Record<number, boolean>;
  errors: Record<number, string>;
  batchAnalyzing: boolean;
  onAnalyze: (id: number) => void;
};

export default function ItemList({ items, analyzing, errors, batchAnalyzing, onAnalyze }: Props) {
  if (!items.length) return <p className="text-sm text-slate-500">No collected items yet.</p>;
  return (
    <ul className="space-y-4">
      {items.map((item) => {
        const safeUrl = /^https?:\/\//i.test(item.url);
        return (
          <li key={item.id} className="min-w-0 rounded-lg border border-slate-200 p-4">
            <h4 className="break-words font-semibold">
              {safeUrl ? <a href={item.url} target="_blank" rel="noopener noreferrer" className="text-blue-700 underline">{item.title}</a> : item.title}
            </h4>
            <p className="mt-2 text-sm text-slate-600">Source: {item.source} · Author: {item.author || "Unknown"}</p>
            <p className="mt-1 text-sm text-slate-500">Published: {item.published_at ? <time dateTime={item.published_at}>{item.published_at}</time> : "Unknown"}</p>
            <p className="my-3 whitespace-pre-wrap break-words text-sm text-slate-600">{item.snippet || "No description available."}</p>
            {safeUrl && <a href={item.url} target="_blank" rel="noopener noreferrer" className="break-all text-sm text-blue-700 underline">{item.url}</a>}
            <section aria-label={`AI Analysis for Item ${item.id}`} className="mt-4 border-t border-slate-200 pt-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h5 className="font-semibold">AI Analysis</h5>
                <button onClick={() => onAnalyze(item.id)} disabled={analyzing[item.id] || batchAnalyzing}
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:opacity-50">
                  {analyzing[item.id] ? "Analyzing..." : "Analyze"}
                </button>
              </div>
              <div aria-live="polite" className="mt-2 space-y-2 text-sm">
                {errors[item.id] && <p role="alert" className="text-red-700">Analysis failed: {errors[item.id]}</p>}
                {item.ai_analyzed_at ? <>
                  <p className="font-medium">{item.ai_relevant ? "Relevant" : "Irrelevant"}</p>
                  <p>Score: {item.ai_relevance_score ?? "Unknown"} · Category: {item.ai_category || "Unknown"}</p>
                  <p className="font-medium">AI Summary (AI-generated)</p>
                  <p className="whitespace-pre-wrap break-words text-slate-600">{item.ai_summary}</p>
                  <p className="text-slate-500">Analyzed: <time dateTime={item.ai_analyzed_at}>{item.ai_analyzed_at}</time></p>
                </> : <p className="text-slate-500">Not analyzed</p>}
              </div>
            </section>
          </li>
        );
      })}
    </ul>
  );
}
