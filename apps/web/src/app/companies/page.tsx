"use client";

import AppShell from "../../components/layout/app-shell";


import {useEffect,useState} from "react";
const API=process.env.NEXT_PUBLIC_API_BASE_URL||"http://localhost:8000";
function csrf(){return decodeURIComponent(document.cookie.split("; ").find(x=>x.startsWith("jobseeker_csrf="))?.split("=").slice(1).join("=")||"");}
async function api(path:string,init:RequestInit={}){const h=new Headers(init.headers);if(init.method)h.set("X-CSRF-Token",csrf());const r=await fetch(API+path,{...init,headers:h,credentials:"include"});if(r.status===401)window.location.assign("/login");return r;}
export default function Companies(){const [rows,setRows]=useState<any[]>([]);const [name,setName]=useState("");const [website,setWebsite]=useState("");const [careers,setCareers]=useState("");const [description,setDescription]=useState("");
async function load(){const r=await api("/api/v1/companies");if(r.ok)setRows(await r.json());}
useEffect(()=>{void load();},[]);
async function add(e:React.FormEvent){e.preventDefault();const r=await api("/api/v1/companies",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name,website,careers_url:careers,description})});if(r.ok){setName("");setWebsite("");setCareers("");setDescription("");await load();}}
return <AppShell><main style={{maxWidth:1000,margin:"0 auto",padding:32,color:"#edf5ef"}}><a href="/dashboard" style={{color:"#54d69a"}}>← Workspace</a><h1>Company intelligence</h1><p style={{color:"#9aaba2"}}>Build a sourced company list and retain career-page references and research notes.</p><form onSubmit={add} style={panel}><h2>Add company</h2><input style={input} required placeholder="Company name" value={name} onChange={e=>setName(e.target.value)}/><input style={input} placeholder="Company website" value={website} onChange={e=>setWebsite(e.target.value)}/><input style={input} placeholder="Careers page URL" value={careers} onChange={e=>setCareers(e.target.value)}/><textarea style={input} placeholder="Company research notes and evidence" value={description} onChange={e=>setDescription(e.target.value)}/><button style={primary}>Save company</button></form><section style={{...panel,marginTop:18}}><h2>Saved companies ({rows.length})</h2>{rows.map(x=><article key={x.id} style={{padding:12,borderTop:"1px solid #25352d"}}><strong>{x.name}</strong><p>{x.description}</p>{x.website&&<a href={x.website} target="_blank" rel="noreferrer" style={{color:"#54d69a"}}>Website</a>} {x.careers_url&&<a href={x.careers_url} target="_blank" rel="noreferrer" style={{color:"#54d69a",marginLeft:12}}>Careers</a>}</article>)}</section></main></AppShell>}
const panel:React.CSSProperties={background:"#111a16",border:"1px solid #25352d",borderRadius:16,padding:20};
const input:React.CSSProperties={display:"block",width:"100%",padding:12,marginTop:9,background:"#09110d",border:"1px solid #34483c",borderRadius:9,color:"#edf5ef"};
const primary:React.CSSProperties={background:"#54d69a",color:"#07110c",border:0,padding:"12px 16px",borderRadius:9,fontWeight:700,cursor:"pointer",marginTop:12};
