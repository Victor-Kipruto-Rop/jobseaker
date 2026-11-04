"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode, KeyboardEvent } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity, Bell, BriefcaseBusiness, CalendarDays, CheckCheck, ChevronDown,
  CircleHelp, Command, Compass, FileText, FolderKanban, GraduationCap,
  LayoutDashboard, LogOut, Menu, Plus, Search, Settings2, ShieldCheck,
  Sparkles, StickyNote, Target, TrendingUp, UserRound, WandSparkles, X,
  ListTodo, BarChart3, Bookmark, CalendarCheck, Users, ChartNoAxesCombined
} from "lucide-react";
import styles from "./app-shell.module.css";

type User = { full_name?: string; email?: string; is_verified?: boolean };
type AppShellProps = { children: ReactNode; user?: User | null; onLogout?: () => void };
type Notice = { id: number; title: string; body: string; read_at?: string | null; created_at?: string };
type SearchRecord = { id: number; title: string; subtitle: string; href: string; kind: string };

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
function csrf() {
  return decodeURIComponent(document.cookie.split("; ").find(item => item.startsWith("jobseeker_csrf="))?.split("=").slice(1).join("=") || "");
}
async function api(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  if (init.method) headers.set("X-CSRF-Token", csrf());
  return fetch(API + path, { ...init, headers, credentials: "include", cache: "no-store" });
}

const navGroups = [
  { heading: "WORKSPACE", items: [
    { label: "Overview", href: "/dashboard", icon: LayoutDashboard },
    { label: "Discover jobs", href: "/opportunities", icon: Compass },
    { label: "Saved opportunities", href: "/saved-opportunities", icon: Bookmark },
    { label: "Applications", href: "/applications", icon: BriefcaseBusiness },
    { label: "Interviews", href: "/interviews", icon: CalendarCheck },
  ]},
  { heading: "CAREER DEVELOPMENT", items: [
    { label: "Career profile", href: "/profile", icon: UserRound },
    { label: "CV & documents", href: "/profile#resumes", icon: FileText },
    { label: "AI career studio", href: "/profile#career-tools", icon: WandSparkles },
    { label: "Skills & learning", href: "/learning", icon: GraduationCap },
    { label: "Career projects", href: "/projects", icon: FolderKanban },
  ]},
  { heading: "INTELLIGENCE", items: [
    { label: "Career analytics", href: "/analytics", icon: ChartNoAxesCombined },
    { label: "Market insights", href: "/market-insights", icon: TrendingUp },
    { label: "Role recommendations", href: "/recommendations", icon: Target },
  ]},
  { heading: "PRODUCTIVITY", items: [
    { label: "Tasks & follow-ups", href: "/tasks", icon: ListTodo },
    { label: "Career calendar", href: "/calendar", icon: CalendarDays },
    { label: "Notes & activity", href: "/notes", icon: StickyNote },
    { label: "Career contacts", href: "/contacts", icon: Users },
  ]},
  { heading: "ACCOUNT", items: [
    { label: "Settings", href: "/settings", icon: Settings2 },
    { label: "Help & guidance", href: "/help", icon: CircleHelp },
  ]},
];

const commandItems = [
  { label: "Go to overview", description: "Your career command centre", href: "/dashboard", icon: LayoutDashboard },
  { label: "Discover opportunities", description: "Search and shortlist roles", href: "/opportunities", icon: Compass },
  { label: "Open applications", description: "Manage your application pipeline", href: "/applications", icon: BriefcaseBusiness },
  { label: "Prepare for interviews", description: "Schedule and manage interviews", href: "/interviews", icon: CalendarCheck },
  { label: "Edit career profile", description: "Experience, education and skills", href: "/profile", icon: UserRound },
  { label: "Open CV documents", description: "Your resumes and career documents", href: "/profile#resumes", icon: FileText },
  { label: "Career analytics", description: "Performance from your own records", href: "/analytics", icon: BarChart3 },
  { label: "Create a task", description: "Add a career follow-up", href: "/tasks?new=1", icon: ListTodo },
  { label: "Write a note", description: "Capture career research", href: "/notes?new=1", icon: StickyNote },
  { label: "Open calendar", description: "Interviews and due dates", href: "/calendar", icon: CalendarDays },
  { label: "Account settings", description: "Security, AI budget and integrations", href: "/settings", icon: Settings2 },
];

