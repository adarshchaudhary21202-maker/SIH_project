# Controlled datasets

This directory deliberately contains no sample chemical-test images. Do not generate synthetic chemical-test images or labels, and do not use internet images as chemical ground truth.

Dataset A, `chemical/`, contains only controlled photos of the approved target kit after a documented procedure. Its only labels are `PRESUMPTIVE_POSITIVE`, `PRESUMPTIVE_NEGATIVE`, and `INCONCLUSIVE`. Each row must cite `controlled_kit_record` and link in notes to a controlled record retained by the programme; these are presumptive reaction outcomes, not drug identifications.

Dataset B, `validation/`, is separate and contains `valid_test`, `shirt`, `wall`, `tree`, `random_object`, `screenshot`, `empty`, `wrong_kit`, `blurred`, and `bad_framing`. Its source is always `validation_capture`. It gates Dataset A: only `valid_test` reaches chemical classification.

## Collection procedure

1. Obtain ethics, safety, and laboratory/agency approval. Use only the approved kit, protocol, controls, and trained personnel.
2. Assign a unique `capture_session` to each independent physical run. Keep all images from one session together; never reuse it across train, validation, and test.
3. Capture original files directly using varied real devices and controlled variation in light, angle, distance, exposure, background, and documented reaction stage. Do not edit colour, scrape web images, fabricate images, or fabricate labels.
4. Store each original file under its dataset/label directory and add one `manifest.csv` row. Record kit ID, device, lighting, distance, angle, exposure, background, reaction stage, and notes. Retain controlled-kit and chain-of-custody records outside this repository under policy.
5. Collect at least three independent capture sessions for every class (more are needed for a useful model), then run the commands below. Scripts fail rather than claim a valid split if this is not met.

`manifest.schema.json` documents fields. `path` must start with `chemical/` or `validation/`; chemical rows require `controlled_kit_record`; validation rows require `validation_capture`.

```powershell
python scripts/assign_splits.py
python scripts/validate_manifest.py
```

Splitting uses capture sessions, seed 42, and targets approximately 70% train, 15% validation, 15% test. Training-only deterministic augmentation uses ±6° rotation, 94% crop/scale, ±10% brightness/contrast, JPEG quality 88, and blur radius 0.5. Test images are never augmented.
