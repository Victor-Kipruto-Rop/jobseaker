"use client";

import { FormEvent, useEffect, useState } from "react";
import { Activity, ArrowRight, CheckCircle2, Eye, EyeOff, LockKeyhole, Mail } from "lucide-react";
import styles from "./login.module.css";

const API=process.env.NEXT_PUBLIC_API_BASE_URL||"http://localhost:8000";
function cookie(name:string){return document.cookie.split("; ").find(item=>item.startsWith(name+"="))?.split("=").slice(1).join("=")||"";}

export default function LoginPage(){
 const [mode,setMode]=useState<"login"|"register">("login");
 const [email,setEmail]=useState("");const [password,setPassword]=useState("");const [fullName,setFullName]=useState("");
 const [error,setError]=useState("");const [busy,setBusy]=useState(false);const [showPassword,setShowPassword]=useState(false);
 useEffect(()=>{void fetch(API+"/api/v1/auth/csrf",{credentials:"include",cache:"no-store"});},[]);
 async function submit(event:FormEvent){
  event.preventDefault();setBusy(true);setError("");
  try{if(!cookie("jobseeker_csrf")){const r=await fetch(API+"/api/v1/auth/csrf",{credentials:"include",cache:"no-store"});if(!r.ok)throw new Error("Unable to initialize secure sign-in. Refresh and try again.");}
   const token=decodeURIComponent(cookie("jobseeker_csrf"));if(!token)throw new Error("Secure sign-in token is missing. Refresh and try again.");
   const endpoint=mode==="login"?"login":"register";
   const response=await fetch(API+"/api/v1/auth/"+endpoint,{method:"POST",credentials:"include",headers:{"Content-Type":"application/json","X-CSRF-Token":token},body:JSON.stringify(mode==="login"?{email,password}:{email,password,full_name:fullName})});
   const data=await response.json();if(!response.ok)throw new Error(data.detail||"Authentication failed.");window.location.assign("/dashboard");
  }catch(e){setError(e instanceof Error?e.message:"Unable to authenticate.");}finally{setBusy(false);}
 }
 return <main className={styles.layout}>
  <section className={styles.story}>
   <a href="/" className={styles.brand}><span><Activity size={18}/></span>jobseeker<span className={styles.brandDot}>.</span></a>
   <div className={styles.storyCopy}><div className={styles.eyebrow}>A MORE DELIBERATE WAY TO MOVE FORWARD</div><h1>Make your next career move <em>count.</em></h1><p>Bring opportunity discovery, application tracking and your professional evidence into one considered workspace.</p>
    <div className={styles.storyPoints}><div><CheckCircle2 size={15}/><span>Roles matched against your recorded skills</span></div><div><CheckCircle2 size={15}/><span>Applications tracked through a clear lifecycle</span></div><div><CheckCircle2 size={15}/><span>AI-assisted drafts remain yours to review</span></div></div>
   </div>
   <div className={styles.storyFoot}>PRIVATE BY DESIGN <span>·</span> EXPLICIT APPROVAL FOR EXTERNAL ACTIONS</div>
  </section>
  <section className={styles.formSide}><div className={styles.formWrap}>
   <div className={styles.mobileBrand}><span><Activity size={17}/></span>jobseeker<span>.</span></div>
   <div className={styles.formEyebrow}>{mode==="login"?"YOUR CAREER WORKSPACE":"START WITH YOUR PROFILE"}</div><h2>{mode==="login"?"Welcome back.":"Create your account."}</h2><p className={styles.formIntro}>{mode==="login"?"Sign in to continue where you left off.":"Set up a private workspace for your career search."}</p>
   <form onSubmit={submit}>
    {mode==="register"&&<label>Full name<input required minLength={2} maxLength={160} value={fullName} onChange={e=>setFullName(e.target.value)} autoComplete="name" placeholder="Your full name"/></label>}
    <label>Email address<span className={styles.inputWrap}><Mail size={15}/><input required type="email" value={email} onChange={e=>setEmail(e.target.value)} autoComplete="email" placeholder="you@example.com"/></span></label>
    <label>Password<span className={styles.inputWrap}><LockKeyhole size={15}/><input required minLength={mode==="register"?12:1} maxLength={128} type={showPassword?"text":"password"} value={password} onChange={e=>setPassword(e.target.value)} autoComplete={mode==="login"?"current-password":"new-password"} placeholder={mode==="register"?"At least 12 characters":"Enter your password"}/><button type="button" onClick={()=>setShowPassword(x=>!x)} aria-label={showPassword?"Hide password":"Show password"}>{showPassword?<EyeOff size={15}/>:<Eye size={15}/>}</button></span></label>
    {mode==="register"&&<small className={styles.helper}>Use at least 12 characters. Your password is never shown again.</small>}
    {error&&<p className={styles.error} role="alert">{error}</p>}
    {mode==="login"&&<div className={styles.forgot}><a href="/forgot-password">Forgot password?</a></div>}
    <button className={styles.submit} disabled={busy}>{busy?"Please wait…":mode==="login"?"Sign in to workspace":"Create secure account"}<ArrowRight size={15}/></button>
   </form>
   <div className={styles.switchMode}>{mode==="login"?"New to JobSeeker?":"Already have an account?"}<button onClick={()=>{setMode(mode==="login"?"register":"login");setError("");}}>{mode==="login"?"Create an account":"Sign in"}</button></div>
   <div className={styles.formFoot}><LockKeyhole size={12}/> Protected by secure sessions and account-scoped access.</div>
  </div></section>
 </main>;
}
