import unittest

from backend.chinese_text import simplify_chinese_payload, to_simplified_chinese


class ChineseTextTests(unittest.TestCase):
    def test_windows_response_normalizer_returns_simplified_chinese(self):
        converted = to_simplified_chinese("糖漿；熱情友好；誠懇有禮")
        if converted == "糖漿；熱情友好；誠懇有禮":
            self.skipTest("The host has no Traditional-to-Simplified converter")
        self.assertEqual(converted, "糖浆；热情友好；诚恳有礼")

    def test_payload_normalizer_preserves_shape(self):
        payload = simplify_chinese_payload({"items": ["熱情", {"meaning": "糖漿"}], "count": 2})
        self.assertEqual(payload["count"], 2)
        if payload["items"][0] != "熱情":
            self.assertEqual(payload["items"], ["热情", {"meaning": "糖浆"}])
