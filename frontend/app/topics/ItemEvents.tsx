"use client";
import Link from "next/link";
import {useEffect,useState} from "react";
import {getEventProcessing,resolveItem,type EventProcessing} from "./api";
const relationNames={new_event:"新事件",duplicate_report:"重复报道",event_update:"事件更新",uncertain:"待复核"};
const matchNames={matched:"与主题匹配",unmatched:"不匹配当前主题",uncertain:"主题匹配待复核"};
export default function ItemEvents({itemId,topicId,disabled,onProcessed}:{itemId:number;topicId:number;disabled:boolean;onProcessed:()=>void}) {
  const [result,setResult]=useState<EventProcessing|null>(null);
  const [busy,setBusy]=useState(false);const [loading,setLoading]=useState(true);const [error,setError]=useState("");
  useEffect(()=>{const controller=new AbortController();getEventProcessing(itemId,controller.signal).then(value=>{if(!controller.signal.aborted)setResult(value);}).catch(reason=>{if(!controller.signal.aborted)setError(reason instanceof Error?reason.message:"事件状态读取失败。");}).finally(()=>{if(!controller.signal.aborted)setLoading(false);});return()=>controller.abort();},[itemId]);
  async function run(){setBusy(true);setError("");try{setResult(await resolveItem(itemId,topicId,true));onProcessed();}catch(reason){setError(reason instanceof Error?reason.message:"事件处理未完成。");try{setResult(await getEventProcessing(itemId));}catch{}}finally{setBusy(false);}}
  const match=result?.matches.find(row=>row.topic_id===topicId);const decision=result?.decision;
  return <section className="mt-4 border-t border-line pt-4" aria-label={`内容 ${itemId} 的事件处理`}><div className="flex flex-wrap items-center justify-between gap-3"><h6 className="text-sm font-semibold">事件识别与去重</h6><button className="btn btn-quiet text-xs" disabled={disabled||busy||loading} onClick={()=>void run()}>{busy?"正在匹配与识别…":result?"检查 / 重试事件识别":"识别事件（含生成简讯）"}</button></div>
    <p className="mt-2 text-xs text-muted">只匹配当前 Topic；事件不是已核实事实。重复报道增加来源，不重复提醒。</p>
    {error&&<p role="alert" className="notice mt-3">{error}</p>}
    {loading?<p className="mt-3 text-xs text-muted">加载中…</p>:!result?<p className="mt-3 text-xs text-muted">尚未处理，可逐条补充历史内容。</p>:<div className="mt-3 space-y-2 text-sm">
      {match?<><p><span className="badge">{matchNames[match.match_status]}</span> 符合度估计 {Math.round(match.relevance_score*100)}% · {match.ai_used?"AI 语义核验":"确定性规则"}</p><p>{match.match_reason}</p>{match.exclusion_reason&&<p>排除判断：{match.exclusion_reason}</p>}</>:<p>当前规则尚未匹配；历史匹配不会无条件继续生效。</p>}
      {decision&&<><p><span className="badge">{relationNames[decision.relation]}</span> {decision.ai_used?"AI 辅助比较":"确定性判断"}</p><p>{decision.reason}</p>{decision.candidate_ids.length>0&&<p className="text-xs text-muted">比较候选：{decision.candidate_ids.map(id=>`#${id}`).join("、")}</p>}{decision.event_id&&<Link className="text-link" href={`/events#event-${decision.event_id}`}>查看事件 #{decision.event_id} 的来源与历史 →</Link>}</>}
    </div>}
  </section>;
}
