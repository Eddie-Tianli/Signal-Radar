"use client";
import { useId, useState, type FormEvent } from "react";
import type { Topic, TopicInput } from "./api";
type Props = { topic: Topic | null; busy: boolean; onSave: (data: TopicInput) => Promise<void>; onCancel: () => void };
export default function TopicForm({ topic, busy, onSave, onCancel }: Props) {
  const fieldId = useId();
  const [name, setName] = useState(topic?.name ?? "");
  const [description, setDescription] = useState(topic?.description ?? "");
  const [enabled, setEnabled] = useState(topic?.enabled ?? true);
  const [error, setError] = useState<string | null>(null);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    if (!name.trim()) { setError("请填写主题名称，不能仅包含空格。"); return; }
    setError(null);
    try { await onSave({ name: name.trim(), description: description.trim() || null, enabled }); }
    catch (error) { setError(error instanceof Error ? error.message : "保存未完成，请重试。"); }
  }
  return <section className="panel mb-6 border-accent/20" aria-label={topic ? "编辑主题" : "创建主题"}><div className="mb-5"><h2 className="section-title">{topic ? "编辑关注主题" : "添加一个关注主题"}</h2><p className="page-description">名称用于第一版搜索，描述帮助 AI 判断相关性。</p></div><form onSubmit={submit}><fieldset disabled={busy} className="grid gap-4 sm:grid-cols-2"><div><label className="field-label" htmlFor={`${fieldId}-name`}>主题名称</label><input id={`${fieldId}-name`} className="w-full" required value={name} placeholder="例如：OpenAI GPT" onChange={event => setName(event.target.value)}/></div><div><label className="field-label" htmlFor={`${fieldId}-description`}>关注方向 <span className="font-normal text-muted">（可选）</span></label><textarea id={`${fieldId}-description`} className="w-full" rows={2} value={description} placeholder="希望追踪哪些变化？" onChange={event => setDescription(event.target.value)}/></div>{topic && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={enabled} onChange={event => setEnabled(event.target.checked)}/>允许 Scheduler 自动更新此主题</label>}<div className="flex items-center gap-2 sm:col-span-2"><button className="btn btn-primary" type="submit">{busy ? "正在保存…" : topic ? "保存修改" : "创建主题"}</button><button className="btn" type="button" onClick={onCancel}>取消</button></div></fieldset>{error && <p role="alert" className="mt-4">{error}</p>}</form></section>;
}
