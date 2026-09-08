import type { ApiError, AuditEvent, Case, CaseCreated, Correction, CustodyEvent, Evidence, EvidenceCreated, LoginRequest, RegisterRequest, RegistrationResult, TestSession, TestSessionCreated, Tokens, User } from './models.js';

// Run the browser UI from an HTTP server (for example VS Code Live Server),
// never from file://. An explicit deployment override still takes precedence.
const base = (globalThis as unknown as { __API_BASE__?:string }).__API_BASE__ || localStorage.getItem('ncb.apiBase') || 'http://localhost:8000';
const tokenStore = { get value():Tokens|null { const raw=sessionStorage.getItem('ncb.tokens'); return raw ? JSON.parse(raw) as Tokens : null }, set value(value:Tokens|null) { value ? sessionStorage.setItem('ncb.tokens', JSON.stringify(value)) : sessionStorage.removeItem('ncb.tokens') } };
export class ApiClient {
  private refreshing?:Promise<boolean>;
  async request<T>(path:string, init:RequestInit={}, retry=true):Promise<T> {
    const access=tokenStore.value?.access_token;
    const response=await fetch(base+path,{...init,headers:{'Content-Type':'application/json',...(access?{Authorization:`Bearer ${access}`}:{ }),...(init.headers||{})}});
    if(response.status===401 && retry && tokenStore.value && await this.refresh()) return this.request<T>(path,init,false);
    if(!response.ok) { let body:{detail?:unknown;message?:string}={}; try { body=await response.json() } catch { /* non-JSON error */ }
      throw {status:response.status,message:(typeof body.detail==='string'&&body.detail)||body.message||`Request failed (${response.status})`,fields:Array.isArray(body.detail)?Object.fromEntries(body.detail.map((e:{loc?:string[];msg:string})=>[e.loc?.at(-1)||'form',e.msg])):undefined} as ApiError;
    }
    return response.status===204 ? undefined as T : response.json() as Promise<T>;
  }
  private async refresh() { if(!this.refreshing) this.refreshing=(async()=>{ try { const tokens=tokenStore.value; if(!tokens)return false; tokenStore.value=await this.request<Tokens>('/auth/refresh',{method:'POST',body:JSON.stringify({refresh_token:tokens.refresh_token})},false); return true } catch { tokenStore.value=null; return false } finally { this.refreshing=undefined } })(); return this.refreshing }
  login(body:LoginRequest) { return this.request<{message:string;badge_id:string;development_otp?:string}>('/auth/login',{method:'POST',body:JSON.stringify(body)}) }
  register(body:RegisterRequest) { return this.request<RegistrationResult>('/auth/register',{method:'POST',body:JSON.stringify(body)}) }
  verifyOtp(badge_id:string,otp:string,device_id:string) { return this.request<Tokens>('/auth/verify-otp',{method:'POST',body:JSON.stringify({badge_id,otp,device_id})}) }
  resend(body:LoginRequest) { return this.request<{message:string;development_otp?:string}>('/auth/resend-otp',{method:'POST',body:JSON.stringify(body)}) }
  async establish(tokens:Tokens) { tokenStore.value=tokens; return this.me() }
  me() { return this.request<User>('/auth/me') }
  async logout() { const tokens=tokenStore.value; try { if(tokens) await this.request('/auth/logout',{method:'POST',body:JSON.stringify({refresh_token:tokens.refresh_token})}) } finally { tokenStore.value=null } }
  cases() { return this.request<Case[]>('/officer/cases') } createCase(body:Record<string,string>) { return this.request<CaseCreated>('/officer/cases',{method:'POST',body:JSON.stringify(body)}) }
  sessions() { return this.request<TestSession[]>('/officer/test-sessions') } createSession(body:Record<string,string>) { return this.request<TestSessionCreated>('/officer/test-sessions',{method:'POST',body:JSON.stringify(body)}) }
  createEvidence(body:Record<string,unknown>) { return this.request<EvidenceCreated>('/officer/evidence',{method:'POST',body:JSON.stringify(body)}) }
  correction(id:string,body:Record<string,unknown>) { return this.request(`/officer/evidence/${id}/corrections`,{method:'POST',body:JSON.stringify(body)}) }
  supervisorEvidence() { return this.request<Evidence[]>('/supervisor/evidence') } corrections() { return this.request<Correction[]>('/supervisor/corrections') }
  verifyEvidence(id:string) { return this.request<{hash_valid:boolean;status:string}>(`/supervisor/evidence/${id}/verify`) }
  approveEvidence(id:string,reason:string) { return this.request(`/supervisor/evidence/${id}/approve`,{method:'POST',body:JSON.stringify({reason})}) } rejectEvidence(id:string,reason:string) { return this.request(`/supervisor/evidence/${id}/reject`,{method:'POST',body:JSON.stringify({reason})}) }
  reviewCorrection(id:string,approved:boolean,reason:string) { return this.request(`/supervisor/corrections/${id}/${approved?'approve':'reject'}`,{method:'POST',body:JSON.stringify({reason})}) }
  audit() { return this.request<AuditEvent[]>('/supervisor/audit') } custody(id:string) { return this.request<CustodyEvent[]>(`/supervisor/evidence/${id}/custody`) }
  transfer(id:string,body:Record<string,string>) { return this.request(`/officer/evidence/${id}/custody`,{method:'POST',body:JSON.stringify(body)}) }
}
export const api=new ApiClient(); export const auth={get active(){return tokenStore.value!==null}};
export async function qrSource(id:string) { const token=tokenStore.value?.access_token; if(!token) throw {status:401,message:'Session expired'} as ApiError; const response=await fetch(`${base}/evidence/${id}/qr`,{headers:{Authorization:`Bearer ${token}`}}); if(!response.ok) throw {status:response.status,message:'Unable to retrieve evidence QR'} as ApiError; return URL.createObjectURL(await response.blob()) }
