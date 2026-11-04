"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Building2, Globe2, Search, ShieldCheck } from "lucide-react";
import AppShell from "../../components/layout/app-shell";
import styles from "./companies.module.css";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
type Company = {
  id:number; name:string; website?:string; domain?:string; careers_url?:string;
  description?:string; industry?:string; headquarters?:string; logo_url?:string;
  favicon_url?:string; brand_color?:string; source_provider?:string; source_board?:string;
  source_url?:string; verified_at?:string|null; last_enriched_at?:string|null; opportunity_count:number;
};
async function api(path:string){const response=await fetch(API+path,{credentials:"include",cache:"no-store"});if(response.status===401)window.location.assign("/login");return response;}
function initials(name:string){return name.trim().split(/\s+/).slice(0,2).map(x=>x[0]).join("").toUpperCase()||"CO";}
function date(value?:string|null){if(!value)return "Not recorded";const parsed=new Date(value);return Number.isNaN(parsed.getTime())?"Not recorded":parsed.toLocaleDateString(undefined,{day:"numeric",month:"short",year:"numeric"});}

export default function CompaniesPage(){
 const [rows,setRows]=useState<Company[]>([]);
 const [query,setQuery]=useState("");
 const [loading,setLoading]=useState(true);
 const [error,setError]=useState("");
 const load=useCallback(async()=>{setLoading(true);setError("");try{const response=await api("/api/v1/companies");if(!response.ok)throw new Error("Company intelligence is unavailable.");const data=await response.json();setRows(Array.isArray(data)?data:[]);}catch(e){setError(e instanceof Error?e.message:"Unable to load companies.");}finally{setLoading(false);}},[]);
 useEffect(()=>{void load();},[load]);
 const visible=useMemo(()=>{const q=query.trim().toLowerCase();return rows.filter(x=>!q||[x.name,x.domain,x.industry,x.headquarters,x.description].join(" ").toLowerCase().includes(q));},[rows,query]);
 const roles=rows.reduce((sum,item)=>sum+item.opportunity_count,0);
 return <AppShell><main className={styles.page}>
  <header className={styles.heading}><div><span className={styles.kicker}>INTELLIGENCE / EMPLOYERS</span><h1>Company intelligence</h1><p>One employer profile connects its published identity, career site and every opportunity you discover.</p></div><div className={styles.metrics}><div><strong>{rows.length}</strong><span>companies</span></div><div><strong>{roles}</strong><span>linked opportunities</span></div></div></header>
  <section className={styles.toolbar}><div><span className={styles.eyebrow}>EMPLOYER DIRECTORY</span><h2>Companies in your workspace</h2><p>Profiles are created from the public career boards you connect.</p></div><label className={styles.search}><Search size={15}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search companies, domains or industries"/></label></section>
  {error&&<div className={styles.error} role="alert">{error}<button onClick={()=>void load()}>Retry</button></div>}
  {loading?<div className={styles.empty}>Loading employer records…</div>:visible.length===0?<div className={styles.empty}><Building2 size={24}/><strong>{rows.length?"No companies match this search":"No company profiles yet"}</strong><p>{rows.length?"Try a different company name or domain.":"Discover a role from a Greenhouse or Lever board. JobSeeker will create its employer profile and link imported vacancies automatically."}</p><Link href="/opportunities">Discover opportunities <ArrowUpRight size={14}/></Link></div>:<div className={styles.grid}>{visible.map(company=><article className={styles.card} key={company.id}>
   <div className={styles.cardTop}><div className={styles.logo} style={company.brand_color?{borderColor:company.brand_color+"55"}:undefined}>{company.logo_url||company.favicon_url?<img src={company.logo_url||company.favicon_url} alt={company.name+" logo"} loading="lazy" referrerPolicy="no-referrer"/>:initials(company.name)}</div><span className={styles.source}>{company.source_provider?company.source_provider+" board":"Manual profile"}</span></div>
   <h3>{company.name}</h3><p className={styles.domain}>{company.domain||company.website||"Website not published"}</p>
   <p className={styles.description}>{company.description||"No public company description was supplied by this career source."}</p>
   <div className={styles.meta}>{company.industry&&<span>{company.industry}</span>}{company.headquarters&&<span>{company.headquarters}</span>}</div>
   <div className={styles.cardBottom}><span><Building2 size={13}/>{company.opportunity_count} {company.opportunity_count===1?"opportunity":"opportunities"}</span>{company.verified_at&&<span title={"Source checked "+date(company.verified_at)}><ShieldCheck size={13}/>Source linked</span>}</div>
   <div className={styles.actions}>{company.website&&<a href={company.website} target="_blank" rel="noreferrer"><Globe2 size={13}/> Website <ArrowUpRight size={12}/></a>}<Link href={"/companies/"+company.id}>Company profile <ArrowUpRight size={13}/></Link></div>
  </article>)}</div>}
  <p className={styles.footnote}>Company facts and brand assets are displayed only when a connected source publishes them. Missing details are left blank rather than guessed. Last source refresh is tracked per profile.</p>
 </main></AppShell>;
}
