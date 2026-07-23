import unittest

from backend.academic_phrase_training import evaluate, find_training_item, training_items


class AcademicPhraseTrainingTests(unittest.TestCase):
    def test_three_task_types_are_derived_without_leaking_answers(self):
        items = training_items("provide evidence for", limit=1)
        self.assertEqual([item["task_type"] for item in items], ["cloze", "zh_to_en", "personal"])
        self.assertNotIn("provide evidence for", items[0]["prompt"].casefold())
        self.assertEqual(find_training_item(items[1]["task_id"])["term"], "provide evidence for")

    def test_cloze_and_translation_require_the_complete_phrase(self):
        item = training_items("provide evidence for", task_type="cloze", limit=1)[0]
        self.assertTrue(evaluate(item, "provide evidence for")["correct"])
        self.assertFalse(evaluate(item, "provide evidence")["correct"])
        item = training_items("provide evidence for", task_type="zh_to_en", limit=1)[0]
        self.assertTrue(evaluate(item, "provide evidence for")["correct"])

    def test_personal_task_requires_phrase_and_complete_sentence(self):
        item = training_items("provide evidence for", task_type="personal", limit=1)[0]
        self.assertTrue(evaluate(item, "My study can provide evidence for a useful connection.")["correct"])
        self.assertFalse(evaluate(item, "provide evidence for")["correct"])


if __name__ == "__main__":
    unittest.main()
