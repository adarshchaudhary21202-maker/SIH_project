"""Train separate controlled-image RandomForest prototype baselines."""
from __future__ import annotations
import csv, io, json, platform, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
import joblib
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from sklearn import __version__ as sklearn_version
from sklearn.ensemble import RandomForestClassifier
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.ai.baseline import image_features
ROOT = Path(__file__).resolve().parents[1]; DATA = ROOT / "data"; OUT = ROOT / "artifacts"; SEED = 42
REQUIRED = {"validation": {"valid_test", "shirt", "wall", "tree", "random_object", "screenshot", "empty", "wrong_kit", "blurred", "bad_framing"}, "chemical": {"PRESUMPTIVE_POSITIVE", "PRESUMPTIVE_NEGATIVE", "INCONCLUSIVE"}}
AUGMENTATION = {"training_only": True, "rotation_degrees": [-6, 6], "crop_scale": 0.94, "brightness": [0.90, 1.10], "contrast": [0.90, 1.10], "jpeg_quality": 88, "gaussian_blur_radius": 0.5, "seed": SEED}
def augment(image: Image.Image) -> list[Image.Image]:
    """Conservative deterministic augmentation; never applied to validation/test rows."""
    base = image.convert("RGB"); crop = ImageOps.fit(base, (round(base.width * .94), round(base.height * .94)), centering=(.5, .5)).resize(base.size)
    buffer = io.BytesIO(); base.save(buffer, format="JPEG", quality=88); jpeg = Image.open(io.BytesIO(buffer.getvalue())).convert("RGB")
    return [base, base.rotate(-6), base.rotate(6), crop, ImageEnhance.Brightness(base).enhance(.90), ImageEnhance.Brightness(base).enhance(1.10), ImageEnhance.Contrast(base).enhance(.90), ImageEnhance.Contrast(base).enhance(1.10), jpeg, base.filter(ImageFilter.GaussianBlur(.5))]
def train(rows: list[dict[str, str]], dataset: str) -> tuple[RandomForestClassifier, dict[str, int]]:
    selected = [row for row in rows if row["dataset"] == dataset and row["split"] == "train"]; missing = REQUIRED[dataset] - {row["label"] for row in selected}
    if missing: raise ValueError(f"{dataset} train split is missing required classes: {', '.join(sorted(missing))}")
    features, labels = [], []
    for row in selected:
        with Image.open(DATA / row["path"]) as source: variants = augment(source)
        features.extend(image_features(item) for item in variants); labels.extend([row["label"]] * len(variants))
    return RandomForestClassifier(n_estimators=200, class_weight="balanced", random_state=SEED, n_jobs=-1).fit(features, labels), {label: sum(row["label"] == label for row in selected) for label in sorted(REQUIRED[dataset])}
def main() -> int:
    with (DATA / "manifest.csv").open(newline="", encoding="utf-8") as source: rows = list(csv.DictReader(source))
    if not rows: print("Refusing to train: manifest is empty. Add controlled images first.", file=sys.stderr); return 1
    if subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_manifest.py")]).returncode: print("Refusing to train: fix manifest errors first.", file=sys.stderr); return 1
    try: validation, validation_counts = train(rows, "validation"); chemical, chemical_counts = train(rows, "chemical")
    except (OSError, ValueError) as exc: print(f"Refusing to train: {exc}", file=sys.stderr); return 1
    OUT.mkdir(exist_ok=True)
    metadata = {"model_version": "controlled-baseline-0.2.0", "trained_at": datetime.now(timezone.utc).isoformat(), "feature_method": "RGB/HSV global mean and standard deviation", "prototype_notice": "RandomForest RGB/HSV global-statistics baseline only; not scientifically or forensically validated.", "datasets": {"validation": {"labels": sorted(REQUIRED["validation"]), "training_image_counts": validation_counts}, "chemical": {"labels": sorted(REQUIRED["chemical"]), "training_image_counts": chemical_counts}}, "random_seed": SEED, "augmentation": AUGMENTATION, "sklearn_version": sklearn_version, "python_version": platform.python_version()}
    joblib.dump({"validation_model": validation, "chemical_model": chemical, "metadata": metadata}, OUT / "baseline.joblib")
    (OUT / "baseline.metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Saved {OUT / 'baseline.joblib'} and metadata."); return 0
if __name__ == "__main__": raise SystemExit(main())
