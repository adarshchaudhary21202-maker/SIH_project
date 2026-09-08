// Run the browser UI from an HTTP server (for example VS Code Live Server),
// never from file://. An explicit deployment override still takes precedence.
const base = globalThis.__API_BASE__ || localStorage.getItem('ncb.apiBase') || 'http://localhost:8000';
const tokenStore = { get value() { const raw = sessionStorage.getItem('ncb.tokens'); return raw ? JSON.parse(raw) : null; }, set value(value) { value ? sessionStorage.setItem('ncb.tokens', JSON.stringify(value)) : sessionStorage.removeItem('ncb.tokens'); } };
export class ApiClient {
    async request(path, init = {}, retry = true) {
        const access = tokenStore.value?.access_token;
        const response = await fetch(base + path, { ...init, headers: { 'Content-Type': 'application/json', ...(access ? { Authorization: `Bearer ${access}` } : {}), ...(init.headers || {}) } });
        if (response.status === 401 && retry && tokenStore.value && await this.refresh())
            return this.request(path, init, false);
        if (!response.ok) {
            let body = {};
            try {
                body = await response.json();
            }
            catch { /* non-JSON error */ }
            throw { status: response.status, message: (typeof body.detail === 'string' && body.detail) || body.message || `Request failed (${response.status})`, fields: Array.isArray(body.detail) ? Object.fromEntries(body.detail.map((e) => [e.loc?.at(-1) || 'form', e.msg])) : undefined };
        }
        return response.status === 204 ? undefined : response.json();
    }
    async refresh() { if (!this.refreshing)
        this.refreshing = (async () => { try {
            const tokens = tokenStore.value;
            if (!tokens)
                return false;
            tokenStore.value = await this.request('/auth/refresh', { method: 'POST', body: JSON.stringify({ refresh_token: tokens.refresh_token }) }, false);
            return true;
        }
        catch {
            tokenStore.value = null;
            return false;
        }
        finally {
            this.refreshing = undefined;
        } })(); return this.refreshing; }
    login(body) { return this.request('/auth/login', { method: 'POST', body: JSON.stringify(body) }); }
    register(body) { return this.request('/auth/register', { method: 'POST', body: JSON.stringify(body) }); }
    verifyOtp(badge_id, otp, device_id) { return this.request('/auth/verify-otp', { method: 'POST', body: JSON.stringify({ badge_id, otp, device_id }) }); }
    resend(body) { return this.request('/auth/resend-otp', { method: 'POST', body: JSON.stringify(body) }); }
    async establish(tokens) { tokenStore.value = tokens; return this.me(); }
    me() { return this.request('/auth/me'); }
    async logout() { const tokens = tokenStore.value; try {
        if (tokens)
            await this.request('/auth/logout', { method: 'POST', body: JSON.stringify({ refresh_token: tokens.refresh_token }) });
    }
    finally {
        tokenStore.value = null;
    } }
    cases() { return this.request('/officer/cases'); }
    createCase(body) { return this.request('/officer/cases', { method: 'POST', body: JSON.stringify(body) }); }
    sessions() { return this.request('/officer/test-sessions'); }
    createSession(body) { return this.request('/officer/test-sessions', { method: 'POST', body: JSON.stringify(body) }); }
    createEvidence(body) { return this.request('/officer/evidence', { method: 'POST', body: JSON.stringify(body) }); }
    correction(id, body) { return this.request(`/officer/evidence/${id}/corrections`, { method: 'POST', body: JSON.stringify(body) }); }
    supervisorEvidence() { return this.request('/supervisor/evidence'); }
    corrections() { return this.request('/supervisor/corrections'); }
    verifyEvidence(id) { return this.request(`/supervisor/evidence/${id}/verify`); }
    approveEvidence(id, reason) { return this.request(`/supervisor/evidence/${id}/approve`, { method: 'POST', body: JSON.stringify({ reason }) }); }
    rejectEvidence(id, reason) { return this.request(`/supervisor/evidence/${id}/reject`, { method: 'POST', body: JSON.stringify({ reason }) }); }
    reviewCorrection(id, approved, reason) { return this.request(`/supervisor/corrections/${id}/${approved ? 'approve' : 'reject'}`, { method: 'POST', body: JSON.stringify({ reason }) }); }
    audit() { return this.request('/supervisor/audit'); }
    custody(id) { return this.request(`/supervisor/evidence/${id}/custody`); }
    transfer(id, body) { return this.request(`/officer/evidence/${id}/custody`, { method: 'POST', body: JSON.stringify(body) }); }
}
export const api = new ApiClient();
export const auth = { get active() { return tokenStore.value !== null; } };
export async function qrSource(id) { const token = tokenStore.value?.access_token; if (!token)
    throw { status: 401, message: 'Session expired' }; const response = await fetch(`${base}/evidence/${id}/qr`, { headers: { Authorization: `Bearer ${token}` } }); if (!response.ok)
    throw { status: response.status, message: 'Unable to retrieve evidence QR' }; return URL.createObjectURL(await response.blob()); }
