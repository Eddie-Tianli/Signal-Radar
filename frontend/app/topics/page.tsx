"use client";

import Link from "next/link";
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
      setError(error instanceof Error ? error.message : "Could not refresh topics.");
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
      setNotice(editing ? "Topic updated." : "Topic created.");
      await refreshTopics();
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(topic: Topic) {
    if (!window.confirm(`Delete topic "${topic.name}"?`)) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await deleteTopic(topic.id);
      setTopics((current) => current.filter((item) => item.id !== topic.id));
      if (editing?.id === topic.id) setEditing(null);
      setNotice("Topic deleted.");
      await refreshTopics();
    } catch (error) {
      setError(error instanceof Error ? error.message : "Could not delete the topic.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 px-6 py-10 text-slate-900">
      <div className="mx-auto max-w-5xl">
        <Link href="/" className="text-sm text-slate-600 underline">SignalRadar home</Link>
        <h1 className="mt-4 text-3xl font-bold">Topic Management</h1>
        <p className="mt-2 text-slate-600">Create and manage the topics you want to follow.</p>
        <div aria-live="polite" className="my-5 space-y-2">
          {notice && <p className="text-emerald-700">{notice}</p>}
          {error && <p role="alert" className="text-red-700">{error}</p>}
        </div>
        <div className="grid items-start gap-8 md:grid-cols-2">
          <TopicForm key={editing?.id ?? "create"} topic={editing} busy={busy || loading}
            onSave={handleSave} onCancel={() => setEditing(null)} />
          <section aria-label="Topic list" aria-busy={loading}>
            <div className="mb-5 flex items-center justify-between">
              <h2 className="text-xl font-semibold">Topics</h2>
              <button disabled={busy || loading} onClick={() => void refreshTopics()}
                className="rounded-lg border border-slate-300 px-3 py-1.5 disabled:opacity-50">Refresh</button>
            </div>
            {loading ? <p role="status" className="text-slate-600">Loading topics...</p> : error && topics.length === 0 ? (
              <p className="text-slate-600">Topic list unavailable. Use Refresh to try again.</p>
            ) : (
              <TopicList topics={topics} busy={busy} onEdit={setEditing} onDelete={(topic) => void handleDelete(topic)} />
            )}
          </section>
        </div>
      </div>
    </main>
  );
}
