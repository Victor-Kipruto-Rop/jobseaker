"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowRight, ArrowUpRight, BriefcaseBusiness, Check, CheckCircle2, FilePlus2, Filter, MessageSquareText, Plus, Search, ShieldCheck, X } from "lucide-react";
import AppShell from "../../components/layout/app-shell";
import styles from "./applications.module.css";

const API=process.env.NEXT_PUBLIC_API_BASE_URL||"http://localhost:8000";
type Application={id:number;role_title:string;company_name?:string;company_logo_url?:string;company_favicon_url?:string;company_website?:string;company_domain?:string;company_description?:string;company_brand_color?:string;status:string;job_url?:string;notes?:string;created_at?:string;applied_at?:string|null};
type Approval={id:number;action_type:string;payload:Record<string,unknown>;rationale:string;status:string;created_at:string;decision_note?:string|null;decided_at?:string|null};
const statuses=["draft","ready","approved","submitted","screening","interview","assessment","offer","accepted","rejected","withdrawn","archived"];
const transitions:Record<string,string[]>={draft:["ready","withdrawn","archived"],ready:["draft","withdrawn","archived"],approved:["ready","submitted","withdrawn"],submitted:["screening","interview","assessment","rejected","withdrawn"],screening:["interview","assessment","rejected","withdrawn"],interview:["assessment","offer","rejected","withdrawn"],assessment:["interview","offer","rejected","withdrawn"],offer:["accepted","rejected","withdrawn"],accepted:["archived"],rejected:["archived"],withdrawn:["archived"],archived:[]};
function csrf(){return decodeURIComponent(document.cookie.split("; ").find(x=>x.startsWith("jobseeker_csrf="))?.split("=").slice(1).join("=")||"");}
async function api(path:string,init:RequestInit={}){const h=new Headers(init.headers);if(init.method)h.set("X-CSRF-Token",csrf());const r=await fetch(API+path,{...init,headers:h,credentials:"include",cache:"no-store"});if(r.status===401)window.location.assign("/login");return r;}
function label(value:string){return value.replaceAll("_"," ").replace(/\b\w/g,c=>c.toUpperCase());}
function date(value?:string|null){if(!value)return "—";const d=new Date(value);return Number.isNaN(d.getTime())?"—":d.toLocaleDateString(undefined,{day:"numeric",month:"short",year:"numeric"});}

