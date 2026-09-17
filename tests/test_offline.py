from __future__ import annotations

import copy
import json
import os
import re
import sys
import unittest
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"
sys.path.insert(0, str(ROOT / "scripts"))

import assemble_raw_payload as assembler
import clean_payload as cleaner
import collect_targeted_reviews as collector
import validate_clean_payload as clean_validator
import validate_payload as raw_validator


def read(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8-sig"))


class RawStageTests(unittest.TestCase):
    def setUp(self):
        self.candidates = read("candidates.json")
        self.reviews = read("review_evidence.json")

    def test_raw_payload_is_valid(self):
        payload = assembler.assemble("B0TEST0001", "US", self.candidates, self.reviews)
        self.assertEqual(raw_validator.validate_payload(payload), [])

    def test_duplicate_questions_and_sources_are_preserved(self):
        rows = assembler.assemble("B0TEST0001", "US", self.candidates, self.reviews)["rows"]
        matching = [row for row in rows if row["问题候选_EN"] == "Does it stay in place on tile floors?"]
        self.assertEqual({row["candidate_id"] for row in matching}, {"AUTO-001", "AUTO-002"})
        self.assertEqual(len({row["记录ID"] for row in rows}), len(rows))

    def test_zero_review_queries_are_retained(self):
        rows = assembler.assemble("B0TEST0001", "US", self.candidates, self.reviews)["rows"]
        self.assertTrue(any(row["评论证据摘录"] == "0条评论证据" for row in rows))

    def test_review_mapping_must_match_id_asin_and_query(self):
        payload = read("valid_payload.json")
        row = next(row for row in payload["rows"] if row["来源类型"] == "目标评论")
        row["review_mapping"]["source_asin"] = "B0COMP0001"
        self.assertTrue(any("review_mapping" in error for error in raw_validator.validate_payload(payload)))

    def test_network_query_dedup_keeps_all_candidate_ids(self):
        queries, mapping = collector.load_questions(FIXTURES / "candidates.json")
        self.assertIn("tile floor", queries)
        self.assertEqual(mapping["tile floor"], ["AUTO-001", "AUTO-002"])


class CleanStageTests(unittest.TestCase):
    def setUp(self):
        self.raw35 = read("clean_35_questions.json")

    def test_35_distinct_questions_produce_more_than_20(self):
        result = cleaner.clean_payload(self.raw35)
        self.assertEqual(len(result["rows"]), 35)
        self.assertGreater(len(result["rows"]), 20)

    def test_default_max_clean_questions_is_unlimited(self):
        result = cleaner.clean_payload(self.raw35)
        self.assertEqual(result["max_clean_questions"], "unlimited")
        self.assertEqual(len(result["rows"]), 35)
        self.assertEqual(len(cleaner.clean_payload(self.raw35, 20)["rows"]), 20)

    def test_distinct_decisions_in_same_intent_are_not_merged(self):
        keys = {row["semantic_key"] for row in cleaner.clean_payload(self.raw35)["rows"]}
        self.assertTrue({"sensitive-skin", "fragrance-free", "lick-safety", "antibacterial"} <= keys)

    def test_true_duplicate_sources_are_merged_only_in_clean(self):
        self.assertEqual(sum(row["semantic_key"] == "sensitive-skin" for row in self.raw35["rows"]), 2)
        result = cleaner.clean_payload(self.raw35)
        self.assertEqual(sum(row["semantic_key"] == "sensitive-skin" for row in result["rows"]), 1)

    def test_pollution_and_garbled_rows_are_removed(self):
        raw = copy.deepcopy(self.raw35)
        bad = copy.deepcopy(raw["rows"][0])
        bad.update({"记录ID": "RAW-BAD", "candidate_id": "BAD", "semantic_key": "bad", "relevance_status": "brand_pollution"})
        raw["rows"].append(bad)
        self.assertEqual(len(cleaner.clean_payload(raw)["rows"]), 35)

    def test_affirmative_answer_requires_target_evidence(self):
        result = cleaner.clean_payload(read("valid_payload.json"))
        self.assertEqual(clean_validator.validate(result), [])
        positive = next(row for row in result["rows"] if row["标准答案_EN"] != cleaner.FALLBACK_EN)
        positive["answer_evidence"] = []
        self.assertTrue(any("target evidence" in error for error in clean_validator.validate(result)))

    def test_competitor_review_cannot_prove_target_feature(self):
        raw = read("valid_payload.json")
        competitor = copy.deepcopy(next(row for row in raw["rows"] if row["来源类型"] == "竞品评论"))
        competitor["semantic_key"] = "competitor-only"
        competitor["answer_evidence"] = [{"kind": "competitor_review", "source_asin": "B0COMP0001", "value": "Concern only"}]
        result = cleaner.clean_payload({**raw, "rows": [competitor]})
        self.assertEqual(result["rows"][0]["标准答案_EN"], cleaner.FALLBACK_EN)

    def test_other_target_asin_is_rejected(self):
        raw = copy.deepcopy(self.raw35)
        raw["rows"][0]["目标ASIN"] = "B0OLD00001"
        with self.assertRaisesRegex(ValueError, "another target ASIN"):
            cleaner.clean_payload(raw)


class WorkbookAndBatchTests(unittest.TestCase):
    def test_two_asins_create_four_single_sheet_workbooks(self):
        output_value = os.environ.get("ALEXA_QA_BATCH_OUTPUT")
        if not output_value:
            self.skipTest("ALEXA_QA_BATCH_OUTPUT not set")
        output = Path(output_value)
        files = sorted(output.glob("*.xlsx"))
        self.assertEqual(len(files), 4)
        self.assertEqual({path.name for path in files}, {
            "B0TEST0001_QA_Raw.xlsx", "B0TEST0001_QA_Clean.xlsx",
            "B0TEST0002_QA_Raw.xlsx", "B0TEST0002_QA_Clean.xlsx",
        })
        for path in files:
            with zipfile.ZipFile(path) as archive:
                workbook = ET.fromstring(archive.read("xl/workbook.xml"))
                sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
                table = ET.fromstring(archive.read("xl/tables/table1.xml"))
            sheets = [node for node in workbook.iter() if node.tag.endswith("sheet")]
            self.assertEqual(len(sheets), 1)
            self.assertEqual(sheets[0].attrib["name"], "Alexa Q&A" if "Clean" in path.name else "Q&A Raw Data")
            self.assertTrue(any(node.attrib.get("state") == "frozen" for node in sheet.iter()))
            self.assertTrue(any(node.tag.endswith("autoFilter") for node in table.iter()))

    def test_production_files_contain_no_historical_asin(self):
        known = {"B0GX1H74RX", "B0BSFPKNH6", "B0C811NJ98"}
        for folder in [ROOT / "scripts", ROOT / "references"]:
            for path in folder.rglob("*"):
                if path.is_file() and path.suffix in {".py", ".mjs", ".md"}:
                    found = set(re.findall(r"B0[A-Z0-9]{8}", path.read_text(encoding="utf-8")))
                    self.assertFalse(known & found, path)


if __name__ == "__main__":
    unittest.main()
