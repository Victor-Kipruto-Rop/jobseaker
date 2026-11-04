"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, CircleAlert, ExternalLink, Gauge, LockKeyhole, LogOut, Mail, RefreshCw, ShieldCheck, SlidersHorizontal, WalletCards } from "lucide-react";
import AppShell from "../../components/layout/app-shell";
import styles from "./settings.module.css";

const API=process.env.NEXT_PUBLIC_API_BASE_URL||"http://localhost:8000";
type Budget={monthly_token_limit:number;hard_token_limit_enabled:boolean;alert_threshold_percent:number;monthly_tokens_used:number;reserved_tokens:number;remaining_tokens:number|null;usage_percent:number|null;enforcement:string;period_start:string};
type Account={id:number;email:string;full_name:string;is_verified:boolean};
type Gmail={connected:boolean;email?:string;last_synced_at?:string|null;scopes?:string[];read_only:boolean};
function csrf(){return decodeURIComponent(document.cookie.split("; ").find(x=>x.startsWith("jobseeker_csrf="))?.split("=").slice(1).join("=")||"");}
async function api(path:string,init:RequestInit={}){const h=new Headers(init.headers);if(init.method)h.set("X-CSRF-Token",csrf());const r=await fetch(API+path,{...init,headers:h,credentials:"include",cache:"no-store"});if(r.status===401)window.location.assign("/login");return r;}
function date(v?:string|null){if(!v)return "Not synced yet";const d=new Date(v);return Number.isNaN(d.getTime())?"Not synced yet":d.toLocaleString();}

