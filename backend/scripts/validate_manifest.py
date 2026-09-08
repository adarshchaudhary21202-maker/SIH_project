"""Validate the controlled-image manifest before splitting, training, or evaluation."""
from __future__ import annotations
import csv, hashlib, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]; DATA = ROOT / "data"; MANIFEST = DATA / "manifest.csv"
CHEMICAL_LABELS = {"PRESUMPTIVE_POSITIVE", "PRESUMPTIVE_NEGATIVE", "INCONCLUSIVE"}
VALIDATION_LABELS = {"valid_test", "shirt", "wall", "tree", "random_object", "screenshot", "empty", "wrong_kit", "blurred", "bad_framing"}
REQUIRED = ("id", "dataset", "path", "label", "split", "capture_session", "ground_truth_source")

def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()

def main() -> int:
    if not MANIFEST.exists():
        print(f"Manifest invalid:\n- missing manifest file: {MANIFEST}", file=sys.stderr); return 1
    with MANIFEST.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source); rows = list(reader); headers = set(reader.fieldnames or [])
    errors: list[str] = []
    if not rows: errors.append("manifest is empty; add real controlled captures before splitting or training")
    if missing_columns := set(REQUIRED) - headers: errors.append("manifest missing required columns: " + ", ".join(sorted(missing_columns)))
    ids: dict[str, int] = {}; hashes: dict[str, tuple[int, str]] = {}; sessions = defaultdict(set)
    by_dataset: Counter[str] = Counter(); labels = defaultdict(Counter); class_sessions = defaultdict(set)
    for line, row in enumerate(rows, start=2):
        prefix = f"row {line}"; missing = [key for key in REQUIRED if not (row.get(key) or "").strip()]
        if missing: errors.append(f"{prefix}: missing required value(s): {', '.join(missing)}"); continue
        image_id, dataset, label = row["id"].strip(), row["dataset"].strip(), row["label"].strip()
        if image_id in ids: errors.append(f"{prefix}: duplicate id '{image_id}' (first used on row {ids[image_id]})")
        ids[image_id] = line
        if dataset not in {"chemical", "validation"}:
            errors.append(f"{prefix}: dataset must be 'chemical' or 'validation', got '{dataset}'"); continue
        if not row["path"].replace("\\", "/").startswith(f"{dataset}/"):
            errors.append(f"{prefix}: path must start with '{dataset}/', got '{row['path']}'")
        allowed = CHEMICAL_LABELS if dataset == "chemical" else VALIDATION_LABELS
        if label not in allowed: errors.append(f"{prefix}: label '{label}' is invalid for dataset '{dataset}'; allowed: {', '.join(sorted(allowed))}")
        source = row["ground_truth_source"].strip()
        if dataset == "chemical" and source != "controlled_kit_record": errors.append(f"{prefix}: chemical image requires ground_truth_source=controlled_kit_record; internet or synthetic labels are prohibited")
        if dataset == "validation" and source != "validation_capture": errors.append(f"{prefix}: validation image requires ground_truth_source=validation_capture")
        if row["split"].strip() not in {"train", "validation", "test"}: errors.append(f"{prefix}: split must be train, validation, or test")
        image_path = DATA / row["path"]
        if not image_path.is_file(): errors.append(f"{prefix}: image file is missing: {image_path}")
        else:
            try:
                digest = file_digest(image_path)
                if digest in hashes:
                    prior_line, prior_path = hashes[digest]; errors.append(f"{prefix}: duplicate image content matches row {prior_line} ({prior_path}); use one capture only once")
                hashes[digest] = (line, row["path"])
            except OSError as exc: errors.append(f"{prefix}: cannot read image '{row['path']}': {exc}")
        session = row["capture_session"].strip(); sessions[(dataset, session)].add(row["split"].strip())
        by_dataset[dataset] += 1; labels[dataset][label] += 1; class_sessions[(dataset, label)].add(session)
    for (dataset, session), splits in sessions.items():
        if len(splits) > 1: errors.append(f"{dataset} capture_session '{session}' occurs in multiple splits ({', '.join(sorted(splits))}); assign an entire session to one split")
    for dataset, required_labels in (("chemical", CHEMICAL_LABELS), ("validation", VALIDATION_LABELS)):
        if not by_dataset[dataset]: errors.append(f"dataset '{dataset}' is empty; collect controlled images for all required classes")
        if missing := required_labels - set(labels[dataset]): errors.append(f"dataset '{dataset}' missing required classes: {', '.join(sorted(missing))}")
        for label in sorted(required_labels & set(labels[dataset])):
            count = len(class_sessions[(dataset, label)])
            if count < 3: errors.append(f"{dataset}/{label} has only {count} capture session(s); at least 3 are required to place the class in train, validation, and test without leakage")
    if errors: print("Manifest invalid:\n- " + "\n- ".join(errors), file=sys.stderr); return 1
    print(f"Manifest valid: {len(rows)} images across {len(sessions)} dataset/capture-session groups.")
    for dataset in ("chemical", "validation"): print(f"  {dataset}: {by_dataset[dataset]} images; " + ", ".join(f"{key}={value}" for key, value in sorted(labels[dataset].items())))
    return 0
if __name__ == "__main__": raise SystemExit(main())
