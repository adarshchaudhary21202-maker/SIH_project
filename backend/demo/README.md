# SIH demo fixtures

`fixtures/validation/` is created by `python scripts/create_demo_validation_data.py`. These synthetic validation fixtures demonstrate application workflow only: they are **not chemical-test data**, are **not forensic ground truth**, and never belong in `data/` or `manifest.csv`.

There are deliberately no chemical positive/negative fixture images. In demo mode, a `valid_test` fixture is accepted by deterministic fixture-marker validation, then `AI_DEMO_PROFILE` selects an allowed UI state (`PRESUMPTIVE_POSITIVE`, `PRESUMPTIVE_NEGATIVE`, or `INCONCLUSIVE`). That is a visible workflow setting, not a chemical prediction, model result, or confidence measure.

Use the generated fixtures as follows:

```powershell
python scripts/create_demo_validation_data.py
$env:AI_DEMO_MODE='true'
$env:AI_DEMO_PROFILE='PRESUMPTIVE_POSITIVE'
python scripts/demo_analyze.py demo/fixtures/validation/valid_test.png
python scripts/demo_analyze.py demo/fixtures/validation/shirt.png
```

The marker mechanism is intentionally limited to these documented software fixtures. An ordinary image is rejected as `UNRECOGNIZED_DEMO_IMAGE`; it does not run a chemical classifier.
