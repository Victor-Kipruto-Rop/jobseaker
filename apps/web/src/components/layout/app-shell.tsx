"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import {
  Activity, Bell, BriefcaseBusiness, ChevronDown,
  FileText, LayoutDashboard, LogOut, Menu, Search, Settings2, ShieldCheck,
  Target, X, CheckCheck
} from "lucide-react";
import styles from "./app-shell.module.css";

type User = { full_name?: string; email?: string; is_verified?: boolean };
type AppShellProps = { children: ReactNode; user?: User | null; onLogout?: () => void };
type Notice = { id: number; title: string; body: string; read_at?: string | null; created_at?: string };

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
function csrf() {
  return decodeURIComponent(document.cookie.split("; ").find(item => item.startsWith("jobseeker_csrf="))?.split("=").slice(1).join("=") || "");
}
async function api(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  if (init.method) headers.set("X-CSRF-Token", csrf());
  return fetch(API + path, { ...init, headers, credentials: "include", cache: "no-store" });
}
const nav = [
  { label: "Overview", href: "/dashboard", icon: LayoutDashboard, section: "YOUR WORKSPACE" },
  { label: "Opportunities", href: "/opportunities", icon: Target, section: "YOUR WORKSPACE" },
  { label: "Applications", href: "/applications", icon: BriefcaseBusiness, section: "YOUR WORKSPACE" },
  { label: "Career profile", href: "/profile", icon: FileText, section: "YOUR WORKSPACE" },
  { label: "Settings", href: "/settings", icon: Settings2, section: "ACCOUNT" },
];
const labels: Record<string,string> = { "/dashboard":"Overview", "/opportunities":"Opportunities", "/applications":"Applications", "/profile":"Career profile", "/settings":"Settings" };

export default function AppShell({ children, user, onLogout }: AppShellProps) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [noticeOpen, setNoticeOpen] = useState(false);
  const [notices, setNotices] = useState<Notice[]>([]);
  const [noticeBusy, setNoticeBusy] = useState(false);
  const [sessionUser, setSessionUser] = useState<User | null>(user ?? null);
  const [approvalCount, setApprovalCount] = useState(0);

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
    try { const response = await api("/api/v1/notifications"); if (response.ok) setNotices(await response.json()); }
    catch { setNotices([]); }
    finally { setNoticeBusy(false); }
  }, []);

  const unread = useMemo(() => notices.filter(item => !item.read_at).length, [notices]);
  const displayName = sessionUser?.full_name?.trim() || sessionUser?.email?.split("@")[0] || "Your account";
  const initials = displayName.split(/[\s._-]+/).filter(Boolean).slice(0,2).map(part => part[0]?.toUpperCase()).join("") || "JS";

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
    const next = !noticeOpen;
    setNoticeOpen(next);
    if (next) await loadNotices();
  }

  const activeLabel = labels[pathname] || "Overview";
  return <div className={styles.frame}>
    {mobileOpen && <button className={styles.scrim} aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}
    <aside className={mobileOpen ? styles.sidebarOpen : styles.sidebar}>
      <a href="/dashboard" className={styles.brand}>
        <span className={styles.brandSymbol}><Activity size={18} strokeWidth={2.2}/></span>
        <span className={styles.brandName}>jobseeker<span>.</span><small>INTELLIGENCE</small></span>
      </a>
      <div className={styles.workspaceCard}>
        <span className={styles.workspaceAvatar}>{initials.slice(0,1)}</span>
        <span className={styles.workspaceMeta}><strong>Career workspace</strong><small>Personal account</small></span>
        <ChevronDown size={15}/>
      </div>
      <nav className={styles.navigation} aria-label="Main navigation">
        <p className={styles.navHeading}>YOUR WORKSPACE</p>
        {nav.slice(0,4).map(({label,href,icon:Icon}) => {
          const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href + "/"));
          return <a key={href} href={href} onClick={() => setMobileOpen(false)} className={active ? styles.navActive : styles.navLink} aria-current={active ? "page" : undefined}>
            <Icon size={17} strokeWidth={1.8}/><span>{label}</span>{label === "Applications" && approvalCount > 0 && <em className={styles.navCount}>{approvalCount}</em>}
          </a>;
        })}
        <p className={styles.navHeading}>ACCOUNT</p>
        <a href="/settings" onClick={() => setMobileOpen(false)} className={pathname === "/settings" ? styles.navActive : styles.navLink} aria-current={pathname === "/settings" ? "page" : undefined}><Settings2 size={17}/><span>Settings</span></a>
      </nav>
      <div className={styles.sidebarBottom}>
        <div className={styles.assurance}><ShieldCheck size={16}/><span><strong>Your actions stay yours</strong><small>External actions need your approval</small></span></div>
        <div className={styles.accountRow}>
          <span className={styles.userAvatar}>{initials}</span>
          <span className={styles.accountDetails}><strong>{displayName}</strong><small>{sessionUser?.email || "Signed-in account"}</small></span>
          <button className={styles.logout} onClick={onLogout || (() => void defaultLogout())} title="Sign out" aria-label="Sign out"><LogOut size={16}/></button>
        </div>
      </div>
    </aside>
    <div className={styles.main}>
      <header className={styles.topbar}>
        <button className={styles.mobileToggle} aria-label="Open navigation" onClick={() => setMobileOpen(true)}><Menu size={19}/></button>
        <div className={styles.breadcrumb}><span>Workspace</span><span className={styles.crumbDivider}>/</span><strong>{activeLabel}</strong></div>
        <div className={styles.topActions}>
          <a className={styles.searchShortcut} href="/opportunities"><Search size={15}/><span>Find an opportunity</span><kbd>⌘ K</kbd></a>
          <div className={styles.noticeWrap}>
            <button className={styles.noticeButton} onClick={() => void toggleNotices()} aria-label={unread ? unread + " unread notifications" : "Notifications"} aria-expanded={noticeOpen}><Bell size={18}/>{unread > 0 && <i/>}</button>
            {noticeOpen && <div className={styles.noticePanel}>
              <div className={styles.noticeHeader}><div><strong>Notifications</strong><small>{unread} unread updates</small></div><button onClick={() => setNoticeOpen(false)} aria-label="Close notifications"><X size={16}/></button></div>
              {noticeBusy ? <p className={styles.noticeEmpty}>Loading updates…</p> : notices.length === 0 ? <p className={styles.noticeEmpty}>You’re all caught up. New account and application updates will appear here.</p> : <div className={styles.noticeList}>{notices.slice(0,8).map(item=><button key={item.id} className={item.read_at ? styles.noticeItem : styles.noticeUnread} onClick={() => void markRead(item)}><span className={styles.noticeDot}/><span><strong>{item.title}</strong><small>{item.body}</small><em>{item.created_at ? new Date(item.created_at).toLocaleString() : ""}</em></span><CheckCheck size={14}/></button>)}</div>}
            </div>}
          </div>
          <a href="/settings" className={styles.topProfile} aria-label="Account settings">{initials}</a>
        </div>
      </header>
      <main className={styles.content}>{children}</main>
      <footer className={styles.footer}><span>JobSeeker Intelligence</span><span>Private career workspace · Human-approved external actions</span></footer>
    </div>
  </div>;
}
