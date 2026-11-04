"use client";

import AppShell from "../../components/layout/app-shell";




import {useEffect,useState} from "react";
const API=process.env.NEXT_PUBLIC_API_BASE_URL||"http://localhost:8000";
export default function Analytics(){const [data,setData]=useState<any>(null);const [error,setError]=useState("");
useEffect(()=>{void fetch(API+"/api/v1/analytics/overview",{credentials:"include",cache:"no-store"}).then(async r=>{if(r.status===401){window.location.assign("/login");return;}if(!r.ok)throw new Error("Analytics unavailable");setData(await r.json());}).catch(e=>setError(e.message));},[]);
return <AppShell><main style={{maxWidth:1000,margin:"0 auto",padding:32,color:"#edf5ef"}}><a href="/dashboard" style={{color:"#54d69a"}}>← Workspace</a><h1>Career analytics</h1><p style={{color:"#9aaba2"}}>A factual summary of your saved opportunities, applications, interviews and AI activity.</p>{error&&<p role="alert">{error}</p>}{data&&<section style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(190px,1fr))",gap:14}}>{[["Saved opportunities",data.saved_opportunities],["Applications",data.applications],["Interviews",data.interviews],["AI tokens",data.ai_tokens]].map(([k,v])=><article key={String(k)} style={panel}><small style={{color:"#9aaba2"}}>{k}</small><div style={{fontSize:32,fontWeight:750,marginTop:8}}>{Number(v).toLocaleString()}</div></article>)}</section>}{data&&<section style={{...panel,marginTop:18}}><h2>Applications by status</h2>{Object.entries(data.applications_by_status).map(([k,v])=><div key={k} style={{display:"flex",justifyContent:"space-between",padding:10,borderTop:"1px solid #25352d"}}><span>{k}</span><strong>{String(v)}</strong></div>)}</section>}</main></AppShell>}
const panel:React.CSSProperties={background:"#111a16",border:"1px solid #25352d",borderRadius:16,padding:20};
