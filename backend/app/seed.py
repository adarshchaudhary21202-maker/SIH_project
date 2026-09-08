"""Development-only seed command: python -m app.seed."""
import asyncio
from sqlalchemy import select
from app.core.database import async_session, engine, Base
from app.models.models import Role, User, TestKit
from app.security.password import hash_password

DEVELOPMENT_PASSWORD = 'ChangeMe-DevOnly-2026!'
USERS = [('officer@example.local','Officer Example','OFFICER'),('supervisor@example.local','Supervisor Example','SUPERVISOR'),('admin@example.local','Administrator Example','ADMIN')]
async def main():
    async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
    async with async_session() as db:
        for name in ('OFFICER','SUPERVISOR','ADMIN'):
            if not (await db.execute(select(Role).where(Role.name==name))).scalar_one_or_none(): db.add(Role(name=name))
        await db.flush()
        for badge, full_name, role in USERS:
            user=(await db.execute(select(User).where(User.badge_id==badge))).scalar_one_or_none()
            if not user: db.add(User(badge_id=badge,email=badge,full_name=full_name,role=role,hashed_password=hash_password(DEVELOPMENT_PASSWORD)))
            elif not user.email: user.email=badge
        if not (await db.execute(select(TestKit).where(TestKit.kit_id=='DEV-KIT-001'))).scalar_one_or_none():
            from datetime import datetime, timedelta
            db.add(TestKit(kit_id='DEV-KIT-001',batch_number='DEV-BATCH',manufacturing_date=datetime.utcnow(),expiry_date=datetime.utcnow()+timedelta(days=365),reagent_information='Development kit'))
        await db.commit()
    print('Seeded development users. Password:', DEVELOPMENT_PASSWORD)
if __name__ == '__main__': asyncio.run(main())
