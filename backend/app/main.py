from datetime import datetime, timedelta
import hashlib, json, secrets, uuid
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
import base64, jwt
from app.core.config import settings
from app.core.database import Base, engine, get_db
from app.models.models import User, Role, OTPVerification, RefreshToken, DeviceSession, Case, TestSession, TestKit, EvidenceRecord, EvidenceVersion, AuditEvent, ChainOfCustodyEvent, CorrectionRequest
from app.security.password import hash_password, verify_password
from app.security.jwt import create_access_token, create_refresh_token, decode_access_token, decode_refresh_token
from app.qr import render_qr

app = FastAPI(title='Digital Evidence Platform API', version='0.1.0')
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
bearer = HTTPBearer()
class Login(BaseModel): badge_id:str; password:str; device_id:str='unknown'; device_name:str|None=None
class OTP(BaseModel): badge_id:str; otp:str=Field(min_length=6,max_length=6); device_id:str='unknown'
class Refresh(BaseModel): refresh_token:str
class CaseIn(BaseModel): case_number:str; title:str; description:str|None=None
class SessionIn(BaseModel): case_id:uuid.UUID; test_kit_id:uuid.UUID; device_session_id:uuid.UUID; gps_latitude:str; gps_longitude:str
class EvidenceIn(BaseModel):
 case_id:uuid.UUID; test_session_id:uuid.UUID; kit_id:str; batch:str; expiry:datetime; gps_latitude:str; gps_longitude:str; device_session_id:uuid.UUID; original_image_reference:str; ai_result:str='PENDING'; ai_confidence:float=0; image_quality:float=0; calibration_score:float=0
class Reason(BaseModel): reason:str|None=None
class CorrectionIn(BaseModel): reason:str; proposed_changes:dict
class CustodyIn(BaseModel): to_user_badge_id:str; location:str; reason:str; authorization_reference:str
async def log(db, actor, action, resource=None, before=None, after=None, reason=None):
 db.add(AuditEvent(actor_badge_id=actor,action=action,resource_id=str(resource) if resource else None,before_state=json.dumps(before,default=str) if before else None,after_state=json.dumps(after,default=str) if after else None,reason=reason))
