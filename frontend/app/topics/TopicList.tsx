import type { Topic } from "./api";
import TopicContent from "./TopicContent";

type Props = {
  topics: Topic[];
  busy: boolean;
  onEdit: (topic: Topic) => void;
  onDelete: (topic: Topic) => void;
};

export default function TopicList({ topics, busy, onEdit, onDelete }: Props) {
  if (topics.length === 0) {
    return <p className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-slate-600">No topics yet. Create your first topic.</p>;
  }
  return (
    <ul className="space-y-4">
      {topics.map((topic) => (
        <li key={topic.id} className="rounded-xl border border-slate-200 bg-white p-5">
          <p className="text-sm text-slate-500">ID: {topic.id}</p>
          <h3 className="mt-1 break-words text-lg font-semibold">{topic.name}</h3>
          <p className="mt-2 whitespace-pre-wrap break-words text-slate-600">{topic.description || "No description"}</p>
          <p className={`mt-3 text-sm font-medium ${topic.enabled ? "text-emerald-700" : "text-slate-500"}`}>
            Enabled: {String(topic.enabled)}
          </p>
          <div className="mt-4 flex gap-3">
            <button disabled={busy} onClick={() => onEdit(topic)} aria-label={`Edit ${topic.name}`}
              className="rounded-lg border border-slate-300 px-3 py-1.5 disabled:opacity-50">Edit</button>
            <button disabled={busy} onClick={() => onDelete(topic)} aria-label={`Delete ${topic.name}`}
              className="rounded-lg border border-red-200 px-3 py-1.5 text-red-700 disabled:opacity-50">Delete</button>
          </div>
          <TopicContent topicId={topic.id} />
        </li>
      ))}
    </ul>
  );
}
