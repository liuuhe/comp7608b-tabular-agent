"""Generate LaTeX sections from DRAFT.md; requires Pandoc, never runs the agent."""

import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def convert(text):
    # Repository evidence links stay in Markdown; a portable paper uses their readable labels.
    text = re.sub(r"\[([^\]]+)\]\((?:\.\./)[^)]+\)", r"\1", text)
    text = text.replace("—", " -- ").replace("–", "--").replace("→", "->")
    parsed = subprocess.run(["pandoc", "--from=gfm", "--to=json"], input=text,
                            text=True, capture_output=True, check=True)
    document = json.loads(parsed.stdout)
    for block in document["blocks"]:
        if block["t"] != "Table":
            continue
        columns = block["c"][2]
        widths = {2: [0.24, 0.76], 3: [0.23, 0.13, 0.64], 4: [0.4, 0.2, 0.2, 0.2]}.get(len(columns))
        if widths:
            for column, width in zip(columns, widths):
                column[1] = {"t": "ColWidth", "c": width}
    rendered = subprocess.run(
        ["pandoc", "--from=json", "--to=latex", "--shift-heading-level-by=-1", "--wrap=none", "--syntax-highlighting=none"],
        input=json.dumps(document), text=True, capture_output=True, check=True,
    ).stdout
    # All current paper tables fit on one page. Keep rows together instead of leaving
    # a lone continuation row at the top of the next page.
    rendered = rendered.replace("\\begin{longtable}[]{", "\\begin{table}[htbp]\\centering\n\\begin{tabular}{")
    rendered = rendered.replace("\\endhead\n", "")
    rendered = rendered.replace("\\bottomrule\\noalign{}\n\\endlastfoot\n", "")
    rendered = rendered.replace("\\end{longtable}", "\\bottomrule\n\\end{tabular}\n\\end{table}")
    return rendered


def main():
    source = ROOT / "DRAFT.md"
    text = source.read_text()
    _, remainder = text.split("## Abstract\n", 1)
    abstract, remainder = remainder.split("## 1. ", 1)
    body, references = ("## 1. " + remainder).split("## References\n", 1)
    body = re.sub(r"^(#{2,4}) \d+(?:\.\d+)*\.\s*", r"\1 ", body, flags=re.M)
    destination = ROOT / "latex"
    if not (destination / "main.tex").is_file():
        raise ValueError("The report/latex/main.tex project must exist first")
    parts = {"abstract.tex": convert(abstract.strip()), "body.tex": convert(body.strip()),
             "references.tex": "\\section*{References}\n" + convert(references.strip())}
    for name, content in parts.items():
        (destination / name).write_text("% Generated from report/DRAFT.md by build_report.py.\n" + content)
    manifest = {
        "status": "working_draft_formal_evaluation_pending", "source": "report/DRAFT.md",
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "pandoc_version": subprocess.check_output(["pandoc", "--version"], text=True).splitlines()[0],
        "generated_sha256": {name: hashlib.sha256((destination / name).read_bytes()).hexdigest()
                             for name in parts},
    }
    (destination / "source-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
