"""Evaluate only held-out manifest test captures; never fabricate metrics."""
from __future__ import annotations
import csv, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; DATA = ROOT / "data"; OUT = ROOT / "artifacts"
def main() -> int:
    with (DATA / "manifest.csv").open(newline="", encoding="utf-8") as source: rows = list(csv.DictReader(source))
    if not any(row["dataset"] == "chemical" for row in rows):
        print("Evaluation skipped: controlled chemical-test test data is not available.")
        return 0
    if not any(row["dataset"] == "chemical" and row["split"] == "test" for row in rows):
        print("Evaluation skipped: controlled chemical-test test data is not available.")
        return 0
    import joblib
    from PIL import Image
    from sklearn.metrics import classification_report, confusion_matrix
    sys.path.insert(0, str(ROOT))
    from app.ai.baseline import image_features
    artifact = OUT / "baseline.joblib"
    if not artifact.is_file(): print(f"Cannot evaluate: model artifact missing: {artifact}. Run train_baseline.py first.", file=sys.stderr); return 1
    saved = joblib.load(artifact); report = {}
    for dataset, model in (("validation", saved["validation_model"]), ("chemical", saved["chemical_model"])):
        test = [row for row in rows if row["dataset"] == dataset and row["split"] == "test"]
        if not test: print(f"Cannot evaluate: no held-out test images for dataset '{dataset}'. Assign complete capture sessions to test and collect every required class.", file=sys.stderr); return 1
        y, predictions = [row["label"] for row in test], []
        for row in test:
            with Image.open(DATA / row["path"]) as image: predictions.append(model.predict([image_features(image)])[0])
        labels = sorted(set(y) | set(predictions)); matrix = confusion_matrix(y, predictions, labels=labels).tolist(); metrics = classification_report(y, predictions, labels=labels, output_dict=True, zero_division=0)
        report[dataset] = {"test_image_count": len(test), "labels": labels, "confusion_matrix": matrix, "precision_recall_f1": metrics}
        with (OUT / f"{dataset}_confusion_matrix.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle); writer.writerow(["actual/predicted", *labels]); writer.writerows([[label, *values] for label, values in zip(labels, matrix)])
        print(f"{dataset}: {len(test)} held-out test images")
        for label in labels: print(f"  {label}: precision={metrics[label]['precision']:.3f} recall={metrics[label]['recall']:.3f} f1={metrics[label]['f1-score']:.3f} support={metrics[label]['support']}")
        for average in ("macro avg", "weighted avg"): print(f"  {average}: precision={metrics[average]['precision']:.3f} recall={metrics[average]['recall']:.3f} f1={metrics[average]['f1-score']:.3f} support={metrics[average]['support']}")
    (OUT / "evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8"); print(f"Saved {OUT / 'evaluation.json'}"); return 0
if __name__ == "__main__": raise SystemExit(main())
