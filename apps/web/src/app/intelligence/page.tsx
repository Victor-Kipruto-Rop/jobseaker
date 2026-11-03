"use client";

import { useEffect, useState } from "react";

type Provider = { configured: boolean; enabled: boolean; healthy: boolean; default: boolean; model: string };
type ProviderResponse = { default_provider: string; fallback_provider: string; providers: Record<string, Provider>; automation_paused: boolean };
type UsageItem = { provider: string; model: string; input_tokens: number; output_tokens: number; requests: number };
const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const panel: React.CSSProperties = {background:"#111a16",border:"1px solid #25352d",borderRadius:16,padding:20};

export default function IntelligencePage() {
  const [status, setStatus] = useState<ProviderResponse | null>(null);
  const [usage, setUsage] = useState<UsageItem[]>([]);
  const [message, setMessage] = useState("");
  const [provider, setProvider] = useState("");
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function refresh() {
    try {
      const [providerResponse, usageResponse] = await Promise.all([
        fetch(`${API}/api/v1/ai/providers`, {cache:"no-store"}),
        fetch(`${API}/api/v1/ai/usage`, {cache:"no-store"}),
      ]);
      if (!providerResponse.ok) throw new Error(`Provider API returned ${providerResponse.status}`);
      const data: ProviderResponse = await providerResponse.json();
      setStatus(data);
      setProvider(current => current || data.default_provider);
      if (usageResponse.ok) {
        const usageData = await usageResponse.json();
        setUsage(usageData.items || []);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to reach the local API");
    }
  }

  useEffect(() => { void refresh(); }, []);

  async function send() {
    if (!message.trim()) return;
    setBusy(true); setError(""); setAnswer("");
    try {
      const response = await fetch(`${API}/api/v1/ai/chat`, {
        method:"POST", headers:{"Content-Type":"application/json"},
        body:JSON.stringify({message, provider:provider || undefined}),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "AI request failed");
      setAnswer(data.text || "");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI request failed");
    } finally { setBusy(false); }
  }

  const totals = usage.reduce((acc,item)=>({input:acc.input+item.input_tokens,output:acc.output+item.output_tokens,requests:acc.requests+item.requests}),{input:0,output:0,requests:0});

  return <main style={{maxWidth:1100,margin:"0 auto",padding:"42px 24px"}}>
    <a href="/" style={{color:"#54d69a"}}>← Career workspace</a>
    <header style={{margin:"34px 0"}}>
      <p style={{color:"#54d69a",letterSpacing:2,fontSize:12}}>AI OPERATIONS</p>
      <h1 style={{fontSize:42,margin:"8px 0"}}>Intelligence workspace</h1>
      <p style={{color:"#9aaba2",lineHeight:1.7}}>Configure server-side AI providers, test career workflows and inspect persisted token usage.</p>
    </header>
    <section style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(210px,1fr))",gap:14}}>
      {Object.entries({Requests:totals.requests.toLocaleString(), "Input tokens":totals.input.toLocaleString(),"Output tokens":totals.output.toLocaleString()}).map(([label,value])=><article key={label} style={panel}><small style={{color:"#9aaba2"}}>{label}</small><div style={{fontSize:28,fontWeight:700,marginTop:8}}>{value}</div></article>)}
    </section>
    <section style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(220px,1fr))",gap:14,marginTop:16}}>
      {status && Object.entries(status.providers).map(([name,item])=><article key={name} style={panel}>
        <div style={{display:"flex",justifyContent:"space-between",gap:12}}><h2 style={{textTransform:"capitalize",margin:0}}>{name}</h2><span style={{color:item.healthy?"#54d69a":"#e7b36c"}}>{item.healthy?"Adapter OK":"Check failed"}</span></div>
        <p style={{color:"#9aaba2",fontSize:13}}>{item.model}</p>
        <small style={{color:"#9aaba2"}}>{item.default?"Default provider":"Configured provider"}</small>
      </article>)}
      {!status && <article style={panel}>Loading provider status…</article>}
    </section>
    <section style={{...panel,marginTop:24}}>
      <h2>Test the career assistant</h2>
      <label style={{display:"block",color:"#9aaba2",fontSize:13,marginBottom:8}}>Provider</label>
      <select value={provider} onChange={e=>setProvider(e.target.value)} style={{background:"#09110d",color:"#edf5ef",padding:12,border:"1px solid #34483c",borderRadius:9}}>
        {Object.keys(status?.providers || {}).map(name=><option key={name} value={name}>{name}</option>)}
      </select>
      <textarea value={message} onChange={e=>setMessage(e.target.value)} placeholder="Ask for help tailoring a CV summary or evaluating a job description…" rows={5} style={{display:"block",width:"100%",marginTop:14,padding:14,background:"#09110d",color:"#edf5ef",border:"1px solid #34483c",borderRadius:10,resize:"vertical"}}/>
      <button disabled={busy || !message.trim()} onClick={()=>void send()} style={{marginTop:12,padding:"12px 18px",background:"#54d69a",color:"#07110c",border:0,borderRadius:9,fontWeight:700,cursor:"pointer"}}>{busy?"Working…":"Send request"}</button>
      {error && <p role="alert" style={{color:"#ff9b87"}}>{error}</p>}
      {answer && <pre style={{whiteSpace:"pre-wrap",lineHeight:1.7,background:"#09110d",padding:18,borderRadius:10,overflowX:"auto"}}>{answer}</pre>}
    </section>
    <section style={{...panel,marginTop:16}}>
      <h2>Usage by model</h2>
      {usage.length===0?<p style={{color:"#9aaba2"}}>No recorded AI requests yet.</p>:<div style={{overflowX:"auto"}}><table style={{width:"100%",textAlign:"left",borderCollapse:"collapse"}}><thead><tr>{["Provider","Model","Requests","Input tokens","Output tokens"].map(x=><th key={x} style={{padding:"10px 8px",color:"#9aaba2"}}>{x}</th>)}</tr></thead><tbody>{usage.map((item,index)=><tr key={item.provider+item.model+index}>{[item.provider,item.model,item.requests.toLocaleString(),item.input_tokens.toLocaleString(),item.output_tokens.toLocaleString()].map((x,i)=><td key={i} style={{padding:"10px 8px",borderTop:"1px solid #25352d"}}>{x}</td>)}</tr>)}</tbody></table></div>}
      <p style={{color:"#9aaba2",fontSize:12}}>Monetary cost is not displayed until verified provider pricing is configured. This ledger is installation-wide in the current development build.</p>
    </section>
    <p style={{marginTop:18,color:"#9aaba2",fontSize:12}}>Automation: {status?.automation_paused===false?"enabled by configuration":"paused"} · AI responses are drafts and require human review.</p>
  </main>;
}
