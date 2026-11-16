# Local browser export verification

For automated browser tests in this project, do not click download controls or wait for a
browser download event. Chrome may open an operating-system Save As dialog that the web
connector cannot complete. Do not change the user's global browser preferences to avoid it.

Open the saved run's result page, then use:

```bash
uv run python scripts/verify_export.py --run runs/<run-id> --output .cache/export-check/<run-id>.zip
```

This verifies the actual HTTP ZIP registered by the result page, compares every entry with
the run artifacts and confirms exclusion of raw data.csv. It does not test the native Save As
dialog; describe that scope accurately. A 404 means the result page must be opened first.
Do not rerun a model analysis merely to repeat export verification.
