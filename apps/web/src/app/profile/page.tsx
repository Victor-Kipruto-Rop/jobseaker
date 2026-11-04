"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, FileText, GraduationCap, Plus, Save, ShieldCheck, Sparkles, Trash2, UploadCloud, UserRound, X } from "lucide-react";
import AppShell from "../../components/layout/app-shell";
import styles from "./profile.module.css";

const API=process.env.NEXT_PUBLIC_API_BASE_URL||"http://localhost:8000";
type Skill={id:number;skill_name:string;proficiency:string;evidence:string};
type Resume={id:number;filename:string;content_type:string;version:number;created_at:string};
type ProfileData={user?:{full_name:string;email:string};profile?:{headline?:string;summary?:string;location?:string;target_roles?:string[]};skills?:Skill[]};
type Analysis={coverage_score:number;matched_terms:string[];missing_terms:string[];warning:string};
function csrf(){return decodeURIComponent(document.cookie.split("; ").find(x=>x.startsWith("jobseeker_csrf="))?.split("=").slice(1).join("=")||"");}
async function api(path:string,init:RequestInit={}){const h=new Headers(init.headers);if(init.method)h.set("X-CSRF-Token",csrf());const r=await fetch(API+path,{...init,headers:h,credentials:"include",cache:"no-store"});if(r.status===401)window.location.assign("/login");return r;}
function date(v:string){const d=new Date(v);return Number.isNaN(d.getTime())?"":d.toLocaleDateString(undefined,{day:"numeric",month:"short",year:"numeric"});}

