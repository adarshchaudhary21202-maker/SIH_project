# Backend

Copy `.env.example` to `.env` and set real random JWT secrets and a matching Ed25519 keypair. PostgreSQL is the production database; SQLite is suitable only for local tests.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# set DATABASE_URL and cryptographic settings in .env
python -m backend.app.seed
uvicorn backend.app.main:app --reload
```

Swagger is at `http://127.0.0.1:8000/docs`.

The seed command is deliberately development-only. It creates `officer@example.local`, `supervisor@example.local`, and `admin@example.local`; its printed password is `ChangeMe-DevOnly-2026!` and must never be deployed.

OTP delivery is behind an `OTPProvider` boundary; in development the code is included only in the login response. Production must replace this with an SMS/email provider and disable development mode.
