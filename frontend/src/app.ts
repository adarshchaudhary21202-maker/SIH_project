import { api, auth, qrSource } from './api.js';
import type { ApiError, Evidence, EvidenceCreated, Role, User } from './models.js';

const root = document.querySelector<HTMLDivElement>('#app')!;
let currentUser: User | null = null;
let selectedRole: Extract<Role, 'OFFICER' | 'SUPERVISOR'> = 'OFFICER';
let pendingLogin: { badge_id: string; password: string; device_id: string; device_name: string } | null = null;
let selectedEvidence: (Evidence | EvidenceCreated) | null = null;
let resendTimer: number | undefined;
let resendAt = 0;

const officerNav = [
  ['dashboard', 'Dashboard'], ['create-case', 'Create Case'], ['create-session', 'Create Test Session'],
  ['kit', 'Kit Verification'], ['capture', 'Test Capture'], ['result', 'Test Result'],
  ['my-evidence', 'My Evidence'], ['evidence-details', 'Evidence Details'], ['evidence-qr', 'Evidence QR'], ['custody', 'Chain of Custody'],
] as const;
const supervisorNav = [
  ['dashboard', 'Dashboard'], ['review', 'Evidence Review'], ['evidence-details', 'Evidence Details'],
  ['verify', 'Verify Evidence'], ['corrections', 'Correction Requests'], ['audit', 'Audit Timeline'],
  ['custody', 'Chain of Custody'], ['officer-activity', 'Officer Activity'],
] as const;

const escapeHtml = (value: unknown) => String(value ?? '').replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]!));
const messageFor = (error: unknown) => (error as ApiError).message || 'Unable to complete the request.';
const apiError = (error: unknown) => `<p class="error" role="alert">${escapeHtml(messageFor(error))}</p>`;
const empty = (text: string) => `<div class="empty">${escapeHtml(text)}</div>`;
const field = (name: string, label: string, type = 'text', value = '') => `<label class="field">${label}<input name="${name}" type="${type}" value="${escapeHtml(value)}" required /></label>`;

function notify(text: string, kind = 'success') {
  const item = document.createElement('div'); item.className = `toast ${kind}`; item.textContent = text;
  document.querySelector('#toast-region')!.append(item); window.setTimeout(() => item.remove(), 4200);
}
function setBusy(button: HTMLButtonElement, busy: boolean) {
  button.disabled = busy; button.dataset.label ||= button.textContent || 'Submit'; button.textContent = busy ? 'Working…' : button.dataset.label;
}
function formatDate(value?: string) { return value ? new Date(value).toLocaleString() : '—'; }

