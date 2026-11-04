"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowRight, CalendarDays, ChevronLeft, ChevronRight, CircleAlert, Clock3, ListTodo } from "lucide-react";
import AppShell from "../layout/app-shell";
import styles from "./career-calendar.module.css";

type Interview={id:number;application_id:number|null;scheduled_at:string|null;interview_type:string};
type Task={id:number;title:string;description:string;status:string;priority:string;due_at:string|null};
type Event={id:string;kind:"interview"|"task";title:string;detail:string;date:Date;href:string};
const API=process.env.NEXT_PUBLIC_API_BASE_URL||"http://localhost:8000";
async function api(path:string){return fetch(API+path,{credentials:"include",cache:"no-store"});}
function dayKey(d:Date){return [d.getFullYear(),String(d.getMonth()+1).padStart(2,"0"),String(d.getDate()).padStart(2,"0")].join("-");}
function monthLabel(d:Date){return d.toLocaleDateString(undefined,{month:"long",year:"numeric"});}
export default function CareerCalendar(){
 const [interviews,setInterviews]=useState<Interview[]>([]);const [tasks,setTasks]=useState<Task[]>([]);
 const [month,setMonth]=useState(()=>new Date(new Date().getFullYear(),new Date().getMonth(),1));
 const [selected,setSelected]=useState(()=>dayKey(new Date()));const [loading,setLoading]=useState(true);const [error,setError]=useState("");
 const load=useCallback(async()=>{setLoading(true);setError("");try{const [i,t]=await Promise.all([api("/api/v1/interviews"),api("/api/v1/workspace/items?item_type=task")]);if(i.status===401||t.status===401){window.location.assign("/login");return;}if(!i.ok||!t.ok)throw new Error("Calendar records could not be loaded.");const [iv,tv]=await Promise.all([i.json(),t.json()]);if(!Array.isArray(iv)||!Array.isArray(tv))throw new Error("The calendar service returned invalid data.");setInterviews(iv);setTasks(tv);}catch(e){setError(e instanceof Error?e.message:"Unable to load calendar.");}finally{setLoading(false);}},[]);
 useEffect(()=>{void load();},[load]);
 const events=useMemo<Event[]>(()=>[
  ...interviews.filter(x=>x.scheduled_at).map(x=>({id:"i"+x.id,kind:"interview" as const,title:"Interview",detail:x.interview_type.replaceAll("_"," "),date:new Date(x.scheduled_at as string),href:"/interviews"})),
  ...tasks.filter(x=>x.due_at&&!["completed","cancelled"].includes(x.status)).map(x=>({id:"t"+x.id,kind:"task" as const,title:x.title,detail:x.priority+" priority",date:new Date(x.due_at as string),href:"/tasks"}))
 ].filter(x=>!Number.isNaN(x.date.getTime())),[interviews,tasks]);
 const cells=useMemo(()=>{const first=new Date(month.getFullYear(),month.getMonth(),1);const start=new Date(first);start.setDate(1-first.getDay());return Array.from({length:42},(_,i)=>{const d=new Date(start);d.setDate(start.getDate()+i);return d;});},[month]);
 const selectedEvents=events.filter(x=>dayKey(x.date)===selected).sort((a,b)=>a.date.getTime()-b.date.getTime());
 const today=dayKey(new Date());
 const upcoming=events.filter(x=>dayKey(x.date)>=today).sort((a,b)=>a.date.getTime()-b.date.getTime()).slice(0,6);
 function changeMonth(step:number){setMonth(current=>new Date(current.getFullYear(),current.getMonth()+step,1));}
 return <AppShell><div className={styles.page}>
  <header className={styles.heading}><div><span className={styles.eyebrow}>PERSONAL PRODUCTIVITY / SCHEDULE</span><h1>Career calendar</h1><p>See interview sessions and task deadlines together. Only dates recorded in your workspace appear here.</p></div><div className={styles.actions}><a href="/interviews">Manage interviews <ArrowRight size={13}/></a><a href="/tasks">Manage tasks <ArrowRight size={13}/></a></div></header>
  {error&&<div className={styles.error}><CircleAlert size={15}/>{error}<button onClick={()=>void load()}>Retry</button></div>}
  <div className={styles.layout}><section className={styles.calendar}><div className={styles.calendarHead}><button onClick={()=>changeMonth(-1)} aria-label="Previous month"><ChevronLeft size={17}/></button><h2>{monthLabel(month)}</h2><button onClick={()=>changeMonth(1)} aria-label="Next month"><ChevronRight size={17}/></button><button className={styles.today} onClick={()=>{const now=new Date();setMonth(new Date(now.getFullYear(),now.getMonth(),1));setSelected(dayKey(now));}}>Today</button></div><div className={styles.weekdays}>{["Sun","Mon","Tue","Wed","Thu","Fri","Sat"].map(d=><span key={d}>{d}</span>)}</div><div className={styles.days}>{cells.map(d=>{const key=dayKey(d);const items=events.filter(x=>dayKey(x.date)===key);return <button key={key} className={[styles.day,d.getMonth()!==month.getMonth()?styles.outside:"",key===today?styles.isToday:"",key===selected?styles.selected:""].join(" ")} onClick={()=>setSelected(key)}><span>{d.getDate()}</span><i>{items.slice(0,3).map(item=><b key={item.id} className={item.kind==="interview"?styles.interviewDot:styles.taskDot}/>)}</i></button>;})}</div><div className={styles.legend}><span><i className={styles.interviewDot}/> Interview</span><span><i className={styles.taskDot}/> Task deadline</span></div>{loading&&<div className={styles.loading}>Refreshing calendar records…</div>}</section>
  <aside className={styles.agenda}><div className={styles.agendaHead}><span>SELECTED DAY</span><h2>{new Date(selected+"T12:00:00").toLocaleDateString(undefined,{weekday:"long",day:"numeric",month:"long"})}</h2></div>{selectedEvents.length===0?<div className={styles.empty}>Nothing scheduled for this day.</div>:selectedEvents.map(item=><a className={styles.event} href={item.href} key={item.id}><span className={item.kind==="interview"?styles.eventIconInterview:styles.eventIconTask}>{item.kind==="interview"?<CalendarDays size={15}/>:<ListTodo size={15}/>}</span><span><strong>{item.title}</strong><small>{item.detail}</small><em><Clock3 size={11}/>{item.date.toLocaleTimeString(undefined,{hour:"numeric",minute:"2-digit"})}</em></span><ArrowRight size={13}/></a>)}<div className={styles.upcomingHead}>UP NEXT</div>{upcoming.length===0?<p className={styles.empty}>No upcoming dated items.</p>:upcoming.map(item=><a className={styles.upcomingItem} href={item.href} key={"up"+item.id}><span>{item.date.toLocaleDateString(undefined,{day:"numeric",month:"short"})}</span><strong>{item.title}</strong></a>)}</aside></div>
 </div></AppShell>;
}
