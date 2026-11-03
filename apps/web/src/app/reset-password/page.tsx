"use client";
import {useEffect,useState} from "react";
const API=process.env.NEXT_PUBLIC_API_BASE_URL||"http://localhost:8000";
function csrf(){return decodeURIComponent(document.cookie.split("; ").find(x=>x.startsWith("jobseeker_csrf="))?.split("=").slice(1).join("=")||"");}
export default function ResetPassword(){const [token,setToken]=useState("");const [password,setPassword]=useState("");const [status,setStatus]=useState("");
useEffect(()=>{setToken(new URLSearchParams(window.location.search).get("token")||"");},[]);
async function submit(e:React.FormEvent){e.preventDefault();const r=await fetch(API+"/api/v1/auth/password-reset/confirm",{method:"POST",headers:{"Content-Type":"application/json","X-CSRF-Token":csrf()},body:JSON.stringify({token,new_password:password})});const d=await r.json();setStatus(r.ok?"Password changed. All existing sessions were revoked. Sign in again.":(d.detail||"Unable to reset password"));}
return <main style={{maxWidth:460,margin:"12vh auto",padding:28,color:"#edf5ef",background:"#111a16",border:"1px solid #25352d",borderRadius:18}}><h1>Choose a new password</h1><form onSubmit={submit}><input required minLength={12} maxLength={128} type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="New password (12+ characters)" style={input}/><button style={primary}>Update password</button></form>{status&&<p role="status">{status}</p>}</main>}
const input:React.CSSProperties={display:"block",width:"100%",padding:12,background:"#09110d",border:"1px solid #34483c",borderRadius:9,color:"#edf5ef"};
const primary:React.CSSProperties={marginTop:14,padding:12,background:"#54d69a",border:0,borderRadius:9,fontWeight:700,cursor:"pointer"};