function loginPage(error = '') {
  clearInterval(resendTimer);
  root.innerHTML = `<main class="auth"><section class="auth-card" aria-labelledby="login-title">
    <p class="brand">NCB · DIGITAL EVIDENCE</p><h1 id="login-title">Secure sign in</h1>
    <p class="muted">Choose the workspace you intend to use. The authenticated server role controls access after verification.</p>
    ${error ? `<p class="error" role="alert">${escapeHtml(error)}</p>` : ''}
    <div class="role-picker" aria-label="Intended workspace">
      <button type="button" data-role="OFFICER" class="${selectedRole === 'OFFICER' ? 'selected' : ''}"><strong>Login as Officer</strong><span>Capture and submit evidence</span></button>
      <button type="button" data-role="SUPERVISOR" class="${selectedRole === 'SUPERVISOR' ? 'selected' : ''}"><strong>Login as Supervisor</strong><span>Review and verify evidence</span></button>
    </div>
    <form id="login-form" novalidate>${field('badge_id', 'Badge ID / Email')}${field('password', 'Password', 'password')}<button class="primary" type="submit">Login</button></form>
    <button id="create-account" class="link-button create-account" type="button">Create Account</button>
  </section></main>`;
  document.querySelectorAll<HTMLButtonElement>('[data-role]').forEach(button => button.onclick = () => { selectedRole = button.dataset.role as typeof selectedRole; loginPage(); });
  document.querySelector<HTMLFormElement>('#login-form')!.onsubmit = submitLogin;
  document.querySelector<HTMLButtonElement>('#create-account')!.onclick = () => registrationPage();
}
function registrationPage(error = '') {
  clearInterval(resendTimer);
  root.innerHTML = `<main class="auth"><section class="auth-card" aria-labelledby="register-title">
    <p class="brand">NCB · DIGITAL EVIDENCE</p><h1 id="register-title">Create account</h1>
    <p class="muted">Register your NCB workspace account. Administrators manage elevated access separately.</p>
    ${error ? `<p class="error" role="alert">${escapeHtml(error)}</p>` : ''}
    <form id="register-form" novalidate>
      ${field('full_name', 'Full name')}${field('email', 'Email', 'email')}${field('badge_id', 'Badge ID')}
      <label class="field">Role<select name="role"><option value="OFFICER">Officer</option><option value="SUPERVISOR">Supervisor</option></select></label>
      ${field('password', 'Password (12+ characters, letters and numbers)', 'password')}${field('confirm_password', 'Confirm password', 'password')}
      <button class="primary" type="submit">Register</button>
    </form>
    <button id="back-to-login" class="link-button" type="button">Back to Login</button>
  </section></main>`;
  document.querySelector<HTMLFormElement>('#register-form')!.onsubmit = submitRegistration;
  document.querySelector<HTMLButtonElement>('#back-to-login')!.onclick = () => loginPage();
}
async function submitRegistration(event: SubmitEvent) {
  event.preventDefault();
  const form = event.currentTarget as HTMLFormElement, data = new FormData(form);
  const full_name = String(data.get('full_name') || '').trim(), email = String(data.get('email') || '').trim(), badge_id = String(data.get('badge_id') || '').trim();
  const password = String(data.get('password') || ''), confirm_password = String(data.get('confirm_password') || ''), role = String(data.get('role') || 'OFFICER') as 'OFFICER'|'SUPERVISOR';
  if (!full_name || !email || !badge_id || !password || !confirm_password) return registrationPage('Complete all required fields.');
  if (password !== confirm_password) return registrationPage('Passwords do not match.');
  const button = form.querySelector<HTMLButtonElement>('button[type="submit"]')!; setBusy(button, true);
  try { await api.register({ full_name, email, badge_id, password, role }); loginPage('Account created. Sign in with your badge ID or email.'); }
  catch (error) { registrationPage(messageFor(error)); } finally { setBusy(button, false); }
}
async function submitLogin(event: SubmitEvent) {
  event.preventDefault(); const form = event.currentTarget as HTMLFormElement; const data = new FormData(form);
  const badge_id = String(data.get('badge_id') || '').trim(), password = String(data.get('password') || '');
  if (!badge_id || !password) return loginPage('Enter both your email/badge ID and password.');
  const device_id = crypto.randomUUID(); pendingLogin = { badge_id, password, device_id, device_name: navigator.userAgent.slice(0, 100) };
  const button = form.querySelector<HTMLButtonElement>('button[type="submit"]')!; setBusy(button, true);
  try { const result = await api.login(pendingLogin); pendingLogin.badge_id = result.badge_id; otpPage(result.development_otp ? `Development OTP: ${result.development_otp}` : 'An OTP has been issued for this account.'); }
  catch (error) { pendingLogin = null; loginPage(messageFor(error)); } finally { setBusy(button, false); }
}
function otpPage(note = '') {
  if (!pendingLogin) return loginPage(); resendAt = Date.now() + 60_000; clearInterval(resendTimer);
  root.innerHTML = `<main class="auth"><section class="auth-card" aria-labelledby="otp-title"><p class="brand">SECOND FACTOR</p><h1 id="otp-title">Verify OTP</h1>
    <p class="muted">Enter the six-digit code for ${escapeHtml(pendingLogin.badge_id)}.</p>${note ? `<p class="notice">${escapeHtml(note)}</p>` : ''}
    <form id="otp-form" novalidate><label class="field">One-time password<input class="otp" name="otp" inputmode="numeric" autocomplete="one-time-code" maxlength="6" required /></label><button class="primary" type="submit">Verify and sign in</button></form>
    <p class="muted" id="resend-status"></p><button id="resend" class="secondary" type="button">Resend OTP</button><button id="back" class="link-button" type="button">Use another account</button>
  </section></main>`;
  document.querySelector<HTMLFormElement>('#otp-form')!.onsubmit = submitOtp;
  document.querySelector<HTMLButtonElement>('#resend')!.onclick = resendOtp;
  document.querySelector<HTMLButtonElement>('#back')!.onclick = () => { pendingLogin = null; loginPage(); };
  updateResend(); resendTimer = window.setInterval(updateResend, 1000);
}
function updateResend() { const seconds = Math.max(0, Math.ceil((resendAt - Date.now()) / 1000)); const button = document.querySelector<HTMLButtonElement>('#resend'), text = document.querySelector('#resend-status'); if (!button || !text) return; button.disabled = seconds > 0; text.textContent = seconds ? `Resend available in ${seconds}s.` : 'You can request a new OTP.'; if (!seconds) clearInterval(resendTimer); }
async function submitOtp(event: SubmitEvent) {
  event.preventDefault(); if (!pendingLogin) return loginPage(); const form = event.currentTarget as HTMLFormElement; const otp = String(new FormData(form).get('otp') || '').trim();
  if (!/^\d{6}$/.test(otp)) return otpPage('Enter a six-digit OTP.');
  const button = form.querySelector<HTMLButtonElement>('button')!; setBusy(button, true);
  try { const user = await api.establish(await api.verifyOtp(pendingLogin.badge_id, otp, pendingLogin.device_id)); currentUser = user; pendingLogin = null; location.hash = '#/dashboard'; }
  catch (error) { const text = messageFor(error); otpPage(/expired/i.test(text) ? 'This OTP has expired. Request a new code.' : text); } finally { setBusy(button, false); }
}
async function resendOtp() { if (!pendingLogin) return; const button = document.querySelector<HTMLButtonElement>('#resend')!; setBusy(button, true); try { await api.resend(pendingLogin); resendAt = Date.now() + 60_000; updateResend(); resendTimer = window.setInterval(updateResend, 1000); notify('OTP reissued.'); } catch (error) { notify(messageFor(error), 'error'); } finally { setBusy(button, false); } }

