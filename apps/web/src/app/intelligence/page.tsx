"use client";

import { useEffect, useState } from "react";

type Provider = { configured: boolean; enabled: boolean; healthy: boolean; default: boolean; model: string };
type ProviderResponse = { default_provider: string; fallback_provider: string; providers: Record<string, Provider>; automation_paused: boolean };
type UsageItem = { provider: string; model: string; input_tokens: number; output_tokens: number; requests: number };
type Conversation = { id: number; title: string; updated_at: string };
const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const panel: React.CSSProperties = {background:"#111a16",border:"1px solid #25352d",borderRadius:16,padding:20};
function csrf() { return decodeURIComponent(document.cookie.split("; ").find(x=>x.startsWith("jobseeker_csrf="))?.split("=").slice(1).join("=") || ""); }

export default function IntelligencePage() {
  const [status,setStatus]=useState<ProviderResponse|null>(null);
  const [usage,setUsage]=useState<UsageItem[]>([]);
  const [conversations,setConversations]=useState<Conversation[]>([]);
  const [conversationId,setConversationId]=useState<number|null>(null);
  const [message,setMessage]=useState("");
  const [provider,setProvider]=useState("");
  const [answer,setAnswer]=useState("");
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");

  async function api(path:string, init:RequestInit={}) {
    const headers = new Headers(init.headers);
    if (init.method && init.method !== "GET") headers.set("X-CSRF-Token",csrf());
    const response=await fetch(API+path,{...init,headers,credentials:"include",cache:"no-store"});
    if(response.status===401){window.location.assign("/login");throw new Error("Please sign in to continue");}
    return response;
  }

  async function refresh() {
    try {
      const me=await api("/api/v1/auth/me");
      if(!me.ok) throw new Error("Unable to verify session");
      const [p,u,c]=await Promise.all([
        api("/api/v1/ai/providers"),api("/api/v1/ai/usage"),api("/api/v1/ai/conversations")
      ]);
      if(!p.ok) throw new Error("Provider API unavailable");
      const pd:ProviderResponse=await p.json();setStatus(pd);setProvider(v=>v||pd.default_provider);
      if(u.ok){const ud=await u.json();setUsage(ud.items||[]);}
      if(c.ok)setConversations(await c.json());
    } catch(err){setError(err instanceof Error?err.message:"Unable to reach API");}
  }

  useEffect(()=>{void refresh();},[]);

  async function openConversation(id:number) {
    try {
      const response=await api("/api/v1/ai/conversations/"+id+"/messages");
      if(!response.ok) throw new Error("Unable to load conversation");
      const rows=await response.json();
      setConversationId(id);
      setAnswer(rows.map((row:{role:string;content:string})=>(row.role==="user"?"You":"Assistant")+":\n"+row.content).join("\n\n"));
    } catch(err){setError(err instanceof Error?err.message:"Unable to load conversation");}
  }

  async function send() {
    if(!message.trim())return;
    setBusy(true);setError("");
    try {
      const response=await api("/api/v1/ai/chat",{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({message,provider:provider||undefined,conversation_id:conversationId||undefined})});
      const data=await response.json();
      if(!response.ok)throw new Error(data.detail||"AI request failed");
      setConversationId(data.conversation_id);
      setAnswer(current=>current+"\n\nYou:\n"+message+"\n\nAssistant ("+data.provider+"):\n"+data.text);
      setMessage("");
      await refresh();
    } catch(err){setError(err instanceof Error?err.message:"AI request failed");}
    finally{setBusy(false);}
  }

  const totals=usage.reduce((a,i)=>({input:a.input+i.input_tokens,output:a.output+i.output_tokens,requests:a.requests+i.requests}),{input:0,output:0,requests:0});
  return <main style={{maxWidth:1180,margin:"0 auto",padding:"36px 22px",color:"#edf5ef"}}>
    <nav style={{display:"flex",justifyContent:"space-between",alignItems:"center",gap:12,flexWrap:"wrap"}}>
      <a href="/dashboard" style={{color:"#54d69a",textDecoration:"none"}}>← Career workspace</a>
      <div style={{display:"flex",gap:16,flexWrap:"wrap"}}><a href="/opportunities" style={{color:"#a7b8ad"}}>Opportunities</a><a href="/applications" style={{color:"#a7b8ad"}}>Applications</a><a href="/profile" style={{color:"#a7b8ad"}}>Profile</a></div>
    </nav>
    <header style={{margin:"32px 0"}}><p style={{color:"#54d69a",letterSpacing:2,fontSize:12}}>AI OPERATIONS</p><h1 style={{fontSize:42,margin:"8px 0"}}>Intelligence workspace</h1><p style={{color:"#9aaba2",lineHeight:1.7}}>Your authenticated career copilot, with persisted conversations and per-account usage.</p></header>
    <section style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(180px,1fr))",gap:14}}>
      {Object.entries({Requests:totals.requests.toLocaleString(),"Input tokens":totals.input.toLocaleString(),"Output tokens":totals.output.toLocaleString()}).map(([k,v])=><article key={k} style={panel}><small style={{color:"#9aaba2"}}>{k}</small><div style={{fontSize:28,fontWeight:700,marginTop:8}}>{v}</div></article>)}
    </section>
    <section style={{display:"grid",gridTemplateColumns:"minmax(220px,0.75fr) minmax(0,2fr)",gap:16,marginTop:18}}>
      <aside style={panel}><div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}><h2 style={{fontSize:17}}>Conversations</h2><button onClick={()=>{setConversationId(null);setAnswer("");}} style={smallButton}>New</button></div>
        {conversations.length===0?<p style={{color:"#9aaba2",fontSize:13}}>Your saved conversations will appear here.</p>:conversations.map(c=><button key={c.id} onClick={()=>void openConversation(c.id)} style={{display:"block",width:"100%",textAlign:"left",padding:11,marginTop:7,background:conversationId===c.id?"#1c3829":"#09110d",border:"1px solid #34483c",borderRadius:9,color:"#edf5ef",cursor:"pointer"}}>{c.title}</button>)}
      </aside>
      <section style={panel}>
        <div style={{display:"flex",justifyContent:"space-between",gap:12,flexWrap:"wrap"}}><h2>Career assistant</h2><select value={provider} onChange={e=>setProvider(e.target.value)} style={field}>{Object.keys(status?.providers||{}).map(name=><option key={name} value={name}>{name}</option>)}</select></div>
        {status&&<div style={{display:"flex",gap:8,flexWrap:"wrap",marginBottom:12}}>{Object.entries(status.providers).map(([name,item])=><span key={name} style={{fontSize:12,color:item.healthy?"#54d69a":"#e7b36c"}}>{name}: {item.healthy?"credentials verified":"not verified"}</span>)}</div>}
        <pre style={{whiteSpace:"pre-wrap",minHeight:210,maxHeight:500,overflowY:"auto",background:"#09110d",padding:16,borderRadius:10,color:"#dce9e0",lineHeight:1.7,fontFamily:"inherit"}}>{answer||"Ask for help evaluating a role, improving a CV section, preparing for an interview or planning your next career move."}</pre>
        <textarea value={message} onChange={e=>setMessage(e.target.value)} placeholder="Ask your career copilot…" rows={4} style={{...field,width:"100%",resize:"vertical"}}/>
        <button disabled={busy||!message.trim()} onClick={()=>void send()} style={primaryButton}>{busy?"Working…":"Send message"}</button>
        {error&&<p role="alert" style={{color:"#ff9b87"}}>{error}</p>}
      </section>
    </section>
    <section style={{...panel,marginTop:16}}><h2>Usage by model</h2>{usage.length===0?<p style={{color:"#9aaba2"}}>No recorded AI requests yet.</p>:<div style={{overflowX:"auto"}}><table style={{width:"100%",textAlign:"left",borderCollapse:"collapse"}}><thead><tr>{["Provider","Model","Requests","Input tokens","Output tokens"].map(x=><th key={x} style={{padding:10,color:"#9aaba2"}}>{x}</th>)}</tr></thead><tbody>{usage.map((i,n)=><tr key={i.provider+i.model+n}>{[i.provider,i.model,i.requests.toLocaleString(),i.input_tokens.toLocaleString(),i.output_tokens.toLocaleString()].map((x,j)=><td key={j} style={{padding:10,borderTop:"1px solid #25352d"}}>{x}</td>)}</tr>)}</tbody></table></div>}<p style={{fontSize:12,color:"#9aaba2"}}>Costs are intentionally not estimated until verified, versioned provider pricing is configured. Automation remains paused by default.</p></section>
  </main>;
}
const field:React.CSSProperties={background:"#09110d",color:"#edf5ef",padding:12,border:"1px solid #34483c",borderRadius:9};
const smallButton:React.CSSProperties={background:"#1c3829",color:"#54d69a",padding:"7px 10px",border:"1px solid #345744",borderRadius:8,cursor:"pointer"};
const primaryButton:React.CSSProperties={marginTop:12,padding:"12px 18px",background:"#54d69a",color:"#07110c",border:0,borderRadius:9,fontWeight:700,cursor:"pointer"};
