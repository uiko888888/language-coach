from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ProfileUiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
        cls.css = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")
        cls.js = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    def test_three_profile_entry_paths_are_present(self):
        for source in ("score", "quick_test", "self_assessment"):
            self.assertIn(f'data-profile-source="{source}"', self.html)
            self.assertIn(f'data-profile-panel="{source}"', self.html)

    def test_profile_has_targets_weaknesses_interests_and_quick_test(self):
        for element_id in (
            "profileSummary", "profileTargetExam", "profileTargetScore", "profileTargetDate",
            "quickTestItems", "loadQuickTestBtn", "submitQuickTestBtn", "saveLearnerProfileBtn",
        ):
            self.assertIn(f'id="{element_id}"', self.html)
        self.assertIn("data-profile-weak", self.html)
        self.assertIn("data-profile-interest", self.html)
        self.assertIn("data-profile-content", self.html)
        self.assertIn('api("/api/learner-profile"', self.js)
        self.assertIn('api("/api/profile/quick-test"', self.js)

    def test_profile_layout_collapses_to_one_column(self):
        self.assertIn("@media (max-width: 980px)", self.css)
        responsive = self.css.split("@media (max-width: 980px)", 1)[1]
        self.assertIn(".profile-summary", responsive)
        self.assertIn(".profile-grid", responsive)
        self.assertIn("grid-template-columns: 1fr", responsive)

    def test_sidebar_and_master_detail_never_switch_to_top_bottom_layout(self):
        mobile = self.css.split("@media (max-width: 720px)", 1)[1]
        self.assertIn(".sidebar", mobile)
        self.assertIn("position: fixed", mobile)
        self.assertIn(".app { margin-left: 92px", mobile)
        self.assertIn(".master-detail", mobile)
        self.assertIn("grid-template-columns: minmax(108px, 34vw) minmax(280px, 1fr)", mobile)
        self.assertNotIn(".app { margin-left: 0", mobile)
        self.assertNotIn(".sidebar {\n    position: static", mobile)


if __name__ == "__main__":
    unittest.main()
