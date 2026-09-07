const base = globalThis.__API_BASE__ || localStorage.getItem('ncb.apiBase') || 'http://127.0.0.1:8000';
const tokenStore = { get value() { const x = sessionStorage.getItem('ncb.tokens'); return x ? JSON.parse(x) : null; }, set value(x) { x ? sessionStorage.setItem('ncb.tokens', JSON.stringify(x)) : sessionStorage.removeItem('ncb.tokens'); } };
export class ApiClient {
    async request(path, init = {}, retry = true) { const access = tokenStore.value?.access_token; const r = await fetch(base + path, { ...init, headers: { 'Content-Type': 'application/json', ...(access ? { Authorization: `Bearer ${access}` } : {}), ...(init.headers || {}) } }); if (r.status === 401 && retry && tokenStore.value && await this.refresh())
        return this.request(path, init, false); if (!r.ok) {
        let b = {};
        try {
            b = await r.json();
        }
        catch { }
        ;
        throw { status: r.status, message: b.detail || b.message || `Request failed (${r.status})`, fields: Array.isArray(b.detail) ? Object.fromEntries(b.detail.map((x) => [x.loc?.at(-1) || 'form', x.msg])) : undefined };
    } if (r.status === 204)
        return undefined; return r.json(); }
    async refresh() { if (!this.refreshing)
        this.refreshing = (async () => { try {
            const t = tokenStore.value;
            if (!t)
                return false;
            tokenStore.value = await this.request('/auth/refresh', { method: 'POST', body: JSON.stringify({ refresh_token: t.refresh_token }) }, false);
            return true;
        }
        catch {
            tokenStore.value = null;
            return false;
        }
        finally {
            this.refreshing = undefined;
        } })(); return this.refreshing; }
    login(b) { return this.request('/auth/login', { method: 'POST', body: JSON.stringify(b) }); }
    verifyOtp(badge_id, otp, device_id) { return this.request('/auth/verify-otp', { method: 'POST', body: JSON.stringify({ badge_id, otp, device_id }) }); }
    resend(b) { return this.request('/auth/resend-otp', { method: 'POST', body: JSON.stringify(b) }); }
    async establish(t) { tokenStore.value = t; return this.me(); }
    me() { return this.request('/auth/me'); }
    async logout() { const t = tokenStore.value; try {
        if (t)
            await this.request('/auth/logout', { method: 'POST', body: JSON.stringify({ refresh_token: t.refresh_token }) });
    }
    finally {
        tokenStore.value = null;
    } }
    cases() { return this.request('/officer/cases'); }
    createCase(b) { return this.request('/officer/cases', { method: 'POST', body: JSON.stringify(b) }); }
    sessions() { return this.request('/officer/test-sessions'); }
    createSession(b) { return this.request('/officer/test-sessions', { method: 'POST', body: JSON.stringify(b) }); }
    endSession(id) { return this.request(`/officer/test-sessions/${id}/end`, { method: 'POST' }); }
    createEvidence(b) { return this.request('/officer/evidence', { method: 'POST', body: JSON.stringify(b) }); }
    qr(id) { return `${base}/evidence/${id}/qr`; }
    correction(id, b) { return this.request(`/officer/evidence/${id}/corrections`, { method: 'POST', body: JSON.stringify(b) }); }
    supervisorEvidence() { return this.request('/supervisor/evidence'); }
    supervisorCases() { return this.request('/supervisor/cases'); }
    verifyEvidence(id) { return this.request(`/supervisor/evidence/${id}/verify`); }
    approveEvidence(id, reason) { return this.request(`/supervisor/evidence/${id}/approve`, { method: 'POST', body: JSON.stringify({ reason }) }); }
    rejectEvidence(id, reason) { return this.request(`/supervisor/evidence/${id}/reject`, { method: 'POST', body: JSON.stringify({ reason }) }); }
    corrections() { return this.request('/supervisor/corrections'); }
    reviewCorrection(id, ok, reason) { return this.request(`/supervisor/corrections/${id}/${ok ? 'approve' : 'reject'}`, { method: 'POST', body: JSON.stringify({ reason }) }); }
    audit() { return this.request('/supervisor/audit'); }
    custody(id) { return this.request(`/supervisor/evidence/${id}/custody`); }
    transfer(id, b) { return this.request(`/officer/evidence/${id}/custody`, { method: 'POST', body: JSON.stringify(b) }); }
}
export const api = new ApiClient();
export const auth = { get active() { return tokenStore.value !== null; } };
/** Fetches the protected QR image with the bearer token; an <img src> cannot attach it. */
export async function qrSource(id) { const token = tokenStore.value?.access_token; if (!token)
    throw { status: 401, message: 'Session expired' }; const r = await fetch(`${base}/evidence/${id}/qr`, { headers: { Authorization: `Bearer ${token}` } }); if (!r.ok)
    throw { status: r.status, message: 'Unable to retrieve evidence QR' }; return URL.createObjectURL(await r.blob()); }