function layout(page: string, content: string) {
  if (!currentUser) return; const nav = currentUser.role === 'SUPERVISOR' ? supervisorNav : officerNav;
  root.innerHTML = `<div class="shell"><aside class="side"><p class="brand">NCB SECURE</p><h1>${escapeHtml(currentUser.full_name)}</h1><p class="muted">${escapeHtml(currentUser.role)} · ${escapeHtml(currentUser.badge_id)}</p><nav class="nav" aria-label="Workspace navigation">${nav.map(([id, label]) => `<button type="button" data-page="${id}" class="${page === id ? 'active' : ''}">${label}</button>`).join('')}</nav><button class="logout" id="logout" type="button">Logout</button></aside><main class="content"><header class="top"><div><h2>${escapeHtml(nav.find(item => item[0] === page)?.[1] || 'Workspace')}</h2><p class="muted">Server-authenticated access</p></div></header><section id="page-content">${content}</section></main></div>`;
  document.querySelectorAll<HTMLButtonElement>('[data-page]').forEach(button => button.onclick = () => location.hash = `#/${button.dataset.page}`);
  document.querySelector<HTMLButtonElement>('#logout')!.onclick = logout;
}
const cards = (items: [string, string][]) => `<div class="grid">${items.map(([label, value]) => `<article class="card"><span class="muted">${escapeHtml(label)}</span><strong class="metric">${escapeHtml(value)}</strong></article>`).join('')}</div>`;