export default function AppShell({ children, user, onLogout }: AppShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [noticeOpen, setNoticeOpen] = useState(false);
  const [quickOpen, setQuickOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [notices, setNotices] = useState<Notice[]>([]);
  const [noticeBusy, setNoticeBusy] = useState(false);
  const [sessionUser, setSessionUser] = useState<User | null>(user ?? null);
  const [approvalCount, setApprovalCount] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [paletteQuery, setPaletteQuery] = useState("");
  const [searchBusy, setSearchBusy] = useState(false);
  const [searchRecords, setSearchRecords] = useState<SearchRecord[]>([]);
  const [searchError, setSearchError] = useState("");

  useEffect(() => {
    if (user !== undefined) { setSessionUser(user); return; }
    let active = true;
    void api("/api/v1/auth/me").then(async response => {
      if (response.status === 401) { window.location.assign("/login"); return null; }
      if (!response.ok) throw new Error("Unable to verify session");
      return response.json();
    }).then(data => { if (active && data) setSessionUser(data); })
      .catch(() => { if (active) window.location.assign("/login"); });
    return () => { active = false; };
  }, [user]);

  useEffect(() => {
    let active = true;
    void api("/api/v1/automations/approvals").then(r => r.ok ? r.json() : [])
      .then(data => { if (active && Array.isArray(data)) setApprovalCount(data.filter((x: {status:string}) => x.status === "pending").length); })
      .catch(() => undefined);
    return () => { active = false; };
  }, []);

  const loadNotices = useCallback(async () => {
    setNoticeBusy(true);
    try {
      const response = await api("/api/v1/notifications");
      if (!response.ok) throw new Error("Notifications are unavailable.");
      const data = await response.json();
      if (!Array.isArray(data)) throw new Error("Unexpected notification response.");
      setNotices(data);
    } catch { setNotices([]); }
    finally { setNoticeBusy(false); }
  }, []);

  const searchWorkspace = useCallback(async (query: string) => {
    if (query.trim().length < 2) { setSearchRecords([]); setSearchError(""); return; }
    setSearchBusy(true); setSearchError("");
    try {
      const [jobsResponse, appsResponse, itemsResponse] = await Promise.all([
        api("/api/v1/opportunities"), api("/api/v1/applications"),
        api("/api/v1/workspace/items?item_type=note"),
      ]);
      if (!jobsResponse.ok || !appsResponse.ok || !itemsResponse.ok) throw new Error("Workspace search is temporarily unavailable.");
      const [jobs, apps, notes] = await Promise.all([jobsResponse.json(), appsResponse.json(), itemsResponse.json()]);
      const term = query.trim().toLowerCase();
      const records: SearchRecord[] = [];
      if (Array.isArray(jobs)) jobs.forEach((job: {id:number;title?:string;company?:string;status?:string}) => {
        if ((job.title + " " + job.company).toLowerCase().includes(term)) records.push({id:job.id,title:job.title||"Untitled opportunity",subtitle:job.company||"Saved opportunity",href:"/opportunities?view=saved",kind:"OPPORTUNITY"});
      });
      if (Array.isArray(apps)) apps.forEach((app: {id:number;role_title?:string;company_name?:string;status?:string}) => {
        if ((app.role_title + " " + app.company_name).toLowerCase().includes(term)) records.push({id:app.id,title:app.role_title||"Untitled application",subtitle:(app.company_name||"Application")+" · "+(app.status||"draft"),href:"/applications",kind:"APPLICATION"});
      });
      if (Array.isArray(notes)) notes.forEach((note: {id:number;title?:string;description?:string}) => {
        if ((note.title + " " + note.description).toLowerCase().includes(term)) records.push({id:note.id,title:note.title||"Untitled note",subtitle:"Career note",href:"/notes",kind:"NOTE"});
      });
      setSearchRecords(records.slice(0,12));
    } catch (error) { setSearchRecords([]); setSearchError(error instanceof Error?error.message:"Search failed."); }
    finally { setSearchBusy(false); }
  }, []);

  useEffect(() => {
    const handle = (event: globalThis.KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault(); setPaletteOpen(value => !value); setNoticeOpen(false); setQuickOpen(false);
      }
      if (event.key === "Escape") { setPaletteOpen(false); setQuickOpen(false); setNoticeOpen(false); }
    };
    window.addEventListener("keydown", handle);
    return () => window.removeEventListener("keydown", handle);
  }, []);

  useEffect(() => { if (searchQuery.trim().length >= 2) void searchWorkspace(searchQuery); else setSearchRecords([]); }, [searchQuery, searchWorkspace]);
  useEffect(() => { if (paletteOpen) setPaletteQuery(""); }, [paletteOpen]);

  const unread = useMemo(() => notices.filter(item => !item.read_at).length, [notices]);
  const displayName = sessionUser?.full_name?.trim() || sessionUser?.email?.split("@")[0] || "Your account";
  const initials = displayName.split(/[\s._-]+/).filter(Boolean).slice(0,2).map(part => part[0]?.toUpperCase()).join("") || "JS";
  const currentItems = navGroups.flatMap(group => group.items);
  const activeItem = currentItems.find(item => {
    const base = item.href.split("?")[0].split("#")[0];
    return pathname === base || (base !== "/dashboard" && pathname.startsWith(base + "/"));
  });
  const activeLabel = activeItem?.label || (pathname === "/dashboard" ? "Overview" : "Workspace");
  const filteredCommands = commandItems.filter(item => (item.label+" "+item.description).toLowerCase().includes(paletteQuery.toLowerCase()));

  function navigate(href: string) {
    setPaletteOpen(false); setQuickOpen(false); setNoticeOpen(false); setMobileOpen(false);
    router.push(href);
  }
  async function defaultLogout() {
    try { await api("/api/v1/auth/logout", { method: "POST" }); }
    finally { window.location.assign("/login"); }
  }
  async function markRead(item: Notice) {
    if (item.read_at) return;
    const response = await api("/api/v1/notifications/" + item.id + "/read", { method: "POST" });
    if (response.ok) setNotices(current => current.map(n => n.id === item.id ? { ...n, read_at: new Date().toISOString() } : n));
  }
  async function toggleNotices() {
    const next = !noticeOpen; setNoticeOpen(next); setQuickOpen(false);
    if (next) await loadNotices();
  }

  function onSearchKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" && searchRecords[0]) navigate(searchRecords[0].href);
    if (event.key === "Escape") setSearchQuery("");
  }

  return <div className={styles.frame}>
    {mobileOpen && <button className={styles.scrim} aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}
    <aside className={mobileOpen ? styles.sidebarOpen : collapsed ? styles.sidebarCollapsed : styles.sidebar}>
      <a href="/dashboard" className={styles.brand}>
        <span className={styles.brandSymbol}><Activity size={18} strokeWidth={2.2}/></span>
        {!collapsed&&<span className={styles.brandName}>jobseeker<span>.</span><small>CAREER INTELLIGENCE</small></span>}
      </a>
      {!collapsed&&<div className={styles.workspaceCard}><span className={styles.workspaceAvatar}>{initials.slice(0,1)}</span><span className={styles.workspaceMeta}><strong>Personal workspace</strong><small>Private career records</small></span><ChevronDown size={15}/></div>}
      <nav className={styles.navigation} aria-label="Main navigation">
        {navGroups.map(group => <div className={styles.navGroup} key={group.heading}>
          {!collapsed&&<p className={styles.navHeading}>{group.heading}</p>}
          {group.items.map(({label,href,icon:Icon}) => {
            const base=href.split("?")[0].split("#")[0];
            const active=pathname===base||(base!=="/dashboard"&&pathname.startsWith(base+"/"));
            return <a key={href} href={href} title={collapsed?label:undefined} onClick={()=>setMobileOpen(false)} className={active?styles.navActive:styles.navLink} aria-current={active?"page":undefined}>
              <Icon size={17} strokeWidth={1.8}/>{!collapsed&&<span>{label}</span>}
              {label==="Applications"&&approvalCount>0&&!collapsed&&<em className={styles.navCount}>{approvalCount}</em>}
            </a>;
          })}
        </div>)}
      </nav>
      <div className={styles.sidebarBottom}>
        {!collapsed&&<div className={styles.assurance}><ShieldCheck size={16}/><span><strong>Your actions stay yours</strong><small>External actions always require your approval</small></span></div>}
        <div className={styles.accountRow}>
          <span className={styles.userAvatar}>{initials}</span>
          {!collapsed&&<span className={styles.accountDetails}><strong>{displayName}</strong><small>{sessionUser?.email||"Signed-in account"}</small></span>}
          <button className={styles.logout} onClick={onLogout||(()=>void defaultLogout())} title="Sign out" aria-label="Sign out"><LogOut size={16}/></button>
        </div>
        <button className={styles.collapseButton} onClick={()=>setCollapsed(value=>!value)} aria-label={collapsed?"Expand sidebar":"Collapse sidebar"} title={collapsed?"Expand sidebar":"Collapse sidebar"}><ChevronDown size={15}/>{!collapsed&&<span>Collapse sidebar</span>}</button>
      </div>
    </aside>
    <div className={styles.main}>
      <header className={styles.topbar}>
        <button className={styles.mobileToggle} aria-label="Open navigation" onClick={()=>setMobileOpen(true)}><Menu size={19}/></button>
        <div className={styles.breadcrumb}><span>Workspace</span><span className={styles.crumbDivider}>/</span><strong>{activeLabel}</strong></div>
        <div className={styles.topActions}>
          <div className={styles.globalSearch}>
            <Search size={15}/>
            <input aria-label="Search your workspace" placeholder="Search jobs, companies, applications..." value={searchQuery} onChange={e=>setSearchQuery(e.target.value)} onKeyDown={onSearchKeyDown}/>
            <button onClick={()=>{setPaletteOpen(true);setQuickOpen(false);}} aria-label="Open command palette"><kbd>⌘ K</kbd></button>
            {searchQuery.length>0&&<button className={styles.clearSearch} onClick={()=>setSearchQuery("")} aria-label="Clear search"><X size={13}/></button>}
            {searchQuery.trim().length>=2&&<div className={styles.searchResults}>
              {searchBusy?<p>Searching your records…</p>:searchError?<p role="alert">{searchError}</p>:searchRecords.length===0?<p>No matching records in your workspace.</p>:searchRecords.map((item,index)=><button key={item.kind+item.id} onClick={()=>navigate(item.href)}><span className={styles.searchKind}>{item.kind}</span><span><strong>{item.title}</strong><small>{item.subtitle}</small></span>{index===0&&<kbd>Enter</kbd>}</button>)}
            </div>}
          </div>
          <div className={styles.quickWrap}>
            <button className={styles.quickCreate} onClick={()=>{setQuickOpen(v=>!v);setNoticeOpen(false);}} aria-expanded={quickOpen}><Plus size={15}/><span>Create</span><ChevronDown size={13}/></button>
            {quickOpen&&<div className={styles.quickMenu}>
              <button onClick={()=>navigate("/applications?new=1")}><BriefcaseBusiness size={15}/><span><strong>Application</strong><small>Track a new role</small></span></button>
              <button onClick={()=>navigate("/tasks?new=1")}><ListTodo size={15}/><span><strong>Task or follow-up</strong><small>Set a career action</small></span></button>
              <button onClick={()=>navigate("/notes?new=1")}><StickyNote size={15}/><span><strong>Career note</strong><small>Capture research or ideas</small></span></button>
              <button onClick={()=>navigate("/interviews?new=1")}><CalendarCheck size={15}/><span><strong>Interview</strong><small>Schedule preparation</small></span></button>
            </div>}
          </div>
          <button className={styles.topIcon} onClick={()=>navigate("/calendar")} aria-label="Open career calendar" title="Calendar"><CalendarDays size={17}/></button>
          <button className={styles.topIcon} onClick={()=>navigate("/settings#gmail")} aria-label="Open activity inbox" title="Activity inbox"><Bell size={17}/></button>
          <div className={styles.noticeWrap}>
            <button className={styles.noticeButton} onClick={()=>void toggleNotices()} aria-label={unread?unread+" unread notifications":"Notifications"} aria-expanded={noticeOpen}><Bell size={18}/>{unread>0&&<i/>}</button>
            {noticeOpen&&<div className={styles.noticePanel}>
              <div className={styles.noticeHeader}><div><strong>Notifications</strong><small>{unread} unread updates</small></div><button onClick={()=>setNoticeOpen(false)} aria-label="Close notifications"><X size={16}/></button></div>
              {noticeBusy?<p className={styles.noticeEmpty}>Loading updates…</p>:notices.length===0?<p className={styles.noticeEmpty}>You’re all caught up. New account and application updates will appear here.</p>:<div className={styles.noticeList}>{notices.slice(0,8).map(item=><button key={item.id} className={item.read_at?styles.noticeItem:styles.noticeUnread} onClick={()=>void markRead(item)}><span className={styles.noticeDot}/><span><strong>{item.title}</strong><small>{item.body}</small><em>{item.created_at?new Date(item.created_at).toLocaleString():""}</em></span><CheckCheck size={14}/></button>)}</div>}
            </div>}
          </div>
          <button className={styles.topProfile} onClick={()=>navigate("/settings")} aria-label="Account settings">{initials}</button>
        </div>
      </header>
      <main className={styles.content}>{children}</main>
      <footer className={styles.footer}><span>JobSeeker Intelligence</span><span>Private career workspace · Human-approved external actions</span></footer>
    </div>

    {paletteOpen&&<div className={styles.paletteBackdrop} role="presentation" onMouseDown={e=>{if(e.target===e.currentTarget)setPaletteOpen(false);}}>
      <section className={styles.commandPalette} role="dialog" aria-modal="true" aria-label="Command palette">
        <div className={styles.paletteSearch}><Command size={17}/><input autoFocus placeholder="Search commands and destinations..." value={paletteQuery} onChange={e=>setPaletteQuery(e.target.value)}/><kbd>ESC</kbd></div>
        <p className={styles.paletteLabel}>NAVIGATE & CREATE</p>
        <div className={styles.paletteItems}>{filteredCommands.length===0?<p className={styles.paletteEmpty}>No matching commands.</p>:filteredCommands.map(item=><button key={item.href} onClick={()=>navigate(item.href)}><span className={styles.paletteIcon}><item.icon size={16}/></span><span><strong>{item.label}</strong><small>{item.description}</small></span><span className={styles.paletteArrow}>↵</span></button>)}</div>
        <div className={styles.paletteFooter}><span><kbd>Ctrl</kbd> / <kbd>⌘</kbd> + <kbd>K</kbd> to toggle</span><span>Escape to close</span></div>
      </section>
    </div>}
  </div>;
}