export default function Applications(){
 const [rows,setRows]=useState<Application[]>([]);
 const [approvals,setApprovals]=useState<Approval[]>([]);
 const [view,setView]=useState<"applications"|"approvals">("applications");
 const [filter,setFilter]=useState("all");
 const [query,setQuery]=useState("");
 const [loading,setLoading]=useState(true);
 const [error,setError]=useState("");
 const [notice,setNotice]=useState("");
 const [creating,setCreating]=useState(false);
 const [role,setRole]=useState("");
 const [company,setCompany]=useState("");
 const [url,setUrl]=useState("");
 const [notes,setNotes]=useState("");
 const [busy,setBusy]=useState<number|null>(null);
 const [editing,setEditing]=useState<number|null>(null);
 const [editNotes,setEditNotes]=useState("");
 const [decisionNote,setDecisionNote]=useState<Record<number,string>>({});

 const load=useCallback(async()=>{
  setLoading(true);setError("");
  try{const [a,b]=await Promise.all([api("/api/v1/applications"),api("/api/v1/automations/approvals")]);if(!a.ok||!b.ok)throw new Error("Unable to load application records and approval requests.");const [ad,bd]=await Promise.all([a.json(),b.json()]);setRows(Array.isArray(ad)?ad:[]);setApprovals(Array.isArray(bd)?bd:[]);}
  catch(e){setError(e instanceof Error?e.message:"Unable to load applications.");}
  finally{setLoading(false);}
 },[]);
 useEffect(()=>{void load();const params=new URLSearchParams(window.location.search);if(params.get("view")==="approvals")setView("approvals");const stage=params.get("stage");if(stage&&statuses.includes(stage))setFilter(stage);},[load]);

 const visible=useMemo(()=>rows.filter(row=>(filter==="all"||row.status===filter)&&(!query.trim()||[row.role_title,row.company_name].join(" ").toLowerCase().includes(query.toLowerCase()))),[rows,filter,query]);
 const pending=approvals.filter(item=>item.status==="pending");
 const active=rows.filter(x=>!["accepted","rejected","withdrawn","archived"].includes(x.status)).length;

 async function create(e:React.FormEvent){
  e.preventDefault();setBusy(-1);setError("");setNotice("");
  try{const r=await api("/api/v1/applications",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({role_title:role,company_name:company,job_url:url,notes})});const d=await r.json();if(!r.ok)throw new Error(d.detail||"Unable to create application.");setRole("");setCompany("");setUrl("");setNotes("");setCreating(false);setNotice("Application draft created.");await load();}
  catch(e){setError(e instanceof Error?e.message:"Unable to create application.");}
  finally{setBusy(null);}
 }
 async function changeStatus(row:Application,status:string){
  setBusy(row.id);setError("");setNotice("");
  try{const r=await api("/api/v1/applications/"+row.id,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({status})});const d=await r.json();if(!r.ok)throw new Error(d.detail||"This status transition is not available.");setNotice("Application stage updated.");await load();}
  catch(e){setError(e instanceof Error?e.message:"Unable to update application.");}
  finally{setBusy(null);}
 }
 async function requestApproval(row:Application){
  setBusy(row.id);setError("");setNotice("");
  try{const r=await api("/api/v1/automations/approvals",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action_type:"application_submission",payload:{application_id:row.id},rationale:"Review this application and explicitly approve whether I may record it as submitted."})});const d=await r.json();if(!r.ok)throw new Error(d.detail||"Unable to request approval.");setNotice("Approval request #"+d.id+" created. It is waiting for your decision.");await load();}
  catch(e){setError(e instanceof Error?e.message:"Unable to request approval.");}
  finally{setBusy(null);}
 }
 async function decide(item:Approval,decision:"approved"|"rejected"){
  setBusy(item.id);setError("");setNotice("");
  try{const r=await api("/api/v1/automations/approvals/"+item.id+"/decision",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({decision,note:decisionNote[item.id]||""})});const d=await r.json();if(!r.ok)throw new Error(d.detail||"Unable to record approval decision.");setNotice(decision==="approved"?"Approval granted. The application is now marked approved.":"Approval request rejected.");await load();}
  catch(e){setError(e instanceof Error?e.message:"Unable to record decision.");}
  finally{setBusy(null);}
 }
 async function saveNotes(row:Application){
  setBusy(row.id);setError("");
  try{const r=await api("/api/v1/applications/"+row.id,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({notes:editNotes})});const d=await r.json();if(!r.ok)throw new Error(d.detail||"Unable to save notes.");setEditing(null);setNotice("Application notes saved.");await load();}
  catch(e){setError(e instanceof Error?e.message:"Unable to save notes.");}
  finally{setBusy(null);}
 }

 return <AppShell><div className={styles.page}>
  <header className={styles.heading}><div><div className={styles.kicker}>YOUR WORKSPACE <span>/</span> APPLICATIONS</div><h1>Application manager</h1><p>Keep every role, decision and next step accountable from first draft to final outcome.</p></div><button className={styles.primaryButton} onClick={()=>setCreating(x=>!x)}><Plus size={15}/>{creating?"Close form":"New application"}</button></header>
  <section className={styles.summary}><div><span>ALL APPLICATIONS</span><strong>{rows.length}</strong></div><div><span>ACTIVE PIPELINE</span><strong>{active}</strong></div><div><span>AWAITING APPROVAL</span><strong>{pending.length}</strong></div><div><span>INTERVIEWS</span><strong>{rows.filter(x=>x.status==="interview").length}</strong></div></section>
  {creating&&<form className={styles.createPanel} onSubmit={create}><div className={styles.formTitle}><div><span className={styles.sectionLabel}>NEW RECORD</span><h2>Create an application draft</h2><p>This only creates a tracker record. It does not submit an application to an employer.</p></div><FilePlus2 size={20}/></div><div className={styles.formGrid}><label>Role title<input required minLength={2} maxLength={250} value={role} onChange={e=>setRole(e.target.value)} placeholder="Data Engineer"/></label><label>Company<input maxLength={250} value={company} onChange={e=>setCompany(e.target.value)} placeholder="Company name"/></label><label className={styles.wide}>Original job URL<input type="url" maxLength={2000} value={url} onChange={e=>setUrl(e.target.value)} placeholder="https://…"/></label><label className={styles.wide}>Notes<textarea maxLength={10000} rows={3} value={notes} onChange={e=>setNotes(e.target.value)} placeholder="Recruiter contact, deadline, preparation notes…"/></label></div><div className={styles.formActions}><button className={styles.primaryButton} disabled={busy===-1}>{busy===-1?"Creating…":"Create draft record"}</button><button type="button" className={styles.cancelButton} onClick={()=>setCreating(false)}>Cancel</button></div></form>}
  {error&&<div className={styles.error} role="alert">{error}</div>}{notice&&<div className={styles.notice} role="status}><CheckCircle2 size={14}/>{notice}</div>}
  <section className={styles.managerPanel}>
   <div className={styles.panelTop}><div className={styles.tabs}><button className={view==="applications"?styles.tabActive:styles.tab} onClick={()=>setView("applications")}>Applications <span>{rows.length}</span></button><button className={view==="approvals"?styles.tabActive:styles.tab} onClick={()=>setView("approvals")}>Approval requests <span>{pending.length}</span></button></div><div className={styles.controls}><label className={styles.search}><Search size={14}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search role or company…"/></label>{view==="applications"&&<label className={styles.filter}><Filter size={13}/><select value={filter} onChange={e=>setFilter(e.target.value)}><option value="all">All stages</option>{statuses.map(s=><option key={s} value={s}>{label(s)}</option>)}</select></label>}</div></div>
   {loading?<div className={styles.loading}>Loading records…</div>:view==="applications"?visible.length===0?<div className={styles.empty}><BriefcaseBusiness size={23}/><strong>{rows.length===0?"Your application tracker is ready.":"No applications match these filters."}</strong><p>{rows.length===0?"Create your first draft or save a role from Opportunities to begin.":"Change the stage filter or search terms."}</p>{rows.length===0&&<a href="/opportunities">Browse opportunities <ArrowRight size={14}/></a>}</div>:<div className={styles.applicationList}>{visible.map(row=><article className={styles.application} key={row.id}>
    <div className={styles.applicationMain}><div className={styles.applicationTitle}><div className={styles.companyMark}>{(row.company_logo_url||row.company_favicon_url)?<img src={row.company_logo_url||row.company_favicon_url} alt={(row.company_name||"Company")+" logo"} loading="lazy" referrerPolicy="no-referrer"/>:(row.company_name||row.role_title).slice(0,1).toUpperCase()}</div><div title={row.company_description||row.company_name||"Company"}><h3>{row.role_title}</h3><p>{row.company_website?<a href={row.company_website} target="_blank" rel="noreferrer">{row.company_name||"Company"}</a>:(row.company_name||"Company not specified")} {row.company_domain&&<small className={styles.companyDomain}>{row.company_domain}</small>} {row.company_brand_color&&<i className={styles.brandColor} style={{backgroundColor:row.company_brand_color}} title={"Published brand color "+row.company_brand_color}/>}<span> · </span>Added {date(row.created_at)}</p></div></div>
     {editing===row.id?<div className={styles.noteEditor}><textarea value={editNotes} onChange={e=>setEditNotes(e.target.value)} rows={3} maxLength={10000}/><div><button onClick={()=>void saveNotes(row)} disabled={busy===row.id}>Save notes</button><button onClick={()=>setEditing(null)}>Cancel</button></div></div>:row.notes?<p className={styles.notes}>{row.notes}</p>:<button className={styles.addNote} onClick={()=>{setEditing(row.id);setEditNotes(row.notes||"");}}><MessageSquareText size={12}/> Add application notes</button>}
     <div className={styles.rowMeta}>{row.job_url&&<a href={row.job_url} target="_blank" rel="noreferrer">Original job listing <ArrowUpRight size={11}/></a>}{row.applied_at&&<span>Recorded submitted {date(row.applied_at)}</span>}</div>
    </div>
    <div className={styles.applicationControls}><span className={styles.status+" "+styles["status_"+row.status]}>{label(row.status)}</span>
     {row.status==="ready"&&<button className={styles.approvalButton} onClick={()=>void requestApproval(row)} disabled={busy===row.id}><ShieldCheck size={13}/>{busy===row.id?"Requesting…":"Request approval"}</button>}
     {row.status==="approved"&&<button className={styles.recordButton} onClick={()=>void changeStatus(row,"submitted")} disabled={busy===row.id}>Record as submitted <ArrowRight size={12}/></button>}
     {transitions[row.status]?.length>0&&<label className={styles.stageSelect}>Update stage<select value="" onChange={e=>{if(e.target.value)void changeStatus(row,e.target.value);}} disabled={busy===row.id}><option value="">Choose stage…</option>{transitions[row.status].map(s=><option key={s} value={s}>{label(s)}</option>)}</select></label>}
    </div>
   </article>)}</div>:approvals.length===0?<div className={styles.empty}><ShieldCheck size={23}/><strong>No approval requests</strong><p>When you mark an application ready, you can request a review here. Nothing is sent to an employer automatically.</p></div>:<div className={styles.approvalList}>{approvals.map(item=><article className={styles.approval} key={item.id}><div className={styles.approvalTop}><span className={styles.approvalIcon}><ShieldCheck size={16}/></span><div><strong>{item.action_type==="application_submission"?"Application submission review":label(item.action_type)}</strong><small>Request #{item.id} · {date(item.created_at)}</small></div><span className={styles.status+" "+styles["status_"+item.status]}>{label(item.status)}</span></div><p>{item.rationale}</p>{item.status==="pending"?<><label className={styles.decisionNote}>Decision note (optional)<textarea rows={2} maxLength={2000} value={decisionNote[item.id]||""} onChange={e=>setDecisionNote(x=>({...x,[item.id]:e.target.value}))} placeholder="Add a reason or reminder…"/></label><div className={styles.decisionActions}><button className={styles.rejectButton} onClick={()=>void decide(item,"rejected")} disabled={busy===item.id}><X size={13}/> Reject request</button><button className={styles.approveButton} onClick={()=>void decide(item,"approved")} disabled={busy===item.id}><Check size={13}/> Approve request</button></div></>:<div className={styles.decisionMeta}>{item.decision_note||"No decision note"}{item.decided_at?" · Decided "+date(item.decided_at):""}</div>}</article>)}</div>}
  </section>
  <div className={styles.safety}><ShieldCheck size={14}/> Approval only records your decision. This workspace does not send applications to employers or perform external submissions.</div>
 </div></AppShell>;
}
