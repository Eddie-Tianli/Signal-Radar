"use client";


import { useEffect, useState } from "react";
import { deleteTopic, listTopics, saveTopic, type Topic, type TopicInput } from "./api";
import TopicForm from "./TopicForm";
import TopicList from "./TopicList";

export default function TopicsPage() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [editing, setEditing] = useState<Topic | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    listTopics(controller.signal)
      .then((data) => { if (!controller.signal.aborted) setTopics(data); })
      .catch((error) => { if (!controller.signal.aborted) setError(error.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);

  async function refreshTopics() {
    setLoading(true);
    setError(null);
    try {
      setTopics(await listTopics());
    } catch (error) {
      setError(error instanceof Error ? error.message : "主题列表刷新失败，请重试。");
    } finally {
      setLoading(false);
    }
  }

  async function handleSave(data: TopicInput) {
    setBusy(true);
    setNotice(null);
    try {
      const saved = await saveTopic(data, editing?.id);
      setTopics((current) => editing
        ? current.map((topic) => topic.id === saved.id ? saved : topic)
        : [...current, saved]);
      setEditing(null);
      setNotice(editing ? "主题已更新。" : "主题已创建。");
      await refreshTopics();
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(topic: Topic) {
    if (!window.confirm(`确定删除主题“${topic.name}”吗？`)) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await deleteTopic(topic.id);
      setTopics((current) => current.filter((item) => item.id !== topic.id));
      if (editing?.id === topic.id) setEditing(null);
      setNotice("主题已删除。");
      await refreshTopics();
    } catch (error) {
      setError(error instanceof Error ? error.message : "主题删除失败，请重试。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main id="main-content" className="px-5 py-8 sm:px-8">
      <div className="mx-auto max-w-7xl">
        <p className="eyebrow">工作区</p>
        <h1 className="mt-4 text-3xl font-bold">主题</h1>
        <p className="mt-2 text-slate-600">创建并管理你关注的主题。</p>
        <div aria-live="polite" className="my-5 space-y-2">
          {notice && <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2 text-emerald-800">{notice}</p>}
          {error && <p role="alert" className="text-red-700">{error}</p>}
        </div>
        <div className="grid items-start gap-6 xl:grid-cols-[300px_minmax(0,1fr)]">
          <TopicForm key={editing?.id ?? "create"} topic={editing} busy={busy || loading}
            onSave={handleSave} onCancel={() => setEditing(null)} />
          <section aria-label="主题列表" aria-busy={loading}>
            <div className="mb-5 flex items-center justify-between">
              <h2 className="text-xl font-semibold">主题</h2>
              <button disabled={busy || loading} onClick={() => void refreshTopics()}
                className="rounded-lg border border-slate-300 px-3 py-1.5 disabled:opacity-50">刷新</button>
            </div>
            {loading ? <p role="status" className="text-slate-600">正在加载主题…</p> : error && topics.length === 0 ? (
              <p className="text-slate-600">主题列表暂不可用，请点击刷新重试。</p>
            ) : (
              <TopicList topics={topics} busy={busy} onEdit={setEditing} onDelete={(topic) => void handleDelete(topic)} />
            )}
          </section>
        </div>
      </div>
    </main>
  );
}
