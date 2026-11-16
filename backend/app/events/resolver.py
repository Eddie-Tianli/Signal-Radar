"""Bounded SQL candidate lookup, conservative relation decisions and atomic evidence writes."""
from datetime import datetime, timedelta, timezone
from app.events.identity import compact,concrete_price
from sqlalchemy import select, or_, and_
from app.ai.provider import AIError
from app.events.identity import entity_keys, fact_key, evidence_key, family, product_keys, digest, url_key, structured
from app.events.models import EventRecord, EventEntityRecord, EventSourceRecord, EventUpdateRecord, EventDecisionRecord
from app.events.schemas import EventRelationInput, EventRelationResult

RESOLVER_VERSION="1"
MAX_CANDIDATES=20


def claims_for(row):
    return row.claims or []


class EventResolver:
    def __init__(self,session,provider):self.session,self.provider=session,provider

    def candidates(self,row):
        keys=entity_keys(row.entities)
        if not keys:return []
        # Indexed entity join and date window, LIMIT is applied in SQL, never load all history.
        window=EventRecord.updated_at>=datetime.now(timezone.utc)-timedelta(days=90)
        if row.event_date:
            days=90 if compact(row.event_type) in ("pricing","priceupdate","priceannouncement","售价公布","产品定价") else 7
            window=or_(EventRecord.event_date.between(row.event_date-timedelta(days=days),row.event_date+timedelta(days=days)),
                and_(EventRecord.event_date.is_(None),window))
        query=select(EventRecord).where(EventRecord.id.in_(select(EventEntityRecord.event_id).where(EventEntityRecord.entity_key.in_(keys))),window)
        if family(row.event_type)!="unknown":query=query.where(EventRecord.event_family.in_([family(row.event_type),"unknown"]))
        return list(self.session.scalars(query.order_by(EventRecord.updated_at.desc(),EventRecord.id.desc()).limit(MAX_CANDIDATES+1)))

    def resolve(self,row,retry=False):
        saved=self.session.scalar(select(EventDecisionRecord).where(EventDecisionRecord.normalized_item_id==row.id,
            EventDecisionRecord.resolver_version==RESOLVER_VERSION))
        if saved and saved.processing_status=="completed" and (saved.relation!="uncertain" or not retry):return saved,None
        data=structured(row);facts=claims_for(row);data["claims"]=facts;keys=entity_keys(row.entities)
        candidates=self.candidates(row)
        # Same URL can locate older events outside the date window, but is not itself proof of same event.
        same_url=self.session.scalar(select(EventRecord).join(EventSourceRecord).where(
            EventSourceRecord.url_key==url_key(row.source_reference["url"])).order_by(EventRecord.id).limit(1))
        if same_url and all(c.id!=same_url.id for c in candidates):candidates.insert(0,same_url)
        if saved is None:
            saved=EventDecisionRecord(normalized_item_id=row.id,resolver_version=RESOLVER_VERSION,event_id=None,
                relation="uncertain",candidate_ids=[],reason="待判断",ai_used=False,processing_status="failed",evidence=data,attempts=[])
            self.session.add(saved)
        saved.candidate_ids=[c.id for c in candidates[:MAX_CANDIDATES]]
        saved.ai_used=False
        saved.evidence=data
        decision=None;target=None;novel=[];importance=0;conflict=False
        if not keys or not facts:
            decision=("uncertain","缺少可确定主体或事实，暂不创建事件。")
        elif len(candidates)>MAX_CANDIDATES:
            decision=("uncertain","实体候选超过上限，不能可靠排除重复，请人工复核。")
        else:
            plausible=[]
            incoming_products=product_keys(row.headline+" "+row.summary)
            for event in candidates:
                if not set(keys)&set(entity_keys(event.primary_entities)):continue
                if family(event.event_type)!=family(row.event_type) and "unknown" not in (family(event.event_type),family(row.event_type)):continue
                if event.event_date and row.event_date and abs((event.event_date-row.event_date).days)>(90 if compact(row.event_type) in ("pricing","priceupdate","priceannouncement","售价公布","产品定价") else 7):continue
                old_products=product_keys(event.canonical_title+" "+event.summary)
                if incoming_products and old_products and incoming_products.isdisjoint(old_products):continue
                plausible.append(event)
            exact=[]
            for event in plausible:
                known={evidence_key(c) for c in event.facts}
                if all(evidence_key(c) in known for c in facts):exact.append(event)
            if len(exact)==1:
                target=exact[0];decision=("duplicate_report","主体、事件类型和现有事实一致，没有新增事实；增加来源不等于官方确认。")
            elif len(exact)>1 or len(plausible)>1:
                decision=("uncertain","存在多个可信候选，暂不强行合并。")
            elif not plausible and family(row.event_type) in ("unknown","other","general") and not incoming_products and row.event_date is None:
                decision=("uncertain","仅有宽泛主体或分类，缺少可识别具体事件的时间、产品或行为类型。")
            elif not plausible:
                decision=("new_event","索引候选中未发现主体、行为和时间兼容的事件。")
            else:
                target=plausible[0]
                known={evidence_key(c) for c in target.facts}
                fresh=[index for index,claim in enumerate(facts) if evidence_key(claim) not in known]
                same_product=incoming_products and incoming_products==product_keys(target.canonical_title+" "+target.summary)
                # A narrow deterministic path: same explicit product and a concrete new price claim.
                price_update=same_product and fresh and all(concrete_price(facts[i]["text"]) for i in fresh)
                explicit_conflict=same_product and fresh and all(facts[i]["status"]=="conflicting" for i in fresh)
                if price_update or explicit_conflict:
                    novel=[facts[i] for i in fresh];importance=0.0 if explicit_conflict else .85
                    conflict=any(c["status"]=="conflicting" for c in novel)
                    decision=("event_update","同一产品出现冲突声称，双方说法与来源均保留，不覆盖旧事实。" if explicit_conflict else "同一明确产品出现新的价格声称；保留来源和未核实状态。")
                else:
                    saved.ai_used=True
                    try:
                        result=self.provider.compare_event(EventRelationInput(incoming=data,
                            candidate={"id":target.id,"title":target.canonical_title,"summary":target.summary[:1800],
                                       "entities":target.primary_entities,"event_type":target.event_type,
                                       "event_date":str(target.event_date) if target.event_date else None,"claims":[*target.facts[:5],*target.facts[5:][-15:]]}))
                        result=EventRelationResult.model_validate_json(result.model_dump_json()) if isinstance(result,EventRelationResult) else EventRelationResult.model_validate(result)
                        indices=set(result.new_fact_indices);conflicts=set(result.conflicting_fact_indices)
                        if not indices<=set(fresh) or not conflicts<=indices or (result.relation!="event_update" and indices):raise ValueError("Invalid fact indices")
                        if result.confidence<.85 or result.relation=="uncertain":
                            decision=("uncertain","AI 不能可靠确认关系："+result.reason)
                        elif result.relation=="event_update" and not indices:
                            decision=("uncertain","AI 声称更新但未指出可追溯新增事实。")
                        else:
                            decision=(result.relation,result.reason)
                            novel=[{**facts[i],"status":"conflicting" if i in conflicts else facts[i]["status"]} for i in sorted(indices)]
                            conflict=bool(conflicts) or any(c["status"]=="conflicting" for c in novel)
                            importance=result.importance
                    except Exception as error:
                        saved.processing_status,saved.error="failed","事件关系核验失败，请检查 Ollama 后重试。"
                        saved.reason=saved.error;saved.relation="uncertain"
                        saved.attempts=[*saved.attempts,{"status":"failed","reason":saved.error,"ai_used":True}]
                        self.session.commit()
                        raise AIError(saved.error,error.status_code if isinstance(error,AIError) else 502) from None
        relation,reason=decision
        update=None
        if relation=="new_event":
            identity=digest({"entities":keys,"family":family(row.event_type),"date":row.event_date,
                "facts":sorted(fact_key(c["text"]) for c in facts)})
            existing=self.session.scalar(select(EventRecord).where(EventRecord.identity_fingerprint==identity))
            if existing:
                target=existing;relation="duplicate_report";reason="事件身份指纹已存在，复用稳定 Event ID。"
            else:
                target=EventRecord(identity_fingerprint=identity,canonical_title=row.headline,event_type=row.event_type,
                    event_family=family(row.event_type),event_date=row.event_date,summary=row.summary,
                    primary_entities=row.entities,facts=facts,event_status="developing" if any(c["status"]=="conflicting" for c in facts) else "active",updated_at=datetime.now(timezone.utc))
                self.session.add(target);self.session.flush()
                for key in keys:self.session.add(EventEntityRecord(event_id=target.id,entity_key=key))
                novel=facts;importance=1.0
        if relation in ("new_event","event_update") and target and novel:
            signature=digest(sorted(evidence_key(c) for c in novel))
            update=self.session.scalar(select(EventUpdateRecord).where(EventUpdateRecord.event_id==target.id,EventUpdateRecord.fact_fingerprint==signature))
            if update is None:
                update=EventUpdateRecord(event_id=target.id,normalized_item_id=row.id,
                    update_type="new_event" if relation=="new_event" else "conflict" if conflict else "new_facts",
                    new_facts=novel,source_reference=row.source_reference,importance=importance,fact_fingerprint=signature)
                self.session.add(update)
                if relation=="event_update":
                    target.facts=[*target.facts,*novel]
                    target.summary=target.summary+"\n新增来源声称："+"；".join(c["text"] for c in novel)
                    target.event_status="developing"
                target.updated_at=datetime.now(timezone.utc)
            else:
                relation="duplicate_report";reason="该事实增量已记录，不重复创建 EventUpdate。";update=None
        if target and relation!="uncertain":
            source=self.session.scalar(select(EventSourceRecord).where(EventSourceRecord.normalized_item_id==row.id))
            if source is None:
                self.session.add(EventSourceRecord(event_id=target.id,normalized_item_id=row.id,
                    source_reference={**row.source_reference,"normalization_id":row.id,"schema_version":row.schema_version,"revision":row.revision,"headline":row.headline},
                    url_key=url_key(row.source_reference["url"]),claims=facts))
            saved.event_id=target.id
        else:saved.event_id=None
        saved.relation,saved.reason,saved.processing_status,saved.error=relation,reason,"completed",None
        saved.attempts=[*saved.attempts,{"relation":relation,"reason":reason,"ai_used":saved.ai_used}]
        self.session.commit()
        return saved,update
