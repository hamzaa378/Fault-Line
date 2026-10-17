'use client';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
 Activity, AlertCircle, ArrowDownRight, ArrowRight, ArrowUpRight, BarChart3,
 Bell, Boxes, CalendarClock, CheckCheck, ChevronDown, ChevronRight, CircleDot, Clock3,
 Code2, Command, ExternalLink, Fingerprint, GitBranch, GitCommitHorizontal, GitPullRequest,
 Layers3, LayoutDashboard, ListFilter, LockKeyhole, LogOut, Plus, Radar, RefreshCw,
 Search, Shield, ShieldCheck, ShieldAlert, Terminal, Users, Waves, Zap
} from 'lucide-react';
import {api, API_URL, Audit, Candidate, Change, Dashboard, Deployment, Event, Incident, Member, Project, User, canWrite, elapsedMinutes, relative, timestamp} from '@/lib/api';
import {IncidentPanel} from '@/components/IncidentPanel';
import {CreateModal, ModalType} from '@/components/CreateModal';

type Tab='overview'|'incidents'|'deployments'|'changes'|'timeline'|'team'|'audit';
const nav:[Tab,string,typeof Activity][]=[['overview','Overview',LayoutDashboard],['incidents','Incidents',AlertCircle],['deployments','Deployments',GitBranch],['changes','Code changes',GitCommitHorizontal],['timeline','Event timeline',Waves],['team','Team members',Users],['audit','Audit trail',ShieldCheck]];
const severityColor:Record<string,string>={SEV1:'#fb6576',SEV2:'#ffb16e',SEV3:'#8a97ff',SEV4:'#5cc9b2'};
function Empty({title,detail}:{title:string;detail:string}){return <div className="empty-state"><div className="empty-icon"><Radar size={27}/></div><h3>{title}</h3><p>{detail}</p></div>}
function Severity({value}:{value:string}){return <span className={`severity sev-${value.toLowerCase()}`}>{value}</span>}
function Status({value}:{value:string}){return <span className={`status-pill ${value}`}><span className="status-dot"/>{value.replaceAll('_',' ')}</span>}
function EventMark({type}:{type:string}){const Icon=type==='incident'||type==='alert'?AlertCircle:type==='deployment'?GitBranch:type==='change'?GitCommitHorizontal:type==='recovery'?ShieldCheck:CircleDot;return <span className={`event-icon ev-${type}`}><Icon size={16}/></span>}
function timeMs(x:string){return new Date(x).getTime()}

