import type { CollectedItem } from "./api";

export default function ItemList({ items }: { items: CollectedItem[] }) {
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
          </li>
        );
      })}
    </ul>
  );
}
