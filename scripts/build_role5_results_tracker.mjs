import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = new URL("../templates/", import.meta.url);
const outputPath = new URL("role5-results-tracker.xlsx", outputDir);

const workbook = Workbook.create();
const summary = workbook.worksheets.add("Summary");
const log = workbook.worksheets.add("Results log");
const lists = workbook.worksheets.add("Lists");

for (const sheet of [summary, log, lists]) {
  sheet.showGridLines = false;
}

summary.getRange("A2:H2").merge();
summary.getRange("A2").values = [["LeanHarness Role 5 Results Tracker"]];
summary.getRange("A2").format = {
  font: { bold: true, size: 16, color: "#1F1F1F" },
  horizontalAlignment: "left",
  verticalAlignment: "center",
};
summary.getRange("A3:H3").merge();
summary.getRange("A3").values = [["Record one row per completed task/configuration. Do not delete ordinary failures, zero rewards, timeouts, or non-zero results."]];
summary.getRange("A3").format = { font: { italic: true, color: "#666666" }, wrapText: true };

summary.getRange("A5:G5").values = [["Configuration", "Runs recorded", "Successful tasks", "Success rate", "Actual cost (USD)", "Cost per success (USD)", "Exceptions"]];
summary.getRange("A5:G5").format = { fill: "#1F4E78", font: { bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", verticalAlignment: "center" };
summary.getRange("A6:A8").values = [["C0"], ["R5-A"], ["R5-A+B"]];
for (let row = 6; row <= 8; row++) {
  summary.getRange(`B${row}`).formulas = [[`=COUNTIF('Results log'!$B$7:$B$206,A${row})`]];
  summary.getRange(`C${row}`).formulas = [[`=COUNTIFS('Results log'!$B$7:$B$206,A${row},'Results log'!$H$7:$H$206,1)`]];
  summary.getRange(`D${row}`).formulas = [[`=IF(B${row}=0,"",C${row}/B${row})`]];
  summary.getRange(`E${row}`).formulas = [[`=SUMIF('Results log'!$B$7:$B$206,A${row},'Results log'!$N$7:$N$206)`]];
  summary.getRange(`F${row}`).formulas = [[`=IF(C${row}=0,"",E${row}/C${row})`]];
  summary.getRange(`G${row}`).formulas = [[`=COUNTIFS('Results log'!$B$7:$B$206,A${row},'Results log'!$I$7:$I$206,"YES")`]];
}
summary.getRange("A5:G8").format.borders = { preset: "all", style: "thin", color: "#D9E2F3" };
summary.getRange("D6:D8").format.numberFormat = [["0.0%"], ["0.0%"], ["0.0%"]];
summary.getRange("E6:F8").format.numberFormat = [["$0.0000", "$0.0000"], ["$0.0000", "$0.0000"], ["$0.0000", "$0.0000"]];

summary.getRange("A11:H11").merge();
summary.getRange("A11").values = [["Role 5 decision rules"]];
summary.getRange("A11").format = { fill: "#D9EAF7", font: { bold: true, color: "#1F1F1F" } };
summary.getRange("A12:H15").values = [
  ["1", "Compare R5-A with C0", "Does clearer result feedback improve success, lower cost, or reduce wasted tool actions?", "", "", "", "", ""],
  ["2", "Compare R5-A+B with R5-A", "This isolates the additional effect of the Command Guard.", "", "", "", "", ""],
  ["3", "Actual cost", "Use the OpenRouter usage-difference value if Harbor reports 0.0.", "", "", "", "", ""],
  ["4", "Keep all outcomes", "Only documented infrastructure failures may be rerun.", "", "", "", "", ""],
];
summary.getRange("A12:C15").format = { wrapText: true, verticalAlignment: "top" };

const headers = [
  "Run date", "Configuration", "Task ID", "Model", "Agent version", "Adapter commit", "Run status", "Reward", "Exception?", "Runtime (s)", "Input tokens", "Output tokens", "Harbor cost (USD)", "Actual OpenRouter cost (USD)", "Tool actions", "Guarded actions", "File-not-found", "Command-not-found", "Permission-denied", "Timeout/exception", "Other failures", "Trajectory path", "Harbor output path", "Notes"
];
log.getRange("A2:X2").merge();
log.getRange("A2").values = [["Role 5 task-level result log"]];
log.getRange("A2").format = { font: { bold: true, size: 15 }, horizontalAlignment: "left" };
log.getRange("A3:X4").merge();
log.getRange("A3").values = [["One row = one task under one configuration. Fill actual cost from OpenRouter's cumulative-usage difference, not only Harbor's cost field. Keep raw paths so every reported result can be audited."]];
log.getRange("A3").format = { font: { italic: true, color: "#666666" }, wrapText: true, verticalAlignment: "top" };
log.getRange("A6:X6").values = [headers];
log.getRange("A6:X6").format = { fill: "#1F4E78", font: { bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", verticalAlignment: "center", wrapText: true };
log.getRange("A6:X206").format.borders = { preset: "all", style: "thin", color: "#E7E6E6" };
log.freezePanes.freezeRows(6);
log.freezePanes.freezeColumns(3);
log.getRange("A7:A206").format.numberFormat = Array.from({ length: 200 }, () => ["yyyy-mm-dd"]);
log.getRange("H7:H206").format.numberFormat = Array.from({ length: 200 }, () => ["0.0"]);
log.getRange("J7:J206").format.numberFormat = Array.from({ length: 200 }, () => ["0.0"]);
log.getRange("K7:L206").format.numberFormat = Array.from({ length: 200 }, () => ["#,##0", "#,##0"]);
log.getRange("M7:N206").format.numberFormat = Array.from({ length: 200 }, () => ["$0.0000", "$0.0000"]);
log.getRange("O7:U206").format.numberFormat = Array.from({ length: 200 }, () => ["#,##0", "#,##0", "#,##0", "#,##0", "#,##0", "#,##0", "#,##0"]);
log.getRange("B7:B206").dataValidation = { rule: { type: "list", values: ["C0", "R5-A", "R5-A+B"] } };
log.getRange("G7:G206").dataValidation = { rule: { type: "list", values: ["completed", "timeout", "infrastructure_failure", "not_run"] } };
log.getRange("I7:I206").dataValidation = { rule: { type: "list", values: ["YES", "NO"] } };

lists.getRange("A1:C1").values = [["Field", "Allowed values / interpretation", "Source"]];
lists.getRange("A1:C1").format = { fill: "#1F4E78", font: { bold: true, color: "#FFFFFF" } };
lists.getRange("A2:C8").values = [
  ["Configuration", "C0, R5-A, R5-A+B", "Shared benchmark design"],
  ["Run status", "completed, timeout, infrastructure_failure, not_run", "Harbor/job logs"],
  ["Exception?", "YES or NO", "Harbor summary"],
  ["Reward", "Official verifier result; do not alter", "Harbor verifier output"],
  ["Actual OpenRouter cost", "Usage-after minus usage-before for the batch/run", "OpenRouter usage record"],
  ["Failure counts", "Count categories in the saved trajectory", "mini-SWE-agent trajectory"],
  ["Paths", "Relative repository/job paths where possible", "Saved run artifacts"],
];
lists.getRange("A1:C8").format.borders = { preset: "all", style: "thin", color: "#D9E2F3" };

summary.getRange("A1:H18").format.font = { name: "Arial", size: 10, color: "#1F1F1F" };
log.getRange("A1:X206").format.font = { name: "Arial", size: 10, color: "#1F1F1F" };
lists.getRange("A1:C8").format.font = { name: "Arial", size: 10, color: "#1F1F1F" };
summary.getRange("A2").format.font = { name: "Arial", size: 16, bold: true, color: "#1F1F1F" };
log.getRange("A2").format.font = { name: "Arial", size: 15, bold: true, color: "#1F1F1F" };

for (const [sheet, widths] of [[summary, [15, 20, 32, 14, 18, 21, 14, 12]], [log, [13, 13, 26, 35, 15, 16, 20, 10, 12, 13, 15, 16, 18, 24, 14, 16, 16, 19, 18, 19, 16, 34, 34, 45]], [lists, [24, 58, 28]]]) {
  widths.forEach((width, index) => sheet.getCell(0, index).format.columnWidth = width);
}
summary.getRange("A2:H2").format.rowHeight = 28;
log.getRange("A2:X2").format.rowHeight = 26;
log.getRange("A6:X6").format.rowHeight = 38;
summary.getRange("A5:G5").format.font = { name: "Arial", size: 10, bold: true, color: "#FFFFFF" };
log.getRange("A6:X6").format.font = { name: "Arial", size: 10, bold: true, color: "#FFFFFF" };
lists.getRange("A1:C1").format.font = { name: "Arial", size: 10, bold: true, color: "#FFFFFF" };
workbook.recalculate();

await fs.mkdir(outputDir, { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath.pathname);
console.log(outputPath.pathname);
