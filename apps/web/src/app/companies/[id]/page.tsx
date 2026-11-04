"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, ArrowUpRight, Building2, CalendarClock, ExternalLink, Globe2, ShieldCheck } from "lucide-react";
import AppShell from "../../../components/layout/app-shell";
import styles from "./company-detail.module.css";

const API=process.env.NEXT_PUBLIC_API_BASE_URL||"http://localhost:8000";
type Role={id:number;title:string;location?:string;employment_type?:string;remote_type?:string;source_name?:string;source_url?:string;status?:string;created_at?:string};
type Company={id:number;name:string;website?:string;domain?:string;careers_url?:string;description?:string;industry?:string;headquarters?:string;logo_url?:string;favicon_url?:string;brand_color?:string;source_provider?:string;source_board?:string;source_url?:string;social_links?:Record<string,string>;evidence?:Record<string,unknown>;verified_at?:string|null;last_enriched_at?:string|null;opportunity_count:number;opportunities:Role[]};
async function api(path:string){const r=await fetch(API+path,{credentials:"include",cache:"no-store"});if(r.status===401)window.location.assign("/login");return r;}
function date(value?:string|null){if(!value)return "Not recorded";const d=new Date(value);return Number.isNaN(d.getTime())?"Not recorded":d.toLocaleDateString(undefined,{day:"numeric",month:"long",year:"numeric"});}
export default function CompanyDetailPage(){
 const params=useParams<{id:string}>();const [company,setCompany]=useState<Company|null>(null);const [loading,setLoading]=useState(true);const [error,setError]=useState("");
 useEffect(()=>{let active=true;void api("/api/v1/companies/"+encodeURIComponent(params.id)).then(async r=>{if(r.status===404)throw new Error("This company profile does not exist in your workspace.");if(!r.ok)throw new Error("Unable to load this company profile.");return r.json();}).then(data=>{if(active)setCompany(data);}).catch(e=>{if(active)setError(e instanceof Error?e.message:"Unable to load company.");}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};},[params.id]);
 return <AppShell><main className={styles.page}><Link className={styles.back} href="/companies"><ArrowLeft size={14}/> All companies</Link>
 {loading?<div className={styles.empty}>Loading company profile…</div>:error?<div className={styles.empty}>{error}<Link href="/companies">Return to companies</Link></div>:company&&<>
  <section className={styles.hero}>
   <div className={styles.heroTop}><div className={styles.logo} style={company.brand_color?{borderColor:company.brand_color+"66"}:undefined}>{company.logo_url||company.favicon_url?<img src={company.logo_url||company.favicon_url} alt={company.name+" logo"} referrerPolicy="no-referrer"/>:company.name.trim().slice(0,1).toUpperCase()}</div><div className={styles.identity}><span className={styles.kicker}>EMPLOYER PROFILE / {company.source_provider||"MANUAL"}</span><h1>{company.name}</h1><p>{company.domain||company.website||"Official website not published by source"}</p></div><div className={styles.roleCount}><strong>{company.opportunity_count}</strong><span>linked roles</span></div></div>
   {company.description&&<p className={styles.description}>{company.description}</p>}
   <div className={styles.facts}>{company.industry&&<span>{company.industry}</span>}{company.headquarters&&<span>{company.headquarters}</span>}{company.source_provider&&<span>{company.source_provider} board: {company.source_board}</span>}</div>
   <div className={styles.links}>{company.website&&<a href={company.website} target="_blank" rel="noreferrer"><Globe2 size={14}/> Company website <ExternalLink size={12}/></a>}{company.careers_url&&<a href={company.careers_url} target="_blank" rel="noreferrer"><Building2 size={14}/> Careers source <ExternalLink size={12}/></a>}{Object.entries(company.social_links||{}).map(([network,url])=><a key={network} href={url} target="_blank" rel="noreferrer">{network} <ExternalLink size={12}/></a>)}</div>
   <div className={styles.provenance}><span><ShieldCheck size={13}/> {company.verified_at?"Source linked":"Source not independently verified"}</span><span><CalendarClock size={13}/> Last enriched {date(company.last_enriched_at)}</span>{company.source_url&&<a href={company.source_url} target="_blank" rel="noreferrer">View source <ArrowUpRight size={12}/></a>}</div>
  </section>
  <section className={styles.roles}><div className={styles.sectionHeading}><div><span className={styles.kicker}>CAREER OPPORTUNITIES</span><h2>Roles from this employer</h2><p>All imported roles connected to this company record.</p></div><span>{company.opportunities.length} records</span></div>
   {company.opportunities.length===0?<div className={styles.empty}>No opportunities have been linked to this company yet.</div>:<div className={styles.roleList}>{company.opportunities.map(role=><article className={styles.role} key={role.id}><div><h3>{role.title}</h3><p>{role.location||"Location not specified"} · {role.employment_type||"Employment type not specified"}</p></div><div className={styles.roleActions}><span>{role.status||"discovered"}</span>{role.source_url&&<a href={role.source_url} target="_blank" rel="noreferrer">Original listing <ArrowUpRight size={12}/></a>}</div></article>)}</div>}
  </section>
  <p className={styles.note}>Only information published by the connected source is populated. Industry, headquarters and social links remain empty when the source does not provide reliable evidence.</p>
 </>}
 </main></AppShell>;
}
