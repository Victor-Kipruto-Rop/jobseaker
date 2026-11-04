"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Activity, ArrowRight, ArrowUpRight, BriefcaseBusiness, CheckCircle2, Clock3, FileText, FileSearch, ShieldCheck, Sparkles, Target, TrendingUp, Users } from "lucide-react";
import AppShell from "../../components/layout/app-shell";
import styles from "./dashboard.module.css";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
type User = { full_name: string; email: string; is_verified: boolean };
type Application = { id: number; role_title: string; company_name?: string; status: string; created_at?: string; applied_at?: string | null };
type Opportunity = { id: number; title: string; company?: string; location?: string; fit?: { fit_score?: number; matched_skills?: string[]; missing_skills?: string[]; warning?: string } };
type Analytics = { saved_opportunities: number; applications: number; applications_by_status: Record<string, number>; interviews: number; ai_tokens: number };

function csrf() {
  return decodeURIComponent(document.cookie.split("; ").find(item => item.startsWith("jobseeker_csrf="))?.split("=").slice(1).join("=") || "");
}
async function api(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  if (init.method) headers.set("X-CSRF-Token", csrf());
  const response = await fetch(API + path, { ...init, headers, credentials: "include", cache: "no-store" });
  if (response.status === 401) window.location.assign("/login");
  return response;
}
function number(value: number) { return Number(value || 0).toLocaleString(); }
function titleCase(value: string) { return value.replaceAll("_", " ").replace(/\b\w/g, letter => letter.toUpperCase()); }

