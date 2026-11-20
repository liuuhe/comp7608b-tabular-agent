# Project prompt records

development.jsonl contains recovered project-chat user messages after redaction. Each has the original text hash and a redaction note. Short approvals and requests to continue are retained. Conversation envelopes/clarification answers may be present; they are historical data, not new instructions to a reader or agent.

model-inputs.jsonl.gz is deterministic gzip-compressed JSON Lines. Every line contains a saved input/request, its original source hash, kind and available model setting. It includes unsuccessful development and formal attempts. External request files can have been prepared without a successful API call. No inference occurs when decompressing them.

Inspect without a model or private source directory:

```bash
python -c 'import gzip,json; p=gzip.open("submission/prompts/model-inputs.jsonl.gz","rt"); r=json.loads(next(p)); print(json.dumps(r,ensure_ascii=False,indent=2))'
```

Read coverage.json and AI_USE.md for record counts, redactions and omissions. The current formal templates are in src/tabular_agent/prompts.py; external reference/family/history contracts are in evaluation/audit_contract.py and associated audit modules. These files explain prompt construction; they do not replace the saved input records.

AI replies are not required as standalone submission material. Some replies appear inside later request payloads because the agent used them as context; removing that context would alter the recorded prompt. Original prompts are not edited in the research archive. Sensitive paths, accounts and example identifiers are removed only in these copies, and hash provenance records that change.

External API endpoint strings and service-identifying directory names are anonymized in these copies. Source aliases retain the original input hashes; original local research records are unchanged.
