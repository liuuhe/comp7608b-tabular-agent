# Group 39 submission materials

**Project:** A Local Tabular Analysis Agent with Bounded Verification and Repair

**Members:** Wang Ming, Liu He, He Xiya

**Version:** group39-20261120-submission-v1 (see VERSION.json and the ZIP's SOURCE_MANIFEST.json).

This folder accompanies the runnable application at the archive root. It contains the AI-use declaration, recoverable project prompts, individual contributions, source attribution, ordinary/changed/failure examples, numerical results and five genuine saved case traces. The final report PDF is submitted alongside the application ZIP. A repository link does not replace the source snapshot.

- Read AI_USE.md and prompts/README.md for AI assistance, redactions and missing prompt records.
- CONTRIBUTIONS.md records confirmed completed responsibilities; no equal percentage is asserted.
- examples/README.md gives offline inspection and fresh-run commands. A fresh run uses local inference and may produce a different outcome.
- results/results.json retains all 252 automatic observations, 126 repeat-averaged input/condition rows, resource measurements and the 27-output human sample. The other 225 outputs remain unrated. automatic_by_input.csv is the same repeat-averaged table in CSV form.
- traces/ contains the real small ordinary demo, a recovered count error, a changed measure, an exhausted execution failure and an unresolved date-scope failure. PROVENANCE.json binds original hashes to the selected/redacted copies. These cases explain behavior; they are deliberately selected examples, not an unbiased performance sample.
- ATTRIBUTION.md acknowledges libraries, data, model services and the report template.

Verify offline from the extracted application root:

```bash
python scripts/package_project.py --verify /absolute/path/to/source.zip
python -m scripts.submission_materials --verify submission
python -m scripts.submission_examples ordinary
```

These commands do not invoke a model or require private research evidence. Rebuilding these exports from the original records requires the original workspace; the exported materials themselves can be inspected independently. Download instructions for the full UCI data are in the root README. Model weights, environments, credentials, full raw datasets and the original private rating sheets are excluded.

MANIFEST.json checks the contents of this folder. SOURCE_MANIFEST.json checks the complete application ZIP. Hashes establish byte integrity, not human authorship, research validity or course acceptance. Nothing here represents a completed course upload or a substitute for the live demonstration.
