import java.io.*;
import java.util.*;
import java.util.regex.*;

/**
 * Calls the psiwatch CLI from Java and reads back the drift report.
 *
 * Requires `psiwatch` to be installed and on PATH (pip install psiwatch).
 * This example uses zero external JSON libraries — just plain regex
 * extraction of the few fields we need, so it compiles and runs with
 * nothing but the JDK. If you already use Jackson/Gson in your project,
 * swap parseHealthScore()/parseDriftedColumns() for a real parser instead —
 * the ProcessBuilder part stays the same either way.
 *
 * Compile:  javac DriftCheck.java
 * Run:      java DriftCheck train.csv new.csv
 */
public class DriftCheck {

    public static void main(String[] args) throws Exception {
        if (args.length < 2) {
            System.err.println("Usage: java DriftCheck <baseline.csv> <new.csv>");
            System.exit(1);
        }

        String baseline = args[0];
        String newFile = args[1];
        String reportPath = "report.json";

        ProcessBuilder pb = new ProcessBuilder(
            "psiwatch", "compare", baseline, newFile, "--output", reportPath
        );
        pb.redirectErrorStream(true);
        Process process = pb.start();

        // Drain stdout so the process doesn't block on a full pipe buffer.
        StringBuilder cliOutput = new StringBuilder();
        try (BufferedReader r = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
            String line;
            while ((line = r.readLine()) != null) {
                cliOutput.append(line).append("\n");
            }
        }

        int exitCode = process.waitFor();
        System.out.print(cliOutput);

        if (exitCode != 0) {
            throw new RuntimeException("psiwatch exited with code " + exitCode);
        }

        String json = readFile(reportPath);

        int healthScore = parseHealthScore(json);
        List<String> driftedColumns = parseDriftedColumns(json);

        System.out.println("\n--- Parsed in Java ---");
        System.out.println("Health score: " + healthScore);
        System.out.println("Drifted columns: " + driftedColumns);

        if (healthScore < 70) {
            System.out.println("⚠ Drift detected — consider blocking deploy / triggering retraining.");
            System.exit(1);
        } else {
            System.out.println("✓ No significant drift.");
        }
    }

    private static String readFile(String path) throws IOException {
        StringBuilder sb = new StringBuilder();
        try (BufferedReader r = new BufferedReader(new FileReader(path))) {
            String line;
            while ((line = r.readLine()) != null) sb.append(line).append("\n");
        }
        return sb.toString();
    }

    /** Extracts "health_score": <number> from the JSON report via regex. */
    private static int parseHealthScore(String json) {
        Matcher m = Pattern.compile("\"health_score\"\\s*:\\s*(\\d+)").matcher(json);
        if (m.find()) return Integer.parseInt(m.group(1));
        throw new RuntimeException("Could not find health_score in report.json");
    }

    /** Extracts the "drifted_columns": [...] array from the JSON report via regex. */
    private static List<String> parseDriftedColumns(String json) {
        List<String> result = new ArrayList<>();
        Matcher block = Pattern.compile("\"drifted_columns\"\\s*:\\s*\\[(.*?)\\]", Pattern.DOTALL).matcher(json);
        if (block.find()) {
            Matcher names = Pattern.compile("\"([^\"]+)\"").matcher(block.group(1));
            while (names.find()) result.add(names.group(1));
        }
        return result;
    }
}
