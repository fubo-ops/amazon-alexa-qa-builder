#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { SpreadsheetFile, Workbook } = require("@oai/artifact-tool");
const HEADERS = [
  "序号", "优先级", "Alexa问题_EN", "Alexa问题_CN", "标准答案_EN", "标准答案_CN",
  "意图分类", "核心关键词", "关键词来源", "卖家精灵指标", "Listing覆盖状态",
  "目标ASIN评论证据数", "竞品评论证据数", "评论证据摘要", "证据ASIN",
  "数据冲突或缺口", "置信度", "建议动作",
];

if (process.argv.length !== 4) throw new Error("usage: build_clean_workbook.mjs PAYLOAD.json OUTPUT.xlsx");
const [inputPath, outputPath] = process.argv.slice(2);
const payload = JSON.parse(await fs.readFile(inputPath, "utf8"));
if (!payload.rows?.length) throw new Error("payload.rows must be non-empty");

const workbook = Workbook.create();
const sheet = workbook.worksheets.add("Alexa Q&A");
sheet.showGridLines = false;
sheet.freezePanes.freezeRows(1);
const endRow = payload.rows.length + 1;
sheet.getRange("A1:R1").values = [HEADERS];
sheet.getRange(`A2:R${endRow}`).values = payload.rows.map((row) => HEADERS.map((header) => row[header] ?? ""));
sheet.getRange(`A1:R${endRow}`).format = { font: { name: "Arial", size: 9 }, verticalAlignment: "top", wrapText: true };
sheet.getRange("A1:R1").format = { fill: "#1F4E78", font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", verticalAlignment: "center", wrapText: true };
sheet.getRange("A1:R1").format.rowHeight = 34;
const widths = [8, 9, 38, 32, 44, 40, 18, 34, 16, 38, 16, 14, 14, 48, 26, 28, 10, 16];
widths.forEach((width, column) => { sheet.getRangeByIndexes(0, column, endRow, 1).format.columnWidth = width; });
for (const [text, fill, color] of [["P0", "#FECACA", "#991B1B"], ["P1", "#FEF3C7", "#92400E"], ["P2", "#DBEAFE", "#1E40AF"]]) {
  sheet.getRange(`B2:B${endRow}`).conditionalFormats.add("containsText", { text, format: { fill, font: { bold: true, color } } });
}
for (const column of ["E", "F", "N", "P"]) {
  sheet.getRange(`${column}2:${column}${endRow}`).conditionalFormats.add("containsText", { text: column === "N" ? "0条评论证据" : "未验证", format: { fill: "#FFEDD5", font: { bold: true, color: "#9A3412" } } });
}
const table = sheet.tables.add(`A1:R${endRow}`, true, "AlexaQATable");
table.style = "TableStyleMedium2";
table.showFilterButton = true;
await fs.mkdir(path.dirname(path.resolve(outputPath)), { recursive: true });
workbook.inspect = async () => ({ ndjson: "" });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(path.resolve(outputPath));
await fs.rm(`${path.resolve(outputPath)}.inspect.ndjson`, { force: true });
console.log(JSON.stringify({ output: path.resolve(outputPath), sheet: "Alexa Q&A", rows: payload.rows.length }));
