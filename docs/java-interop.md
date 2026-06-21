# Using psiwatch from Java or JavaScript

`psiwatch` is a Python CLI tool — it doesn't need a Java or JS port to be usable
from a Java or Node.js codebase. Like any CLI tool, you can shell out to it and
read back the JSON report it produces. This doc shows exactly how.

No changes to `psiwatch` itself are required for any of this — it already
supports everything below today, as long as `psiwatch` is installed
(`pip install psiwatch`) somewhere on the machine/container that runs it.

---

## 1. Generate a machine-readable report

```bash
psiwatch compare train.csv new.csv --output report.json
```

This writes a JSON file shaped like this (real output, abbreviated):

```json
{
  "health_score": 0,
  "warnings": [],
  "summary": {
    "high_count": 1,
    "medium_count": 0,
    "pass_count": 0,
    "drifted_columns": ["age"],
    "stable_columns": []
  },
  "columns": {
    "age": {
      "severity": "HIGH",
      "reasons": ["Mean shifted by 3.47 std devs (29.50 → 49.50)", "PSI = 24.412 (significant drift)"],
      "metrics": { "psi": 24.412, "baseline_mean": 29.5, "new_mean": 49.5 }
    }
  },
  "generated_at": "2026-06-20 11:18:48"
}
```

The fields you'll care about most from another language:
- `health_score` — 0–100, use this to gate a pipeline
- `summary.drifted_columns` — list of column names that drifted
- `columns.<name>.severity` — `"PASS"`, `"MEDIUM"`, or `"HIGH"` per column

---

## 2. Calling it from Java

```java
import java.io.*;
import java.util.*;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

public class DriftCheck {
    public static void main(String[] args) throws Exception {
        ProcessBuilder pb = new ProcessBuilder(
            "psiwatch", "compare", "train.csv", "new.csv", "--output", "report.json"
        );
        pb.redirectErrorStream(true);
        Process process = pb.start();

        // drain stdout so the process doesn't block on a full pipe
        try (BufferedReader r = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
            String line;
            while ((line = r.readLine()) != null) System.out.println(line);
        }

        int exitCode = process.waitFor();
        if (exitCode != 0) {
            throw new RuntimeException("psiwatch exited with code " + exitCode);
        }

        ObjectMapper mapper = new ObjectMapper();
        JsonNode report = mapper.readTree(new File("report.json"));

        int healthScore = report.get("health_score").asInt();
        System.out.println("Health score: " + healthScore);

        if (healthScore < 70) {
            List<String> drifted = new ArrayList<>();
            report.get("summary").get("drifted_columns").forEach(n -> drifted.add(n.asText()));
            System.out.println("Drifted columns: " + drifted);
            // e.g. fail the build, trigger an alert, block deployment, etc.
        }
    }
}
```

Uses Jackson (`com.fasterxml.jackson.core:jackson-databind`) for JSON parsing —
swap for `org.json` or Gson if that's what your project already uses; the
`ProcessBuilder` part stays the same either way.

---

## 3. Calling it from JavaScript / Node.js

```javascript
const { execFile } = require("child_process");
const fs = require("fs");

execFile(
  "psiwatch",
  ["compare", "train.csv", "new.csv", "--output", "report.json"],
  (error, stdout, stderr) => {
    if (error) {
      console.error("psiwatch failed:", stderr);
      process.exit(1);
    }

    const report = JSON.parse(fs.readFileSync("report.json", "utf8"));
    console.log("Health score:", report.health_score);

    if (report.health_score < 70) {
      console.log("Drifted columns:", report.summary.drifted_columns);
      // e.g. fail a CI step, send a Slack alert, etc.
    }
  }
);
```

Or with the JSON printed straight to stdout instead of a file
(`--format json` instead of `--output report.json`), skipping the file
read entirely:

```javascript
execFile("psiwatch", ["compare", "train.csv", "new.csv", "--format", "json"],
  (error, stdout) => {
    const report = JSON.parse(stdout);
    console.log(report.health_score);
  }
);
```

---

## 4. Using it as a CI/CD gate (language-agnostic)

Since `psiwatch` is just a CLI, this works the same regardless of what
language your pipeline step is written in:

```bash
psiwatch compare train.csv new.csv --output report.json --fail-on-drift
echo $?   # exits 1 if health_score < 80 — use this to fail a build step
```

A Java-based Jenkins/Gradle pipeline, a JS-based GitHub Action, or any other
CI runner can all call this the same way a shell script would.

---

## Notes

- This requires `psiwatch` to be installed wherever the command runs
  (`pip install psiwatch`) — Java/JS code doesn't need any Python knowledge
  beyond knowing it's installed and on `PATH`.
- No psiwatch source code changes are needed for any of the above — this is
  purely about invoking an existing CLI tool and reading its output, which
  works for any language capable of running a subprocess and parsing JSON.