export default function Dashboard() {
  const [user, setUser] = useState<User | null>(null);
  const [applications, setApplications] = useState<Application[]>([]);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [verification, setVerification] = useState("");
  const [verificationBusy, setVerificationBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [userResponse, appResponse, opportunityResponse, analyticsResponse] = await Promise.all([
        api("/api/v1/auth/me"), api("/api/v1/applications"), api("/api/v1/opportunities"), api("/api/v1/analytics/overview"),
      ]);
      if (!userResponse.ok) throw new Error("Your session could not be verified. Please sign in again.");
      const [userData, appData, opportunityData, analyticsData] = await Promise.all([
        userResponse.json(), appResponse.ok ? appResponse.json() : [], opportunityResponse.ok ? opportunityResponse.json() : [],
        analyticsResponse.ok ? analyticsResponse.json() : null,
      ]);
      setUser(userData);
      setApplications(Array.isArray(appData) ? appData : []);
      setOpportunities(Array.isArray(opportunityData) ? opportunityData : []);
      setAnalytics(analyticsData);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load your workspace.");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const counts = analytics?.applications_by_status || {};
  const pipeline = useMemo(() => {
    const ordered = ["draft", "ready", "approved", "submitted", "screening", "interview", "assessment", "offer", "accepted"];
    return ordered.map(status => ({ status, count: Number(counts[status] || 0) })).filter(item => item.count > 0);
  }, [counts]);
  const maxPipeline = Math.max(1, ...pipeline.map(item => item.count));
  const activeApplications = applications.filter(item => !["archived", "rejected", "withdrawn", "accepted"].includes(item.status));
  const firstName = user?.full_name?.trim().split(/\s+/)[0] || user?.email?.split("@")[0] || "there";
  const topOpportunity = [...opportunities].sort((a, b) => Number(b.fit?.fit_score || 0) - Number(a.fit?.fit_score || 0))[0];
  const recentApplications = applications.slice(0, 5);

  async function logout() {
    await api("/api/v1/auth/logout", { method: "POST" });
    window.location.assign("/login");
  }
  async function requestVerification() {
    setVerificationBusy(true); setVerification("");
    try {
      const response = await api("/api/v1/auth/verification/request", { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Unable to request verification.");
      setVerification(data.status === "sent" ? "Verification email requested. Check your inbox." : "Verification request accepted. Follow the instructions for your environment.");
    } catch (cause) { setVerification(cause instanceof Error ? cause.message : "Verification request failed."); }
    finally { setVerificationBusy(false); }
  }

  return <AppShell user={user} onLogout={() => void logout()}>
    <div className={styles.page}>
      <header className={styles.pageHeader}>
        <div><p className={styles.eyebrow}>CAREER OPERATIONS / OVERVIEW</p><h1 className={styles.pageTitle}>Good to see you, {firstName}.</h1><p className={styles.pageSubtitle}>Your career search, opportunities and next steps in one place.</p></div>
        <div className={styles.headerActions}><a className={styles.secondaryAction} href="/applications"><BriefcaseBusiness size={14}/> Track applications</a><a className={styles.primaryAction} href="/discovery"><FileSearch size={14}/> Discover opportunities <ArrowUpRight size={14}/></a></div>
      </header>

      {user && !user.is_verified && <div className={styles.alert}><strong>Verify your email to unlock account-sensitive integrations.</strong> Your workspace remains available while verification is pending. <button disabled={verificationBusy} onClick={() => void requestVerification()}>{verificationBusy ? "Requesting…" : "Request verification"}</button>{verification && <div role="status" style={{marginTop:7}}>{verification}</div>}</div>}

      {loading ? <div className={styles.loading}>Loading your career workspace…</div> : error ? <div className={styles.error} role="alert">{error}<p><button className={styles.secondaryAction} onClick={() => void load()}>Try again</button></p></div> : <>
        <section className={styles.hero}>
          <div className={styles.heroCopy}>
            <span className={styles.heroTag}><Sparkles size={13}/> YOUR CAREER COMMAND CENTRE</span>
            <h2 className={styles.heroTitle}>Make your next move with clarity.</h2>
            <p className={styles.heroDescription}>Turn job discovery into a deliberate process. Review your strongest matches, keep applications moving and use your data to decide what deserves attention next.</p>
            <div className={styles.heroActions}><a className={styles.primaryAction} href="/discovery">Explore matching roles <ArrowRight size={14}/></a><a className={styles.secondaryAction} href="/intelligence">Open career intelligence</a></div>
          </div>
          <div className={styles.heroAside}><span className={styles.heroAsideLabel}>ACTIVE APPLICATIONS</span><strong className={styles.heroAsideValue}>{number(activeApplications.length)}</strong><span className={styles.heroAsideFoot}>Roles still moving through your pipeline</span></div>
        </section>

        <section className={styles.metrics} aria-label="Career metrics">
          <article className={styles.metric}><div className={styles.metricTop}><span>Saved opportunities</span><span className={styles.metricIcon}><Target size={15}/></span></div><div className={styles.metricValue}>{number(analytics?.saved_opportunities ?? opportunities.length)}</div><div className={styles.metricFoot}>Roles in your opportunity library</div></article>
          <article className={styles.metric}><div className={styles.metricTop}><span>Applications</span><span className={styles.metricIcon}><BriefcaseBusiness size={15}/></span></div><div className={styles.metricValue}>{number(analytics?.applications ?? applications.length)}</div><div className={styles.metricFoot}>Across all application stages</div></article>
          <article className={styles.metric}><div className={styles.metricTop}><span>Interviews</span><span className={styles.metricIcon}><Users size={15}/></span></div><div className={styles.metricValue}>{number(analytics?.interviews ?? 0)}</div><div className={styles.metricFoot}>Recorded in your interview workspace</div></article>
          <article className={styles.metric}><div className={styles.metricTop}><span>AI activity</span><span className={styles.metricIcon}><Activity size={15}/></span></div><div className={styles.metricValue}>{number(analytics?.ai_tokens ?? 0)}</div><div className={styles.metricFoot}>Input and output tokens recorded</div></article>
        </section>

        <div className={styles.gridMain}>
          <section className={styles.panel}>
            <div className={styles.panelHeader}><div><h2 className={styles.panelTitle}>Application pipeline</h2><p className={styles.panelDescription}>A live view of where your applications currently stand</p></div><a className={styles.textLink} href="/applications">Manage pipeline <ArrowUpRight size={13}/></a></div>
            {pipeline.length ? <div className={styles.pipeline}>{pipeline.map(item => <div className={styles.pipelineRow} key={item.status}><span className={styles.pipelineLabel}>{titleCase(item.status)}</span><div className={styles.track} role="progressbar" aria-label={titleCase(item.status)} aria-valuemin={0} aria-valuemax={maxPipeline} aria-valuenow={item.count}><div className={styles.fill} style={{width: (item.count / maxPipeline * 100) + "%"}}/></div><span className={styles.pipelineCount}>{item.count}</span></div>)}</div> : <div className={styles.empty}>Your application pipeline will appear here once you create your first application.<br/><a href="/discovery">Find an opportunity to get started →</a></div>}
          </section>
          <section className={styles.panel}>
            <div className={styles.panelHeader}><div><h2 className={styles.panelTitle}>Your next best moves</h2><p className={styles.panelDescription}>Actions based on what is actually in your workspace</p></div><Sparkles size={16} color="#83dca4"/></div>
            <div className={styles.insightList}>
              {applications.length === 0 && <div className={styles.insight}><span className={styles.insightIcon}><FileSearch size={15}/></span><div className={styles.insightText}><strong>Start with targeted discovery</strong><p>Search relevant job boards and save roles that match your target profile.</p></div></div>}
              {applications.some(item => item.status === "draft") && <div className={styles.insight}><span className={styles.insightIcon}><FileText size={15}/></span><div className={styles.insightText}><strong>Review your application drafts</strong><p>{applications.filter(item => item.status === "draft").length} draft applications are waiting for your attention.</p></div></div>}
              {applications.some(item => item.status === "ready") && <div className={styles.insight}><span className={styles.insightIcon}><ShieldCheck size={15}/></span><div className={styles.insightText}><strong>Review approval requirements</strong><p>Ready applications need your explicit approval before they can be recorded as submitted.</p></div></div>}
              {activeApplications.length > 0 && <div className={styles.insight}><span className={styles.insightIcon}><Clock3 size={15}/></span><div className={styles.insightText}><strong>Keep your pipeline current</strong><p>Update application stages when an employer responds or your status changes.</p></div></div>}
              {applications.length > 0 && opportunities.length === 0 && <div className={styles.insight}><span className={styles.insightIcon}><Target size={15}/></span><div className={styles.insightText}><strong>Build your opportunity pipeline</strong><p>Save promising roles so you can compare fit and create drafts from them.</p></div></div>}
              {applications.length > 0 && !applications.some(item => ["draft", "ready"].includes(item.status)) && activeApplications.length === 0 && <div className={styles.insight}><span className={styles.insightIcon}><CheckCircle2 size={15}/></span><div className={styles.insightText}><strong>Your active pipeline is clear</strong><p>Review your outcomes and discover the next set of relevant opportunities.</p></div></div>}
            </div>
          </section>
        </div>

        <div className={styles.bottomGrid}>
          <section className={styles.panel}>
            <div className={styles.panelHeader}><div><h2 className={styles.panelTitle}>Recent applications</h2><p className={styles.panelDescription}>The latest roles added to your tracker</p></div><a className={styles.textLink} href="/applications">View all <ArrowUpRight size={13}/></a></div>
            {recentApplications.length ? <div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>ROLE / COMPANY</th><th>STATUS</th><th>ADDED</th></tr></thead><tbody>{recentApplications.map(item => <tr key={item.id}><td className={styles.roleName}>{item.role_title}<span className={styles.companyName}>{item.company_name || "Company not specified"}</span></td><td><span className={styles.status}>{titleCase(item.status)}</span></td><td>{item.created_at ? new Date(item.created_at).toLocaleDateString() : "—"}</td></tr>)}</tbody></table></div> : <div className={styles.empty}>No applications recorded yet. Create a draft from a saved opportunity or add one manually.<br/><a href="/applications">Open application tracker →</a></div>}
          </section>
          <section className={styles.panel}>
            <div className={styles.panelHeader}><div><h2 className={styles.panelTitle}>Strongest saved match</h2><p className={styles.panelDescription}>Based on recorded skill coverage</p></div><TrendingUp size={16} color="#83dca4"/></div>
            {topOpportunity ? <div className={styles.opportunityList}><div className={styles.opportunity}><span className={styles.companyMark}>{(topOpportunity.company || topOpportunity.title || "J").slice(0,1).toUpperCase()}</span><div className={styles.opportunityCopy}><strong>{topOpportunity.title}</strong><small>{topOpportunity.company || "Company not specified"}{topOpportunity.location ? " · " + topOpportunity.location : ""}</small></div><span className={styles.fitScore}>{Math.round(topOpportunity.fit?.fit_score || 0)}%</span></div><p className={styles.panelDescription}>{topOpportunity.fit?.matched_skills?.length || 0} matched skills · {topOpportunity.fit?.missing_skills?.length || 0} skill gaps</p><a className={styles.textLink} href="/opportunities">Review saved opportunities <ArrowRight size={13}/></a></div> : <div className={styles.empty}>No saved opportunities with fit evidence yet.<br/><a href="/discovery">Discover and save roles →</a></div>}
          </section>
        </div>
      </>}
    </div>
  </AppShell>;
}

