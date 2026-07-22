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

    def test_private_dictionary_manager_supports_stardict_and_local_controls(self):
        for element_id in (
            "privateDictionaryList", "stardictImportForm", "stardictPath", "stardictName",
            "stardictKind", "stardictPriority", "importStardictBtn", "privateDictionaryStatus",
        ):
            self.assertIn(f'id="{element_id}"', self.html)
        self.assertIn('api("/api/private-dictionaries/stardict"', self.js)
        self.assertIn("data-private-toggle", self.js)
        self.assertIn("data-private-remove", self.js)
        self.assertIn("X-Language-Coach-Token", self.js)

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
        self.assertIn("我的语料搭配", self.js)
        self.assertIn("按你的文章、生词上下文和插件摘录中的实际出现次数排序", self.js)
        self.assertIn("机器翻译不冒充出版词典释义", self.js)
        self.assertIn("item.contexts = (item.contexts || []).map", self.js)

    def test_dictionary_separates_general_personal_and_unverified_phrases(self):
        for label in ("通用常见搭配", "我的语料搭配", "开放词典短语"):
            self.assertIn(label, self.js)
        self.assertIn("function commonCollocations(item)", self.js)
        self.assertIn("Tatoeba 开放例句和公开文章语料", self.js)
        self.assertIn("data-save-sense=", self.js)
        self.assertIn("function lexicalCardMetadata(item, sense", self.js)
        for field in ("sense_key", "meaning_zh", "concept_en", "grammar_frame", "confusion_note"):
            self.assertIn(field, self.js)

    def test_dictionary_query_workflow_has_correction_history_and_reference_actions(self):
        for element_id in ("lexiconGuidance", "lexiconHistory", "clearLexiconHistoryBtn"):
            self.assertIn(element_id, self.html + self.js)
        for contract in (
            'api("/api/lexicon/history")', "data-copy-lexical", "data-jump-lexical-section",
            "oxfordlearnersdictionaries.com", "dictionary.cambridge.org", "ldoceonline.com",
            "collinsdictionary.com", "merriam-webster.com",
        ):
            self.assertIn(contract, self.js)
        self.assertIn(".dictionary-section-nav", self.css)
        self.assertIn(".external-dictionaries", self.css)

    def test_dictionary_multiword_compare_keeps_reviewed_boundaries_distinct_from_open_evidence(self):
        self.assertIn('data-search-query="cordial, keen, zeal"', self.html)
        self.assertIn('data-search-query="say, tell, speak, talk"', self.html)
        self.assertIn('data-search-query="effective, efficient"', self.html)
        self.assertIn('id="lexicalComparisonCatalog"', self.html)
        self.assertIn('api("/api/lexicon/comparisons")', self.js)
        self.assertIn("function renderLexicalComparisonCatalog()", self.js)
        self.assertIn('api(`/api/lexicon/compare?', self.js)
        self.assertIn("function renderLexicalComparison(comparison)", self.js)
        self.assertIn('comparison.mode === "candidate" ? "候选组 · 待核对"', self.js)
        self.assertIn('group.reviewed ? " · 已审核" : " · 待核对"', self.js)
        self.assertIn("不要这样理解", self.js)
        for selector in (".comparison-grid", ".comparison-term-card", ".comparison-dimensions", ".comparison-memory-rule"):
            self.assertIn(selector, self.css)

    def test_single_dictionary_entry_starts_with_an_english_first_learning_summary(self):
        for contract in (
            "function lexicalLearningSummary(item", "function reliableCollocations(items)",
            "function personalCollocations(items)", "function lexicalSenseOutline(item",
            "function comparisonCandidateButtons(baseTerm, terms)", "英文语义焦点",
            "人工整理基础组", "另有其他义项", "与易混词一起比较",
        ):
            self.assertIn(contract, self.js)
        self.assertIn("phraseCards(observedCollocations)", self.js)
        for selector in (".lexical-learning-summary", ".lexical-sense-outline", ".learning-concept-en", ".learning-summary-grid", ".comparison-candidate-list"):
            self.assertIn(selector, self.css)

    def test_content_center_uses_hubs_without_expanding_sidebar_sources(self):
        self.assertIn('id="articleHubFilter"', self.html)
        self.assertIn('api("/api/content-hubs")', self.js)
        self.assertIn('catch (_error)', self.js)
        self.assertIn('<option value="subscribed">我的订阅</option>', self.js)
        self.assertIn("data-subscribe-category", self.js)
        self.assertIn("source.transcript_available", self.js)
        self.assertNotIn('data-view="Reuters"', self.html)
        self.assertNotIn('data-view="The Economist"', self.html)

    def test_runtime_compatibility_and_backup_controls_are_visible(self):
        for element_id in (
            "compatibilityBanner", "compatibilityMessage", "runtimeVersion",
            "createBackupBtn", "backupSelect", "restoreBackupBtn", "backupStatus",
        ):
            self.assertIn(f'id="{element_id}"', self.html)
        self.assertIn('const FRONTEND_APP_VERSION = "0.8.0-alpha.25.13";', self.js)
        self.assertIn('const SUPPORTED_SCHEMA_VERSION = "23";', self.js)
        self.assertIn('const schemaCompatible =', self.js)
        self.assertIn('api("/api/backups"', self.js)
        self.assertIn(".compatibility-banner", self.css)

    def test_review_workspace_is_a_split_recall_rating_loop(self):
        for element_id in (
            "reviewKindFilter", "reviewSummary", "reviewDueCount", "reviewQueue",
            "reviewDetail", "undoReviewBtn", "revealReviewAnswerBtn",
        ):
            self.assertIn(element_id, self.html + self.js)
        for contract in (
            'api(`/api/reviews?kind=', "data-select-review", "data-rate-review",
            'api("/api/reviews/undo"', "function renderReviews()", "reviewAnswerRevealed",
        ):
            self.assertIn(contract, self.js)
        for selector in (".review-workspace", ".review-rating-grid", ".review-kind-filter"):
            self.assertIn(selector, self.css)

    def test_comparison_review_manager_exposes_fail_closed_workflow(self):
        for element_id in (
            "comparisonReviewSummary", "comparisonReviewStatusFilter",
            "comparisonReviewExamFilter", "comparisonReviewList", "refreshComparisonReviewsBtn",
        ):
            self.assertIn(f'id="{element_id}"', self.html)
        for contract in (
            'api(`/api/lexicon/comparison-reviews?', "function renderComparisonReviews()",
            "data-save-comparison-review", "候选组 · 待核对",
        ):
            self.assertIn(contract, self.js)
        for selector in (".comparison-review-manager", ".comparison-review-row", ".comparison-review-summary"):
            self.assertIn(selector, self.css)

    def test_complete_word_review_is_a_dedicated_attempt_and_fsrs_loop(self):
        for element_id in (
            "memoryReviewPane", "completeWordReviewPane", "completeWordSearch",
            "completeWordQueue", "completeWordDetail", "completeWordUndoBtn",
        ):
            self.assertIn(f'id="{element_id}"', self.html)
        for contract in (
            'data-review-mode="complete-words"', "data-complete-word-scope",
            'api(`/api/complete-word-reviews?', "submitCompleteWordReview",
            'kind: "complete-word"', "canUndoCompleteWord", "data-rate-complete-word",
        ):
            self.assertIn(contract, self.html + self.js)
        for selector in (".complete-word-workspace", ".complete-word-card", ".complete-word-result"):
            self.assertIn(selector, self.css)

    def test_comparison_training_is_a_split_attempt_feedback_fsrs_loop(self):
        for element_id in (
            "comparisonTrainingPane", "comparisonTrainingTopic", "comparisonTrainingType",
            "comparisonTrainingSummary", "comparisonTrainingQueue", "comparisonTrainingDetail",
        ):
            self.assertIn(f'id="{element_id}"', self.html)
        for contract in (
            'data-review-mode="comparison"', 'api(`/api/lexicon/comparison-training?',
            'api("/api/lexicon/comparison-training/answer"', "submitComparisonTraining",
            'state.reviewKind = "comparison"', "comparisonTrainingHintUsed",
        ):
            self.assertIn(contract, self.html + self.js)
        for selector in (
            ".comparison-training-workspace", ".comparison-training-options",
            ".comparison-training-result", ".comparison-training-hint",
        ):
            self.assertIn(selector, self.css)

    def test_output_workspace_is_a_split_source_attempt_review_loop(self):
        for element_id in (
            "view-output", "outputSourceTitle", "outputSourceText", "outputTaskTabs",
            "outputTaskBody", "outputHistoryList", "startOutputBtn", "markArticleReadBtn",
            "dailyMetricProgress",
        ):
            self.assertIn(f'id="{element_id}"', self.html)
        for contract in (
            'data-view="output"', "function renderOutput()", "async function startOutputTraining(",
            'api("/api/output-attempts"', "data-save-output-self-review", "data-save-output-review",
            "daily_metric_targets:", "data-request-semantic-feedback", "data-output-feedback-decision",
            "data-save-output-custom-review", "data-contrast-answer", 'api("/api/output/feedback/status")',
            'api("/api/output/contrasts")',
        ):
            self.assertIn(contract, self.html + self.js)
        for selector in (".semantic-feedback-panel", ".custom-review-panel", ".usage-contrast-panel"):
            self.assertIn(selector, self.css)
        self.assertIn("grid-template-columns: minmax(330px, 0.9fr) minmax(520px, 1.25fr)", self.css)
        responsive = self.css.split("@media (max-width: 980px)", 1)[1]
        self.assertNotIn(".output-workspace", responsive.split("@media (max-width: 720px)", 1)[0])

    def test_speaking_workspace_is_a_private_split_record_review_loop(self):
        for element_id in (
            "view-speaking", "speakingSourceTitle", "speakingTaskList", "speakingSourceText",
            "speakingTaskDetail", "speakingRecorder", "speakingAttemptDetail", "speakingHistoryList",
        ):
            self.assertIn(f'id="{element_id}"', self.html)
        for contract in (
            'data-view="speaking"', "function renderSpeaking()", "async function startSpeakingTraining(",
            "navigator.mediaDevices.getUserMedia", "new MediaRecorder(", "data-pause-speaking",
            "data-stop-speaking", "data-save-speaking", "data-transcribe-speaking",
            "data-save-speaking-review", "data-save-speaking-stuck", "data-delete-speaking",
            "data-repeat-speaking", 'api("/api/speaking/transcription/status")',
            'api(`/api/speaking-attempts/${attemptId}/transcript`',
        ):
            self.assertIn(contract, self.html + self.js)
        self.assertIn("grid-template-columns: minmax(330px, 0.9fr) minmax(520px, 1.25fr)", self.css)
        responsive = self.css.split("@media (max-width: 980px)", 1)[1]
        self.assertNotIn(".speaking-workspace", responsive.split("@media (max-width: 720px)", 1)[0])
        self.assertIn('window.addEventListener("pagehide"', self.js)
        self.assertIn("releaseSpeakingStream();", self.js)

    def test_training_loop_exposes_deep_explanations_metrics_and_mastery(self):
        for contract in (
            'class="option-analysis"', 'class="location-signals"',
            'data-toggle-quiz-hint=', 'class="mastery-progress"',
            'data-next-set-type-only=', 'answer_changes:', 'hint_used:',
        ):
            self.assertIn(contract, self.js)
        for selector in (".option-analysis", ".location-signals", ".mastery-progress", ".quiz-hint-row"):
            self.assertIn(selector, self.css)

    def test_practice_translation_fetches_missing_translation_instead_of_showing_empty_rows(self):
        self.assertIn('async function toggleArticleTranslation()', self.js)
        self.assertIn('!article.translation_aligned', self.js)
        self.assertIn('await translateArticle(article.id)', self.js)
        self.assertIn('article?.translation_aligned ? "显示译文" : "一键翻译"', self.js)

    def test_reader_supports_direct_dictionary_lookup_and_paragraph_translation(self):
        self.assertIn('data-translate-paragraph=', self.js)
        self.assertIn('async function translateArticleParagraph(', self.js)
        self.assertIn('/paragraphs/${paragraphIndex}/translate', self.js)
        self.assertIn('searchLexicon(selected).catch', self.js)
        self.assertNotIn('if (word) renderLookup(word.dataset.word)', self.js)
        self.assertIn('双击文章中的单词进入完整词典', self.html)
        self.assertIn('.paragraph-translate-button', self.css)

    def test_article_training_actions_respect_server_quality_gate(self):
        self.assertIn("function articleTrainingAction(article", self.js)
        self.assertIn("article.training_eligible", self.js)
        self.assertIn("摘要不可出题", self.js)
        self.assertIn("这是来源摘要，不是原文", self.js)
        self.assertIn('$("#generateQuizBtn").disabled = !article.training_eligible', self.js)

    def test_reader_keeps_source_metadata_outside_article_body_and_collects_feedback(self):
        for contract in (
            "function sourceMetadataHtml(article)", "图片说明", "披露声明",
            'data-extraction-feedback="correct"', "/extraction-feedback",
            "saveExtractionFeedback", 'api("/api/extraction/quality")',
            "分类器数据", "人工校验",
        ):
            self.assertIn(contract, self.js)
        self.assertIn(".source-metadata", self.css)

    def test_extraction_annotation_workspace_is_split_and_persists_real_block_labels(self):
        for element_id in (
            "extractionLabelDialog", "extractionLabelMeta", "extractionLabelProgress",
            "extractionBlockList", "extractionBlockDetail", "extractionUsableCount",
            "previousExtractionBlockBtn", "nextExtractionBlockBtn", "extractionBatchSelect",
            "extractionBatchAnalytics", "nextExtractionArticleBtn",
        ):
            self.assertIn(f'id="{element_id}"', self.html)
        for contract in (
            "data-open-extraction-labeler", "function renderExtractionLabeler()",
            "async function openExtractionLabeler(", "async function saveExtractionBlockLabel(",
            "/extraction-blocks", "/extraction-block-labels", "data-save-extraction-label",
            "data-open-extraction-batch", "async function openExtractionReviewBatch()",
            "async function recordExtractionActivity()", "/api/extraction/review-batches",
            "/activity", "async function nextExtractionReviewArticle()",
        ):
            self.assertIn(contract, self.js)
        self.assertIn(".extraction-label-workspace", self.css)
        self.assertIn("grid-template-columns: 290px minmax(0, 1fr)", self.css)

    def test_server_practice_state_and_prescription_are_user_controlled(self):
        for element_id in (
            "resumePracticeBand", "resumePracticeTitle", "resumePracticeSummary",
            "resumePracticeBtn", "abandonPracticeBtn", "prescriptionBand",
            "prescriptionStatus", "prescriptionBody",
        ):
            self.assertIn(f'id="{element_id}"', self.html)
        for contract in (
            'api("/api/practice-runs/active")', 'api("/api/practice-runs"',
            'api(`/api/practice/prescription?style=', "function practiceRunSnapshot()",
            "async function restoreServerPracticeRun()", "function prescriptionHtml(",
            'state.learnerSettings.recommendations_enabled === false',
            '$("#prescriptionBand").hidden = interest',
        ):
            self.assertIn(contract, self.js)
        self.assertIn(".resume-practice-band", self.css)
        self.assertIn(".prescription-metrics", self.css)

    def test_article_pool_preserves_split_default_and_adds_personalized_grid(self):
        for element_id in (
            "articlePoolLayout", "articleCountAll", "articleCountPublic", "articleCountPrivate",
        ):
            self.assertIn(f'id="{element_id}"', self.html)
        for contract in (
            'data-article-layout="split"', 'data-article-layout="grid"',
            'data-article-visibility="private"', 'function articleGridCard(article)',
            'api("/api/article-preferences"', 'article_layout: "split"',
        ):
            self.assertIn(contract, self.html + self.js)
        self.assertIn(".master-detail.article-layout-grid", self.css)
        self.assertIn("grid-template-columns: clamp(260px, 26vw, 320px) minmax(0, 1fr)", self.css)

    def test_dictionary_exposes_frequency_attribution_and_layer_status(self):
        self.assertIn('id="lexicalDataStatus"', self.html)
        for contract in (
            'api("/api/dictionary/status")', "function lexicalFrequencyPanel(item)",
            "function openExampleCards(examples, item)", "通用常用度", "你的内容池",
            "数据来源与许可证", 'item.type === "open"',
        ):
            self.assertIn(contract, self.html + self.js)
        for selector in (".lexical-frequency-panel", ".lexical-source-disclosure", ".lexical-layer-row", ".lexical-quality-row"):
            self.assertIn(selector, self.css)
        self.assertIn('quality.ready ? "已验证"', self.js)


if __name__ == "__main__":
    unittest.main()
