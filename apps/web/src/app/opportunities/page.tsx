"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowDownUp, ArrowUpRight, Bookmark, BriefcaseBusiness, Building2, Check, ExternalLink, MapPin, Plus, RefreshCw, Search, Sparkles, Trash2 } from "lucide-react";
import AppShell from "../../components/layout/app-shell";
import styles from "./opportunities.module.css";

const API=process.env.NEXT_PUBLIC_API_BASE_URL||"http://localhost:8000";
type Opportunity={id:number;title:string;company?:string;company_website?:string;company_domain?:string;company_logo_url?:string;company_favicon_url?:string;company_description?:string;company_brand_color?:string;company_brand_source?:string;location?:string;source_name?:string;source_url?:string;status?:string;created_at?:string;fit?:{fit_score?:number;matched_skills?:string[];missing_skills?:string[];warning?:string}};
type SavedSearch={id:number;name:string;query:{source:"greenhouse"|"lever";board:string;company_name?:string|null;keywords?:string[];location?:string|null;remote_only?:boolean}};
type Filters={source:"greenhouse"|"lever";board:string;company:string;name:string;keywords:string;location:string;remote:boolean};
const initial:Filters={source:"greenhouse",board:"",company:"",name:"",keywords:"",location:"",remote:false};
function csrf(){return decodeURIComponent(document.cookie.split("; ").find(x=>x.startsWith("jobseeker_csrf="))?.split("=").slice(1).join("=")||"");}
async function api(path:string,init:RequestInit={}){const headers=new Headers(init.headers);if(init.method)headers.set("X-CSRF-Token",csrf());const r=await fetch(API+path,{...init,headers,credentials:"include",cache:"no-store"});if(r.status===401)window.location.assign("/login");return r;}
function keywords(value:string){return [...new Set(value.split(/[,\n]/).map(x=>x.trim()).filter(Boolean))].slice(0,20);}
function score(item:Opportunity){return Math.round(Number(item.fit?.fit_score||0));}