async function dashboard() { if (currentUser?.role === 'SUPERVISOR') { const [evidence, corrections] = await Promise.all([api.supervisorEvidence(), api.corrections()]); layout('dashboard', cards([['Evidence records', String(evidence.length)], ['Pending review', String(evidence.filter(item => item.status === 'PENDING_REVIEW').length)], ['Correction requests', String(corrections.filter(item => item.status === 'PENDING').length)]])); } else { const [cases, sessions] = await Promise.all([api.cases(), api.sessions()]); layout('dashboard', cards([['My cases', String(cases.length)], ['Test sessions', String(sessions.length)], ['Active sessions', String(sessions.filter(item => item.status === 'STARTED').length)]])); } }
function createCase() { layout('create-case', `<article class="card"><form id="case-form">${field('case_number', 'Case number')}${field('title', 'Case title')}<label class="field">Description<textarea name="description"></textarea></label><button class="primary">Create case</button></form></article>`); document.querySelector<HTMLFormElement>('#case-form')!.onsubmit = async event => { event.preventDefault(); try { await api.createCase(Object.fromEntries(new FormData(event.currentTarget as HTMLFormElement)) as Record<string, string>); notify('Case created successfully.'); location.hash = '#/dashboard'; } catch (error) { notify(messageFor(error), 'error'); } }; }
function createSession() { layout('create-session', `<article class="card"><p class="notice">The API requires existing Case, Test Kit, and Device Session UUIDs. This client does not fabricate those identifiers.</p><form id="session-form">${field('case_id', 'Case UUID')}${field('test_kit_id', 'Test kit UUID')}${field('device_session_id', 'Device session UUID')}${field('gps_latitude', 'GPS latitude')}${field('gps_longitude', 'GPS longitude')}<button class="primary">Start test session</button></form></article>`); document.querySelector<HTMLFormElement>('#session-form')!.onsubmit = async event => { event.preventDefault(); try { await api.createSession(Object.fromEntries(new FormData(event.currentTarget as HTMLFormElement)) as Record<string, string>); notify('Test session started.'); location.hash = '#/dashboard'; } catch (error) { notify(messageFor(error), 'error'); } }; }
function kitVerification() { layout('kit', empty('Kit validation is enforced by the backend during session and evidence submission. No client-side verification decision is made.')); }
function testCapture() { layout('capture', `<article class="card"><h3>Test capture</h3><p class="muted">Camera capture is a placeholder until the authorized upload service is connected. No local image analysis or chemical classification is performed.</p></article>`); }
function testResult() { layout('result', `<article class="card"><h3>Submit capture metadata</h3><p class="notice">All result fields remain server-supplied or pending. This form does not calculate, classify, or trust a frontend result.</p><form id="evidence-form">${field('case_id', 'Case UUID')}${field('test_session_id', 'Test session UUID')}${field('kit_id', 'Kit ID')}${field('batch', 'Kit batch')}${field('expiry', 'Kit expiry', 'datetime-local')}${field('gps_latitude', 'GPS latitude')}${field('gps_longitude', 'GPS longitude')}${field('device_session_id', 'Device session UUID')}${field('original_image_reference', 'Authorized image reference')}<button class="primary">Submit evidence</button></form></article>`); document.querySelector<HTMLFormElement>('#evidence-form')!.onsubmit = async event => { event.preventDefault(); const body = Object.fromEntries(new FormData(event.currentTarget as HTMLFormElement)) as Record<string, unknown>; body.expiry = new Date(String(body.expiry)).toISOString(); Object.assign(body, { ai_result: 'PENDING', ai_confidence: 0, image_quality: 0, calibration_score: 0 }); try { selectedEvidence = await api.createEvidence(body); notify('Evidence submitted for server review.'); location.hash = '#/evidence-details'; } catch (error) { notify(messageFor(error), 'error'); } }; }
async function evidenceReview(supervisor: boolean) { const evidence = supervisor ? await api.supervisorEvidence() : []; const page = supervisor ? 'review' : 'my-evidence'; const contents = evidence.length ? `<div class="table-wrap"><table class="table"><thead><tr><th>Reference</th><th>Kit</th><th>Status</th><th></th></tr></thead><tbody>${evidence.map(item => `<tr><td>${escapeHtml(item.qr_reference)}</td><td>${escapeHtml(item.kit_id)}</td><td><span class="status">${escapeHtml(item.status)}</span></td><td><button class="secondary" data-evidence="${item.id}">Details</button></td></tr>`).join('')}</tbody></table></div>` : empty(supervisor ? 'No evidence records are available.' : 'The current API has no officer evidence-list endpoint. Newly submitted evidence is available by its ID/QR reference.'); layout(page, contents); document.querySelectorAll<HTMLButtonElement>('[data-evidence]').forEach(button => button.onclick = () => { selectedEvidence = evidence.find(item => item.id === button.dataset.evidence) || null; location.hash = '#/evidence-details'; }); }
function evidenceDetails() { if (!selectedEvidence) return layout('evidence-details', empty('Choose an evidence record first.')); const e = selectedEvidence; const full = 'kit_id' in e; const reviewActions = currentUser?.role === 'SUPERVISOR' ? `<div class="actions"><button class="primary" data-review="approve">Approve evidence</button><button class="secondary" data-review="reject">Reject evidence</button></div>` : ''; layout('evidence-details', `<article class="card"><div class="detail"><b>Evidence ID</b><span>${escapeHtml(e.id)}</span><b>QR reference</b><span>${escapeHtml(e.qr_reference)}</span><b>Status</b><span>${escapeHtml(e.status)}</span>${full ? `<b>Kit</b><span>${escapeHtml(e.kit_id)}</span><b>Captured</b><span>${formatDate(e.timestamp)}</span>` : ''}<b>Hash</b><span class="hash">${escapeHtml(e.sha256_hash)}</span></div>${reviewActions}</article>`); document.querySelectorAll<HTMLButtonElement>('[data-review]').forEach(button => button.onclick = async () => { const reason = window.prompt(`${button.dataset.review === 'approve' ? 'Approval' : 'Rejection'} reason (optional):`) || ''; try { if (button.dataset.review === 'approve') await api.approveEvidence(e.id, reason); else await api.rejectEvidence(e.id, reason); notify(`Evidence ${button.dataset.review}d.`); route(); } catch (error) { notify(messageFor(error), 'error'); } }); }
async function evidenceQr() { if (!selectedEvidence) return layout('evidence-qr', empty('Choose an evidence record first.')); layout('evidence-qr', `<article class="card">Loading server-generated QR…</article>`); const source = await qrSource(selectedEvidence.id); layout('evidence-qr', `<article class="card"><p class="muted">Server-generated evidence QR</p><img class="qr" alt="Evidence QR code" src="${source}"></article>`); }
async function verifyEvidence() { if (!selectedEvidence) return layout('verify', empty('Choose an evidence record first.')); const result = await api.verifyEvidence(selectedEvidence.id); layout('verify', cards([['Integrity signature', result.hash_valid ? 'Valid' : 'Invalid'], ['Evidence status', result.status]])); }
async function correctionRequests() { const list = await api.corrections(); layout('corrections', list.length ? `<div class="table-wrap"><table class="table"><thead><tr><th>Evidence</th><th>Reason</th><th>Status</th><th>Action</th></tr></thead><tbody>${list.map(item => `<tr><td>${escapeHtml(item.evidence_id)}</td><td>${escapeHtml(item.reason)}</td><td>${escapeHtml(item.status)}</td><td>${item.status === 'PENDING' ? `<button class="secondary" data-correction="${item.id}" data-approved="true">Approve</button> <button class="secondary" data-correction="${item.id}" data-approved="false">Reject</button>` : '—'}</td></tr>`).join('')}</tbody></table></div>` : empty('No correction requests.')); document.querySelectorAll<HTMLButtonElement>('[data-correction]').forEach(button => button.onclick = async () => { const reason = window.prompt('Review reason (optional):') || ''; try { await api.reviewCorrection(button.dataset.correction!, button.dataset.approved === 'true', reason); notify('Correction reviewed.'); route(); } catch (error) { notify(messageFor(error), 'error'); } }); }
async function auditTimeline() { const list = await api.audit(); layout('audit', list.length ? `<div class="table-wrap"><table class="table"><thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Reason</th></tr></thead><tbody>${list.map(item => `<tr><td>${formatDate(item.timestamp)}</td><td>${escapeHtml(item.actor_badge_id)}</td><td>${escapeHtml(item.action)}</td><td>${escapeHtml(item.reason)}</td></tr>`).join('')}</tbody></table></div>` : empty('No audit activity.')); }
async function custody() { if (!selectedEvidence) return layout('custody', empty('Choose an evidence record first.')); if (currentUser?.role === 'OFFICER') { layout('custody', `<article class="card"><form id="custody-form">${field('to_user_badge_id', 'Receiving badge ID')}${field('location', 'Transfer location')}${field('reason', 'Reason')}${field('authorization_reference', 'Authorization reference')}<button class="primary">Record transfer</button></form></article>`); document.querySelector<HTMLFormElement>('#custody-form')!.onsubmit = async event => { event.preventDefault(); try { await api.transfer(selectedEvidence!.id, Object.fromEntries(new FormData(event.currentTarget as HTMLFormElement)) as Record<string, string>); notify('Custody transfer recorded.'); } catch (error) { notify(messageFor(error), 'error'); } }; return; } const events = await api.custody(selectedEvidence.id); layout('custody', events.length ? `<div class="table-wrap"><table class="table"><thead><tr><th>From</th><th>To</th><th>Location</th><th>Time</th></tr></thead><tbody>${events.map(item => `<tr><td>${escapeHtml(item.from_user_badge_id)}</td><td>${escapeHtml(item.to_user_badge_id)}</td><td>${escapeHtml(item.location)}</td><td>${formatDate(item.timestamp)}</td></tr>`).join('')}</tbody></table></div>` : empty('No custody transfers recorded.')); }
async function officerActivity() { const events = await api.audit(); layout('officer-activity', events.length ? `<div class="table-wrap"><table class="table"><thead><tr><th>Officer</th><th>Activity</th><th>Time</th></tr></thead><tbody>${events.map(item => `<tr><td>${escapeHtml(item.actor_badge_id)}</td><td>${escapeHtml(item.action)}</td><td>${formatDate(item.timestamp)}</td></tr>`).join('')}</tbody></table></div>` : empty('No officer activity.')); }
async function logout() { try { await api.logout(); } finally { currentUser = null; selectedEvidence = null; location.hash = ''; loginPage('You have been signed out.'); } }

async function route() {
  if (!auth.active) return loginPage();
  try { currentUser = await api.me(); } catch { currentUser = null; return loginPage('Your session has expired. Please sign in again.'); }
  const requested = location.hash.replace('#/', '') || 'dashboard'; const allowed = (currentUser.role === 'SUPERVISOR' ? supervisorNav : officerNav).map(item => item[0]); const page = allowed.includes(requested as never) ? requested : 'dashboard';
  if (page !== requested) { location.hash = `#/${page}`; return; }
  const pages: Record<string, () => void | Promise<void>> = { dashboard, 'create-case': createCase, 'create-session': createSession, kit: kitVerification, capture: testCapture, result: testResult, 'my-evidence': () => evidenceReview(false), review: () => evidenceReview(true), 'evidence-details': evidenceDetails, 'evidence-qr': evidenceQr, verify: verifyEvidence, corrections: correctionRequests, audit: auditTimeline, custody, 'officer-activity': officerActivity };
  try { await pages[page](); } catch (error) { layout(page, apiError(error)); }
}
window.addEventListener('hashchange', route); route();
