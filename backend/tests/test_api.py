import asyncio
import os
from datetime import datetime, timedelta
from pathlib import Path

DB = Path('test_validation.db')
if DB.exists(): DB.unlink()
os.environ.update({
    'DATABASE_URL': 'sqlite+aiosqlite:///./test_validation.db',
    'JWT_SECRET_KEY': 'a' * 64,
    'JWT_REFRESH_SECRET_KEY': 'b' * 64,
    'ED25519_PRIVATE_KEY': '98d130fff2c0402a971d15aee805737fc66f069b49cb3dd76d6d90f4bab4b2ff',
    'ED25519_PUBLIC_KEY': '85f6e8a4d1b3a8b8d8ee5e48ed2c08263c40bd0c1a1568faa73940aea7929252',
    'ENVIRONMENT': 'testing',
})

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.core.database import async_session
from app.main import EvidenceIn, app, digest
from app.models.models import AuditEvent, DeviceSession, EvidenceRecord, EvidenceVersion, OTPVerification, TestKit
from app.seed import main as seed

asyncio.run(seed())

@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client

def login(client, badge, password='ChangeMe-DevOnly-2026!'):
    response = client.post('/auth/login', json={'badge_id': badge, 'password': password, 'device_id': 'test-device'})
    assert response.status_code == 202
    return response.json()

def authenticate(client, badge):
    pending = login(client, badge)
    verified = client.post('/auth/verify-otp', json={'badge_id': badge, 'otp': pending['development_otp'], 'device_id': 'test-device'})
    assert verified.status_code == 200
    tokens = verified.json()
    return {'Authorization': f"Bearer {tokens['access_token']}"}, tokens['refresh_token']

async def latest_device_id():
    async with async_session() as db:
        return str((await db.execute(select(DeviceSession).order_by(DeviceSession.created_at.desc()))).scalars().first().id)

async def development_kit_id():
    async with async_session() as db:
        return str((await db.execute(select(TestKit).where(TestKit.kit_id == 'DEV-KIT-001'))).scalar_one().id)

def test_openapi_swagger_and_unauthorized_requests(client):
    assert client.get('/health').status_code == 200
    assert client.get('/openapi.json').status_code == 200
    assert client.get('/docs').status_code == 200
    assert client.get('/supervisor/cases').status_code == 403
    assert client.get('/auth/me', headers={'Authorization': 'Bearer invalid'}).status_code == 401
    assert client.get('/auth/me', headers={'Authorization': 'Bearer ' + 'x.y.z'}).status_code == 401

def test_auth_otp_resend_limits_expiry_and_token_lifecycle(client):
    assert client.post('/auth/login', json={'badge_id': 'officer@example.local', 'password': 'wrong'}).status_code == 401
    pending = login(client, 'officer@example.local')
    async def raw_otp_and_expire():
        async with async_session() as db:
            otp = (await db.execute(select(OTPVerification).order_by(OTPVerification.created_at.desc()))).scalars().first()
            assert otp.otp_hash != pending['development_otp']
            otp.expires_at = datetime.utcnow() - timedelta(seconds=1)
            await db.commit()
    asyncio.run(raw_otp_and_expire())
    assert client.post('/auth/verify-otp', json={'badge_id': 'officer@example.local', 'otp': pending['development_otp']}).status_code == 400
    pending = login(client, 'officer@example.local')
    for _ in range(3):
        assert client.post('/auth/verify-otp', json={'badge_id': 'officer@example.local', 'otp': '000000'}).status_code == 401
    assert client.post('/auth/verify-otp', json={'badge_id': 'officer@example.local', 'otp': pending['development_otp']}).status_code == 429
    assert client.post('/auth/resend-otp', json={'badge_id': 'officer@example.local', 'password': 'unused'}).status_code == 429
    async def unlock_resend():
        async with async_session() as db:
            otp = (await db.execute(select(OTPVerification).where(OTPVerification.badge_id == 'officer@example.local', OTPVerification.expires_at >= datetime.utcnow()))).scalars().first()
            otp.resend_available_at = datetime.utcnow() - timedelta(seconds=1); await db.commit()
    asyncio.run(unlock_resend())
    resent = client.post('/auth/resend-otp', json={'badge_id': 'officer@example.local', 'password': 'unused'}); assert resent.status_code == 202
    assert len(resent.json()['development_otp']) == 6
    assert client.post('/auth/resend-otp', json={'badge_id': 'unknown@example.local', 'password': 'unused'}).status_code == 404
    headers, refresh = authenticate(client, 'officer@example.local')
    assert client.get('/auth/me', headers=headers).json()['role'] == 'OFFICER'
    refreshed = client.post('/auth/refresh', json={'refresh_token': refresh}); assert refreshed.status_code == 200
    assert client.post('/auth/logout', json={'refresh_token': refreshed.json()['refresh_token']}).status_code == 200
    assert client.post('/auth/refresh', json={'refresh_token': refreshed.json()['refresh_token']}).status_code == 401

def test_rbac_lists_and_validation_errors(client):
    officer, _ = authenticate(client, 'officer@example.local')
    supervisor, _ = authenticate(client, 'supervisor@example.local')
    assert client.get('/supervisor/cases', headers=officer).status_code == 403
    assert client.get('/officer/cases', headers=supervisor).status_code == 403
    assert client.get('/supervisor/cases', headers=supervisor).status_code == 200
    assert client.get('/supervisor/evidence', headers=supervisor).status_code == 200
    assert client.get('/supervisor/corrections', headers=supervisor).status_code == 200
    assert client.post('/officer/test-sessions', headers=officer, json={}).status_code == 422
    assert client.post('/officer/evidence', headers=officer, json={}).status_code == 422
    assert client.post('/supervisor/evidence/00000000-0000-0000-0000-000000000000/approve', headers=supervisor, json={}).status_code == 404

