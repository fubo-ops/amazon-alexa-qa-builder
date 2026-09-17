#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { SpreadsheetFile, Workbook } = require("@oai/artifact-tool");

const HEADERS = [
  "记录ID", "目标ASIN", "Amazon站点", "问题候选_EN", "问题候选_CN",
  "答案候选_EN", "答案候选_CN", "原始关键词", "关键词来源", "来源查询词",
  "意图初始标签", "卖家精灵指标", "来源ASIN", "来源类型", "评论ID",
  "评论证据摘录", "证据归属", "Listing事实依据", "数据冲突或缺口", "采集状态",
];

if (process.argv.length !== 4) {
  throw new Error("usage: build_workbook.mjs PAYLOAD.json OUTPUT.xlsx");
}

const [inputPath, outputPath] = process.argv.slice(2);
const payload = JSON.parse(await fs.readFile(inputPath, "utf8"));
if (!Array.isArray(payload.rows) || payload.rows.length === 0) {
  throw new Error("payload.rows must be a non-empty array");
}

const workbook = Workbook.create();
const sheet = workbook.worksheets.add("Q&A Raw Data");
sheet.showGridLines = false;
sheet.freezePanes.freezeRows(1);

const endRow = payload.rows.length + 1;
sheet.getRange("A1:T1").values = [HEADERS];
const WRITE_BATCH_SIZE = 1000;
for (let offset = 0; offset < payload.rows.length; offset += WRITE_BATCH_SIZE) {
  const rows = payload.rows.slice(offset, offset + WRITE_BATCH_SIZE);
  const values = rows.map((row) => HEADERS.map((column) => String(row[column] ?? "")));
  sheet.getRangeByIndexes(offset + 1, 0, values.length, HEADERS.length).values = values;
}
const header = sheet.getRange("A1:T1");
header.format = {
  fill: "#1F4E78",
  font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
  borders: { preset: "inside", style: "thin", color: "#FFFFFF" },
};
header.format.rowHeight = 34;

if (endRow > 1) {
  const gaps = sheet.getRange(`S2:S${endRow}`);
  gaps.conditionalFormats.add("containsText", { text: "资料冲突", format: { fill: "#FECACA", font: { bold: true, color: "#991B1B" } } });
  gaps.conditionalFormats.add("containsText", { text: "未验证", format: { fill: "#FEF3C7", font: { color: "#92400E" } } });

  sheet.getRange(`P2:P${endRow}`).conditionalFormats.add("containsText", {
    text: "0条评论证据",
    format: { fill: "#FFEDD5", font: { bold: true, color: "#9A3412" } },
  });
  sheet.getRange(`T2:T${endRow}`).conditionalFormats.add("containsText", {
    text: "0条评论证据",
    format: { fill: "#FFEDD5", font: { bold: true, color: "#9A3412" } },
  });
  sheet.getRange(`F2:F${endRow}`).conditionalFormats.add("containsText", {
    text: "Not verified",
    format: { fill: "#FEF3C7", font: { bold: true, color: "#92400E" } },
  });
  sheet.getRange(`G2:G${endRow}`).conditionalFormats.add("containsText", {
    text: "未验证",
    format: { fill: "#FEF3C7", font: { bold: true, color: "#92400E" } },
  });
}

const widths = [25, 14, 12, 36, 30, 44, 40, 28, 18, 28, 18, 28, 14, 16, 18, 46, 16, 42, 36, 24];
for (let col = 0; col < widths.length; col += 1) {
  sheet.getRangeByIndexes(0, col, 1, 1).format.columnWidth = widths[col];
}

const table = sheet.tables.add(`A1:T${endRow}`, true, "QARawDataTable");
table.style = "TableStyleMedium2";
table.showFilterButton = true;

await fs.mkdir(path.dirname(path.resolve(outputPath)), { recursive: true });
workbook.inspect = async () => ({ ndjson: "" });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(path.resolve(outputPath));
await fs.rm(`${path.resolve(outputPath)}.inspect.ndjson`, { force: true });
console.log(JSON.stringify({
  output: path.resolve(outputPath),
  sheet: "Q&A Raw Data",
  rows: payload.rows.length,
  candidates: new Set(payload.rows.map((row) => row.candidate_id)).size,
}));
