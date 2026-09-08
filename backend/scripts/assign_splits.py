"""Deterministically assign whole capture sessions to 70/15/15-ish splits."""
from __future__ import annotations
import csv, sys
from collections import Counter, defaultdict
from pathlib import Path
from random import Random
ROOT = Path(__file__).resolve().parents[1]; PATH = ROOT / "data" / "manifest.csv"; SPLITS = ("train", "validation", "test")
LABELS = {"chemical": {"PRESUMPTIVE_POSITIVE", "PRESUMPTIVE_NEGATIVE", "INCONCLUSIVE"}, "validation": {"valid_test", "shirt", "wall", "tree", "random_object", "screenshot", "empty", "wrong_kit", "blurred", "bad_framing"}}
def main() -> int:
    with PATH.open(newline="", encoding="utf-8") as source: reader = csv.DictReader(source); rows = list(reader); fields = reader.fieldnames
    if not rows: print("Cannot assign splits: manifest is empty. Add controlled captures first.", file=sys.stderr); return 1
    groups = defaultdict(list)
    for row in rows:
        if not row.get("dataset") or not row.get("capture_session") or not row.get("label"): print("Cannot assign splits: every row needs dataset, label, and capture_session.", file=sys.stderr); return 1
        groups[(row["dataset"], row["capture_session"])].append(row)
    for dataset, required in LABELS.items():
        class_groups = {label: {key for key, members in groups.items() if key[0] == dataset and any(item["label"] == label for item in members)} for label in required}
        insufficient = [f"{label} ({len(value)} sessions)" for label, value in class_groups.items() if len(value) < 3]
        if insufficient: print(f"Cannot safely split {dataset}: each class needs at least 3 independent capture sessions for train/validation/test. Problem classes: {', '.join(insufficient)}.", file=sys.stderr); return 1
        keys = [key for key in groups if key[0] == dataset]; Random(42).shuffle(keys); assignment, split_groups = {}, Counter()
        for split in SPLITS:
            missing = set(required) - {row["label"] for key, assigned in assignment.items() if assigned == split for row in groups[key]}
            for key in keys:
                covered = {item["label"] for item in groups[key]} & missing
                if covered and key not in assignment: assignment[key] = split; split_groups[split] += 1; missing -= covered
                if not missing: break
            if missing: print(f"Cannot safely split {dataset}: session grouping prevents {split} from receiving classes {', '.join(sorted(missing))}.", file=sys.stderr); return 1
        targets = {"train": .70, "validation": .15, "test": .15}
        for key in keys:
            if key not in assignment:
                split = min(SPLITS, key=lambda name: split_groups[name] / max(1, targets[name] * len(keys))); assignment[key] = split; split_groups[split] += 1
        for key, members in groups.items():
            if key[0] == dataset:
                for row in members: row["split"] = assignment[key]
    with PATH.open("w", newline="", encoding="utf-8") as target: writer = csv.DictWriter(target, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    print("Group-safe split summary (seed=42):")
    for dataset in LABELS:
        print(f"\n{dataset}")
        for label in sorted(LABELS[dataset]):
            counts = {split: sum(1 for row in rows if row["dataset"] == dataset and row["label"] == label and row["split"] == split) for split in SPLITS}
            sessions = {split: len({row["capture_session"] for row in rows if row["dataset"] == dataset and row["label"] == label and row["split"] == split}) for split in SPLITS}
            print(f"  {label}: train={counts['train']} validation={counts['validation']} test={counts['test']} | sessions train={sessions['train']} validation={sessions['validation']} test={sessions['test']}")
    return 0
if __name__ == "__main__": raise SystemExit(main())