export default function Settings(){
 const [account,setAccount]=useState<Account|null>(null);const [budget,setBudget]=useState<Budget|null>(null);const [gmail,setGmail]=useState<Gmail|null>(null);
 const [limit,setLimit]=useState(0);const [enabled,setEnabled]=useState(false);const [threshold,setThreshold]=useState(80);
 const [loading,setLoading]=useState(true);const [saving,setSaving]=useState(false);const [syncing,setSyncing]=useState(false);const [connecting,setConnecting]=useState(false);
 const [error,setError]=useState("");const [notice,setNotice]=useState("");
 const load=useCallback(async()=>{
  setLoading(true);setError("");
  try{const [a,b,g]=await Promise.all([api("/api/v1/auth/me"),api("/api/v1/ai/budget"),api("/api/v1/integrations/gmail/account")]);
   if(!a.ok)throw new Error("Unable to load your account details.");const [ad,bd,gd]=await Promise.all([a.json(),b.ok?b.json():null,g.ok?g.json():{connected:false,read_only:true}]);
   setAccount(ad);setBudget(bd);setGmail(gd);if(bd){setLimit(bd.monthly_token_limit);setEnabled(bd.hard_token_limit_enabled);setThreshold(bd.alert_threshold_percent);}
  }catch(e){setError(e instanceof Error?e.message:"Unable to load settings.");}
  finally{setLoading(false);}
 },[]);
 useEffect(()=>{void load();},[load]);

 async function saveBudget(e:React.FormEvent){e.preventDefault();setSaving(true);setError("");setNotice("");try{const r=await api("/api/v1/ai/budget",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({monthly_token_limit:limit,hard_token_limit_enabled:enabled,alert_threshold_percent:threshold})});const d=await r.json();if(!r.ok)throw new Error(d.detail||"Unable to save usage controls.");setBudget(d);setNotice("AI usage controls saved. Enforcement: "+d.enforcement+".");}catch(e){setError(e instanceof Error?e.message:"Unable to save controls.");}finally{setSaving(false);}}
 async function connectGmail(){setConnecting(true);setError("");try{const r=await api("/api/v1/integrations/gmail/authorize",{method:"POST"});const d=await r.json();if(!r.ok)throw new Error(d.detail||"Unable to start Gmail authorization.");if(!d.read_only||!d.scopes?.includes("https://www.googleapis.com/auth/gmail.readonly"))throw new Error("The requested Gmail permission did not match the read-only scope.");window.location.assign(d.authorization_url);}catch(e){setError(e instanceof Error?e.message:"Unable to connect Gmail.");setConnecting(false);}}
 async function disconnectGmail(){if(!window.confirm("Disconnect Gmail and remove locally synchronized message records?"))return;setError("");try{const r=await api("/api/v1/integrations/gmail/account",{method:"DELETE"});const d=await r.json();if(!r.ok)throw new Error(d.detail||"Unable to disconnect Gmail.");setGmail({connected:false,read_only:true});setNotice("Gmail disconnected and synchronized message records removed.");}catch(e){setError(e instanceof Error?e.message:"Unable to disconnect Gmail.");}}
 async function syncGmail(){setSyncing(true);setError("");setNotice("");try{const r=await api("/api/v1/integrations/gmail/sync",{method:"POST"});const d=await r.json();if(!r.ok)throw new Error(d.detail||"Gmail synchronization failed.");setNotice("Gmail sync completed. "+(d.synced??d.messages_synced??"")+" messages processed.");await load();}catch(e){setError(e instanceof Error?e.message:"Gmail sync failed.");}finally{setSyncing(false);}}
 async function verifyEmail(){setError("");setNotice("");try{const r=await api("/api/v1/auth/verification/request",{method:"POST"});const d=await r.json();if(!r.ok)throw new Error(d.detail||"Unable to request verification.");setNotice(d.status==="already_verified"?"Your email is already verified.":d.status==="sent"?"Verification email sent. Check your inbox.":"Verification instructions have been generated for this environment.");}catch(e){setError(e instanceof Error?e.message:"Verification request failed.");}}
 async function logout(){try{await api("/api/v1/auth/logout",{method:"POST"});}finally{window.location.assign("/login");}}
 const percent=budget?.usage_percent??null;
 return <AppShell user={account}><div className={styles.page}>
  <header className={styles.heading}><div><div className={styles.kicker}>YOUR WORKSPACE <span>/</span> SETTINGS</div><h1>Account and workspace settings</h1><p>Control your account, AI consumption and connected services from one place.</p></div></header>
  {error&&<div className={styles.error} role="alert"><CircleAlert size={14}/>{error}</div>}{notice&&<div className={styles.notice} role="status"><Check size={14}/>{notice}</div>}
  {loading?<div className={styles.loading}>Loading account settings…</div>:<>
   <section className={styles.accountPanel}><div className={styles.accountIdentity}><span className={styles.accountAvatar}>{(account?.full_name||account?.email||"J").slice(0,1).toUpperCase()}</span><div><span className={styles.sectionLabel}>ACCOUNT IDENTITY</span><h2>{account?.full_name||"Your account"}</h2><p>{account?.email}</p></div></div><div className={styles.accountStatus}><span className={account?.is_verified?styles.verified:styles.unverified}>{account?.is_verified?"Email verified":"Email not verified"}</span>{!account?.is_verified&&<button onClick={()=>void verifyEmail()}>Verify email</button>}</div></section>

   <section className={styles.settingsGrid}>
    <article className={styles.panel}><div className={styles.panelHeading}><span className={styles.panelIcon}><Gauge size={17}/></span><div><span className={styles.sectionLabel}>USAGE GOVERNANCE</span><h2>AI token budget</h2><p>Set a monthly usage ceiling and warning threshold for AI-assisted career tools.</p></div></div>
     {budget&&<div className={styles.usageStats}><div><small>Used this month</small><strong>{Number(budget.monthly_tokens_used||0).toLocaleString()}</strong></div><div><small>Reserved</small><strong>{Number(budget.reserved_tokens||0).toLocaleString()}</strong></div><div><small>Remaining</small><strong>{budget.remaining_tokens===null?"—":Number(budget.remaining_tokens).toLocaleString()}</strong></div></div>}
     {percent!==null&&<div className={styles.usageBar}><div><span>Monthly consumption</span><strong>{percent}%</strong></div><div className={styles.track}><i style={{width:Math.min(100,percent)+"%"}}/></div></div>}
     <form onSubmit={saveBudget} className={styles.budgetForm}><label>Monthly token limit<input type="number" min={0} max={100000000} value={limit} onChange={e=>setLimit(Number(e.target.value))}/><small>Use 0 for no configured cap. The server enforces this before generation.</small></label><label className={styles.toggleRow}><input type="checkbox" checked={enabled} onChange={e=>setEnabled(e.target.checked)}/><span><strong>Enforce hard monthly limit</strong><small>Block new AI generation when the allowance is exhausted.</small></span></label><label>Alert threshold<input type="number" min={1} max={100} value={threshold} onChange={e=>setThreshold(Number(e.target.value))}/><small>Percentage of monthly allowance used before warning.</small></label><button className={styles.primaryButton} disabled={saving}><SlidersHorizontal size={14}/>{saving?"Saving…":"Save usage controls"}</button></form>
     <div className={styles.subtleNote}><WalletCards size={14}/> Token limits are not monetary cost limits. Costs depend on the provider and model used.</div>
    </article>

    <article className={styles.panel}><div className={styles.panelHeading}><span className={styles.panelIcon}><Mail size={17}/></span><div><span className={styles.sectionLabel}>CONNECTED SERVICES</span><h2>Gmail integration</h2><p>Optional read-only access to help organize application correspondence.</p></div></div>
     <div className={styles.connectionCard}><div className={styles.connectionTop}><span className={gmail?.connected?styles.connectedDot:styles.disconnectedDot}/><strong>{gmail?.connected?"Connected":"Not connected"}</strong><span className={styles.readOnly}>READ ONLY</span></div>{gmail?.connected?<><p className={styles.connectedEmail}>{gmail.email}</p><small>Last synchronized: {date(gmail.last_synced_at)}</small><div className={styles.scopes}>{(gmail.scopes||[]).map(scope=><span key={scope}>{scope.split("/").pop()}</span>)}</div></>:<p className={styles.connectionDescription}>Connect Gmail to view messages relevant to your job search. The integration requests only the <strong>gmail.readonly</strong> permission. It cannot send, delete or modify email.</p>}</div>
     <div className={styles.connectionActions}>{gmail?.connected?<><button className={styles.primaryButton} onClick={()=>void syncGmail()} disabled={syncing}><RefreshCw size={14}/>{syncing?"Synchronizing…":"Sync messages"}</button><button className={styles.dangerButton} onClick={()=>void disconnectGmail()}>Disconnect</button></>:<button className={styles.primaryButton} onClick={()=>void connectGmail()} disabled={connecting||!account?.is_verified}><ExternalLink size={14}/>{connecting?"Connecting…":account?.is_verified?"Connect Gmail":"Verify email to connect"}</button>}</div>
     {!account?.is_verified&&!gmail?.connected&&<p className={styles.connectionDescription}>Verify your account email before connecting Gmail. This is enforced by the backend.</p>}
     <div className={styles.subtleNote}><LockKeyhole size={14}/> Gmail tokens are stored server-side. Message access remains scoped to your account.</div>
    </article>
   </section>

   <section className={styles.securityPanel}><div><span className={styles.panelIcon}><ShieldCheck size={17}/></span><div><span className={styles.sectionLabel}>SECURITY & PRIVACY</span><h2>Account controls</h2><p>Your session is protected by secure cookies, CSRF validation and account-scoped API access. AI-generated content remains a draft until you review it.</p></div></div><button onClick={()=>void logout()}><LogOut size={14}/> Sign out</button></section>
   <div className={styles.footnote}>No outbound email sending or automatic job application submission is enabled from this workspace.</div>
  </>}
 </div></AppShell>;
}
