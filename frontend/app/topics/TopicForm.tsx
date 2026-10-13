"use client";
import { useId, useState, type FormEvent } from "react";
import RuleEditor from "./RuleEditor";
import type { TopicRuleInput, Topic, TopicInput } from "./api";
type Props = { topic: Topic | null; busy: boolean; onSave: (data: TopicInput) => Promise<void>; onCancel: () => void };
export default function TopicForm({ topic, busy, onSave, onCancel }: Props) {
  const fieldId = useId();
  const [name, setName] = useState(topic?.name ?? "");
  const [description, setDescription] = useState(topic?.description ?? "");
  const [enabled, setEnabled] = useState(topic?.enabled ?? true);
  const [threshold, setThreshold] = useState(String(topic?.relevance_threshold ?? .8));
  const [includeRules, setIncludeRules] = useState<TopicRuleInput[]>(topic?.include_rules.map(({ id, text, enabled }) => ({ id, text, enabled })) ?? []);
  const [excludeRules, setExcludeRules] = useState<TopicRuleInput[]>(topic?.exclude_rules.map(({ id, text, enabled }) => ({ id, text, enabled })) ?? []);
  const [error, setError] = useState<string | null>(null);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    if (!name.trim()) { setError("请填写主题名称，不能仅包含空格。"); return; }
    if ([...includeRules, ...excludeRules].some(rule => !rule.text.trim())) { setError("请填写条件内容，或删除空条件。"); return; }
    if (!threshold.trim() || !Number.isFinite(Number(threshold)) || Number(threshold) < 0 || Number(threshold) > 1) { setError("符合度阈值必须在 0～1 之间。"); return; }
    setError(null);
    try { await onSave({ name: name.trim(), description: description.trim() || null, enabled, relevance_threshold: Number(threshold), include_rules: includeRules.map(rule => ({ ...rule, text: rule.text.trim() })), exclude_rules: excludeRules.map(rule => ({ ...rule, text: rule.text.trim() })) }); }
    catch (error) { setError(error instanceof Error ? error.message : "保存未完成，请重试。"); }
  }
  return <section className="panel mb-6 border-accent/20" aria-label={topic ? "编辑主题" : "创建主题"}><div className="mb-5"><h2 className="section-title">{topic ? "编辑关注主题" : "添加一个关注主题"}</h2><p className="page-description">用自然语言描述关注意图。名称辅助检索，描述是判断的主要依据；保存后规则生效，旧分析需重新确认。</p></div><form onSubmit={submit}><fieldset disabled={busy} className="grid gap-4 sm:grid-cols-2"><div><label className="field-label" htmlFor={`${fieldId}-name`}>主题名称</label><input id={`${fieldId}-name`} className="w-full" required maxLength={200} value={name} placeholder="例如：OpenAI GPT" onChange={event => setName(event.target.value)}/></div><div><label className="field-label" htmlFor={`${fieldId}-description`}>自然语言需求 <span className="font-normal text-muted">（可选）</span></label><textarea id={`${fieldId}-description`} className="w-full" rows={4} maxLength={2000} value={description} placeholder="希望追踪哪些变化？" onChange={event => setDescription(event.target.value)}/></div><RuleEditor label="包含条件" id={`${fieldId}-include`} rules={includeRules} onChange={setIncludeRules}/><RuleEditor label="排除条件" id={`${fieldId}-exclude`} rules={excludeRules} onChange={setExcludeRules}/><div><label className="field-label" htmlFor={`${fieldId}-threshold`}>符合度阈值（0～1）</label><input id={`${fieldId}-threshold`} type="number" min="0" max="1" step="0.01" required value={threshold} onChange={event => setThreshold(event.target.value)}/><p className="mt-2 text-xs leading-6 text-muted">默认 0.80。达到阈值且未命中排除条件才有效；无法确定的内容待复核。仅提及排除词不会自动排除。</p></div><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={enabled} onChange={event => setEnabled(event.target.checked)}/>允许 Scheduler 自动更新此主题</label><div className="flex items-center gap-2 sm:col-span-2"><button className="btn btn-primary" type="submit">{busy ? "正在保存…" : topic ? "保存修改" : "创建主题"}</button><button className="btn" type="button" onClick={onCancel}>取消</button></div></fieldset>{error && <p role="alert" className="mt-4">{error}</p>}</form></section>;
}
