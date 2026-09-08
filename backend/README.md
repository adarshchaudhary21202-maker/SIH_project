# Digital Companion for Field Drug Testing

Status: **SIH prototype / MVP baseline**. This prototype provides presumptive image classification and validation assistance. It is not definitive drug identification and must not be treated as a substitute for laboratory confirmation or authorized forensic procedures.

## Architecture

`POST /ai/analyze` decodes an upload, validates it before chemical classification, applies prototype quality gates, then returns the stable `AIResult` contract. Evidence, hashing, signatures, and chain-of-custody components are unchanged; integrity of a recorded artifact does not make an AI output scientifically correct.

`kit_detected` and `test_area_detected` are prototype validation indicators, not a trained object detector or localization result. Quality and calibration values are prototype focus/brightness/contrast/exposure heuristics, not forensic measurements.

## Datasets

Dataset A is `data/chemical/` with exactly `PRESUMPTIVE_POSITIVE`, `PRESUMPTIVE_NEGATIVE`, and `INCONCLUSIVE`. It accepts real controlled prototype test-kit captures only, recorded in `manifest.csv` with `ground_truth_source=controlled_kit_record`. Do not create fabricated chemical images/labels or use web images as ground truth.

Dataset B is `data/validation/` with `valid_test`, `shirt`, `wall`, `tree`, `random_object`, `screenshot`, `empty`, `wrong_kit`, `blurred`, and `bad_framing`. It is logically separate and runs first. See `data/README.md` for collection and manifest requirements.

`manifest.csv` records `id,dataset,path,label,split,capture_session,kit_id,ground_truth_source,device,lighting,distance_cm,angle_deg,exposure,background,reaction_stage,notes`. The validator detects missing paths, duplicate IDs/bytes, wrong labels/dataset/path/source, session leakage, missing classes, and insufficient sessions. Splits are deterministic (seed 42), capture-session safe, and target approximately 70/15/15.

## Explicit demo mode

`AI_DEMO_MODE=true` is the default SIH workflow demo setting and is visible in `/health` as `mode: "DEMO"`. It is intended only to demonstrate application workflow and UI integration. It is not evidence of forensic model performance.

Demo validation still runs before any result state. It recognizes only documented synthetic validation fixtures from `demo/fixtures/validation/`; unrecognized images are rejected. A valid fixture reaches a deterministic UI state selected by `AI_DEMO_PROFILE` (`PRESUMPTIVE_POSITIVE`, `PRESUMPTIVE_NEGATIVE`, or `INCONCLUSIVE`). This profile is not a chemical prediction, uses no chemical model, has confidence `0`, and is explicitly described in the response.

Create fixtures outside real training data:

```powershell
cd backend
python scripts/create_demo_validation_data.py
$env:AI_DEMO_MODE='true'
$env:AI_DEMO_PROFILE='PRESUMPTIVE_POSITIVE'
```

They are synthetic validation fixtures for software testing only. No demo chemical fixture or chemical ground truth is created. Details: `demo/README.md`.

## Real-data validation, training, and evaluation

```powershell
cd backend
python scripts/assign_splits.py
python scripts/validate_manifest.py
python scripts/train_baseline.py
python scripts/evaluate_baseline.py
```

Training refuses empty/invalid data and uses train rows only. Conservative deterministic augmentation is train-only: ±6° rotation, crop/scale, brightness/contrast, JPEG compression, and mild blur. Test rows are never augmented.

The baseline is a RandomForest using global RGB/HSV mean and standard-deviation features. It is not scientifically or forensically validated. Real-data model files are `artifacts/baseline.joblib` and `artifacts/baseline.metadata.json`. Metadata includes model version, timestamp, feature method, data labels/counts, seed, augmentation, scikit-learn, and Python versions.

Evaluation operates only on held-out controlled test captures. When controlled chemical-test test data is absent, it prints `Evaluation skipped: controlled chemical-test test data is not available.` and creates no metrics. Once controlled data exists, it writes confusion matrices and precision/recall/F1/support for applicable held-out datasets. No accuracy claim exists before that evaluation.

## API and CLI

Python 3.12 is the supported runtime.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

- `GET http://127.0.0.1:8000/health` reports status, model version, and explicit mode.
- `POST http://127.0.0.1:8000/ai/analyze` accepts multipart form field `image`. Unsupported/non-image media types receive HTTP 415; invalid bytes receive a complete inconclusive AI result.

```powershell
curl.exe -F "image=@demo/fixtures/validation/shirt.png" http://127.0.0.1:8000/ai/analyze
python scripts/demo_analyze.py demo/fixtures/validation/valid_test.png
pytest
```

The CLI prints Validation (`valid`, reason, kit/test-area indicators, quality and calibration) followed by Classification (result, confidence, explanation, version).

## AI output contract and limitations

Every response contains `valid`, `validation_reason`, `kit_detected`, `test_area_detected`, `quality_score`, `calibration_score`, `result`, `confidence`, `explanation`, and `model_version`. `result` is only `PRESUMPTIVE_POSITIVE`, `PRESUMPTIVE_NEGATIVE`, or `INCONCLUSIVE`.

Every chemical-result explanation states: **“Presumptive result only; not definitive drug identification.”** Where a trained baseline is present, its confidence is an uncalibrated model probability, not a scientific probability of drug identity. In demo/fallback mode, no trained chemical-model confidence is claimed.

Demo scenarios: upload `shirt.png` → rejected and chemical classification skipped; upload `valid_test.png` with `AI_DEMO_PROFILE=PRESUMPTIVE_POSITIVE` → valid workflow state with zero confidence; upload `blurred.png` → rejected/insufficient input and inconclusive result. Never use any of these fixtures as evidence or controlled chemical data.
