"use client";

import { FormEvent, useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
function cookie(name: string) {
  return document.cookie.split("; ").find(item => item.startsWith(name + "="))?.split("=").slice(1).join("=") || "";
}

export default function LoginPage() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { void fetch(API + "/api/v1/auth/csrf", { credentials: "include" }); }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const endpoint = mode === "login" ? "login" : "register";
      const response = await fetch(API + "/api/v1/auth/" + endpoint, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": decodeURIComponent(cookie("jobseeker_csrf")) },
        body: JSON.stringify(mode === "login" ? { email, password } : { email, password, full_name: fullName }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Authentication failed");
      window.location.assign("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to authenticate");
    } finally {
      setBusy(false);
    }
  }

  return <main style={{minHeight:"100vh",display:"grid",gridTemplateColumns:"minmax(0,1fr) minmax(320px,520px)",background:"#07110c",color:"#edf5ef"}}>
    <section style={{padding:"clamp(28px,7vw,90px)",display:"flex",flexDirection:"column",justifyContent:"space-between",background:"radial-gradient(circle at 15% 20%,#173b2b 0,transparent 48%),#09140e"}}>
      <a href="/" style={{color:"#54d69a",fontWeight:800,fontSize:22,textDecoration:"none"}}>JobSeeker<span style={{color:"#edf5ef"}}>.</span></a>
      <div style={{maxWidth:620}}>
        <p style={{color:"#54d69a",letterSpacing:3,fontSize:12}}>CAREER OPERATIONS INTELLIGENCE</p>
        <h1 style={{fontSize:"clamp(42px,6vw,76px)",lineHeight:1.02,letterSpacing:-2}}>Build a more intentional career.</h1>
        <p style={{color:"#a7b8ad",fontSize:18,lineHeight:1.8}}>Discover opportunities, understand your strengths and organize every application in one secure workspace.</p>
      </div>
      <small style={{color:"#708579"}}>Your data stays tied to your account. External actions remain approval-gated.</small>
    </section>
    <section style={{display:"grid",placeItems:"center",padding:28}}>
      <form onSubmit={submit} style={{width:"100%",maxWidth:400,background:"#111a16",border:"1px solid #25352d",borderRadius:20,padding:28}}>
        <p style={{color:"#54d69a",fontSize:12,letterSpacing:2}}>{mode === "login" ? "WELCOME BACK" : "CREATE YOUR ACCOUNT"}</p>
        <h2 style={{fontSize:30,margin:"8px 0 24px"}}>{mode === "login" ? "Sign in" : "Get started"}</h2>
        {mode === "register" && <label style={{display:"block",fontSize:13,color:"#a7b8ad",marginBottom:14}}>Full name<input required minLength={2} maxLength={160} value={fullName} onChange={e=>setFullName(e.target.value)} autoComplete="name" style={field}/></label>}
        <label style={{display:"block",fontSize:13,color:"#a7b8ad",marginBottom:14}}>Email address<input required type="email" value={email} onChange={e=>setEmail(e.target.value)} autoComplete="email" style={field}/></label>
        <label style={{display:"block",fontSize:13,color:"#a7b8ad",marginBottom:8}}>Password<input required minLength={mode === "register" ? 12 : 1} maxLength={128} type="password" value={password} onChange={e=>setPassword(e.target.value)} autoComplete={mode === "login" ? "current-password" : "new-password"} style={field}/></label>
        {mode === "register" && <small style={{color:"#81958a"}}>Use at least 12 characters.</small>}
        {error && <p role="alert" style={{color:"#ff9b87",fontSize:13}}>{error}</p>}
        <button disabled={busy} type="submit" style={{width:"100%",marginTop:20,padding:14,background:"#54d69a",border:0,borderRadius:10,fontWeight:800,color:"#07110c",cursor:"pointer"}}>{busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}</button>
        <p style={{textAlign:"center",fontSize:13,color:"#a7b8ad",marginTop:22}}>{mode === "login" ? "New to JobSeeker?" : "Already have an account?"} <button type="button" onClick={()=>{setMode(mode==="login"?"register":"login");setError("");}} style={{background:"none",border:0,color:"#54d69a",cursor:"pointer",fontWeight:700}}>{mode==="login"?"Create account":"Sign in"}</button></p>
      </form>
    </section>
    <style jsx>{`@media(max-width:760px){main{grid-template-columns:1fr!important}main section:first-child{min-height:260px;padding:28px!important}main section:first-child h1{font-size:42px}}`}</style>
  </main>;
}

const field: React.CSSProperties = {display:"block",width:"100%",marginTop:7,padding:12,background:"#09110d",color:"#edf5ef",border:"1px solid #34483c",borderRadius:9,outline:"none"};
