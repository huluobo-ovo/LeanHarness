import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const workbookPath = new URL("../templates/role5-results-tracker.xlsx", import.meta.url).pathname;
const outputDir = "/private/tmp/role5-results-tracker-preview";
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(workbookPath));
await workbook.recalculate();

const summaryCheck = await workbook.inspect({
  kind: "table",
  range: "Summary!A5:G15",
  include: "values,formulas",
  tableMaxRows: 15,
  tableMaxCols: 8,
});
const errorScan = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 50 },
  summary: "formula error scan",
});
await fs.mkdir(outputDir, { recursive: true });
const preview = await workbook.render({ sheetName: "Summary", range: "A1:H15", scale: 2 });
await fs.writeFile(`${outputDir}/summary.png`, new Uint8Array(await preview.arrayBuffer()));
console.log(summaryCheck.ndjson);
console.log(errorScan.ndjson);
console.log(`${outputDir}/summary.png`);