export default function Profile(){
 const [data,setData]=useState<ProfileData|null>(null);
 const [resumes,setResumes]=useState<Resume[]>([]);
 const [form,setForm]=useState({full_name:"",headline:"",summary:"",location:"",target_roles:""});
 const [skillName,setSkillName]=useState("");const [proficiency,setProficiency]=useState("not_assessed");const [evidence,setEvidence]=useState("");
 const [file,setFile]=useState<File|null>(null);const [uploading,setUploading]=useState(false);
 const [jobDescription,setJobDescription]=useState("");const [selectedResume,setSelectedResume]=useState<number|null>(null);const [analysis,setAnalysis]=useState<Analysis|null>(null);const [analyzing,setAnalyzing]=useState(false);
 const [loading,setLoading]=useState(true);const [saving,setSaving]=useState(false);const [error,setError]=useState("");const [notice,setNotice]=useState("");

 const load=useCallback(async()=>{
  setLoading(true);setError("");
  try{const [p,r]=await Promise.all([api("/api/v1/profile"),api("/api/v1/resumes")]);if(!p.ok||!r.ok)throw new Error("Unable to load your career profile and CV library.");const [pd,rd]=await Promise.all([p.json(),r.json()]);setData(pd);setResumes(Array.isArray(rd)?rd:[]);setForm({full_name:pd.user?.full_name||"",headline:pd.profile?.headline||"",summary:pd.profile?.summary||"",location:pd.profile?.location||"",target_roles:(pd.profile?.target_roles||[]).join(", ") });}
  catch(e){setError(e instanceof Error?e.message:"Unable to load profile.");}
  finally{setLoading(false);}
 },[]);
 useEffect(()=>{void load();},[load]);

 async function saveProfile(e:React.FormEvent){e.preventDefault();setSaving(true);setError("");setNotice("");try{const r=await api("/api/v1/profile",{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({...form,target_roles:form.target_roles.split(",").map(x=>x.trim()).filter(Boolean)})});const d=await r.json();if(!r.ok)throw new Error(d.detail||"Unable to save profile.");setNotice("Career profile saved.");await load();}catch(e){setError(e instanceof Error?e.message:"Unable to save profile.");}finally{setSaving(false);}}
 async function addSkill(e:React.FormEvent){e.preventDefault();setError("");setNotice("");try{const r=await api("/api/v1/profile/skills",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({skill_name:skillName,proficiency,evidence})});const d=await r.json();if(!r.ok)throw new Error(d.detail||"Unable to save skill.");setSkillName("");setEvidence("");setNotice("Skill evidence saved.");await load();}catch(e){setError(e instanceof Error?e.message:"Unable to save skill.");}}
 async function removeSkill(id:number){const r=await api("/api/v1/profile/skills/"+id,{method:"DELETE"});if(!r.ok){setError("Unable to remove skill.");return;}await load();}
 async function uploadResume(e:React.FormEvent){e.preventDefault();if(!file)return;setUploading(true);setError("");setNotice("");try{const body=new FormData();body.append("file",file);const r=await api("/api/v1/resumes",{method:"POST",body});const d=await r.json();if(!r.ok)throw new Error(d.detail||"Unable to upload CV.");setNotice("CV uploaded and text extraction completed ("+Number(d.extracted_characters||0).toLocaleString()+" characters).");setFile(null);await load();}catch(e){setError(e instanceof Error?e.message:"CV upload failed.");}finally{setUploading(false);}}
 async function deleteResume(id:number){if(!window.confirm("Delete this CV and its extracted text?"))return;const r=await api("/api/v1/resumes/"+id,{method:"DELETE"});if(!r.ok){setError("Unable to delete CV.");return;}setResumes(x=>x.filter(item=>item.id!==id));if(selectedResume===id){setSelectedResume(null);setAnalysis(null);}setNotice("CV deleted from your private library.");}
 async function analyze(e:React.FormEvent){e.preventDefault();if(!selectedResume)return;setAnalyzing(true);setError("");setAnalysis(null);try{const r=await api("/api/v1/resumes/"+selectedResume+"/analyze",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({job_description:jobDescription})});const d=await r.json();if(!r.ok)throw new Error(d.detail||"Unable to analyse CV.");setAnalysis(d);}catch(e){setError(e instanceof Error?e.message:"CV analysis failed.");}finally{setAnalyzing(false);}}

 const skills=data?.skills||[];
 return <AppShell><div className={styles.page}>
  <header className={styles.heading}><div><div className={styles.kicker}>YOUR WORKSPACE <span>/</span> CAREER PROFILE</div><h1>Your professional record</h1><p>Keep your experience, skills and source documents accurate. Recommendations are only as strong as the evidence you provide.</p></div><div className={styles.profileCount}><strong>{skills.length}</strong><span>skills recorded</span></div></header>
  {error&&<div className={styles.error} role="alert">{error}</div>}{notice&&<div className={styles.notice} role="status"><Check size={14}/>{notice}</div>}
  {loading?<div className={styles.loading}>Loading your career profile…</div>:<>
   <section className={styles.profileIntro}><span className={styles.profileAvatar}><UserRound size={24}/></span><div><strong>{form.full_name||"Your name"}</strong><small>{form.headline||"Add a professional headline to introduce your experience."}</small><small>{data?.user?.email||""}{form.location?" · "+form.location:""}</small></div><span className={styles.privateLabel}><ShieldCheck size={13}/> Private profile</span></section>
   <section className={styles.twoColumn}>
    <article className={styles.panel}><div className={styles.panelHeading}><div><span className={styles.sectionLabel}>01 / PROFESSIONAL IDENTITY</span><h2>Career profile</h2><p>These details inform your role matching and draft assistance.</p></div><UserRound size={18}/></div>
     <form onSubmit={saveProfile} className={styles.form}>
      <label>Full name<input required minLength={2} maxLength={160} value={form.full_name} onChange={e=>setForm({...form,full_name:e.target.value})}/></label>
      <label>Professional headline<input maxLength={250} placeholder="Data Engineer | Analytics & Platform Engineering" value={form.headline} onChange={e=>setForm({...form,headline:e.target.value})}/></label>
      <label>Location<input maxLength={250} placeholder="Nairobi, Kenya" value={form.location} onChange={e=>setForm({...form,location:e.target.value})}/></label>
      <label>Target roles<input maxLength={1000} placeholder="Data Engineer, Analytics Engineer" value={form.target_roles} onChange={e=>setForm({...form,target_roles:e.target.value})}/><small>Separate multiple roles with commas.</small></label>
      <label>Professional summary<textarea rows={6} maxLength={8000} placeholder="Describe your experience, strengths and the kind of work you want to do…" value={form.summary} onChange={e=>setForm({...form,summary:e.target.value})}/><small>{form.summary.length.toLocaleString()} / 8,000 characters</small></label>
      <button className={styles.primaryButton} disabled={saving}><Save size={14}/>{saving?"Saving…":"Save career profile"}</button>
     </form>
    </article>
    <article className={styles.panel}><div className={styles.panelHeading}><div><span className={styles.sectionLabel}>02 / SKILLS & EVIDENCE</span><h2>What you can demonstrate</h2><p>Record proficiency and evidence, not just a list of keywords.</p></div><GraduationCap size={18}/></div>
     <form className={styles.skillForm} onSubmit={addSkill}><label>Skill<input required maxLength={120} placeholder="Python, SQL, Apache Spark…" value={skillName} onChange={e=>setSkillName(e.target.value)}/></label><label>Proficiency<select value={proficiency} onChange={e=>setProficiency(e.target.value)}><option value="not_assessed">Not assessed</option><option value="beginner">Beginner</option><option value="intermediate">Intermediate</option><option value="advanced">Advanced</option><option value="expert">Expert</option></select></label><label>Evidence<textarea rows={3} maxLength={2000} placeholder="Project, work experience, coursework or certification…" value={evidence} onChange={e=>setEvidence(e.target.value)}/></label><button className={styles.secondaryButton}><Plus size={13}/> Add skill evidence</button></form>
     <div className={styles.skillList}>{skills.length===0?<div className={styles.emptySkills}><Sparkles size={18}/><strong>Your skills will appear here.</strong><small>Add a skill with evidence to improve fit analysis.</small></div>:skills.map(skill=><div className={styles.skillRow} key={skill.id}><div><strong>{skill.skill_name}</strong><span>{skill.proficiency.replaceAll("_"," ")}{skill.evidence?" · "+skill.evidence:""}</span></div><button onClick={()=>void removeSkill(skill.id)} aria-label={"Remove "+skill.skill_name}><X size={14}/></button></div>)}</div>
    </article>
   </section>

   <section className={styles.panel}><div className={styles.panelHeading}><div><span className={styles.sectionLabel}>03 / SOURCE DOCUMENTS</span><h2>CV library</h2><p>Upload PDF or DOCX files. The backend extracts text for role-specific keyword coverage checks.</p></div><FileText size={18}/></div>
    <div className={styles.resumeLayout}><div className={styles.uploadBox}><form onSubmit={uploadResume}><span className={styles.uploadIcon}><UploadCloud size={21}/></span><strong>Add a CV to your library</strong><small>PDF or DOCX · maximum 10 MB</small><label className={styles.filePicker}>Choose file<input type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={e=>setFile(e.target.files?.[0]||null)}/></label>{file&&<span className={styles.fileName}>{file.name}</span>}<button className={styles.primaryButton} disabled={!file||uploading}>{uploading?"Uploading and extracting…":"Upload CV"}</button></form></div>
     <div className={styles.resumeList}>{resumes.length===0?<div className={styles.emptySkills}><FileText size={18}/><strong>No CV documents uploaded.</strong><small>Upload a source CV to run a transparent keyword coverage review.</small></div>:resumes.map(resume=><div className={styles.resumeRow} key={resume.id}><span className={styles.resumeIcon}><FileText size={16}/></span><div><strong>{resume.filename}</strong><small>Added {date(resume.created_at)} · {resume.content_type==="application/pdf"?"PDF":"DOCX"}</small></div><button onClick={()=>{setSelectedResume(resume.id);setAnalysis(null);}} className={selectedResume===resume.id?styles.selectedButton:styles.resumeAction}>{selectedResume===resume.id?"Selected":"Analyse"}</button><button className={styles.deleteButton} onClick={()=>void deleteResume(resume.id)} aria-label={"Delete "+resume.filename}><Trash2 size={14}/></button></div>)}</div>
    </div>
   </section>

   <section className={styles.panel}><div className={styles.panelHeading}><div><span className={styles.sectionLabel}>04 / ROLE ALIGNMENT</span><h2>CV keyword coverage</h2><p>Compare a selected CV with a job description. No external AI provider is called.</p></div><Sparkles size={18}/></div>
    <form className={styles.analysisForm} onSubmit={analyze}><label>Selected CV<select required value={selectedResume||""} onChange={e=>{setSelectedResume(Number(e.target.value)||null);setAnalysis(null);}}><option value="">Choose a CV document</option>{resumes.map(r=><option key={r.id} value={r.id}>{r.filename}</option>)}</select></label><label>Target job description<textarea required minLength={20} maxLength={30000} rows={5} value={jobDescription} onChange={e=>setJobDescription(e.target.value)} placeholder="Paste the job description you want to compare against your CV…"/></label><button className={styles.primaryButton} disabled={!selectedResume||jobDescription.trim().length<20||analyzing}>{analyzing?"Checking coverage…":"Analyse keyword coverage"}</button></form>
    {analysis&&<div className={styles.analysisResult}><div className={styles.scoreBlock}><strong>{analysis.coverage_score}%</strong><span>keyword coverage</span></div><div className={styles.termColumns}><div><strong>Present in CV <span>{analysis.matched_terms.length}</span></strong><div>{analysis.matched_terms.length?analysis.matched_terms.map(x=><em key={x}>{x}</em>):<small>No matching terms found.</small>}</div></div><div><strong>Not found <span>{analysis.missing_terms.length}</span></strong><div>{analysis.missing_terms.length?analysis.missing_terms.map(x=><em key={x}>{x}</em>):<small>No missing terms found.</small>}</div></div></div><p>{analysis.warning}</p></div>}
   </section>
   <div className={styles.privacyNote}><ShieldCheck size={14}/> Your profile and CV records are scoped to your account. Keyword coverage is a transparent heuristic, not a commercial ATS score or a guarantee of selection.</div>
  </>}
 </div></AppShell>;
}
