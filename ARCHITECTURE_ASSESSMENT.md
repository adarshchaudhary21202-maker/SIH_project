# Digital Evidence Platform Architecture Assessment

This document outlines the architectural boundaries and responsibilities for the presumptive colorimetric field drug testing digital evidence platform.

## 1. File Classification

### FRONTEND (Deliberately Untouched)
The frontend is responsible for the client-side user experience, user interface layouts, device features (camera, video/audio capture, offline data storage), GPS collection, and API communications.
* **Paths**:
  * `sih-drug-tester/www/index.html` (Main interactive UI, layouts, styles, Tailwind-based screen configurations)
  * `sih-drug-tester/www/css/style.css` (Custom frontend component styles)
  * `sih-drug-tester/www/js/app.js` (Client-side behaviors, mock analyzer workflow, local file hash and cryptographic operations, offline counters)
  * `sih-drug-tester/android/...` (Native platform project for Android builds, Gradle scripts, configuration settings)

### BACKEND (To Be Created)
The backend is the trusted server-side authority. It executes authentication, secure OTP dispatch/hash validation, role-based access control, cryptographic verification, data persistence, and auditing.
* **Paths**:
  * `backend/app/` (FastAPI core application)
  * `backend/alembic/` (Alembic database migration configuration and revisions)
  * `backend/tests/` (Unit and integration tests for FastAPI, auth, cryptographic signature, etc.)

### AI (To Be Created as Stubs)
The AI is a separate service. We must not build a real machine learning model yet. We will design clean interface abstractions to handle future image validations, quality calculations, calibration scores, and reagent interpretations.
* **Paths**:
  * `backend/app/ai/interface.py` (AI Service abstract interface)
  * `backend/app/ai/stub.py` (Development AI Stub returning mock classifications, confidence intervals, and calibration scores)

### SHARED / CONFIGURATION
Configuration files, project-wide settings, and package manifests.
* **Paths**:
  * `sih-drug-tester/package.json` (Frontend package metadata and dependency configuration)
  * `sih-drug-tester/capacitor.config.json` (Capacitor wrapper configurations)
  * `backend/.env.example` / `backend/.env` (System environment variables)
  * `backend/requirements.txt` (Backend dependency tracking)
  * `backend/Dockerfile` (Backend packaging configuration)

---

## 2. Separation of Concerns & Security Boundaries

1. **Authentication Flow**: The frontend presents user forms and gathers Badge IDs and PINs. The backend validates credentials, calculates/verifies secure hashes, generates high-entropy OTP tokens, and verifies them securely before issuing cryptographic JWT tokens.
2. **Access Control**: Role-Based Access Control (RBAC) is enforced strictly on the server side using FastAPI middleware/dependency injection. The roles are `OFFICER`, `SUPERVISOR`, and `ADMIN`.
3. **Data Integrity**: The backend enforces the immutability of evidence. It calculates deterministic SHA-256 hashes of critical fields, generates Ed25519 digital signatures, and tracks all mutations via formal `AuditEvent` records and supervisor-approved `CorrectionRequest` workflows.
4. **Offline Resilience vs Server Trust**: The frontend operates locally when disconnected, compiling offline metadata and files. Upon reconnect, it syncs with the backend APIs. The backend is the ultimate source of truth, validating every kit's validity and recording timestamps and GPS locations into a tamper-evident schema.
