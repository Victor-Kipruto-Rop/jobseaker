"use client";

import AppShell from "../../components/layout/app-shell";
import {useEffect,useState} from "react";
const API=process.env.NEXT_PUBLIC_API_BASE_URL||"http://localhost:8000";
function csrf(){return decodeURIComponent(document.cookie.split("; ").find(x=>x.startsWith("jobseeker_csrf="))?.split("=").slice(1).join("=")||"");}
export default function Notifications(){const [rows,setRows]=useState<any[]>([]);
async function load(){const r=await fetch(API+"/api/v1/notifications",{credentials:"include",cache:"no-store"});if(r.status===401){window.location.assign("/login");return;}if(r.ok)setRows(await r.json());}
useEffect(()=>{void load();},[]);
async function read(id:number){await fetch(API+"/api/v1/notifications/"+id+"/read",{method:"POST",credentials:"include",headers:{"X-CSRF-Token":csrf()}});await load();}
return <AppShell><main style={{maxWidth:900,margin:"0 auto",padding:32,color:"#edf5ef"}}><a href="/dashboard" style={{color:"#54d69a"}}>← Workspace</a><h1>Notification center</h1><section style={panel}>{rows.map(x=><article key={x.id} style={{padding:14,borderBottom:"1px solid #25352d"}}><div style={{display:"flex",justifyContent:"space-between",gap:12}}><strong>{x.title}</strong>{!x.read_at&&<button onClick={()=>void read(x.id)} style={button}>Mark read</button>}</div><p style={{color:"#9aaba2"}}>{x.body.replace(/^interview:\d+ /,"")}</p><small style={{color:"#708579"}}>{new Date(x.created_at).toLocaleString()}</small></article>)}{rows.length===0&&<p style={{color:"#9aaba2"}}>No notifications yet.</p>}</section></main></AppShell>}
const panel:React.CSSProperties={background:"#111a16",border:"1px solid #25352d",borderRadius:16,padding:20};
const button:React.CSSProperties={background:"#1c3829",border:"1px solid #345744",color:"#54d69a",padding:"8px 12px",borderRadius:8,cursor:"pointer"};
