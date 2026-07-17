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

    def test_learning_modes_have_distinct_dashboard_actions(self):
        self.assertIn('id="modeInsights"', self.html)
        self.assertIn('id="examReviewSection"', self.html)
        self.assertIn("async function startModeFocus()", self.js)
        self.assertIn('state.learningMode === "interest"', self.js)
        self.assertIn('$("#examReviewSection").hidden = interest', self.js)
        self.assertIn('data-quiz-article="${article.id}"', self.js)

    def test_first_run_profile_and_quick_start_use_dialogs(self):
        self.assertIn('<dialog class="profile-dialog" id="profileEditor"', self.html)
        self.assertIn('id="openProfileDialogBtn"', self.html)
        self.assertIn('id="closeProfileDialogBtn"', self.html)
        self.assertIn('id="cancelProfileDialogBtn"', self.html)
        self.assertIn('<dialog class="assistant-dialog" id="assistantDialog"', self.html)
        self.assertIn('id="openAssistantBtn"', self.html)
        self.assertIn('data-assistant-mode="interest"', self.html)
        self.assertIn('data-assistant-mode="exam"', self.html)
        self.assertIn('if (!state.learnerProfile?.completed) openProfileDialog();', self.js)
        self.assertIn('const QUICK_START_SEEN_KEY = "lc-v2-quick-start-seen";', self.js)

    def test_user_center_exposes_user_controlled_settings(self):
        self.assertIn('data-view="profile"', self.html)
        self.assertIn('id="view-profile"', self.html)
        for element_id in (
            "userProfileStatus", "userProfileSummary", "userDomainList",
            "userCalibrationSummary", "userPreferenceSummary", "userPlanSummary",
            "userRecommendationStatus",
        ):
            self.assertIn(f'id="{element_id}"', self.html)
        self.assertIn("data-open-profile-dialog", self.html)
        self.assertIn("data-edit-plan", self.html)
        self.assertIn("function renderUserCenter()", self.js)
        self.assertIn('document.body.append(dialog)', self.js)
        self.assertIn('profile: ["用户中心"', self.js)

    def test_user_center_preserves_desktop_sidebar_and_responsive_content(self):
        self.assertIn(".user-center-layout", self.css)
        self.assertIn("grid-template-columns: minmax(0, 1.65fr) minmax(320px, 0.85fr)", self.css)
        responsive = self.css.split("@media (max-width: 980px)", 1)[1]
        self.assertIn(".user-center-layout", responsive)
        self.assertIn(".user-domain-list", responsive)

    def test_practice_controls_use_exam_specific_taxonomy(self):
        for element_id in ("quizSessionMode", "quizScope", "quizPracticeType"):
            self.assertIn(f'id="{element_id}"', self.html)
        for removed_id in ("quizPracticeMode", "quizMode", "examQuestionType", "loadQuizzesBtn"):
            self.assertNotIn(f'id="{removed_id}"', self.html)
            self.assertNotIn(f'$("#{removed_id}")', self.js)
        self.assertIn('async function applyQuizControlChange()', self.js)
        self.assertIn('$("#quizPracticeType").addEventListener("change", applyQuizControlChange);', self.js)
        self.assertIn('await applyQuizControlChange();', self.js)
        self.assertIn('const mode = "mixed";', self.js)
        self.assertIn('async function generatePassagePractice(', self.js)
        self.assertIn('$("#quizScope").value = "passage";', self.js)

    def test_scope_switch_replaces_question_type_with_paper_selector(self):
        self.assertIn('$("#quizPracticeType").hidden = isFull || scope === "passage";', self.js)
        self.assertIn('$("#quizPaperSelect").hidden = !isFull;', self.js)
        self.assertIn('state.quizzes = state.selectedPaper ? flattenPaperQuizzes(state.selectedPaper) : [];', self.js)

    def test_dictionary_places_chinese_before_examples_and_labels_sources(self):
        self.assertIn("function contextExamples(contexts)", self.js)
        self.assertIn('class="sense-meaning"', self.js)
        self.assertIn('class="sense-examples"', self.js)
        self.assertIn("搭配（按个人语料排序）", self.js)
        self.assertIn("机器翻译不冒充出版词典释义", self.js)
        self.assertIn("item.contexts = (item.contexts || []).map", self.js)


if __name__ == "__main__":
    unittest.main()
