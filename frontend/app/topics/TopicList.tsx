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
    return <p className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-slate-600">暂无主题，请创建第一个关注的主题。</p>;
  }
  return (
    <ul className="space-y-4">
      {topics.map((topic) => (
        <li id={`topic-${topic.id}`} key={topic.id} className="min-w-0 scroll-mt-6 rounded-xl border border-slate-200 bg-white p-5 sm:p-6">
          <p className="text-sm text-slate-500">ID: {topic.id}</p>
          <h3 className="mt-1 break-words text-lg font-semibold">{topic.name}</h3>
          <p className="mt-2 whitespace-pre-wrap break-words text-slate-600">{topic.description || "暂无描述"}</p>
          <p className={`mt-3 text-sm font-medium ${topic.enabled ? "text-emerald-700" : "text-slate-500"}`}>
            {topic.enabled ? "已启用" : "已停用"}
          </p>
          <div className="mt-4 flex gap-3">
            <button disabled={busy} onClick={() => onEdit(topic)} aria-label={`编辑 ${topic.name}`}
              className="rounded-lg border border-slate-300 px-3 py-1.5 disabled:opacity-50">编辑</button>
            <button disabled={busy} onClick={() => onDelete(topic)} aria-label={`删除 ${topic.name}`}
              className="rounded-lg border border-red-200 px-3 py-1.5 text-red-700 disabled:opacity-50">删除</button>
          </div>
          <TopicContent topicId={topic.id} topicName={topic.name} />
        </li>
      ))}
    </ul>
  );
}
