"use client";

import AppShell from "../../components/layout/app-shell";
import {useEffect,useState} from "react";
const API=process.env.NEXT_PUBLIC_API_BASE_URL||"http://localhost:8000";
function csrf(){return decodeURIComponent(document.cookie.split("; ").find(x=>x.startsWith("jobseeker_csrf="))?.split("=").slice(1).join("=")||"");}
async function api(path:string,init:RequestInit={}){const h=new Headers(init.headers);if(init.method)h.set("X-CSRF-Token",csrf());const r=await fetch(API+path,{...init,headers:h,credentials:"include"});if(r.status===401)window.location.assign("/login");return r;}
export default function Recruiters(){const [rows,setRows]=useState<any[]>([]);const [name,setName]=useState("");const [email,setEmail]=useState("");const [url,setUrl]=useState("");const [notes,setNotes]=useState("");
async function load(){const r=await api("/api/v1/recruiters");if(r.ok)setRows(await r.json());}
useEffect(()=>{void load();},[]);
async function add(e:React.FormEvent){e.preventDefault();const r=await api("/api/v1/recruiters",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({full_name:name,email:email||null,profile_url:url,notes})});if(r.ok){setName("");setEmail("");setUrl("");setNotes("");await load();}}
return <AppShell><main style={{maxWidth:1000,margin:"0 auto",padding:32,color:"#edf5ef"}}><a href="/dashboard" style={{color:"#54d69a"}}>← Workspace</a><h1>Recruiter CRM</h1><p style={{color:"#9aaba2"}}>Maintain a private record of recruiter contacts and your professional relationship history.</p><form onSubmit={add} style={panel}><h2>Add recruiter</h2><input style={input} required placeholder="Full name" value={name} onChange={e=>setName(e.target.value)}/><input style={input} type="email" placeholder="Email" value={email} onChange={e=>setEmail(e.target.value)}/><input style={input} placeholder="Public profile URL" value={url} onChange={e=>setUrl(e.target.value)}/><textarea style={input} placeholder="Notes and interaction history" value={notes} onChange={e=>setNotes(e.target.value)}/><button style={primary}>Save contact</button></form><section style={{...panel,marginTop:18}}><h2>Contacts ({rows.length})</h2>{rows.map(x=><article key={x.id} style={{padding:12,borderTop:"1px solid #25352d"}}><strong>{x.full_name}</strong><div style={{color:"#9aaba2"}}>{x.email}</div>{x.profile_url&&<a href={x.profile_url} target="_blank" rel="noreferrer" style={{color:"#54d69a"}}>Profile</a>}<p>{x.notes}</p></article>)}</section></main></AppShell>}
const panel:React.CSSProperties={background:"#111a16",border:"1px solid #25352d",borderRadius:16,padding:20};
const input:React.CSSProperties={display:"block",width:"100%",padding:12,marginTop:9,background:"#09110d",border:"1px solid #34483c",borderRadius:9,color:"#edf5ef"};
const primary:React.CSSProperties={background:"#54d69a",color:"#07110c",border:0,padding:"12px 16px",borderRadius:9,fontWeight:700,cursor:"pointer",marginTop:12};
