"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowRight, ArrowUpRight, BriefcaseBusiness, CalendarDays, CheckCircle2,
  CircleAlert, Clock3, FileText, Search, ShieldCheck, Sparkles, Target,
  TrendingUp, UserRound, WalletCards
} from "lucide-react";
import AppShell from "../../components/layout/app-shell";
import styles from "./dashboard.module.css";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
type User = { id:number; full_name:string; email:string; is_verified:boolean };
type Application = { id:number; role_title:string; company_name?:string; status:string; created_at?:string; applied_at?:string|null; job_url?:string };
type Opportunity = { id:number; title:string; company?:string; location?:string; source_url?:string; fit?:{fit_score?:number;matched_skills?:string[];missing_skills?:string[];warning?:string} };
type Analytics = { saved_opportunities:number; applications:number; applications_by_status:Record<string,number>; interviews:number; ai_tokens:number };
type Profile = { profile?:{headline?:string;summary?:string;location?:string;target_roles?:string[]}; skills?:{id:number;skill_name:string}[] };
function csrf(){return decodeURIComponent(document.cookie.split("; ").find(item=>item.startsWith("jobseeker_csrf="))?.split("=").slice(1).join("=")||"");}
async function api(path:string,init:RequestInit={}){const headers=new Headers(init.headers);if(init.method)headers.set("X-CSRF-Token",csrf());const response=await fetch(API+path,{...init,headers,credentials:"include",cache:"no-store"});if(response.status===401)window.location.assign("/login");return response;}
function fmt(value:number){return Number(value||0).toLocaleString();}
function titleCase(value:string){return value.replaceAll("_"," ").replace(/\b\w/g,c=>c.toUpperCase());}
function date(value?:string|null){if(!value)return "Not recorded";const parsed=new Date(value);return Number.isNaN(parsed.getTime())?"Not recorded":parsed.toLocaleDateString(undefined,{day:"numeric",month:"short",year:"numeric"});}
const stages=["draft","ready","approved","submitted","screening","interview","assessment","offer","accepted","rejected","withdrawn","archived"];