export default function Opportunities({initialView="all"}:{initialView?:"all"|"saved"}){
 const [filters,setFilters]=useState<Filters>(initial);
 const [roles,setRoles]=useState<Opportunity[]>([]);
 const [searches,setSearches]=useState<SavedSearch[]>([]);
 const [query,setQuery]=useState("");
 const [sort,setSort]=useState("fit");
 const [loading,setLoading]=useState(true);
 const [searching,setSearching]=useState(false);
 const [savingSearch,setSavingSearch]=useState(false);
 const [error,setError]=useState("");
 const [notice,setNotice]=useState("");
 const [discoverySummary,setDiscoverySummary]=useState<{fetched:number;matched_filters:number;saved:number;duplicates_or_invalid:number;refreshed_existing?:number;company_profile?:{name:string;website:string;domain:string;logo_url:string;favicon_url:string;description:string;brand_color:string;source_url:string;brand_assets_verified:boolean}}|null>(null);
 const [applicationBusy,setApplicationBusy]=useState<number|null>(null);\n const [viewMode,setViewMode]=useState<"all"|"saved">(initialView);

 const load=useCallback(async()=>{
  setLoading(true);setError("");
  try{const [r,s]=await Promise.all([api("/api/v1/opportunities"),api("/api/v1/saved-searches")]);
   if(!r.ok||!s.ok)throw new Error("Unable to load your saved opportunities and searches.");
   const [rd,sd]=await Promise.all([r.json(),s.json()]);setRoles(Array.isArray(rd)?rd:[]);setSearches(Array.isArray(sd)?sd:[]);
  }catch(e){setError(e instanceof Error?e.message:"Unable to load opportunities.");}
  finally{setLoading(false);}
 },[]);
 useEffect(()=>{void load();},[load]);

 const visible=useMemo(()=>{
  const term=query.trim().toLowerCase();
  const list=roles.filter(item=>!term||[item.title,item.company,item.location,...(item.fit?.matched_skills||[])].join(" ").toLowerCase().includes(term));
  return list.sort((a,b)=>sort==="fit"?score(b)-score(a):sort==="newest"?new Date(b.created_at||0).getTime()-new Date(a.created_at||0).getTime():a.title.localeCompare(b.title));
 },[roles,query,sort]);
 const update=(key:keyof Filters,value:string|boolean)=>setFilters(current=>({...current,[key]:value}));

 async function discover(event?:React.FormEvent,override?:SavedSearch){
  event?.preventDefault();setError("");setNotice("");setSearching(true);setDiscoverySummary(null);
  const f=override?{source:override.query.source,board:override.query.board,company:override.query.company_name||"",name:override.name,keywords:(override.query.keywords||[]).join(", "),location:override.query.location||"",remote:Boolean(override.query.remote_only)}:filters;
  try{
   const r=await api("/api/v1/opportunities/discover",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({source:f.source,board:f.board,company_name:f.company||null,limit:100,keywords:keywords(f.keywords),location:f.location||null,remote_only:f.remote})});
   const d=await r.json();if(!r.ok)throw new Error(d.detail||"Discovery could not complete.");
   setDiscoverySummary(d);setNotice("Discovery completed. New matching listings have been added to your saved opportunities.");await load();
  }catch(e){setError(e instanceof Error?e.message:"Discovery failed.");}
  finally{setSearching(false);}
 }
 async function saveSearch(){
  setError("");setNotice("");setSavingSearch(true);
  try{
   if(filters.board.trim().length===0)throw new Error("Enter a company board identifier first.");
   const r=await api("/api/v1/saved-searches",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:filters.name.trim()||filters.board+" role search",source:filters.source,board:filters.board,company_name:filters.company||null,keywords:keywords(filters.keywords),location:filters.location||null,remote_only:filters.remote})});
   const d=await r.json();if(!r.ok)throw new Error(d.detail||"Unable to save this search.");
   setNotice("Search saved to your recurring search list.");setFilters(x=>({...x,name:""}));await load();
  }catch(e){setError(e instanceof Error?e.message:"Unable to save search.");}
  finally{setSavingSearch(false);}
 }
 async function removeSearch(id:number){
  const r=await api("/api/v1/saved-searches/"+id,{method:"DELETE"});
  if(!r.ok){setError("Unable to remove saved search.");return;}setSearches(x=>x.filter(s=>s.id!==id));
 }
 async function createApplication(item:Opportunity){
  setApplicationBusy(item.id);setError("");setNotice("");
  try{const r=await api("/api/v1/applications",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({role_title:item.title,company_name:item.company||"",job_url:item.source_url||"",opportunity_id:item.id,notes:"Created from saved opportunity."})});const d=await r.json();if(!r.ok)throw new Error(d.detail||"Unable to create application draft.");setNotice("Application draft created for "+item.title+".");}
  catch(e){setError(e instanceof Error?e.message:"Unable to create application.");}
  finally{setApplicationBusy(null);}
 }

 return <AppShell><div className={styles.page}>
  <header className={styles.heading}><div><div className={styles.kicker}>YOUR WORKSPACE <span>/</span> OPPORTUNITIES</div><h1>Opportunity library</h1><p>Find relevant roles, compare skill evidence and turn a good match into a trackable application.</p></div><div className={styles.headingActions}><div className={styles.viewSwitch}><button className={viewMode==="all"?styles.viewActive:styles.viewButton} onClick={()=>setViewMode("all")}>Discover</button><button className={viewMode==="saved"?styles.viewActive:styles.viewButton} onClick={()=>setViewMode("saved")}>Saved roles</button></div><div className={styles.headingMeta}><strong>{roles.length.toLocaleString()}</strong><span>saved roles</span></div></div></header>
  {viewMode==="all"&&  <section className={styles.searchLayout}>
   <div className={styles.searchPanel}>
    <div className={styles.panelTop}><div><span className={styles.sectionLabel}>DISCOVERY ENGINE</span><h2>Search company job boards</h2><p>Connect a public Greenhouse or Lever board. Results are imported into your private opportunity library.</p></div><span className={styles.panelIcon}><Search size={18}/></span></div>
    <form onSubmit={e=>void discover(e)} className={styles.form}>
     <div className={styles.formGrid}>
      <label>Job board provider<select value={filters.source} onChange={e=>update("source",e.target.value)}><option value="greenhouse">Greenhouse</option><option value="lever">Lever</option></select></label>
      <label>Board identifier<input required maxLength={80} placeholder="e.g. stripe" value={filters.board} onChange={e=>update("board",e.target.value)}/></label>
      <label>Company name<input maxLength={250} placeholder="Optional display name" value={filters.company} onChange={e=>update("company",e.target.value)}/></label>
      <label>Location<input maxLength={120} placeholder="Nairobi, Remote, Africa…" value={filters.location} onChange={e=>update("location",e.target.value)}/></label>
     </div>
     <label className={styles.fullField}>Skills and role keywords<input placeholder="Data Engineer, Python, SQL, dbt, Spark" value={filters.keywords} onChange={e=>update("keywords",e.target.value)}/><small>Separate terms with commas. Listings are filtered against their available title and description.</small></label>
     <div className={styles.formBottom}><label className={styles.checkLabel}><input type="checkbox" checked={filters.remote} onChange={e=>update("remote",e.target.checked)}/><span>Remote or distributed roles only</span></label><div className={styles.formActions}><button type="button" className={styles.secondaryButton} disabled={savingSearch} onClick={()=>void saveSearch()}><Bookmark size={14}/>{savingSearch?"Saving…":"Save search"}</button><button className={styles.primaryButton} disabled={searching}>{searching?<RefreshCw size={14} className={styles.spin}/>:<Search size={14}/>}{searching?"Searching…":"Find matching roles"}</button></div></div>
    </form>
    {error&&<p className={styles.error} role="alert">{error}</p>}{notice&&<p className={styles.notice} role="status"><Check size={14}/>{notice}</p>}
    {discoverySummary&&<><div className={styles.resultSummary}><div><strong>{discoverySummary.fetched}</strong><small>found on board</small></div><div><strong>{discoverySummary.matched_filters}</strong><small>matched filters</small></div><div><strong>{discoverySummary.saved}</strong><small>newly saved</small></div><div><strong>{discoverySummary.refreshed_existing||0}</strong><small>existing roles enriched</small></div><div><strong>{discoverySummary.duplicates_or_invalid}</strong><small>duplicates skipped</small></div></div>{discoverySummary.company_profile&&<div className={styles.companyProfile}><div className={styles.companyProfileMark}>{discoverySummary.company_profile.logo_url||discoverySummary.company_profile.favicon_url?<img src={discoverySummary.company_profile.logo_url||discoverySummary.company_profile.favicon_url} alt={discoverySummary.company_profile.name+" logo"} referrerPolicy="no-referrer"/>:<Building2 size={17}/>}</div><div><strong>{discoverySummary.company_profile.name}</strong>{discoverySummary.company_profile.brand_color&&<i className={styles.brandColor} style={{backgroundColor:discoverySummary.company_profile.brand_color}} title={"Published brand color "+discoverySummary.company_profile.brand_color}/>}<small>{discoverySummary.company_profile.domain||"Company domain not verified"} · {discoverySummary.company_profile.brand_assets_verified?"Published brand assets found":"No published logo found; using neutral fallback"}</small>{discoverySummary.company_profile.website&&<a href={discoverySummary.company_profile.website} target="_blank" rel="noreferrer">Company website <ExternalLink size={11}/></a>}</div></div>}</>}
   </div>
   <aside className={styles.savedSearchPanel}><div className={styles.panelTop}><div><span className={styles.sectionLabel}>YOUR SEARCHES</span><h2>Saved searches</h2><p>Keep your preferred company feeds ready to run.</p></div><span className={styles.count}>{searches.length}</span></div>
    {searches.length===0?<div className={styles.savedEmpty}><Bookmark size={18}/><strong>No saved searches</strong><small>Save a board and its filters to reuse it later.</small></div>:<div className={styles.savedSearchList}>{searches.map(item=><div className={styles.savedSearch} key={item.id}><div><strong>{item.name}</strong><small>{item.query.source} · {item.query.board}</small><small>{[item.query.location,...(item.query.keywords||[])].filter(Boolean).join(" · ")||"No additional filters"}</small></div><div className={styles.savedActions}><button title="Run search" aria-label={"Run "+item.name} onClick={()=>void discover(undefined,item)} disabled={searching}><RefreshCw size={14}/></button><button title="Delete search" aria-label={"Delete "+item.name} onClick={()=>void removeSearch(item.id)}><Trash2 size={14}/></button></div></div>)}</div>}
   </aside>
  </section>}

  <section className={styles.rolesSection} id="saved-opportunities">
   <div className={styles.rolesHeading}><div><span className={styles.sectionLabel}>PRIVATE OPPORTUNITY LIBRARY</span><h2>Saved opportunities <span>{roles.length}</span></h2><p>Each role is scored against the skills and evidence in your career profile.</p></div><div className={styles.listControls}><label><Search size={14}/><input aria-label="Filter saved opportunities" placeholder="Filter roles…" value={query} onChange={e=>setQuery(e.target.value)}/></label><div><ArrowDownUp size={13}/><select aria-label="Sort opportunities" value={sort} onChange={e=>setSort(e.target.value)}><option value="fit">Best skill fit</option><option value="newest">Recently saved</option><option value="title">Role title</option></select></div></div></div>
   {loading?<div className={styles.loading}>Loading saved opportunities…</div>:visible.length===0?<div className={styles.emptyLibrary}><span><BriefcaseBusiness size={22}/></span><strong>{roles.length===0?"Your opportunity library is ready.":"No roles match this filter."}</strong><p>{roles.length===0?"Run a company board search above. Matching roles will be saved here with their source links and skill-fit evidence.":"Try another keyword or clear your search."}</p>{query&&<button onClick={()=>setQuery("")}>Clear filter</button>}</div>:<div className={styles.roleList}>{visible.map(item=><article className={styles.roleRow} key={item.id}>
    <div className={styles.companyMark} title={item.company||"Company"}>{(item.company_logo_url||item.company_favicon_url)?<img src={item.company_logo_url||item.company_favicon_url} alt={(item.company||"Company")+" logo"} loading="lazy" referrerPolicy="no-referrer"/>:(item.company||item.title||"J").trim().slice(0,1).toUpperCase()}</div>
    <div className={styles.roleMain}><div className={styles.roleTitleLine}><h3>{item.title}</h3><span className={styles.source}>{item.source_name||"Saved role"}</span></div><div className={styles.roleMeta}><span><Building2 size={12}/>{item.company_website?<a href={item.company_website} target="_blank" rel="noreferrer">{item.company||"Company"} <ExternalLink size={10}/></a>:(item.company||"Company not listed")}</span>{item.location&&<span><MapPin size={12}/>{item.location}</span>}</div><div className={styles.skillEvidence}><span>{item.fit?.matched_skills?.length||0} matched skills</span><span>{item.fit?.missing_skills?.length||0} skill gaps</span>{item.fit?.warning&&<em>{item.fit.warning}</em>}</div></div>
    <div className={styles.fitColumn}><strong>{score(item)}%</strong><small>skill fit</small><div className={styles.fitTrack}><i style={{width:score(item)+"%"}}/></div></div>
    <div className={styles.roleActions}><button onClick={()=>void createApplication(item)} disabled={applicationBusy===item.id}>{applicationBusy===item.id?"Creating…":<><Plus size={13}/> Create draft</>}</button>{item.source_url&&<a href={item.source_url} target="_blank" rel="noreferrer" aria-label={"Open original listing for "+item.title}><ExternalLink size={14}/></a>}</div>
   </article>)}</div>}
  </section>
  <div className={styles.disclaimer}><Sparkles size={14}/> Fit is transparent keyword and skill coverage, not a probability of being hired. Discovery imports publicly available board listings; always review the original posting.</div>
 </div></AppShell>;
}
