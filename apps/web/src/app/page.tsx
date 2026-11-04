import { Activity, ArrowRight, BriefcaseBusiness, ChartNoAxesCombined, FileText, ShieldCheck, Sparkles, Target, Users } from "lucide-react";
import styles from "./home.module.css";

const features = [
  { icon: Target, title: "Opportunity intelligence", description: "Discover roles from supported job boards, preserve original listings and compare skill evidence." },
  { icon: Sparkles, title: "Explainable AI assistance", description: "Turn profile evidence into useful role insights and editable career drafts, with you in control." },
  { icon: BriefcaseBusiness, title: "Application operations", description: "Track every opportunity through a clear lifecycle, from first review to final outcome." },
  { icon: FileText, title: "CV and career studio", description: "Keep your source documents organized and create role-specific drafts you can review and edit." },
  { icon: Users, title: "Recruiter workspace", description: "Organize employer research, recruiter conversations and interview preparation in one place." },
  { icon: ChartNoAxesCombined, title: "Career analytics", description: "Understand your own pipeline and activity using account-linked records, not invented benchmarks." },
];

export default function Home() {
  return <main className={styles.page}>
    <nav className={styles.nav}>
      <a href="/" className={styles.brand}><span className={styles.mark}><Activity size={18}/></span><span>jobseeker<span>.</span></span></a>
      <div className={styles.navActions}><a href="#platform">Platform</a><a href="/login">Sign in</a><a className={styles.navCta} href="/login">Open workspace <ArrowRight size={13}/></a></div>
    </nav>
    <section className={styles.hero}>
      <div className={styles.copy}>
        <span className={styles.eyebrow}>CAREER OPERATIONS INTELLIGENCE</span>
        <h1 className={styles.title}>A clearer path to your <em>next opportunity.</em></h1>
        <p className={styles.description}>JobSeeker Intelligence brings opportunity discovery, application management, career documents and practical AI assistance into one focused workspace. Your decisions stay yours. External actions remain approval-gated.</p>
        <div className={styles.actions}><a className={styles.primary} href="/login">Enter your workspace <ArrowRight size={15}/></a><a className={styles.secondary} href="#platform">Explore the platform</a></div>
        <div className={styles.micro}><ShieldCheck size={14}/> Private workspace · Editable AI drafts · Human-approved actions</div>
      </div>
      <div className={styles.preview} aria-label="Illustrative dashboard preview">
        <div className={styles.previewTop}><span>CAREER WORKSPACE / OVERVIEW</span><span className={styles.live}>PRODUCT PREVIEW</span></div>
        <div className={styles.previewBody}>
          <div className={styles.previewCard}><div className={styles.previewLabel}>OPPORTUNITY DISCOVERY</div><div className={styles.previewNumber}>01</div><div className={styles.previewHint}>Find roles with evidence</div></div>
          <div className={styles.previewCard}><div className={styles.previewLabel}>APPLICATION CONTROL</div><div className={styles.previewNumber}>02</div><div className={styles.previewHint}>Keep every next step visible</div></div>
          <div className={styles.chartCard}><div className={styles.chartHead}><strong>Career activity</strong><span className={styles.chartLegend}>Discovery · Applications</span></div><svg className={styles.chart} viewBox="0 0 520 142" role="img" aria-label="Illustrative career activity chart"><path d="M0 112H520M0 78H520M0 44H520M0 10H520" stroke="#26372c" strokeWidth="1" strokeDasharray="3 5" fill="none"/><path d="M0 108 C45 105 55 83 100 90 S155 70 200 79 S260 44 300 60 S365 29 405 43 S470 18 520 25" stroke="#75d99d" strokeWidth="3" fill="none" strokeLinecap="round"/><path d="M0 123 C45 120 55 110 100 114 S155 94 200 102 S260 85 300 93 S365 75 405 81 S470 65 520 72" stroke="#527d60" strokeWidth="2" fill="none" strokeLinecap="round"/><path d="M0 108 C45 105 55 83 100 90 S155 70 200 79 S260 44 300 60 S365 29 405 43 S470 18 520 25V142H0Z" fill="#5fc887" opacity=".08"/></svg></div>
          <div className={styles.pipelineCard}><div className={styles.chartHead}><strong>Application lifecycle</strong><span className={styles.chartLegend}>Illustrative workflow</span></div>{[["Discover",92],["Review",72],["Prepare",48],["Interview",26]].map(([label,width])=><div className={styles.pipelineLine} key={String(label)}><span>{label}</span><div className={styles.track}><div className={styles.bar} style={{width:String(width)+"%"}}/></div><span>→</span></div>)}</div>
        </div>
      </div>
    </section>
    <section className={styles.section} id="platform">
      <div className={styles.sectionHead}><div><span className={styles.sectionEyebrow}>ONE CONNECTED WORKSPACE</span><h2 className={styles.sectionTitle}>Built around the work behind a career move.</h2></div><p className={styles.sectionDescription}>From finding a relevant opening to preparing a thoughtful application, each tool supports a real part of the process.</p></div>
      <div className={styles.features}>{features.map(({icon:Icon,title,description})=><article className={styles.feature} key={title}><span className={styles.featureIcon}><Icon size={17}/></span><h3>{title}</h3><p>{description}</p></article>)}</div>
    </section>
    <footer className={styles.footer}><span><strong>JobSeeker Intelligence</strong> · Career operations workspace</span><span>External actions require explicit approval. AI outputs remain drafts.</span></footer>
  </main>;
}
