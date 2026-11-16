"use client";
import {useEffect,useState} from "react";
import BriefCard from "../BriefCard";
import {briefHistory,generateBrief,type BriefCardData} from "../topics/api";
export default function EventBriefPanel({eventId}:{eventId:number}){
 const [history,setHistory]=useState<BriefCardData[]>([]);const [selected,setSelected]=useState(0);const [loading,setLoading]=useState(true);const [busy,setBusy]=useState(false);const [error,setError]=useState("");
 useEffect(()=>{const controller=new AbortController();briefHistory(eventId,controller.signal).then(rows=>{if(!controller.signal.aborted){setHistory(rows);setSelected(rows[0]?.version_id??0);}}).catch(reason=>{if(!controller.signal.aborted)setError(reason instanceof Error?reason.message:"简讯历史读取失败。");}).finally(()=>{if(!controller.signal.aborted)setLoading(false);});return()=>controller.abort();},[eventId]);
 async function generate(){setBusy(true);setError("");try{const value=await generateBrief(eventId,!!history.length);setHistory(await briefHistory(eventId));setSelected(value.version_id);}catch(reason){setError(reason instanceof Error?reason.message:"简讯生成未完成。");}finally{setBusy(false);}}
 const current=history.find(b=>b.version_id===selected)??history[0];
 return <section><div className="mb-4 flex flex-wrap items-center gap-3"><h3 className="font-semibold">事件 Brief 与版本</h3><button className="btn btn-quiet ml-auto text-xs" disabled={loading||busy} onClick={()=>void generate()}>{busy?"正在生成简讯…":history.length?"重新生成 / 重试 AI":"生成事件简讯"}</button>{!!history.length&&<><label className="text-xs" htmlFor={`brief-version-${eventId}`}>历史版本</label><select id={`brief-version-${eventId}`} value={selected} onChange={e=>setSelected(Number(e.target.value))}>{history.map(row=><option key={row.version_id} value={row.version_id}>版本 {row.version} · {row.generation_status==="completed"?"AI完成":row.generation_status==="processing"?"处理中":"程序降级"}</option>)}</select></>}</div>
 {error&&<p role="alert" className="notice mb-3">{error}</p>}{loading?<p className="text-sm text-muted">正在读取已保存简讯…</p>:current?<BriefCard brief={current} allowMarkRead={current.version_id===history[0]?.version_id}/>:<p className="empty">尚未形成 Brief。可单独生成，不必重新扫描。</p>}
 </section>;
}
