"use client";
import Link from "next/link";
import {useEffect,useState} from "react";
import BriefCard from "./BriefCard";
import {readFeed,listTopics,type BriefCardData,type Topic} from "./topics/api";
export default function ReadingFeed({mode}:{mode:"focus"|"discover"}){
 const [cards,setCards]=useState<BriefCardData[]>([]);const [topics,setTopics]=useState<Topic[]>([]);const [topic,setTopic]=useState(0);const [sort,setSort]=useState("latest");const [revision,setRevision]=useState(0);const [loading,setLoading]=useState(true);const [error,setError]=useState("");const [scope,setScope]=useState("");
 useEffect(()=>{const controller=new AbortController();Promise.all([readFeed(mode,topic||undefined,sort,controller.signal),listTopics(controller.signal)]).then(([feed,rows])=>{if(!controller.signal.aborted){setCards(feed.cards);setScope(feed.scope);setTopics(rows);}}).catch(reason=>{if(!controller.signal.aborted)setError(reason instanceof Error?reason.message:"信息流读取失败。");}).finally(()=>{if(!controller.signal.aborted)setLoading(false);});return()=>controller.abort();},[mode,topic,sort,revision]);
 return <main id="main-content" className="page"><header className="page-heading"><div><p className="eyebrow mb-2">{mode==="focus"?"FOLLOW WITH INTENT":"EXPLORE YOUR LIBRARY"}</p><h1 className="page-title">{mode==="focus"?"精准关注":"开放发现"}</h1><p className="page-description">{mode==="focus"?"严格遵守当前 Topic 规则，只读已通过匹配的事件。":"在已采集的事件库中换个视角，兼顾新鲜度、主题与来源多样性，不改变你的关注规则。"}</p></div><div className="flex gap-2"><button className="btn" disabled={loading} onClick={()=>{setLoading(true);setError("");setRevision(v=>v+1);}}>刷新</button><Link href="/topics" className="btn btn-primary">管理主题 / 一键更新</Link></div></header>
 <p className="notice mb-5 text-xs leading-6">{scope||"数据仅来自本机已采集事件库，不是全网新闻覆盖。"}</p>
 {mode==="focus"&&<div className="mb-6 flex flex-wrap items-center gap-3"><label htmlFor="feed-topic" className="text-sm">关注主题</label><select id="feed-topic" value={topic} onChange={e=>{setLoading(true);setError("");setTopic(Number(e.target.value));}}><option value={0}>全部已启用主题</option>{topics.filter(t=>t.enabled).map(t=><option key={t.id} value={t.id}>{t.name}</option>)}</select><label htmlFor="feed-sort" className="text-sm">排序</label><select id="feed-sort" value={sort} onChange={e=>{setLoading(true);setSort(e.target.value);}}><option value="latest">最新</option><option value="relevance">符合度</option><option value="popularity">YouTube 热度（未知排后）</option><option value="updated">事件有进展优先</option></select></div>}
 {error&&<p role="alert" className="mb-5">{error} 已加载内容仍可阅读。</p>}{loading&&<p role="status" className="mb-4 text-sm text-muted">正在读取已保存的简讯…</p>}
 {!loading&&!cards.length?<section className="empty"><h2 className="mb-2 font-semibold">{error?"暂时无法取得数据":"暂无可阅读的事件简讯"}</h2><p>{error?"请检查后端和数据库，不代表没有新闻。":"先更新一个主题，或到事件库为已有事件生成简讯。待复核内容不会混入精准关注。"}</p><Link className="btn mt-4" href="/events">查看事件库</Link></section>:<div className="grid items-start gap-5 xl:grid-cols-2">{cards.map(card=><BriefCard key={`${card.id}-${card.version}`} brief={card}/>)}</div>}
 {mode==="discover"&&<p className="mt-6 text-xs leading-6 text-muted">最多每个主要来源频道展示两条，使用日内稳定探索和已读降权；来源多样性不等于观点对立，也不是可信度认证。</p>}
 </main>;
}
