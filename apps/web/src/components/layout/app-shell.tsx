"use client";

import { useState } from "react";
import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import {
  Activity, Bell, BriefcaseBusiness, Building2, CalendarDays,
  ChartNoAxesCombined, ChevronDown, Command, FileText, Gauge, Inbox,
  LayoutDashboard, LogOut, Menu, Search, Settings2, ShieldCheck, Sparkles,
  Users
} from "lucide-react";
import styles from "./app-shell.module.css";

type AppShellProps = {
  children: ReactNode;
  user?: { full_name?: string; email?: string; is_verified?: boolean } | null;
  onLogout?: () => void;
};
type NavigationItem = { label: string; href: string; icon: typeof LayoutDashboard };

const primaryNav: NavigationItem[] = [
  { label: "Overview", href: "/dashboard", icon: LayoutDashboard },
  { label: "Discover jobs", href: "/discovery", icon: Search },
  { label: "Saved opportunities", href: "/opportunities", icon: BriefcaseBusiness },
  { label: "Applications", href: "/applications", icon: Activity },
  { label: "Career intelligence", href: "/intelligence", icon: Sparkles },
  { label: "Career analytics", href: "/analytics", icon: ChartNoAxesCombined },
];
const workspaceNav: NavigationItem[] = [
  { label: "CV Studio", href: "/cv-studio", icon: FileText },
  { label: "Career Studio", href: "/career-studio", icon: Command },
  { label: "Interviews", href: "/interviews", icon: CalendarDays },
  { label: "Recruiters", href: "/recruiters", icon: Users },
  { label: "Companies", href: "/companies", icon: Building2 },
  { label: "Inbox", href: "/inbox", icon: Inbox },
  { label: "Notifications", href: "/notifications", icon: Bell },
];
const accountNav: NavigationItem[] = [
  { label: "Approvals", href: "/approvals", icon: ShieldCheck },
  { label: "Settings", href: "/settings", icon: Settings2 },
];

export default function AppShell({ children, user, onLogout }: AppShellProps) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const displayName = user?.full_name?.trim() || user?.email?.split("@")[0] || "Your account";
  const initials = displayName.split(/[\s._-]+/).filter(Boolean).slice(0, 2).map(part => part[0]?.toUpperCase()).join("") || "JS";

  function navGroup(title: string, items: NavigationItem[]) {
    return <div className={styles.navGroup} key={title}>
      <p className={styles.navLabel}>{title}</p>
      {items.map(({ label, href, icon: Icon }) => {
        const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href + "/"));
        return <a key={href} href={href} onClick={() => setMobileOpen(false)}
          className={active ? styles.navItemActive : styles.navItem} aria-current={active ? "page" : undefined}>
          <Icon size={17} strokeWidth={1.8} /><span>{label}</span>
          {active && <span className={styles.activeMark} />}
        </a>;
      })}
    </div>;
  }

  return <div className={styles.shell}>
    {mobileOpen && <button className={styles.scrim} aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}
    <aside className={mobileOpen ? styles.sidebarOpen : styles.sidebar}>
      <a href="/dashboard" className={styles.brand}>
        <span className={styles.brandMark}><Gauge size={19} strokeWidth={2.2} /></span>
        <span className={styles.brandText}>jobseeker<span>.</span><small>INTELLIGENCE</small></span>
      </a>
      <div className={styles.workspacePicker}>
        <span className={styles.workspaceIcon}>J</span>
        <span><strong>Personal workspace</strong><small>Career operations</small></span>
        <ChevronDown size={15} />
      </div>
      <nav className={styles.navigation} aria-label="Main navigation">
        {navGroup("WORKSPACE", primaryNav)}
        {navGroup("CAREER TOOLS", workspaceNav)}
        {navGroup("PREFERENCES", accountNav)}
      </nav>
      <div className={styles.sidebarFooter}>
        <div className={styles.securityNote}><ShieldCheck size={16} /><span>Private by design<br/><small>External actions require approval</small></span></div>
        <div className={styles.userRow}>
          <span className={styles.avatar}>{initials}</span>
          <span className={styles.userIdentity}><strong>{displayName}</strong><small>{user?.email || "Signed-in account"}</small></span>
          {onLogout && <button className={styles.logoutButton} onClick={onLogout} aria-label="Sign out" title="Sign out"><LogOut size={17} /></button>}
        </div>
      </div>
    </aside>
    <div className={styles.mainColumn}>
      <header className={styles.topbar}>
        <button className={styles.mobileMenu} aria-label="Open navigation" onClick={() => setMobileOpen(true)}><Menu size={20} /></button>
        <div className={styles.breadcrumb}><span>Workspace</span><span className={styles.breadcrumbSlash}>/</span><strong>{primaryNav.find(item => item.href === pathname)?.label || workspaceNav.find(item => item.href === pathname)?.label || accountNav.find(item => item.href === pathname)?.label || "Overview"}</strong></div>
        <div className={styles.topbarActions}>
          <a href="/discovery" className={styles.quickSearch}><Search size={15}/><span>Find opportunities</span><kbd>↗</kbd></a>
          <a href="/notifications" className={styles.iconButton} aria-label="Notifications"><Bell size={18}/></a>
          <a href="/profile" className={styles.topAvatar} aria-label="Profile">{initials}</a>
        </div>
      </header>
      <main className={styles.content}>{children}</main>
    </div>
  </div>;
}