export default function Home(){
 const router=useRouter();
 const [token,setToken]=useState('');const [user,setUser]=useState<User|null>(null);
 const [projects,setProjects]=useState<Project[]>([]);const [pid,setPid]=useState('');
 const [tab,setTab]=useState<Tab>('overview');const [sidebar,setSidebar]=useState(false);
 const [loading,setLoading]=useState(true);const [updating,setUpdating]=useState(false);
 const [error,setError]=useState('');const [query,setQuery]=useState('');
 const [stats,setStats]=useState<Dashboard|null>(null);
 const [incidents,setIncidents]=useState<Incident[]>([]);const [deploys,setDeploys]=useState<Deployment[]>([]);
 const [changes,setChanges]=useState<Change[]>([]);const [events,setEvents]=useState<Event[]>([]);
 const [members,setMembers]=useState<Member[]>([]);const [audit,setAudit]=useState<Audit[]>([]);
 const [selected,setSelected]=useState<Incident|null>(null);const [modal,setModal]=useState<ModalType|null>(null);
 const [order,setOrder]=useState<'occurred'|'received'>('occurred');const [eventFilter,setEventFilter]=useState('all');
 const [replay,setReplay]=useState(false);const [replayStep,setReplayStep]=useState(0);
 const project=projects.find(p=>p.id===pid);
 const role=project?.role;
 const canRespond=canWrite(role,'responder');const canMaintain=canWrite(role,'maintainer');const isOwner=canWrite(role,'owner');
 useEffect(()=>{
  const stored=localStorage.getItem('faultline_token');
  if(!stored){router.replace('/login');return}
  setToken(stored);
  try{setUser(JSON.parse(localStorage.getItem('faultline_user')||'null') as User)}catch{setUser(null)}
  api<Project[]>('/api/projects',stored).then(rows=>{
   setProjects(rows);
   const saved=localStorage.getItem('faultline_project');
   setPid(rows.find(p=>p.id===saved)?.id || rows[0]?.id || '');
   setLoading(false);
  }).catch(()=>{localStorage.removeItem('faultline_token');router.replace('/login')});
 },[router]);
 const refresh=useCallback(async(silent=false)=>{
  if(!pid||!token)return;
  if(!silent)setUpdating(true);
  try{
   const scope=`/api/projects/${pid}`;
   const requests=[api<Dashboard>(`${scope}/dashboard`,token),api<Incident[]>(`${scope}/incidents`,token),
     api<Deployment[]>(`${scope}/deployments`,token),api<Change[]>(`${scope}/changes`,token),
     api<Event[]>(`${scope}/events?order=${order}`,token),api<Member[]>(`${scope}/members`,token)];
   const results=await Promise.all(requests);
   const [st,inc,dep,ch,ev,mem]=results as [Dashboard,Incident[],Deployment[],Change[],Event[],Member[]];
   setStats(st);setIncidents(inc);setDeploys(dep);setChanges(ch);setEvents(ev);setMembers(mem);
   setReplayStep(ev.length-1);
   if(canWrite(projects.find(p=>p.id===pid)?.role,'maintainer')){
    const rows=await api<Audit[]>(`${scope}/audit`,token);setAudit(rows);
   } else setAudit([]);
   setError('');
  }catch(e){setError(e instanceof Error?e.message:'Could not load workspace')}
  finally{if(!silent)setUpdating(false)}
 },[pid,token,order,projects]);
 useEffect(()=>{if(!pid||!token)return;void refresh();const i=setInterval(()=>void refresh(true),15000);return ()=>clearInterval(i)},[pid,token,refresh]);
 function chooseProject(id:string){setPid(id);localStorage.setItem('faultline_project',id);setSelected(null);setReplay(false);setTab('overview')}
 function logout(){localStorage.removeItem('faultline_token');localStorage.removeItem('faultline_user');localStorage.removeItem('faultline_project');router.push('/login')}
 async function saved(newId?:string){setModal(null);if(newId){const rows=await api<Project[]>('/api/projects',token);setProjects(rows);chooseProject(newId)}else void refresh()}
 async function changedIncident(){void refresh(true);if(selected){try{const fresh=await api<Incident>(`/api/projects/${pid}/incidents/${selected.id}`,token);setSelected(fresh)}catch{setSelected(null)}}}
 const filteredInc=incidents.filter(i=>(`${i.title} ${i.service} ${i.severity} ${i.status}`).toLowerCase().includes(query.toLowerCase()));
 const filteredDep=deploys.filter(d=>(`${d.version} ${d.service} ${d.commit_sha}`).toLowerCase().includes(query.toLowerCase()));
 const filteredChanges=changes.filter(c=>(`${c.title} ${c.author} ${c.sha}`).toLowerCase().includes(query.toLowerCase()));
 const visibleEvents=useMemo(()=>{
  const matches=events.filter(e=>(eventFilter==='all'||e.type===eventFilter)&&(`${e.summary} ${e.source}`).toLowerCase().includes(query.toLowerCase()));
  if(!replay)return matches;
  const ascending=[...events].sort((a,b)=>timeMs(order==='occurred'?a.occurred_at:a.received_at)-timeMs(order==='occurred'?b.occurred_at:b.received_at));
  const cutoff=ascending[Math.min(replayStep,ascending.length-1)];
  if(!cutoff)return [];
  const clock=order==='occurred'?'occurred_at':'received_at';
  return matches.filter(e=>timeMs(e[clock])<=timeMs(cutoff[clock]));
 },[events,order,replay,replayStep,eventFilter,query]);
 const selectedNav=nav.find(n=>n[0]===tab);
 if(!token||loading)return <div className="app-loading"><div className="loading-brand"><Activity size={30}/></div><p>Connecting your workspace...</p></div>;
 return <div className="app-shell">
  {sidebar&&<div className="mobile-scrim" onClick={()=>setSidebar(false)}/>}
  <aside className={`sidebar ${sidebar?'sidebar-open':''}`}>
   <div className="brand sidebar-brand"><span className="brand-mark"><Activity size={22}/></span><span>faultline<span className="brand-dot">.</span></span></div>
   <div className="sidebar-project-label">WORKSPACE</div>
   <div className="project-select-wrap"><span className="project-icon"><Layers3 size={18}/></span><select aria-label="Select workspace" value={pid} onChange={e=>chooseProject(e.target.value)}>{projects.map(p=><option value={p.id} key={p.id}>{p.name}</option>)}</select><ChevronDown size={14}/></div>
   <button className="add-project" onClick={()=>setModal('project')}><Plus size={14}/> New workspace</button>
   <div className="nav-section-label">WORKSPACE</div>
   <nav aria-label="Main navigation" className="main-nav">{nav.slice(0,5).map(([id,label,Icon])=><button key={id} className={`nav-item ${tab===id?'active':''}`} onClick={()=>{setTab(id);setSidebar(false);setQuery('')}}><Icon size={18}/>{label}{id==='incidents'&&stats&&<span className="nav-counter">{stats.active_incidents}</span>}</button>)}</nav>
   <div className="nav-section-label nav-section-label-secondary">MANAGE</div>
   <nav className="main-nav">{nav.slice(5).filter(([id])=>id!=='audit'||canMaintain).map(([id,label,Icon])=><button className={`nav-item ${tab===id?'active':''}`} key={id} onClick={()=>{setTab(id);setSidebar(false);setQuery('')}}><Icon size={18}/>{label}</button>)}</nav>
   <div className="sidebar-bottom"><div className="system-status"><span className="ping"/><div><strong>System online</strong><small>Last synced {new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}</small></div></div>
     <div className="profile"><span className="profile-avatar">{(user?.name||'U').slice(0,1)}</span><div className="profile-info"><strong>{user?.name||'Operator'}</strong><small>{role||'No workspace'}</small></div><button title="Sign out" className="icon-btn" onClick={logout}><LogOut size={17}/></button></div>
   </div>
  </aside>
  <main className="app-main">
   <header className="topbar"><div className="topbar-left"><button className="mobile-menu icon-btn" onClick={()=>setSidebar(true)}><Command size={21}/></button><span className="crumb-muted">Workspace</span><ChevronRight size={14}/><span className="crumb-text">{project?.name||'No workspace'}</span><ChevronRight size={14}/><span className="crumb-current">{selectedNav?.[1]}</span></div>
    <div className="topbar-right"><span className="live-indicator"><span className="ping"/> AUTO-SYNC 15S</span><button className={`icon-btn ${updating?'spinning':''}`} aria-label="Refresh data" onClick={()=>void refresh()}><RefreshCw size={17}/></button><span className="topbar-divider"/><span className="header-avatar">{(user?.name||'U').slice(0,1)}</span></div></header>
   <div className="content-container">
    {!project&&<div className="onboarding"><div className="eyebrow">GET STARTED</div><h1>Your next incident starts here.</h1><p>Create a workspace to begin monitoring deployments, changes, and production events.</p><button className="btn btn-primary" onClick={()=>setModal('project')}><Plus size={17}/> Create workspace</button></div>}
    {project&&<>
     <div className="page-heading"><div><span className="eyebrow">{tab==='overview'?'OPERATIONS / COMMAND CENTER':`WORKSPACE / ${tab.toUpperCase()}`}</span><h1>{({overview:'Good to have you back.',incidents:'Incident response',deployments:'Deployment history',changes:'Code changes',timeline:'The full picture.',team:'Your response team',audit:'Evidence audit log'} as Record<Tab,string>)[tab]}</h1><p>{({overview:'Here’s what’s happening across your production systems.',incidents:'Investigate, assign and resolve production issues.',deployments:'Every release, every environment, one source of truth.',changes:'Connect code changes to the failures that follow.',timeline:'When an event happened is not always when it arrived.',team:'Control who can see and change your project.',audit:'A traceable record of actions and decisions.'} as Record<Tab,string>)[tab]}</p></div>
      <div className="heading-actions">{tab==='overview'||tab==='incidents'?canRespond&&<button className="btn btn-primary" onClick={()=>setModal('incident')}><Plus size={16}/> Report incident</button>:tab==='deployments'?canMaintain&&<button className="btn btn-primary" onClick={()=>setModal('deployment')}><Plus size={16}/> Record deployment</button>:tab==='changes'?canMaintain&&<button className="btn btn-primary" onClick={()=>setModal('change')}><Plus size={16}/> Record change</button>:tab==='timeline'?canMaintain&&<button className="btn btn-primary" onClick={()=>setModal('event')}><Plus size={16}/> Ingest event</button>:tab==='team'?isOwner&&<button className="btn btn-primary" onClick={()=>setModal('member')}><Plus size={16}/> Add member</button>:null}</div>
     </div>
     {error&&<div className="inline-error"><ShieldAlert size={17}/>{error}<button className="link-button" onClick={()=>void refresh()}>Retry</button></div>}
     {tab==='overview'&&<>
      <div className="metric-grid">
       <Metric label="Active incidents" value={stats?.active_incidents??'—'} note={`${stats?.incidents_total||0} total recorded`} icon={AlertCircle} kind="red"/>
       <Metric label="Critical priority" value={stats?.critical_open??'—'} note="Unresolved SEV1 alerts" icon={Zap} kind="amber"/>
       <Metric label="Deployments" value={stats?.deployments_total??'—'} note={`${stats?.failed_deployments||0} failed releases`} icon={GitBranch} kind="purple"/>
       <Metric label="Incident patterns" value={stats?.recurring.length??'—'} note="Recurring signatures detected" icon={Radar} kind="green"/>
      </div>
      <div className="dashboard-grid"><section className="panel span-seven"><PanelHead title="Incidents requiring attention" hint="PRIORITY QUEUE" action={()=>setTab('incidents')}/>
       <div className="incident-queue">{incidents.filter(i=>i.status!=='resolved').slice(0,5).map(i=><button className="queue-item" key={i.id} onClick={()=>setSelected(i)}><span className={`queue-indicator sevbar-${i.severity.toLowerCase()}`}/><div className="queue-title"><strong>{i.title}</strong><span>{i.service} <span className="divider-dot">•</span> {relative(i.first_seen_at)}</span></div><Severity value={i.severity}/><ChevronRight size={16} className="queue-chevron"/></button>)}
       {incidents.every(i=>i.status==='resolved')&&<Empty title="All clear" detail="No unresolved incidents in this workspace."/>}</div>
      </section><section className="panel span-five"><div className="panel-heading"><div><span className="eyebrow">HEALTH DISTRIBUTION</span><h3>Incident breakdown</h3></div><BarChart3 size={18} className="dim-icon"/></div>
       <div className="breakdown">{(['SEV1','SEV2','SEV3','SEV4'] as const).map(s=><div className="breakdown-row" key={s}><div className="breakdown-label"><span>{s}</span><strong>{stats?.by_severity[s]||0}</strong></div><div className="progress-track"><div className="progress-bar" style={{width:`${stats?.incidents_total ? ((stats.by_severity[s]||0)/stats.incidents_total)*100 : 0}%`,background:severityColor[s]}}/></div></div>)}</div>
       <div className="panel-bottom-stat"><div className="pulse-icon"><Activity size={17}/></div><div><strong>{stats?.incidents_total||0} tracked incidents</strong><small>Across all priority levels</small></div></div></section>
      <section className="panel span-seven"><PanelHead title="Recent activity" hint="EVIDENCE STREAM" action={()=>setTab('timeline')}/>
       <div className="compact-timeline">{events.slice(0,6).map(e=><div className="compact-event" key={e.id}><EventMark type={e.type}/><div><strong>{e.summary}</strong><span>{e.source} <span className="divider-dot">•</span> {relative(e.occurred_at)}</span></div><span className="compact-time">{timestamp(e.occurred_at)}</span></div>)}
       {!events.length&&<Empty title="No events yet" detail="Events appear here as your team records deployments and incidents."/>}</div></section>
      <section className="panel span-five"><div className="panel-heading"><div><span className="eyebrow">PATTERN DETECTION</span><h3>Recurring problems</h3></div><Fingerprint size={18} className="dim-icon"/></div>
       <div className="recurrence-list">{stats?.recurring.map((r,i)=><div className="recurrence-item" key={i}><span className="recurrence-count">{r.count}×</span><div><strong>{r.signature}</strong><small>{r.service}</small></div></div>)}
       {!stats?.recurring.length&&<Empty title="No repeated signatures" detail="We'll highlight recurring incident titles within the same service."/>}</div>
       <div className="insight-footnote"><ShieldCheck size={15}/> Grouping is rule-based and transparent.</div>
      </section></div>
     </>}
     {['incidents','deployments','changes'].includes(tab)&&<section className="panel list-panel"><div className="list-controls"><div className="search-box"><Search size={17}/><input aria-label="Search records" placeholder={`Search ${tab}...`} value={query} onChange={e=>setQuery(e.target.value)}/></div><span className="record-count">{tab==='incidents'?filteredInc.length:tab==='deployments'?filteredDep.length:filteredChanges.length} RECORDS</span></div>
      {tab==='incidents'&&<div className="table-wrapper"><table className="data-table"><thead><tr><th>INCIDENT</th><th>SEVERITY</th><th>STATUS</th><th>FIRST OBSERVED</th><th>ASSIGNEE</th><th/></tr></thead><tbody>{filteredInc.map(i=><tr key={i.id} onClick={()=>setSelected(i)} className="click-row"><td><strong>{i.title}</strong><span className="cell-sub">{i.service} · #{i.id.slice(0,8)}</span></td><td><Severity value={i.severity}/></td><td><Status value={i.status}/></td><td className="td-secondary">{timestamp(i.first_seen_at)}</td><td className="td-secondary">{members.find(m=>m.user_id===i.assigned_to_id)?.name||'Unassigned'}</td><td><ChevronRight size={17}/></td></tr>)}</tbody></table>{!filteredInc.length&&<Empty title="No incidents found" detail="Try another search or report a new incident."/>}</div>}
      {tab==='deployments'&&<div className="table-wrapper"><table className="data-table"><thead><tr><th>RELEASE</th><th>SERVICE</th><th>ENVIRONMENT</th><th>STATE</th><th>COMMIT</th><th>DEPLOYED AT</th></tr></thead><tbody>{filteredDep.map(d=><tr key={d.id}><td><strong className="mono">{d.version}</strong><span className="cell-sub">{d.actor||'Unspecified actor'}</span></td><td>{d.service}</td><td className="td-secondary">{d.environment}</td><td><Status value={d.status}/></td><td className="mono td-secondary">{d.commit_sha?d.commit_sha.slice(0,9):'—'}</td><td className="td-secondary">{timestamp(d.deployed_at)}</td></tr>)}</tbody></table>{!filteredDep.length&&<Empty title="No deployments found" detail="Record a release to start building deploy history."/>}</div>}
      {tab==='changes'&&<div className="table-wrapper"><table className="data-table"><thead><tr><th>COMMIT</th><th>CHANGE SUMMARY</th><th>SERVICE</th><th>AUTHOR</th><th>COMMITTED</th></tr></thead><tbody>{filteredChanges.map(c=><tr key={c.id}><td><span className="mono sha-pill">{c.sha.slice(0,8)}</span></td><td><strong>{c.title}</strong><span className="cell-sub">{c.changed_files.length} file(s) changed</span></td><td>{c.service}</td><td className="td-secondary">{c.author}</td><td className="td-secondary">{timestamp(c.committed_at)}</td></tr>)}</tbody></table>{!filteredChanges.length&&<Empty title="No code changes found" detail="Record commits to enrich incident investigations."/>}</div>}
     </section>}
     {tab==='timeline'&&<>
      <div className="timeline-toolbar panel"><div className="toolbar-left"><div className="segmented"><button className={order==='occurred'?'selected':''} onClick={()=>setOrder('occurred')}>Event time</button><button className={order==='received'?'selected':''} onClick={()=>setOrder('received')}>Arrival time</button></div><select aria-label="Filter events" value={eventFilter} onChange={e=>setEventFilter(e.target.value)} className="event-filter"><option value="all">All signals</option>{['deployment','change','incident','alert','recovery','note'].map(x=><option key={x} value={x}>{x}</option>)}</select></div><div className="toolbar-right"><span className="timestamp-hint"><Clock3 size={14}/> Dual-clock timeline</span><button className={`btn ${replay?'btn-primary':'btn-ghost'}`} onClick={()=>{setReplay(!replay);setReplayStep(events.length-1)}}><CalendarClock size={15}/>{replay?'Exit replay':'Replay history'}</button></div></div>
      {replay&&<div className="replay-strip"><div className="replay-top"><span><Zap size={16}/> POINT-IN-TIME REPLAY</span><strong>{events.length?timestamp([...events].sort((a,b)=>timeMs(order==='occurred'?a.occurred_at:a.received_at)-timeMs(order==='occurred'?b.occurred_at:b.received_at))[Math.max(0,replayStep)][order==='occurred'?'occurred_at':'received_at']):'No events'}</strong></div><input type="range" aria-label="Replay timestamp" min={0} max={Math.max(0,events.length-1)} value={Math.min(replayStep,Math.max(0,events.length-1))} onChange={e=>setReplayStep(Number(e.target.value))}/><div className="replay-foot">Move the slider to reveal only the evidence available up to that event.</div></div>}
      <div className="timeline-explainer"><Shield size={16}/> <span><strong>Two clocks, one consistent history.</strong> Event time reconstructs the actual sequence. Arrival time reveals delayed or out-of-order signals. Yellow labels mark events arriving more than 15 minutes after occurrence.</span></div>
      <section className="panel event-panel"><div className="panel-heading"><div><span className="eyebrow">CHRONOLOGICAL EVIDENCE</span><h3>Activity stream</h3></div><span className="record-count">{visibleEvents.length} EVENTS</span></div>
      <div className="event-list">{visibleEvents.map(e=><div key={e.id} className="timeline-event"><div className="event-spine"><EventMark type={e.type}/></div><div className="event-body"><div className="event-type-line"><span>{e.type.toUpperCase()}</span><span className="event-source">{e.source}</span>{elapsedMinutes(e.received_at,e.occurred_at)>15&&<span className="late-badge">DELAYED ARRIVAL</span>}</div><strong>{e.summary}</strong><div className="event-metadata"><span><Clock3 size={12}/> Event: {timestamp(e.occurred_at)}</span><span>Received: {timestamp(e.received_at)}</span></div></div></div>)}{!visibleEvents.length&&<Empty title="Nothing in this time window" detail="Adjust the replay position or record a new event."/>}</div></section>
     </>}
     {tab==='team'&&<section className="panel list-panel"><div className="panel-heading"><div><span className="eyebrow">ACCESS AND COLLABORATION</span><h3>Workspace contributors</h3></div><span className="record-count">{members.length} PEOPLE</span></div><div className="team-grid">{members.map(m=><div key={m.user_id} className="member-card"><span className="member-avatar">{m.name.slice(0,1)}</span><div><strong>{m.name}</strong><small>{m.email}</small></div><span className="member-role">{m.role}</span></div>)}</div><div className="permissions-note"><LockKeyhole size={18}/><span>Permissions are checked by the API on every request, not only hidden in the interface. Owners manage membership. Maintainers record releases and changes. Responders handle incidents. Viewers have read-only access.</span></div></section>}
     {tab==='audit'&&<section className="panel event-panel"><div className="panel-heading"><div><span className="eyebrow">ACCOUNTABILITY</span><h3>Change and action log</h3></div><span className="record-count">{audit.length} RECORDS</span></div><div className="audit-list">{audit.map(a=><div className="audit-row" key={a.id}><span className="audit-icon"><ShieldCheck size={15}/></span><div><strong>{a.action.replaceAll('.',' / ').replaceAll('_',' ')}</strong><small>{a.incident_id?`Incident ${a.incident_id.slice(0,8)} · `:''}{a.actor_id?'Team action':'System action'}</small></div><span className="td-secondary">{timestamp(a.created_at)}</span></div>)}{!audit.length&&<Empty title="No audit events" detail="Changes will be recorded here."/>}</div></section>}
     <div className="content-footer"><span>FAULTLINE / BUILT FOR CLEARER INCIDENT RESPONSE</span><span>v1.0 · Data refreshed every 15 seconds</span></div>
    </>}
   </div>
  </main>
  {modal&&<CreateModal type={modal} token={token} projectId={pid} onClose={()=>setModal(null)} onSaved={id=>void saved(id)}/>}
  {selected&&<IncidentPanel incident={selected} projectId={pid} token={token} members={members} canEdit={canRespond} onClose={()=>setSelected(null)} onChanged={()=>void changedIncident()}/>}
 </div>
}
function PanelHead({title,hint,action}:{title:string;hint:string;action:()=>void}){return <div className="panel-heading"><div><span className="eyebrow">{hint}</span><h3>{title}</h3></div><button onClick={action} className="panel-more">View all <ArrowUpRight size={15}/></button></div>}
function Metric({label,value,note,icon:Icon,kind}:{label:string;value:number|string;note:string;icon:typeof Activity;kind:string}){return <div className={`metric-card metric-${kind}`}><div className="metric-header"><span>{label}</span><div className="metric-icon"><Icon size={18}/></div></div><div className="metric-number">{value}</div><div className="metric-note"><ArrowUpRight size={13}/>{note}</div></div>}
