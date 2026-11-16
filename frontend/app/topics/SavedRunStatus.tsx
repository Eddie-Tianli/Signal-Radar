"use client";
import Link from "next/link";
import {useEffect,useState} from "react";
import {readingStatus,apiErrorMessage,type ReadingStatus} from "./api";
const stages:Record<string,string>={scan:"采集",normalize:"规范化",match:"主题匹配",events:"事件识别",brief:"生成简讯",digest:"整理综合报告",complete:"处理结束"};
export default function SavedRunStatus({topicId,revision,busy,onStage}:{topicId:number;revision:number;busy:boolean;onStage:(stage:string)=>void}){
 const [run,setRun]=useState<ReadingStatus|null>(null);const [error,setError]=useState("");
 useEffect(()=>{const controller=new AbortController();function load(){readingStatus(topicId,controller.signal).then(value=>{if(!controller.signal.aborted){setRun(value);setError("");if(busy&&value?.active)onStage(value.stage);}}).catch(()=>{if(!controller.signal.aborted)setError("保存的运行状态暂不可用，不代表处理成功或没有更新。");});}load();const interval=busy?setInterval(load,3000):null;return()=>{controller.abort();if(interval)clearInterval(interval);};},[topicId,revision,busy,onStage]);
 if(error)return <p role="alert" className="notice mt-4 text-xs">{error}</p>;
 if(!run)return null;
 const state=run.status==="running"?(run.active?"处理中":"运行未确认 / 可能中断"):run.status==="completed"?"已完成":run.status==="partial"?"部分完成":run.status==="interrupted"?"已中断":"失败";
 return <aside className="notice mt-4 text-xs leading-6" aria-label="已保存运行状态"><p>已保存的最近运行 #{run.id} · {state} · {stages[run.stage]||run.stage}</p><p>采集 {String(run.stats.fetched??0)} · 本轮有效 {String(run.stats.valid_items??0)} · 待处理 {String(run.stats.pending_remaining??0)}</p>{run.error&&<p>{apiErrorMessage(run.error)}</p>}{run.report_id&&<Link className="text-link" href={`/digests#digest-${run.report_id}`}>阅读本次报告 →</Link>}</aside>;
}
