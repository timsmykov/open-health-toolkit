from datetime import date
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from health_toolkit import catalog, diary, documents, nutrition, nutri_score, oura


def pdf_fixture(path):
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Resources << /Font << /F 7 0 R >> >> /Contents 4 0 R >>",
        b"BT /F 14 Tf 30 150 Td (Synthetic reference page) Tj ET 30 30 220 70 re S",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Contents 6 0 R >>",
        b"30 30 220 70 re S",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    result = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, content in enumerate(objects, 1):
        offsets.append(len(result))
        result.extend(f"{index} 0 obj\n".encode())
        if index in (4, 6):
            result.extend(f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream")
        else:
            result.extend(content)
        result.extend(b"\nendobj\n")
    xref = len(result)
    result.extend(b"xref\n0 8\n0000000000 65535 f \n")
    for offset in offsets:
        result.extend(f"{offset:010d} 00000 n \n".encode())
    result.extend(f"trailer\n<< /Root 1 0 R /Size 8 >>\nstartxref\n{xref}\n%%EOF\n".encode())
    path.write_bytes(result)


class NutriScoreTest(unittest.TestCase):
    def test_official_updated_samples(self):
        samples = (
            ("general", "100g", [321, 17.1, 0, 0.025, 0.2, 1.9, 90], {}, 0, "A"),
            ("red_meat", "100g", [653, 0, 2.8, 0.1275, 23.2, 0, 0], {}, 1, "B"),
            ("cheese", "100g", [1523, 0.5, 19.8, 1.8, 24.1, 0, 0.1], {}, 15, "D"),
            ("fats_oils_nuts_seeds", "100g", [2513, 11.2, 6.4, 0, 17.2, 7.3, 0], {"fat_g": 49.7}, -6, "A"),
            ("beverage", "100ml", [29, 1.2, 0, 0.04, 0.1, 0, 0], {"non_nutritive_sweeteners": True}, 5, "C"),
        )
        keys = ("energy_kj", "total_sugars_g", "saturated_fat_g", "salt_g", "protein_g", "fiber_g",
                "fruit_vegetable_legume_percent")
        for category, basis, values, extras, points, grade in samples:
            with self.subTest(category=category):
                result = nutri_score.score(category, basis, dict(zip(keys, values)) | extras)
                self.assertEqual((result["score"], result["grade"]), (points, grade))
        self.assertEqual(nutri_score.score("water", "100ml", {})["grade"], "A")

    def test_missing_input_and_exact_boundaries(self):
        self.assertIn("fruit_vegetable_legume_percent", nutri_score.score("general", "100g", {})["missing"])
        label = {"energy_kj": 335, "total_sugars_g": 3.4, "saturated_fat_g": 1,
                 "sodium_mg": 80, "protein_g": 2.4, "fiber_g": 3, "fruit_vegetable_legume_percent": 40}
        self.assertEqual(nutri_score.score("general", "100g", label)["score"], 0)
        label["sodium_mg"] = 80.01
        self.assertEqual(nutri_score.score("general", "100g", label)["score"], 1)
        with self.assertRaises(ValueError):
            nutri_score.score("beverage", "100g", label)

    def test_catalog_uses_documented_same_basis(self):
        card = catalog.get("bls-G541100", {})[0]
        request = {"category": "general", "basis": "100g", "fruit_vegetable_legume_percent": 100}
        result = nutri_score.score_card(card, request, "Test case using a raw single ingredient")
        self.assertEqual(result["grade"], "A")
        self.assertNotIn("grade", request)
        with self.assertRaises(ValueError):
            nutri_score.score_card(card, request, "")
        wrong = {**card, "nutrients": {"salt_g": {"basis": "100g", "source": "label", "unit": "mg", "value": 100}}}
        with self.assertRaisesRegex(ValueError, "salt_g requires g"):
            nutri_score.score_card(wrong, request, "Test label")


class ToolkitTest(unittest.TestCase):
    def test_reference_portion_and_goal(self):
        rows = catalog.find("green sweet pepper", kind="ingredient")
        self.assertEqual(rows[0]["id"], "bls-G541100")
        item = {"food_id": rows[0]["id"], "grams": 50}
        result = catalog.calculate(item, {})
        self.assertGreater(result["nutrients"]["vitamin_c_mg"]["value"], 0)
        goal = {"id": "example", "method": "portion_targets_v1", "targets": {"added_sugars_g": {"max": 1}}}
        self.assertEqual(nutrition.assess_portion(result, goal)["results"]["added_sugars_g"]["status"], "unknown")

    def test_diary_snapshot_and_period(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "diary.sqlite"
            item = {"food_id": "bls-C133000", "grams": 60}
            day = date(2000, 1, 2)
            result = catalog.calculate(item, {})
            saved = diary.log(db, "fixture-id", day, item, result)
            self.assertEqual(diary.log(db, "fixture-id", day, item, result), saved)
            with self.assertRaises(ValueError):
                diary.log(db, "fixture-id", day, {**item, "grams": 20}, result)
            summary = diary.report(db, day, 28)
            self.assertEqual((summary["entries"], summary["days_without_entries"]), (1, 27))
            self.assertEqual(db.stat().st_mode & 0o777, 0o600)

    def test_oura_fetch_pagination_and_aggregation(self):
        def page(path, params, token):
            self.assertTrue(path.endswith("/heartrate"))
            if not params.get("next_token"):
                return {"data": [{"timestamp": "2000-01-01T01:05:00Z", "bpm": 60, "source": "awake"}],
                        "next_token": "fixture-page-2"}
            return {"data": [{"timestamp": "2000-01-01T01:11:00Z", "bpm": 64, "source": "awake"},
                             {"timestamp": "1999-12-31T23:55:00Z", "bpm": 80, "source": "awake"}]}

        result = oura.fetch("heartrate", date(2000, 1, 1), date(2000, 1, 2), "UTC", "fixture-token", page=page)
        self.assertEqual(result["out_of_window_records"], 1)
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["records"][0]["mean_bpm"], 62)
        self.assertNotIn("bpm", result["records"][0])

    def test_oura_report_coverage_and_long_sleep_selection(self):
        data = [{"collection": "sleep", "timezone": "UTC", "records": [
            {"id": "one", "day": "2000-01-02", "type": "long_sleep", "total_sleep_duration": 100},
            {"id": "two", "day": "2000-01-02", "type": "long_sleep", "total_sleep_duration": 200,
             "lowest_heart_rate": 45},
            {"id": "three", "day": "2000-01-02", "type": "late_nap", "total_sleep_duration": 500},
        ]}]
        metrics = oura.report(data, date(2000, 1, 2), 7)["metrics"]
        self.assertEqual(metrics["main_sleep_seconds"]["mean"], 200)
        self.assertEqual(metrics["main_sleep_low_bpm"]["mean"], 45)
        self.assertEqual(metrics["steps"]["days_with_values"], 0)

    @unittest.skipUnless(shutil.which("pdftotext") and shutil.which("pdftoppm"), "Poppler required")
    def test_document_bundle_preserves_images_and_page_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf = root / "fixture.pdf"
            pdf_fixture(pdf)
            bundle = root / "bundle"
            result = documents.extract(pdf, bundle)
            self.assertEqual([p["text_status"] for p in result["pages"]], ["embedded_text", "ocr_required"])
            output = documents.export_markdown(bundle, "Synthetic reference")
            self.assertEqual(len(output), 2)
            for entry in result["pages"]:
                self.assertTrue((bundle / entry["page_image"]).read_bytes().startswith(b"\x89PNG"))
            text = (bundle / "page-0001.md").read_text()
            self.assertIn("Synthetic reference page", text)
            self.assertIn("(page-0001.png)", text)
            layout = json.loads((bundle / "page-0001.json").read_text())
            self.assertEqual(len(layout["blocks"][0]["bbox"]), 4)


if __name__ == "__main__":
    unittest.main()