def digest(data): return hashlib.sha256(json.dumps(data,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()
def sign(value): return base64.b64encode(Ed25519PrivateKey.from_private_bytes(bytes.fromhex(settings.ED25519_PRIVATE_KEY)).sign(value.encode())).decode()
def valid_sig(value, signature):
 try: Ed25519PublicKey.from_public_bytes(bytes.fromhex(settings.ED25519_PUBLIC_KEY)).verify(base64.b64decode(signature),value.encode()); return True
 except Exception: return False
async def user_for(credentials:HTTPAuthorizationCredentials=Depends(bearer),db:AsyncSession=Depends(get_db)):
 try: claims=decode_access_token(credentials.credentials)
 except jwt.PyJWTError: raise HTTPException(401,'Invalid or expired access token')
 user=(await db.execute(select(User).where(User.badge_id==claims.get('sub')))).scalar_one_or_none()
 if not user or user.account_status!='ACTIVE': raise HTTPException(401,'Account unavailable')
 return user
def roles(*allowed):
 async def dep(user:User=Depends(user_for)):
  if user.role not in allowed: raise HTTPException(403,'Insufficient role')
  return user
 return dep
async def issue(db,user):
 access=create_access_token({'sub':user.badge_id,'role':user.role}); refresh=create_refresh_token({'sub':user.badge_id,'jti':str(uuid.uuid4())})
 db.add(RefreshToken(token_hash=hashlib.sha256(refresh.encode()).hexdigest(),badge_id=user.badge_id,expires_at=datetime.utcnow()+timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)))
 await log(db,user.badge_id,'AUTH_LOGIN'); return {'access_token':access,'refresh_token':refresh,'token_type':'bearer'}
@app.on_event('startup')
async def tables():
 async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
@app.get('/health')
async def health(): return {'status':'ok'}
@app.post('/auth/login',status_code=202)
async def login(body:Login,request:Request,db:AsyncSession=Depends(get_db)):
 user=(await db.execute(select(User).where(User.badge_id==body.badge_id))).scalar_one_or_none()
 if not user or not verify_password(body.password,user.hashed_password) or user.account_status!='ACTIVE': raise HTTPException(401,'Invalid credentials')
 code=f'{secrets.randbelow(1000000):06d}'; now=datetime.utcnow(); await db.execute(update(OTPVerification).where(OTPVerification.badge_id==user.badge_id).values(expires_at=now))
 db.add(OTPVerification(badge_id=user.badge_id,otp_hash=hash_password(code),expires_at=now+timedelta(seconds=settings.OTP_EXPIRY_SECONDS),resend_available_at=now+timedelta(seconds=settings.OTP_RESEND_COOLDOWN_SECONDS)))
 db.add(DeviceSession(badge_id=user.badge_id,device_id=body.device_id,device_name=body.device_name,ip_address=request.client.host if request.client else None))
 await log(db,user.badge_id,'OTP_ISSUED')
 response={'message':'OTP issued'}
 if settings.ENVIRONMENT in ('development','testing'): response['development_otp']=code
 return response
@app.post('/auth/verify-otp')
async def verify(body:OTP,db:AsyncSession=Depends(get_db)):
 otp=(await db.execute(select(OTPVerification).where(OTPVerification.badge_id==body.badge_id, OTPVerification.expires_at>=datetime.utcnow()).order_by(OTPVerification.created_at.desc()))).scalars().first()
 if not otp or otp.expires_at < datetime.utcnow(): raise HTTPException(400,'OTP expired or unavailable')
 if otp.attempts >= settings.OTP_MAX_ATTEMPTS: raise HTTPException(429,'OTP attempt limit reached')
 otp.attempts+=1
 if not verify_password(body.otp,otp.otp_hash):
  await db.commit()
  raise HTTPException(401,'Invalid OTP')
 user=(await db.execute(select(User).where(User.badge_id==body.badge_id))).scalar_one(); await log(db,user.badge_id,'OTP_VERIFIED'); return await issue(db,user)
@app.post('/auth/resend-otp',status_code=202)
async def resend(body:Login,db:AsyncSession=Depends(get_db)):
 latest=(await db.execute(select(OTPVerification).where(OTPVerification.badge_id==body.badge_id, OTPVerification.expires_at>=datetime.utcnow()).order_by(OTPVerification.created_at.desc()))).scalars().first()
 if latest and latest.resend_available_at>datetime.utcnow(): raise HTTPException(429,'OTP resend cooldown active')
 user=(await db.execute(select(User).where(User.badge_id==body.badge_id))).scalar_one_or_none()
 if not user: raise HTTPException(404,'User not found')
 code=f'{secrets.randbelow(1000000):06d}'; now=datetime.utcnow(); await db.execute(update(OTPVerification).where(OTPVerification.badge_id==user.badge_id).values(expires_at=now)); db.add(OTPVerification(badge_id=user.badge_id,otp_hash=hash_password(code),expires_at=now+timedelta(seconds=settings.OTP_EXPIRY_SECONDS),resend_available_at=now+timedelta(seconds=settings.OTP_RESEND_COOLDOWN_SECONDS))); return {'message':'OTP reissued', **({'development_otp':code} if settings.ENVIRONMENT in ('development','testing') else {})}
@app.post('/auth/refresh')
async def refresh(body:Refresh,db:AsyncSession=Depends(get_db)):
 try: claims=decode_refresh_token(body.refresh_token)
 except jwt.PyJWTError: raise HTTPException(401,'Invalid refresh token')
 stored=(await db.execute(select(RefreshToken).where(RefreshToken.token_hash==hashlib.sha256(body.refresh_token.encode()).hexdigest()))).scalar_one_or_none()
 if not stored or stored.revoked or stored.expires_at<datetime.utcnow(): raise HTTPException(401,'Refresh token revoked or expired')
 stored.revoked=True; user=(await db.execute(select(User).where(User.badge_id==claims['sub']))).scalar_one(); return await issue(db,user)
@app.post('/auth/logout')
async def logout(body:Refresh,db:AsyncSession=Depends(get_db)):
 token=(await db.execute(select(RefreshToken).where(RefreshToken.token_hash==hashlib.sha256(body.refresh_token.encode()).hexdigest()))).scalar_one_or_none()
 if token: token.revoked=True; await log(db,token.badge_id,'AUTH_LOGOUT')
 return {'message':'Logged out'}
@app.get('/auth/me')
async def me(user:User=Depends(user_for)): return {'badge_id':user.badge_id,'full_name':user.full_name,'role':user.role,'account_status':user.account_status}
@app.post('/officer/cases')
async def create_case(body:CaseIn,user:User=Depends(roles('OFFICER','ADMIN')),db:AsyncSession=Depends(get_db)):
 case=Case(case_number=body.case_number,title=body.title,description=body.description,created_by_officer_id=user.badge_id); db.add(case); await db.flush(); await log(db,user.badge_id,'CASE_CREATED',case.id,after={'case_number':body.case_number}); return {'id':case.id,'case_number':case.case_number,'status':case.status}
@app.get('/officer/cases')
async def own_cases(user:User=Depends(roles('OFFICER','ADMIN')),db:AsyncSession=Depends(get_db)): return (await db.execute(select(Case).where(Case.created_by_officer_id==user.badge_id))).scalars().all()
@app.post('/officer/test-sessions')
async def start_session(body:SessionIn,user:User=Depends(roles('OFFICER','ADMIN')),db:AsyncSession=Depends(get_db)):
 case=(await db.get(Case,body.case_id)); kit=(await db.get(TestKit,body.test_kit_id))
 if not case or case.created_by_officer_id!=user.badge_id or not kit: raise HTTPException(404,'Case or kit unavailable')
 session=TestSession(officer_badge_id=user.badge_id,case_id=body.case_id,test_kit_id=body.test_kit_id,device_session_id=body.device_session_id,gps_latitude=body.gps_latitude,gps_longitude=body.gps_longitude); db.add(session); await db.flush(); await log(db,user.badge_id,'TEST_SESSION_STARTED',session.id); return {'id':session.id,'status':session.status}
@app.post('/officer/test-sessions/{session_id}/end')
async def end_session(session_id:uuid.UUID,user:User=Depends(roles('OFFICER','ADMIN')),db:AsyncSession=Depends(get_db)):
 s=await db.get(TestSession,session_id)
 if not s or s.officer_badge_id!=user.badge_id: raise HTTPException(404,'Session not found')
 if s.ended_at: raise HTTPException(409,'Session already ended')
 s.ended_at=datetime.utcnow(); s.status='COMPLETED'; await log(db,user.badge_id,'TEST_SESSION_ENDED',s.id); return {'id':s.id,'status':s.status}
@app.get('/officer/test-sessions')
async def own_sessions(user:User=Depends(roles('OFFICER','ADMIN')),db:AsyncSession=Depends(get_db)): return (await db.execute(select(TestSession).where(TestSession.officer_badge_id==user.badge_id))).scalars().all()
@app.post('/officer/evidence')
async def evidence(body:EvidenceIn,user:User=Depends(roles('OFFICER','ADMIN')),db:AsyncSession=Depends(get_db)):
 session=await db.get(TestSession,body.test_session_id); kit=(await db.execute(select(TestKit).where(TestKit.kit_id==body.kit_id))).scalar_one_or_none()
 if not session or session.officer_badge_id!=user.badge_id or not kit: raise HTTPException(400,'Invalid test session or kit')
 payload=body.model_dump(); payload['officer_id']=user.badge_id; h=digest(payload); item=EvidenceRecord(**body.model_dump(),officer_id=user.badge_id,sha256_hash=h,digital_signature=sign(h),qr_reference='EV-'+uuid.uuid4().hex[:16].upper()); db.add(item); await db.flush(); await log(db,user.badge_id,'EVIDENCE_CREATED',item.id,after={'hash':h}); return {'id':item.id,'qr_reference':item.qr_reference,'sha256_hash':h,'digital_signature':item.digital_signature,'status':item.status}
@app.get('/evidence/{evidence_id}/qr')
async def evidence_qr(evidence_id:uuid.UUID,user:User=Depends(user_for),db:AsyncSession=Depends(get_db)):
 item=await db.get(EvidenceRecord,evidence_id)
 if not item: raise HTTPException(404,'Evidence not found')
 if user.role=='OFFICER' and item.officer_id!=user.badge_id: raise HTTPException(403,'Not authorized for this evidence')
 return Response(render_qr(item.qr_reference), media_type='image/png')
@app.post('/officer/evidence/{evidence_id}/corrections')
async def correction(evidence_id:uuid.UUID,body:CorrectionIn,user:User=Depends(roles('OFFICER','ADMIN')),db:AsyncSession=Depends(get_db)):
 item=await db.get(EvidenceRecord,evidence_id)
 if not item or item.officer_id!=user.badge_id: raise HTTPException(404,'Evidence not found')
 req=CorrectionRequest(evidence_id=item.id,requested_by_badge_id=user.badge_id,reason=body.reason,proposed_changes_json=json.dumps(body.proposed_changes)); item.status='CORRECTION_PENDING'; db.add(req); await db.flush(); await log(db,user.badge_id,'CORRECTION_REQUESTED',item.id,reason=body.reason); return {'id':req.id,'status':req.status}
@app.get('/supervisor/cases')
async def cases(user:User=Depends(roles('SUPERVISOR','ADMIN')),db:AsyncSession=Depends(get_db)): return (await db.execute(select(Case))).scalars().all()
@app.get('/supervisor/evidence')
async def evidence_list(user:User=Depends(roles('SUPERVISOR','ADMIN')),db:AsyncSession=Depends(get_db)): return (await db.execute(select(EvidenceRecord))).scalars().all()
@app.post('/supervisor/evidence/{evidence_id}/approve')
async def approve(evidence_id:uuid.UUID,body:Reason,user:User=Depends(roles('SUPERVISOR','ADMIN')),db:AsyncSession=Depends(get_db)):
 item=await db.get(EvidenceRecord,evidence_id)
 if not item: raise HTTPException(404,'Evidence not found')
 item.status='APPROVED'; await log(db,user.badge_id,'EVIDENCE_APPROVED',item.id,reason=body.reason); return {'id':item.id,'status':item.status}
@app.post('/supervisor/evidence/{evidence_id}/reject')
async def reject(evidence_id:uuid.UUID,body:Reason,user:User=Depends(roles('SUPERVISOR','ADMIN')),db:AsyncSession=Depends(get_db)):
 item=await db.get(EvidenceRecord,evidence_id)
 if not item: raise HTTPException(404,'Evidence not found')
 item.status='REJECTED'; await log(db,user.badge_id,'EVIDENCE_REJECTED',item.id,reason=body.reason); return {'id':item.id,'status':item.status}
@app.get('/supervisor/evidence/{evidence_id}/verify')
async def verify_evidence(evidence_id:uuid.UUID,user:User=Depends(roles('SUPERVISOR','ADMIN')),db:AsyncSession=Depends(get_db)):
 item=await db.get(EvidenceRecord,evidence_id)
 if not item: raise HTTPException(404,'Evidence not found')
 return {'evidence_id':item.id,'hash_valid':valid_sig(item.sha256_hash,item.digital_signature),'status':item.status}
@app.get('/supervisor/corrections')
async def corrections(user:User=Depends(roles('SUPERVISOR','ADMIN')),db:AsyncSession=Depends(get_db)): return (await db.execute(select(CorrectionRequest))).scalars().all()
@app.post('/supervisor/corrections/{request_id}/approve')
async def approve_correction(request_id:uuid.UUID,body:Reason,user:User=Depends(roles('SUPERVISOR','ADMIN')),db:AsyncSession=Depends(get_db)):
 req=await db.get(CorrectionRequest,request_id)
 if not req or req.status!='PENDING': raise HTTPException(404,'Pending correction not found')
 req.status='APPROVED'; req.reviewed_by_badge_id=user.badge_id; req.reviewed_at=datetime.utcnow(); item=await db.get(EvidenceRecord,req.evidence_id); n=(await db.scalar(select(func.count(EvidenceVersion.id)).where(EvidenceVersion.evidence_record_id==item.id)))+1; db.add(EvidenceVersion(evidence_record_id=item.id,version_number=n,changed_by_badge_id=req.requested_by_badge_id,changes_json=req.proposed_changes_json,reason=req.reason,approval_status='APPROVED',approver_badge_id=user.badge_id)); item.status='APPROVED'; await log(db,user.badge_id,'CORRECTION_APPROVED',item.id,reason=body.reason); return {'id':req.id,'status':req.status}
@app.post('/supervisor/corrections/{request_id}/reject')
async def reject_correction(request_id:uuid.UUID,body:Reason,user:User=Depends(roles('SUPERVISOR','ADMIN')),db:AsyncSession=Depends(get_db)):
 req=await db.get(CorrectionRequest,request_id)
 if not req or req.status!='PENDING': raise HTTPException(404,'Pending correction not found')
 req.status='REJECTED'; req.reviewed_by_badge_id=user.badge_id; req.reviewed_at=datetime.utcnow(); req.rejection_reason=body.reason
 item=await db.get(EvidenceRecord,req.evidence_id); item.status='PENDING_REVIEW'
 await log(db,user.badge_id,'CORRECTION_REJECTED',item.id,reason=body.reason); return {'id':req.id,'status':req.status}
@app.get('/supervisor/audit')
async def audit_history(user:User=Depends(roles('SUPERVISOR','ADMIN')),db:AsyncSession=Depends(get_db)): return (await db.execute(select(AuditEvent).order_by(AuditEvent.timestamp.desc()))).scalars().all()
@app.get('/supervisor/evidence/{evidence_id}/custody')
async def custody_history(evidence_id:uuid.UUID,user:User=Depends(roles('SUPERVISOR','ADMIN')),db:AsyncSession=Depends(get_db)): return (await db.execute(select(ChainOfCustodyEvent).where(ChainOfCustodyEvent.evidence_id==evidence_id))).scalars().all()
@app.post('/officer/evidence/{evidence_id}/custody')
async def transfer(evidence_id:uuid.UUID,body:CustodyIn,user:User=Depends(roles('OFFICER','SUPERVISOR','ADMIN')),db:AsyncSession=Depends(get_db)):
 item=await db.get(EvidenceRecord,evidence_id)
 if not item: raise HTTPException(404,'Evidence not found')
 event=ChainOfCustodyEvent(evidence_id=item.id,from_user_badge_id=user.badge_id,to_user_badge_id=body.to_user_badge_id,location=body.location,reason=body.reason,authorization_reference=body.authorization_reference); db.add(event); await log(db,user.badge_id,'CUSTODY_TRANSFER',item.id,reason=body.reason); return {'id':event.id}









