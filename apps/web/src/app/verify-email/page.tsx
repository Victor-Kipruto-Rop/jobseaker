"use client";
import {useEffect,useState} from "react";
const API=process.env.NEXT_PUBLIC_API_BASE_URL||"http://localhost:8000";
export default function VerifyEmail(){const [token,setToken]=useState("");const [status,setStatus]=useState("Confirming email address…");
useEffect(()=>{const value=new URLSearchParams(window.location.search).get("token")||"";setToken(value);if(value){void fetch(API+"/api/v1/auth/verification/confirm",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({token:value})}).then(async r=>{const d=await r.json();setStatus(r.ok?"Email address verified. You can return to your workspace.":(d.detail||"Verification failed"));});}else setStatus("Verification token is missing.");},[]);
return <main style={{maxWidth:500,margin:"12vh auto",padding:28,color:"#edf5ef",background:"#111a16",border:"1px solid #25352d",borderRadius:18}}><h1>Email verification</h1><p role="status">{status}</p><a href="/dashboard" style={{color:"#54d69a"}}>Return to workspace</a></main>}
