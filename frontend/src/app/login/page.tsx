'use client';
import { FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { Activity, ArrowRight, Fingerprint, GitBranch, ShieldCheck } from 'lucide-react';
export default function LoginPage(){
  const router=useRouter();
  const [email,setEmail]=useState('alex@faultline.dev');
  const [password,setPassword]=useState('DemoPassword123!');
  const [name,setName]=useState('');
  const [signup,setSignup]=useState(false);
  const [error,setError]=useState('');
  const [loading,setLoading]=useState(false);
  async function submit(e:FormEvent){e.preventDefault();setLoading(true);setError('');try{
    const response=await api<{access_token:string;user:{name:string;email:string;id:string}}>(signup?'/api/auth/register':'/api/auth/login',undefined,{method:'POST',body:JSON.stringify(signup?{name,email,password}:{email,password})});
    localStorage.setItem('faultline_token',response.access_token);
    localStorage.setItem('faultline_user',JSON.stringify(response.user));
    router.push('/');
  }catch(err){setError(err instanceof Error?err.message:'Unable to log in')}finally{setLoading(false)}}
  return <div className="auth-viewport">
    <div className="auth-backdrop"><div className="orbit orbit-a"/><div className="orbit orbit-b"/><div className="orbit orbit-c"/></div>
    <section className="auth-story">
      <div className="brand auth-brand"><span className="brand-mark"><Activity size={23}/></span><span>faultline<span className="brand-dot">.</span></span></div>
      <span className="eyebrow">INCIDENT INTELLIGENCE PLATFORM / V1.0</span>
      <h1>Every outage<br/>has a <em>story.</em></h1>
      <p>Trace deployments. Connect the evidence. Find out what changed before everything broke.</p>
      <div className="auth-features"><div><GitBranch size={17}/><span>Change-aware timelines</span></div><div><Fingerprint size={17}/><span>Explainable incident leads</span></div><div><ShieldCheck size={17}/><span>Immutable evidence trail</span></div></div>
      <div className="auth-footer-note">BUILT TO UNDERSTAND WHAT HAPPENED.</div>
    </section>
    <section className="auth-card"><div className="auth-card-inner"><div className="auth-glyph"><Activity size={25}/></div><div className="eyebrow">WELCOME TO FAULTLINE</div><h2>{signup?'Create an account':'Sign in to investigate'}</h2><p className="subdued">Your workspace for incidents, releases, and change history.</p>
      <form onSubmit={submit} className="stack-form">
        {signup&&<label>Full name<input placeholder="Alex Morgan" autoComplete="name" value={name} onChange={e=>setName(e.target.value)} required minLength={2}/></label>}
        <label>Work email<input type="email" autoComplete="email" value={email} onChange={e=>setEmail(e.target.value)} required/></label>
        <label>Password<input type="password" autoComplete={signup?'new-password':'current-password'} value={password} onChange={e=>setPassword(e.target.value)} required minLength={10}/></label>
        {error&&<div className="form-error" role="alert">{error}</div>}
        <button className="btn btn-primary auth-submit" disabled={loading}>{loading?'Connecting...':signup?'Create account':'Enter workspace'} <ArrowRight size={16}/></button>
      </form>
      <button className="link-button auth-switch" onClick={()=>{setSignup(!signup);setError('')}}>{signup?'Already have an account? Sign in':'New to Faultline? Create an account'}</button>
      <div className="demo-hint"><span className="small-dot"/>Demo mode: credentials are prefilled. Sample workspace loads automatically.</div>
    </div></section>
  </div>
}
