"use client";

import { useEffect, useState } from "react";

type Provider = { configured: boolean; enabled: boolean; healthy: boolean; default: boolean; model: string };
type ProviderResponse = { default_provider: string; fallback_provider: string; providers: Record<string, Provider>; automation_paused: boolean };

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export default function IntelligencePage() {
  const [status, setStatus] = useState<ProviderResponse | null>(null);
  const [message, setMessage] = useState("");
  const [provider, setProvider] = useState("");
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function refresh() {
    try {
      const response = await fetch(`${API}/api/v1/ai/providers`, { cache: "no-store" });
      if (!response.ok) throw new Error(`API returned ${response.status}`);
      const data: ProviderResponse = await response.json();
      setStatus(data);
      setProvider((current) => current || data.default_provider);
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
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, provider: provider || undefined }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "AI request failed");
      setAnswer(data.text || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI request failed");
    } finally {
      setBusy(false);
    }
  }

  return <main style={{maxWidth:1100,margin:"0 auto",padding:"42px 24px"}}>
    <a href="/" style={{color:"#54d69a"}}>← Career workspace</a>
    <header style={{margin:"34px 0"}}>
      <p style={{color:"#54d69a",letterSpacing:2,fontSize:12}}>AI OPERATIONS</p>
      <h1 style={{fontSize:42,margin:"8px 0"}}>Intelligence workspace</h1>
      <p style={{color:"#9aaba2",lineHeight:1.7}}>Connect your approved AI providers and test career-assistance workflows. Credentials stay on the API server.</p>
    </header>
    <section style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(220px,1fr))",gap:14}}>
      {status && Object.entries(status.providers).map(([name,item])=><article key={name} style={{background:"#111a16",border:"1px solid #25352d",borderRadius:16,padding:20}}>
        <div style={{display:"flex",justifyContent:"space-between",gap:12}}><h2 style={{textTransform:"capitalize",margin:0}}>{name}</h2><span style={{color:item.healthy?"#54d69a":"#e7b36c"}}>{item.healthy?"Ready":"Unavailable"}</span></div>
        <p style={{color:"#9aaba2",fontSize:13}}>{item.model}</p>
        <small style={{color:"#9aaba2"}}>{item.default?"Default provider":"Configured provider"}</small>
      </article>)}
      {!status && <article style={{background:"#111a16",padding:20,borderRadius:16,color:"#9aaba2"}}>Loading provider status…</article>}
    </section>
    <section style={{marginTop:24,background:"#111a16",border:"1px solid #25352d",borderRadius:18,padding:22}}>
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
    <p style={{marginTop:18,color:"#9aaba2",fontSize:12}}>Automation: {status?.automation_paused===false?"enabled by configuration":"paused"} · AI responses are drafts and require human review.</p>
  </main>;
}
