# psiwatch — Java & JavaScript Examples

Runnable, tested examples showing how to call the `psiwatch` CLI from Java
and from Node.js, and read back its JSON drift report.

`psiwatch` itself requires no code changes for this — it's a Python CLI tool,
and like any CLI tool (`git`, `ffmpeg`, etc.) it can be invoked as a
subprocess from any language that can run one and parse JSON.

**Prerequisite for both examples:** `psiwatch` must be installed and on
`PATH`:
```bash
pip install psiwatch
```

---

## java-example/

```bash
cd java-example
java DriftCheck.java train.csv new.csv
```

Uses Java's single-file source launcher (Java 11+), so no separate compile
step is needed. Parses the JSON report with plain regex — zero external
dependencies required. If your project already uses Jackson/Gson, swap the
two parse*() helper methods for real JSON parsing; the subprocess-calling
part stays identical either way.

## js-example/

```bash
cd js-example
node drift-check.js train.csv new.csv
```

Uses Node's built-in `child_process` and `JSON.parse` — no npm install
needed, no dependencies in `package.json`.

---

## What both examples do

1. Run `psiwatch compare <baseline> <new> --output report.json` as a subprocess
2. Wait for it to finish, check the exit code
3. Read and parse `report.json`
4. Print `health_score` and the list of drifted columns
5. Exit with a non-zero code if `health_score < 70` — useful for failing a
   CI/CD step on significant drift

`train.csv`/`new.csv` included in each folder are small sample files with
deliberately shifted data (ages 20-39 vs ages 40-59), so running either
example out of the box will correctly show HIGH drift — that's expected, not
a bug. Swap in your own CSVs to test real data.

See `java-interop.md` for the full write-up, including the exact JSON shape
`psiwatch` produces and a CI/CD gating example.
