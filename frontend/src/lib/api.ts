export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
export interface User { id:string; name:string; email:string }
export interface Project { id:string; name:string; slug:string; description:string; created_at:string; role:string }
export interface Incident { id:string; project_id:string; title:string; description:string; service:string; severity:'SEV1'|'SEV2'|'SEV3'|'SEV4'; status:'open'|'investigating'|'mitigated'|'resolved'; assigned_to_id:string|null; first_seen_at:string; resolved_at:string|null; resolution:string; version:number; created_at:string }
export interface Deployment { id:string; project_id:string; version:string; environment:string; service:string; status:string; commit_sha:string; actor:string; deployed_at:string; created_at:string }
export interface Change { id:string; project_id:string; sha:string; title:string; author:string; service:string; changed_files:string[]; committed_at:string }
export interface Event { id:string; project_id:string; source:string; external_id:string; type:string; summary:string; occurred_at:string; received_at:string; entity_id:string|null; entity_type:string|null; details:Record<string, unknown> }
export interface Member { user_id:string; email:string; name:string; role:string }
export interface Note { id:string; incident_id:string; author_id:string; author_name:string; body:string; created_at:string }
export interface Candidate { deployment_id:string; version:string; service:string; deployed_at:string; score:number; reasons:string[]; commit_sha:string; note:string }
export interface Dashboard { incidents_total:number; active_incidents:number; critical_open:number; deployments_total:number; failed_deployments:number; recurring:{service:string; signature:string; count:number; incident_ids:string[]}[]; by_severity:Record<string,number>; by_status:Record<string,number> }
export interface Audit { id:string; action:string; actor_id:string|null; incident_id:string|null; before:Record<string,unknown>; after:Record<string,unknown>; created_at:string }
export async function api<T>(path:string, token?:string, options:RequestInit = {}):Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {cache:'no-store', ...options,
    headers:{'Content-Type':'application/json', ...(token?{Authorization:`Bearer ${token}`} : {}), ...(options.headers||{})}});
  if (!res.ok) {
    const data: {detail?:unknown} = await res.json().catch(()=>({}));
    const detail = Array.isArray(data.detail) ? data.detail.map((x: {msg?:string})=>x.msg||'Invalid field').join(', ') : data.detail;
    const error = new Error(typeof detail === 'string' ? detail : `Request failed (${res.status})`) as Error & {status:number};
    error.status=res.status; throw error;
  }
  return res.json() as Promise<T>;
}
export function timestamp(date:string | null | undefined):string {
  if(!date) return '—';
  const d=new Date(date); return Number.isNaN(d.getTime())?'—':d.toLocaleString(undefined, {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'});
}
export function relative(date:string):string {
  const diff=(Date.now()-new Date(date).getTime())/60000;
  if(diff<0) return 'scheduled';
  if(diff<1) return 'just now'; if(diff<60) return `${Math.floor(diff)}m ago`;
  if(diff<1440) return `${Math.floor(diff/60)}h ago`; return `${Math.floor(diff/1440)}d ago`;
}
export function elapsedMinutes(a:string,b:string):number {return Math.round((new Date(a).getTime()-new Date(b).getTime())/60000);}
export function canWrite(role:string | undefined, min:'responder'|'maintainer'|'owner') {
  const rank:Record<string,number>={viewer:0,responder:1,maintainer:2,owner:3};
  return (rank[role||'viewer']||0) >= rank[min];
}
