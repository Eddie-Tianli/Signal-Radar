"use client";

import { useId, useState, type FormEvent } from "react";
import type { Topic, TopicInput } from "./api";

type Props = {
  topic: Topic | null;
  busy: boolean;
  onSave: (data: TopicInput) => Promise<void>;
  onCancel: () => void;
};

export default function TopicForm({ topic, busy, onSave, onCancel }: Props) {
  const fieldId = useId();
  const [name, setName] = useState(topic?.name ?? "");
  const [description, setDescription] = useState(topic?.description ?? "");
  const [enabled, setEnabled] = useState(topic?.enabled ?? true);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    if (!name.trim()) {
      setError("Name cannot be empty or whitespace only.");
      return;
    }
    setError(null);
    try {
      await onSave({ name: name.trim(), description: description.trim() || null, enabled });
      setName("");
      setDescription("");
    } catch (error) {
      setError(error instanceof Error ? error.message : "Could not save the topic.");
    }
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6">
      <h2 className="mb-5 text-xl font-semibold">{topic ? `Edit Topic #${topic.id}` : "Create Topic"}</h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <fieldset disabled={busy} className="space-y-4 disabled:opacity-60">
          <div>
            <label htmlFor={`${fieldId}-name`} className="mb-1 block font-medium">Name</label>
            <input id={`${fieldId}-name`} required value={name} onChange={(event) => setName(event.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2" />
          </div>
          <div>
            <label htmlFor={`${fieldId}-description`} className="mb-1 block font-medium">Description</label>
            <textarea id={`${fieldId}-description`} rows={3} value={description} onChange={(event) => setDescription(event.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2" />
          </div>
          {topic && (
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} />
              Enabled
            </label>
          )}
          <div className="flex gap-3">
            <button type="submit" className="rounded-lg bg-slate-900 px-4 py-2 text-white hover:bg-slate-700">
              {busy ? "Please wait..." : topic ? "Save changes" : "Create topic"}
            </button>
            {topic && <button type="button" onClick={onCancel} className="rounded-lg border border-slate-300 px-4 py-2">Cancel</button>}
          </div>
        </fieldset>
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      </form>
    </section>
  );
}
