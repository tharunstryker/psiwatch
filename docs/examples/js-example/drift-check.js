const { execFile } = require("child_process");
const fs = require("fs");

/**
 * Calls the psiwatch CLI from Node.js and reads back the drift report.
 *
 * Requires `psiwatch` to be installed and on PATH (pip install psiwatch).
 *
 * Run: node drift-check.js train.csv new.csv
 */

const [baseline, newFile] = process.argv.slice(2);

if (!baseline || !newFile) {
  console.error("Usage: node drift-check.js <baseline.csv> <new.csv>");
  process.exit(1);
}

const reportPath = "report.json";

execFile(
  "psiwatch",
  ["compare", baseline, newFile, "--output", reportPath],
  (error, stdout, stderr) => {
    if (stdout) console.log(stdout);

    if (error) {
      console.error("psiwatch failed:", stderr || error.message);
      process.exit(1);
    }

    const report = JSON.parse(fs.readFileSync(reportPath, "utf8"));

    console.log("\n--- Parsed in Node.js ---");
    console.log("Health score:", report.health_score);
    console.log("Drifted columns:", report.summary.drifted_columns);

    if (report.health_score < 70) {
      console.log("⚠ Drift detected — consider blocking deploy / triggering retraining.");
      process.exit(1);
    } else {
      console.log("✓ No significant drift.");
    }
  }
);
