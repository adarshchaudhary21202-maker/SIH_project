/** Types mirror the REST payloads returned by the existing FastAPI service. */
export type Role = 'OFFICER' | 'SUPERVISOR' | 'ADMIN';
export interface Tokens { access_token:string; refresh_token:string; token_type:string }
export interface User { badge_id:string; full_name:string; role:Role; account_status:string }
export interface Case { id:string; case_number:string; title:string; description?:string; status:string; created_at?:string }
export interface CaseCreated { id:string; case_number:string; status:string }
export interface TestSession { id:string; case_id:string; test_kit_id:string; device_session_id:string; status:string; started_at?:string }
export interface TestSessionCreated { id:string; status:string }
export interface Evidence { id:string; case_id:string; test_session_id:string; officer_id:string; kit_id:string; batch:string; expiry:string; timestamp:string; gps_latitude:string; gps_longitude:string; original_image_reference:string; ai_result:string; ai_confidence:number; image_quality:number; calibration_score:number; sha256_hash:string; digital_signature:string; qr_reference:string; status:string }
export interface EvidenceCreated { id:string; qr_reference:string; sha256_hash:string; digital_signature:string; status:string }
export interface Correction { id:string; evidence_id:string; requested_by_badge_id:string; reason:string; status:string; proposed_changes_json:string; created_at:string }
export interface AuditEvent { id:string; actor_badge_id:string; action:string; timestamp:string; resource_id?:string; reason?:string }
export interface CustodyEvent { id:string; evidence_id:string; from_user_badge_id:string; to_user_badge_id:string; timestamp:string; location:string; reason:string; authorization_reference:string }
export interface LoginRequest { badge_id:string; password:string; device_id:string; device_name?:string }
export interface RegisterRequest { full_name:string; email:string; badge_id:string; password:string; role:'OFFICER'|'SUPERVISOR' }
export interface RegistrationResult { message:string; badge_id:string; email:string; role:Role }
export interface ApiError { status:number; message:string; fields?:Record<string,string> }