export default function Dashboard(){
  const [user,setUser]=useState<User|null>(null);
  const [applications,setApplications]=useState<Application[]>([]);
  const [opportunities,setOpportunities]=useState<Opportunity[]>([]);
  const [analytics,setAnalytics]=useState<Analytics|null>(null);
  const [profile,setProfile]=useState<Profile|null>(null);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");
  const [verification,setVerification]=useState("");
  const [verifying,setVerifying]=useState(false);

  const load=useCallback(async()=>{
    setLoading(true);setError("");
    try{
      const [u,a,o,n,p]=await Promise.all([
        api("/api/v1/auth/me"),api("/api/v1/applications"),api("/api/v1/opportunities"),
        api("/api/v1/analytics/overview"),api("/api/v1/profile")
      ]);
      if(!u.ok)throw new Error("Your sign-in session could not be verified. Please sign in again.");
      const [ud,ad,od,nd,pd]=await Promise.all([u.json(),a.ok?a.json():[],o.ok?o.json():[],n.ok?n.json():null,p.ok?p.json():null]);
      setUser(ud);setApplications(Array.isArray(ad)?ad:[]);setOpportunities(Array.isArray(od)?od:[]);setAnalytics(nd);setProfile(pd);
    }catch(e){setError(e instanceof Error?e.message:"Your workspace could not be loaded.");}
    finally{setLoading(false);}
  },[]);
  useEffect(()=>{void load();},[load]);

  const counts=analytics?.applications_by_status||{};
  const pipeline=useMemo(()=>stages.map(status=>({status,count:Number(counts[status]||0)})).filter(x=>x.count>0),[counts]);
  const active=applications.filter(x=>!["accepted","rejected","withdrawn","archived"].includes(x.status));
  const interviews=applications.filter(x=>x.status==="interview").length;
  const pending=applications.filter(x=>["draft","ready","approved"].includes(x.status));
  const topMatches=[...opportunities].sort((x,y)=>Number(y.fit?.fit_score||0)-Number(x.fit?.fit_score||0)).slice(0,3);
  const recent=applications.slice(0,6);
  const skillCount=profile?.skills?.length||0;
  const completionParts=[Boolean(profile?.profile?.headline),Boolean(profile?.profile?.summary),Boolean(profile?.profile?.location),Boolean(profile?.profile?.target_roles?.length),skillCount>0];
  const completion=Math.round(completionParts.filter(Boolean).length/completionParts.length*100);
  const firstName=user?.full_name?.trim().split(/\s+/)[0]||"there";

  async function requestVerification(){
    setVerifying(true);setVerification("");
    try{const r=await api("/api/v1/auth/verification/request",{method:"POST"});const d=await r.json();if(!r.ok)throw new Error(d.detail||"Unable to request verification.");setVerification(d.status==="already_verified"?"Your email is already verified.":d.status==="sent"?"Verification email requested. Check your inbox.":"Request accepted. Follow the instructions for your environment.");}
    catch(e){setVerification(e instanceof Error?e.message:"Verification request failed.");}
    finally{setVerifying(false);}
  }

  return <AppShell user={user}>
    <div className={styles.page}>
      <header className={styles.heading}>
        <div><div className={styles.kicker}>CAREER WORKSPACE <span>/</span> OVERVIEW</div><h1>Good morning, {firstName}.</h1><p>Here is where your search stands and what deserves your attention today.</p></div>
        <div className={styles.headingActions}><a className={styles.buttonSecondary} href="/applications"><BriefcaseBusiness size={15}/> View applications</a><a className={styles.buttonPrimary} href="/opportunities"><Search size={15}/> Find opportunities <ArrowUpRight size={14}/></a></div>
      </header>

      {user&&!user.is_verified&&<section className={styles.verifyBanner}><span className={styles.verifyIcon}><ShieldCheck size={17}/></span><div><strong>Verify your email address</strong><p>Confirm your account email to unlock account-sensitive integrations. Your career workspace remains available.</p>{verification&&<small role="status">{verification}</small>}</div><button onClick={()=>void requestVerification()} disabled={verifying}>{verifying?"Requesting…":"Send verification email"}</button></section>}

      {loading?<div className={styles.loading}><span className={styles.loader}/> Loading your workspace data…</div>:error?<div className={styles.error} role="alert"><CircleAlert size={18}/><div><strong>We couldn't load your workspace</strong><p>{error}</p><button onClick={()=>void load()}>Retry loading</button></div></div>:<>
        <section className={styles.metrics} aria-label="Your career metrics">
          <article className={styles.metric}><div className={styles.metricHead}><span>Saved opportunities</span><span className={styles.metricIcon}><Target size={16}/></span></div><strong>{fmt(analytics?.saved_opportunities??opportunities.length)}</strong><small>Roles in your library</small><a href="/opportunities">Review saved roles <ArrowUpRight size={12}/></a></article>
          <article className={styles.metric}><div className={styles.metricHead}><span>Applications</span><span className={styles.metricIcon}><BriefcaseBusiness size={16}/></span></div><strong>{fmt(analytics?.applications??applications.length)}</strong><small>{active.length} currently active</small><a href="/applications">Open tracker <ArrowUpRight size={12}/></a></article>
          <article className={styles.metric}><div className={styles.metricHead}><span>Interviews</span><span className={styles.metricIcon}><CalendarDays size={16}/></span></div><strong>{fmt(analytics?.interviews??interviews)}</strong><small>Recorded interview stages</small><a href="/applications">Review pipeline <ArrowUpRight size={12}/></a></article>
          <article className={styles.metric}><div className={styles.metricHead}><span>Profile readiness</span><span className={styles.metricIcon}><UserRound size={16}/></span></div><strong>{completion}%</strong><small>{skillCount} skills recorded</small><a href="/profile">Improve your profile <ArrowUpRight size={12}/></a></article>
        </section>

        <section className={styles.focusRow}>
          <article className={styles.pipelinePanel}>
            <div className={styles.panelHeading}><div><span className={styles.sectionIndex}>01 / APPLICATION FLOW</span><h2>Pipeline overview</h2><p>Applications by their current recorded stage</p></div><a href="/applications">Full tracker <ArrowUpRight size={13}/></a></div>
            {pipeline.length===0?<div className={styles.emptyState}><span><BriefcaseBusiness size={20}/></span><strong>Your pipeline starts with one good role.</strong><p>Save an opportunity and create an application draft to begin tracking progress.</p><a href="/opportunities">Explore opportunities <ArrowRight size={14}/></a></div>:<div className={styles.pipelineBody}>
              <div className={styles.pipelineTotal}><strong>{fmt(applications.length)}</strong><span>total applications</span><small>{fmt(active.length)} active in progress</small></div>
              <div className={styles.stageList}>{pipeline.slice(0,7).map(item=><div className={styles.stageRow} key={item.status}><span>{titleCase(item.status)}</span><div className={styles.stageTrack}><i style={{width:Math.max(3,item.count/Math.max(1,...pipeline.map(x=>x.count))*100)+"%"}}/></div><b>{item.count}</b></div>)}</div>
            </div>}
          </article>

          <article className={styles.actionPanel}>
            <div className={styles.panelHeading}><div><span className={styles.sectionIndex}>02 / ATTENTION</span><h2>What needs your attention</h2><p>Based on your actual workspace records</p></div><Sparkles size={17}/></div>
            <div className={styles.actionList}>
              {pending.some(x=>x.status==="draft")&&<a href="/applications" className={styles.actionItem}><span className={styles.actionGlyph}><FileText size={16}/></span><span><strong>Review application drafts</strong><small>{pending.filter(x=>x.status==="draft").length} drafts need your review</small></span><ArrowRight size={15}/></a>}
              {pending.some(x=>x.status==="ready")&&<a href="/applications?view=approvals" className={styles.actionItem}><span className={styles.actionGlyph}><ShieldCheck size={16}/></span><span><strong>Submission approval required</strong><small>{pending.filter(x=>x.status==="ready").length} ready applications are awaiting your decision</small></span><ArrowRight size={15}/></a>}
              {opportunities.length===0&&<a href="/opportunities" className={styles.actionItem}><span className={styles.actionGlyph}><Search size={16}/></span><span><strong>Build your opportunity shortlist</strong><small>Discover roles from supported company boards</small></span><ArrowRight size={15}/></a>}
              {completion<100&&<a href="/profile" className={styles.actionItem}><span className={styles.actionGlyph}><UserRound size={16}/></span><span><strong>Complete your career profile</strong><small>{completion}% complete · add skills and evidence</small></span><ArrowRight size={15}/></a>}
              {pending.length===0&&opportunities.length>0&&completion===100&&<div className={styles.allClear}><CheckCircle2 size={18}/><span><strong>Nothing urgent is waiting.</strong><small>Your workspace is up to date. Keep your application stages current.</small></span></div>}
            </div>
            <div className={styles.profileProgress}><div><span>Profile completeness</span><b>{completion}%</b></div><div className={styles.progressTrack}><i style={{width:completion+"%"}}/></div><a href="/profile">Update career details <ArrowRight size={12}/></a></div>
          </article>
        </section>

        <section className={styles.lowerGrid}>
          <article className={styles.tablePanel}>
            <div className={styles.panelHeading}><div><span className={styles.sectionIndex}>03 / RECENT ACTIVITY</span><h2>Recent applications</h2><p>Your latest application records</p></div><a href="/applications">View all <ArrowUpRight size={13}/></a></div>
            {recent.length===0?<div className={styles.emptyState}><span><BriefcaseBusiness size={20}/></span><strong>No applications recorded yet</strong><p>Start from a saved opportunity or create a draft manually.</p><a href="/opportunities">Find your first role <ArrowRight size={14}/></a></div>:<div className={styles.tableScroll}><table className={styles.table}><thead><tr><th>ROLE / COMPANY</th><th>STATUS</th><th>CREATED</th><th/></tr></thead><tbody>{recent.map(row=><tr key={row.id}><td><strong>{row.role_title}</strong><small>{row.company_name||"Company not specified"}</small></td><td><span className={styles.status+" "+styles["status_"+row.status]}>{titleCase(row.status)}</span></td><td>{date(row.created_at)}</td><td><a href="/applications" aria-label={"Open "+row.role_title}><ArrowUpRight size={14}/></a></td></tr>)}</tbody></table></div>}
          </article>
          <article className={styles.matchPanel}>
            <div className={styles.panelHeading}><div><span className={styles.sectionIndex}>04 / YOUR SHORTLIST</span><h2>Strongest saved matches</h2><p>Ranked by recorded skill-fit evidence</p></div><TrendingUp size={17}/></div>
            {topMatches.length===0?<div className={styles.emptyState}><span><Target size={20}/></span><strong>No matched roles yet</strong><p>Add skills to your profile and save opportunities to see evidence-based fit.</p><a href="/opportunities">Explore roles <ArrowRight size={14}/></a></div>:<div className={styles.matchList}>{topMatches.map((item,index)=><div className={styles.matchItem} key={item.id}><span className={styles.matchRank}>0{index+1}</span><div className={styles.matchCopy}><strong>{item.title}</strong><small>{item.company||"Company not specified"}{item.location?" · "+item.location:""}</small><div className={styles.matchBar}><i style={{width:Math.min(100,Math.max(0,Number(item.fit?.fit_score||0)))+"%"}}/></div><small>{item.fit?.matched_skills?.length||0} matched skills · {item.fit?.missing_skills?.length||0} gaps</small></div><b>{Math.round(Number(item.fit?.fit_score||0))}%</b></div>)}</div>}
            <a className={styles.panelFootLink} href="/opportunities">Open opportunity library <ArrowRight size={13}/></a>
          </article>
        </section>
        <div className={styles.dataNote}><ShieldCheck size={14}/> Metrics reflect records in your account. Skill-fit percentages are heuristic evidence, not a hiring probability.</div>
      </>}
    </div>
  </AppShell>;
}