def make_evidence(client, officer, number):
    case = client.post('/officer/cases', headers=officer, json={'case_number': number, 'title': 'Validation'}); assert case.status_code == 200
    device_id = asyncio.run(latest_device_id())
    session = client.post('/officer/test-sessions', headers=officer, json={'case_id': case.json()['id'], 'test_kit_id': asyncio.run(development_kit_id()), 'device_session_id': device_id, 'gps_latitude': '12.1', 'gps_longitude': '77.1'}); assert session.status_code == 200
    body = {'case_id': case.json()['id'], 'test_session_id': session.json()['id'], 'kit_id': 'DEV-KIT-001', 'batch': 'DEV-BATCH', 'expiry': '2027-01-01T00:00:00', 'gps_latitude': '12.1', 'gps_longitude': '77.1', 'device_session_id': device_id, 'original_image_reference': 'storage://image.jpg'}
    evidence = client.post('/officer/evidence', headers=officer, json=body); assert evidence.status_code == 200
    return case, session, body, evidence.json()

def test_evidence_cryptography_qr_immutability_and_audit(client):
    officer, _ = authenticate(client, 'officer@example.local'); supervisor, _ = authenticate(client, 'supervisor@example.local')
    case, session, body, evidence = make_evidence(client, officer, 'CASE-EVIDENCE')
    eid = evidence['id']
    payload = EvidenceIn(**body).model_dump(); payload['officer_id'] = 'officer@example.local'
    assert evidence['sha256_hash'] == digest(payload)
    assert client.get(f'/supervisor/evidence/{eid}/verify', headers=supervisor).json()['hash_valid'] is True
    qr = client.get(f'/evidence/{eid}/qr', headers=officer); assert qr.status_code == 200 and qr.headers['content-type'] == 'image/png'
    assert evidence['qr_reference'] not in qr.content.decode('latin1')
    assert client.put(f'/officer/evidence/{eid}', headers=officer, json={'ai_result': 'tampered'}).status_code == 404
    async def original_record():
        async with async_session() as db:
            return (await db.get(EvidenceRecord, __import__('uuid').UUID(eid))).ai_result, (await db.get(EvidenceRecord, __import__('uuid').UUID(eid))).sha256_hash
    assert asyncio.run(original_record()) == ('PENDING', evidence['sha256_hash'])
    assert client.post(f'/supervisor/evidence/{eid}/approve', headers=supervisor, json={'reason': 'accepted'}).json()['status'] == 'APPROVED'
    assert client.post(f'/supervisor/evidence/{eid}/reject', headers=supervisor, json={'reason': 'recheck'}).json()['status'] == 'REJECTED'
    audit = client.get('/supervisor/audit', headers=supervisor); assert audit.status_code == 200
    actions = {event['action'] for event in audit.json()}; assert {'EVIDENCE_CREATED', 'EVIDENCE_APPROVED', 'EVIDENCE_REJECTED'} <= actions
    assert client.patch('/supervisor/audit', headers=supervisor, json={}).status_code == 405
    assert client.post(f'/officer/test-sessions/{session.json()["id"]}/end', headers=officer).status_code == 200
    assert client.post(f'/officer/test-sessions/{session.json()["id"]}/end', headers=officer).status_code == 409

def test_corrections_versions_and_chain_of_custody_integrity(client):
    officer, _ = authenticate(client, 'officer@example.local'); supervisor, _ = authenticate(client, 'supervisor@example.local')
    _, _, _, evidence = make_evidence(client, officer, 'CASE-CORRECTION'); eid = evidence['id']
    transfer = {'to_user_badge_id': 'supervisor@example.local', 'location': 'Locker A', 'reason': 'review', 'authorization_reference': 'AUTH-1'}
    assert client.post(f'/officer/evidence/{eid}/custody', headers=officer, json=transfer).status_code == 200
    custody = client.get(f'/supervisor/evidence/{eid}/custody', headers=supervisor).json(); assert len(custody) == 1 and custody[0]['from_user_badge_id'] == 'officer@example.local'
    pending = client.post(f'/officer/evidence/{eid}/corrections', headers=officer, json={'reason': 'correct label', 'proposed_changes': {'ai_result': 'NEGATIVE'}}); assert pending.status_code == 200
    assert client.post(f'/supervisor/corrections/{pending.json()["id"]}/approve', headers=supervisor, json={'reason': 'verified'}).status_code == 200
    async def version_and_original():
        async with async_session() as db:
            original = await db.get(EvidenceRecord, __import__('uuid').UUID(eid))
            versions = (await db.execute(select(EvidenceVersion).where(EvidenceVersion.evidence_record_id == __import__('uuid').UUID(eid)))).scalars().all()
            return original.ai_result, len(versions), versions[0].changes_json
    original, count, changes = asyncio.run(version_and_original()); assert original == 'PENDING' and count == 1 and 'NEGATIVE' in changes
    second = client.post(f'/officer/evidence/{eid}/corrections', headers=officer, json={'reason': 'reject test', 'proposed_changes': {'batch': 'changed'}})
    assert client.post(f'/supervisor/corrections/{second.json()["id"]}/reject', headers=supervisor, json={'reason': 'not justified'}).json()['status'] == 'REJECTED'
    assert client.get('/supervisor/corrections', headers=supervisor).status_code == 200
    assert client.post(f'/officer/evidence/{eid}/custody', headers=supervisor, json=transfer).status_code == 200



