"use client";
import Link from "next/link";
import {useState} from "react";
import {markBriefRead,type BriefCardData} from "./topics/api";
import {formatTime} from "./DigestArticle";
export default function BriefCard({brief,compact=false,allowMarkRead=true}:{brief:BriefCardData;compact?:boolean;allowMarkRead?:boolean}){
 const [read,setRead]=useState(!!brief.is_read);const [error,setError]=useState("");const [busy,setBusy]=useState(false);
 const sources=brief.current_sources?.length?brief.current_sources:brief.sources;
 async function mark(){setBusy(true);setError("");try{await markBriefRead(brief.id);setRead(true);}catch(reason){setError(reason instanceof Error?reason.message:"已读状态保存失败。");}finally{setBusy(false);}}
 return <article className="panel min-w-0 border-t-2 border-t-accent/40" aria-label={`事件简讯：${brief.title}`}>
  <div className="mb-3 flex flex-wrap items-center gap-2"><span className="badge">{brief.generation_status==="completed"?"AI 事件简讯":"程序资料摘要"}</span><span className="badge">{brief.verification_status==="conflicting"?"存在冲突 · 未核验":"来源声称 · 未独立核验"}</span>{brief.has_update&&<span className="badge badge-active">事件有进展</span>}{read&&<span className="text-xs text-muted">已读此版本</span>}</div>
  <h2 className="break-words text-xl font-semibold leading-8"><Link className="hover:text-accent" href={`/events#event-${brief.event_id}`}>{brief.title}</Link></h2>
  <p className="mt-2 text-xs text-muted">{formatTime(brief.updated_at)} · {brief.event_type} · {sources.length} 个原始链接 · 版本 {brief.version}</p>
  <p className={`mt-4 whitespace-pre-wrap break-words text-sm leading-8 ${compact?"line-clamp-4":""}`}>{brief.summary}</p>
  {brief.error&&<p className="notice mt-3 text-xs">{brief.error}</p>}
  {!!brief.topics?.length&&<details className="mt-4 text-xs"><summary className="text-muted">匹配的关注主题与理由</summary><ul className="mt-2 space-y-2">{brief.topics.map(topic=><li key={topic.topic_id}><Link className="text-link" href={`/topics#topic-${topic.topic_id}`}>{topic.name}</Link> · 符合度估计 {Math.round(topic.score*100)}%<p className="mt-1 text-muted">{topic.reason}</p></li>)}</ul></details>}
  {brief.popularity_score!==undefined&&<p className="mt-3 text-xs text-muted">YouTube 热度：{brief.popularity_score===null?"未知":`${Math.round(brief.popularity_score*100)}%`}（可用来源最高值，非 AI 符合度）</p>}
  {!compact&&<details className="mt-4 text-sm"><summary>原始来源与资料范围</summary><ul className="mt-3 space-y-2">{sources.map((source,index)=><li key={`${source.item_id}-${index}`} className="break-words text-xs leading-6">{source.source} · {source.author||"作者未知"} · Item #{source.item_id}<br/>{/^https?:\/\//i.test(source.url)&&<a className="text-link" href={source.url} target="_blank" rel="noopener noreferrer">{source.headline||"查看原文"}（新标签页）↗</a>}</li>)}</ul><ul className="mt-3 space-y-1 text-xs text-muted">{brief.warnings.map((warning,index)=><li key={index}>{warning}</li>)}</ul></details>}
  <p className="mt-3 text-[11px] text-muted">{brief.generation_status==="completed"?`AI 模型：${brief.model_name||"未记录"}`:"程序资料摘要，AI 生成未完成"}</p>
  <footer className="mt-5 flex flex-wrap items-center gap-3 border-t border-line pt-4"><Link className="text-link text-xs" href={`/events#event-${brief.event_id}`}>事件时间线与历史 →</Link>{allowMarkRead&&<button className="btn btn-quiet ml-auto text-xs" disabled={read||busy} onClick={()=>void mark()}>{busy?"正在保存…":read?"已读":"标记已读"}</button>}</footer>
  {error&&<p role="alert" className="mt-2 text-xs">{error}</p>}
 </article>;
}
