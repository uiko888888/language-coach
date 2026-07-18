const api = async (path, options = {}) => {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
};

const FRONTEND_APP_VERSION = "0.8.0-alpha.23.0.6";
const SUPPORTED_API_VERSION = "1";

const state = {
  articles: [],
  books: [],
  selectedBook: null,
  cards: [],
  reviews: { items: [], summary: { due: 0 }, scheduler: {} },
  reviewKind: "all",
  selectedReviewId: null,
  reviewAnswerRevealed: false,
  canUndoReview: false,
  quizzes: [],
  mistakes: [],
  feeds: [],
  feedStatus: null,
  extractionQuality: { adapters: [], sources: [], classifier_readiness: null },
  extractionAnnotation: null,
  extractionBlockIndex: 0,
  runtime: null,
  backups: [],
  sourceCatalog: [],
  subscriptions: [],
  today: { lanes: [], subscription_count: 0 },
  lexiconResults: [],
  lexiconMeta: { resolution: null, suggestions: [] },
  lexiconHistory: { recent: [], frequent: [] },
  lexicalDataStatus: { layers: [], sources: [], counts: {} },
  selectedLexicalItem: null,
  lexiconFilter: "all",
  progress: { xp: 0, level: 1, level_xp: 0, streak: 0 },
  learnerSettings: {
    daily_minutes: 15,
    daily_tasks: ["reading", "practice", "review"],
    daily_targets: { reading: 1, practice: 5, review: 2, vocabulary: 5 },
    short_goal: "",
    short_goal_date: "",
    long_goal: "",
    long_goal_date: "",
    recommendations_enabled: true,
    article_layout: "split",
    article_density: "comfortable",
  },
  learnerProfile: { completed: false, cefr: "B1", confidence: "low", recommended_levels: ["B1", "B2"] },
  profileSource: "",
  quickTestItems: [],
  examTypes: [],
  examResources: [],
  examPapers: [],
  selectedPaper: null,
  practiceSessions: [],
  practiceAnalytics: null,
  activePracticeData: null,
  practiceRun: null,
  prescription: null,
  selectedPracticeSession: null,
  evidenceReplay: "",
  showTranslation: false,
  articleTopics: [],
  articleTopic: "",
  articleHubs: [],
  articleHub: "",
  articleContentTypes: [],
  articleContentType: "",
  recommendedOnly: false,
  articleVisibility: "",
  articleFacets: { visibility: { all: 0, public: 0, private: 0 }, topics: {}, levels: {} },
  bridge: null,
  browserClips: [],
  quizDraftRestored: false,
  selectedArticle: null,
  selectedPoolArticleId: null,
  selectedMistakeId: null,
  similarByMistake: {},
  analysis: null,
  answerFeedback: {},
  showAnswers: false,
  quizSession: {
    mode: localStorage.getItem("lc-v2-quiz-session-mode") || "practice",
    display: localStorage.getItem("lc-v2-quiz-display") || "single",
    activeIndex: 0,
    answers: {},
    confidence: {},
    flagged: {},
    questionStartedAt: {},
    answerChanges: {},
    committedAnswers: {},
    hintUsed: {},
    startedAt: Date.now(),
    elapsedSeconds: 0,
    submitted: false,
    result: null,
  },
  lookupTranslations: {},
  wordnetTranslationsInFlight: new Set(),
  wordnetAutoTranslationFailed: false,
  style: localStorage.getItem("lc-v2-style") || "IELTS",
  learningMode: localStorage.getItem("lc-v2-learning-mode") || "exam",
};

const titles = {
  dashboard: ["今日训练", "文章、词汇、题目和错题都走本地数据库。"],
  articles: ["文章池", "每日来源、个人导入和分级文章会进入这里。"],
  reader: ["阅读台", "一篇文章可以进入精读、查词、翻译和对应考试训练。"],
  quiz: ["题目", "先做题，再看证据和解析，错题会自动收集。"],
  cards: ["记忆复习", "到期词块与已掌握错题在同一队列中主动回忆。"],
  mistakes: ["错题", "保存你的错误答案、正确答案和原文证据。"],
  history: ["训练记录", "查看单次训练详情、能力趋势和下一步建议。"],
  lexicon: ["词汇中心", "从单词、中文、词形或词源进入同一张词汇网络。"],
  profile: ["用户中心", "自主维护学习画像、目标、偏好和计划。"],
};

const sampleImport = `A useful study plan should connect vocabulary with context. If a learner only memorizes isolated words, she may recognize them in reading but still hesitate when using them in speaking or writing. A better routine is to read a short article, mark repeated phrases, listen to the same passage, and then turn the most important sentences into questions.

This approach creates several chances to meet the same expression. The word is no longer a dry item in a list. It becomes part of a sentence, a sound pattern, a collocation, and finally an answer that the learner can actively recall.`;

function $(selector) {
  return document.querySelector(selector);
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}

function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 1500);
}

const QUICK_START_SEEN_KEY = "lc-v2-quick-start-seen";

function openProfileDialog() {
  const dialog = $("#profileEditor");
  if (dialog && dialog.parentElement !== document.body) document.body.append(dialog);
  if (!dialog?.open) dialog?.showModal();
}

function closeProfileDialog() {
  const dialog = $("#profileEditor");
  if (dialog?.open) dialog.close();
}

function openAssistant() {
  const dialog = $("#assistantDialog");
  if (!dialog?.open) dialog?.showModal();
}

function closeAssistant() {
  const dialog = $("#assistantDialog");
  if (dialog?.open) dialog.close();
}

function maybeOpenAssistant() {
  if (!state.learnerProfile?.completed || localStorage.getItem(QUICK_START_SEEN_KEY)) return;
  localStorage.setItem(QUICK_START_SEEN_KEY, "1");
  openAssistant();
}

function formatDuration(totalSeconds) {
  const seconds = Math.max(0, Number(totalSeconds) || 0);
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = Math.floor(seconds % 60);
  return hours
    ? `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`
    : `${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
}

function formatDateTime(value) {
  if (!value) return "--";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { hour12: false });
}

function normalizeConfidenceValue(value) {
  const score = Number(value);
  return [1, 2, 3].includes(score) ? score : null;
}

function quizElapsedSeconds() {
  const session = state.quizSession;
  if (session.submitted) return session.elapsedSeconds;
  return session.elapsedSeconds + Math.floor((Date.now() - session.startedAt) / 1000);
}

function resetQuizSession({ preserveSettings = true } = {}) {
  const mode = preserveSettings ? state.quizSession.mode : "practice";
  const display = preserveSettings ? state.quizSession.display : "single";
  state.answerFeedback = {};
  state.showAnswers = false;
  state.quizSession = {
    mode,
    display,
    activeIndex: 0,
    answers: {},
    confidence: {},
    flagged: {},
    questionStartedAt: {},
    answerChanges: {},
    committedAnswers: {},
    hintUsed: {},
    startedAt: Date.now(),
    elapsedSeconds: 0,
    submitted: false,
    result: null,
  };
}

function quizDraftPayload() {
  if (!state.quizzes.length || state.quizSession.submitted) return null;
  return {
    style: state.style,
    articleId: state.selectedArticle?.id || null,
    quizIds: state.quizzes.map(quiz => quiz.id),
    mode: state.quizSession.mode,
    display: state.quizSession.display,
    activeIndex: state.quizSession.activeIndex,
    answers: state.quizSession.answers,
    confidence: state.quizSession.confidence,
    flagged: state.quizSession.flagged,
    answerChanges: state.quizSession.answerChanges,
    committedAnswers: state.quizSession.committedAnswers,
    hintUsed: state.quizSession.hintUsed,
    feedback: state.answerFeedback,
    elapsedSeconds: quizElapsedSeconds(),
    savedAt: Date.now(),
  };
}

function persistQuizDraft() {
  const draft = quizDraftPayload();
  if (draft) localStorage.setItem("lc-v2-quiz-draft", JSON.stringify(draft));
}

function clearQuizDraft() {
  localStorage.removeItem("lc-v2-quiz-draft");
  state.quizDraftRestored = false;
}

function restoreQuizDraft() {
  try {
    const draft = JSON.parse(localStorage.getItem("lc-v2-quiz-draft") || "null");
    const currentIds = state.quizzes.map(quiz => quiz.id);
    if (!draft || draft.style !== state.style
      || Number(draft.articleId || 0) !== Number(state.selectedArticle?.id || 0)
      || JSON.stringify(draft.quizIds || []) !== JSON.stringify(currentIds)) return false;
    state.quizSession.mode = draft.mode === "mock" ? "mock" : "practice";
    state.quizSession.display = draft.display === "all" ? "all" : "single";
    state.quizSession.activeIndex = Number(draft.activeIndex) || 0;
    state.quizSession.answers = draft.answers || {};
    state.quizSession.confidence = draft.confidence || {};
    state.quizSession.flagged = draft.flagged || {};
    state.quizSession.questionStartedAt = {};
    state.quizSession.answerChanges = draft.answerChanges || {};
    state.quizSession.committedAnswers = draft.committedAnswers || draft.answers || {};
    state.quizSession.hintUsed = draft.hintUsed || {};
    state.answerFeedback = draft.feedback || {};
    state.showAnswers = Object.keys(state.answerFeedback).length > 0;
    state.quizSession.elapsedSeconds = Math.max(0, Number(draft.elapsedSeconds) || 0);
    state.quizSession.startedAt = Date.now();
    state.quizDraftRestored = true;
    return true;
  } catch (_error) {
    clearQuizDraft();
    return false;
  }
}

function practiceRunSnapshot() {
  if (!state.quizzes.length || state.quizSession.submitted) return null;
  const session = state.quizSession;
  return {
    id: state.practiceRun?.id || undefined,
    article_id: state.selectedArticle?.id || null,
    style: state.style,
    question_type: state.quizzes[0]?.question_type || "mixed",
    scope: $("#quizScope")?.value || "specialty",
    session_mode: session.mode,
    quiz_ids: state.quizzes.map(quiz => quiz.id),
    answers: session.answers,
    confidence: session.confidence,
    flagged: session.flagged,
    answer_changes: session.answerChanges,
    hint_used: session.hintUsed,
    feedback: state.answerFeedback,
    active_index: session.activeIndex,
    display_mode: session.display,
    elapsed_seconds: quizElapsedSeconds(),
    status: "in_progress",
  };
}

let practiceRunSyncTimer;
let practiceRunSyncChain = Promise.resolve();

async function syncPracticeRunNow({ newRun = false } = {}) {
  const snapshot = practiceRunSnapshot();
  if (!snapshot) return null;
  if (newRun) {
    delete snapshot.id;
    state.practiceRun = null;
  }
  const data = await api("/api/practice-runs", { method: "POST", body: JSON.stringify(snapshot) });
  state.practiceRun = data.run;
  state.activePracticeData = { run: data.run, quizzes: state.quizzes };
  renderResumePractice();
  return data.run;
}

function schedulePracticeRunSync() {
  clearTimeout(practiceRunSyncTimer);
  if (!state.quizzes.length || state.quizSession.submitted) return;
  practiceRunSyncTimer = setTimeout(() => {
    practiceRunSyncChain = practiceRunSyncChain
      .then(() => syncPracticeRunNow())
      .catch(error => toast(`训练进度暂未同步：${error.message}`));
  }, 350);
}

async function loadActivePracticeData() {
  try {
    state.activePracticeData = await api("/api/practice-runs/active");
  } catch (_error) {
    state.activePracticeData = { run: null, quizzes: [] };
  }
  if (state.activePracticeData.run?.style) {
    state.style = state.activePracticeData.run.style;
    localStorage.setItem("lc-v2-style", state.style);
    $("#globalStyle").value = state.style;
  }
}

async function restoreServerPracticeRun() {
  const data = state.activePracticeData;
  if (!data?.run || !(data.quizzes || []).length) return false;
  const run = data.run;
  if (run.article_id && Number(state.selectedArticle?.id) !== Number(run.article_id)) {
    const article = await api(`/api/articles/${run.article_id}?exam=${encodeURIComponent(run.style)}`);
    state.selectedArticle = article.article;
    state.analysis = article.analysis;
  }
  state.practiceRun = run;
  state.quizzes = data.quizzes;
  resetQuizSession();
  state.quizSession.mode = run.session_mode === "mock" ? "mock" : "practice";
  state.quizSession.display = run.display_mode === "all" ? "all" : "single";
  state.quizSession.activeIndex = Number(run.active_index) || 0;
  state.quizSession.answers = run.answers || {};
  state.quizSession.confidence = run.confidence || {};
  state.quizSession.flagged = run.flagged || {};
  state.quizSession.answerChanges = run.answer_changes || {};
  state.quizSession.committedAnswers = { ...(run.answers || {}) };
  state.quizSession.hintUsed = run.hint_used || {};
  state.quizSession.elapsedSeconds = Number(run.elapsed_seconds) || 0;
  state.quizSession.startedAt = Date.now();
  state.answerFeedback = run.feedback || {};
  state.showAnswers = Object.keys(state.answerFeedback).length > 0;
  if ($("#quizScope")?.querySelector(`option[value="${run.scope}"]`)) $("#quizScope").value = run.scope;
  clearQuizDraft();
  return true;
}

async function finishServerPracticeRun(action = "complete", practiceSessionId = null) {
  clearTimeout(practiceRunSyncTimer);
  if (!state.practiceRun?.id) return;
  await practiceRunSyncChain.catch(() => null);
  if (action === "complete" && practiceRunSnapshot()) await syncPracticeRunNow();
  await api(`/api/practice-runs/${state.practiceRun.id}/${action}`, {
    method: "POST",
    body: JSON.stringify({ practice_session_id: practiceSessionId }),
  });
  state.practiceRun = null;
  state.activePracticeData = { run: null, quizzes: [] };
  renderResumePractice();
}

function setView(name, { pushHistory = true } = {}) {
  const currentView = document.querySelector(".view.active")?.id?.replace("view-", "") || "dashboard";
  document.querySelectorAll(".view").forEach(view => view.classList.toggle("active", view.id === `view-${name}`));
  document.querySelectorAll(".nav-item").forEach(item => {
    const matchesView = item.dataset.view === name;
    const matchesLexicon = name !== "lexicon" || item.dataset.lexiconFilter === state.lexiconFilter;
    item.classList.toggle("active", matchesView && matchesLexicon);
  });
  $("#viewTitle").textContent = titles[name]?.[0] || "Language Coach";
  $("#viewSubtitle").textContent = titles[name]?.[1] || "";
  if (pushHistory && currentView !== name) {
    const params = new URLSearchParams(window.location.search);
    params.set("view", name);
    if (name !== "lexicon") params.delete("q");
    window.history.pushState({ view: name }, "", `${window.location.pathname}?${params.toString()}`);
  }
}

function badge(text, kind = "") {
  return `<span class="badge ${kind}">${escapeHtml(text)}</span>`;
}

function excerpt(text, max = 160) {
  const clean = String(text || "").replace(/\s+/g, " ").trim();
  return clean.length > max ? `${clean.slice(0, max)}...` : clean;
}

function sentenceFor(text, word) {
  const sentences = String(text || "").replace(/\n+/g, " ").match(/[^.!?]+[.!?]+/g) || [text || ""];
  const found = sentences.find(sentence => sentence.toLowerCase().includes(word.toLowerCase()));
  return (found || sentences[0] || "").trim();
}

function searchableEnglish(text, clickable = true) {
  return String(text || "").split(/(\b[A-Za-z][A-Za-z'-]*\b)/g).map(token => {
    if (!/^[A-Za-z][A-Za-z'-]*$/.test(token)) return escapeHtml(token).replace(/\n/g, "<br>");
    return clickable ? `<span class="reader-word universal-word" data-word="${escapeHtml(token)}">${escapeHtml(token)}</span>` : escapeHtml(token);
  }).join("");
}

function articleParagraphs(text, className = "") {
  return String(text || "").split(/\n\s*\n/).filter(Boolean).map(paragraph => `<p class="${className}">${searchableEnglish(paragraph)}</p>`).join("");
}

function bilingualParagraphs(text, translation = "", showTranslation = false, className = "article-paragraph") {
  const originals = String(text || "").split(/\n\s*\n/).map(value => value.trim()).filter(Boolean);
  const translations = String(translation || "").split(/\n\s*\n/).map(value => value.trim()).filter(Boolean);
  return originals.map((paragraph, index) => `
    <section class="bilingual-pair">
      <p class="${className}">${searchableEnglish(paragraph)}</p>
      ${showTranslation ? `<p class="paragraph-translation ${translations[index] ? "" : "missing"}">${translations[index] ? escapeHtml(translations[index]) : "本段暂无译文"}</p>` : ""}
    </section>
  `).join("");
}

function evidenceBilingualParagraphs(text, translation = "", showTranslation = false, evidence = "") {
  const originals = String(text || "").split(/\n\s*\n/).map(value => value.trim()).filter(Boolean);
  const translations = String(translation || "").split(/\n\s*\n/).map(value => value.trim()).filter(Boolean);
  const needle = String(evidence || "").trim().toLowerCase();
  return originals.map((paragraph, index) => {
    const target = needle && (paragraph.toLowerCase().includes(needle) || needle.includes(paragraph.toLowerCase().slice(0, 80)));
    return `
      <section class="bilingual-pair ${target ? "evidence-replay-target" : ""}" ${target ? "id=\"readerEvidenceTarget\"" : ""}>
        <p class="article-paragraph">${searchableEnglish(paragraph)}</p>
        ${showTranslation ? `<p class="paragraph-translation ${translations[index] ? "" : "missing"}">${translations[index] ? escapeHtml(translations[index]) : "本段暂无译文"}</p>` : ""}
      </section>
    `;
  }).join("");
}

function renderStats() {
  $("#statArticles").textContent = state.articles.length;
  $("#statCards").textContent = state.cards.length;
  $("#statQuizzes").textContent = state.quizzes.length;
  $("#statMistakes").textContent = state.mistakes.filter(item => !item.solved).length;
  $("#progressLevel").textContent = `Lv.${state.progress.level || 1}`;
  $("#progressXp").textContent = `${state.progress.level_xp || 0}/100 XP · ${state.progress.streak || 0} 天`;
}

const dailyTaskLabels = {
  reading: "阅读",
  practice: "考试练习",
  review: "错题复盘",
  vocabulary: "词块复习",
};

const profileWeakLabels = {
  "reading-speed": "阅读速度", evidence: "证据定位", inference: "推断", paraphrase: "同义替换",
  "vocabulary-use": "词汇运用", listening: "听力", speaking: "口语", writing: "写作", grammar: "语法",
};

const profileConfidenceLabels = { high: "较高", medium: "中等", low: "待校准" };

function renderLearnerSettings() {
  const settings = state.learnerSettings;
  $("#dailyMinutes").value = String(settings.daily_minutes || 15);
  document.querySelectorAll("[data-daily-task]").forEach(input => {
    input.checked = (settings.daily_tasks || []).includes(input.dataset.dailyTask);
  });
  document.querySelectorAll("[data-daily-target]").forEach(input => {
    input.value = String(settings.daily_targets?.[input.dataset.dailyTarget] || 1);
  });
  $("#shortGoal").value = settings.short_goal || "";
  $("#shortGoalDate").value = settings.short_goal_date || "";
  $("#longGoal").value = settings.long_goal || "";
  $("#longGoalDate").value = settings.long_goal_date || "";
  $("#recommendationsEnabled").checked = settings.recommendations_enabled !== false;
  const goals = [];
  if (settings.short_goal) goals.push(`<span><strong>近期：</strong>${escapeHtml(settings.short_goal)}${settings.short_goal_date ? ` · ${escapeHtml(settings.short_goal_date)}` : ""}</span>`);
  if (settings.long_goal) goals.push(`<span><strong>长期：</strong>${escapeHtml(settings.long_goal)}${settings.long_goal_date ? ` · ${escapeHtml(settings.long_goal_date)}` : ""}</span>`);
  $("#goalSummary").innerHTML = goals.join("") || `<span>尚未设置近期或长期目标</span>`;
  renderLearnerProfile();
}

function setProfileSource(source) {
  state.profileSource = ["score", "quick_test", "self_assessment"].includes(source) ? source : "score";
  document.querySelectorAll("[data-profile-source]").forEach(button => {
    button.classList.toggle("active", button.dataset.profileSource === state.profileSource);
  });
  document.querySelectorAll("[data-profile-panel]").forEach(panel => {
    panel.hidden = panel.dataset.profilePanel !== state.profileSource;
  });
}

function renderLearnerProfile() {
  const settings = state.learnerSettings;
  const profile = state.learnerProfile || {};
  $("#profileStatus").textContent = profile.completed ? `${profile.cefr} · ${profileConfidenceLabels[profile.confidence] || "待校准"}` : "待建立";
  const target = profile.target_exam ? `${profile.target_exam}${profile.target_score != null ? ` ${profile.target_score}` : ""}${profile.target_date ? ` · ${profile.target_date}` : ""}` : "未设置";
  const weak = (profile.weak_areas || []).map(value => profileWeakLabels[value] || value).join("、") || "待训练数据校准";
  $("#profileSummary").innerHTML = `
    <div><span>当前基线</span><strong>${escapeHtml(profile.cefr || "B1")}</strong><small>${escapeHtml(profile.evidence || "默认起点")}</small></div>
    <div><span>目标</span><strong>${escapeHtml(target)}</strong><small>能力分与 XP 分开记录</small></div>
    <div><span>当前薄弱项</span><strong>${escapeHtml(weak)}</strong><small>推荐难度：${escapeHtml((profile.recommended_levels || ["B1", "B2"]).join(" / "))}</small></div>
  `;
  const calibration = state.today.calibration || {};
  const domainLabels = { reading: "阅读", listening: "听力", vocabulary: "词汇", writing: "写作", speaking: "口语" };
  const domainText = Object.entries(profile.domains || {}).map(([domain, value]) => `${domainLabels[domain] || domain} ${value.cefr}`).join(" · ");
  $("#calibrationSummary").innerHTML = calibration.profile_completed
    ? `<strong>分项：</strong>${escapeHtml(domainText || "等待训练数据")}<br><strong>下次校准：</strong>${calibration.due ? "完成下一次训练后执行" : `${calibration.days_remaining ?? 7} 天后`} · 只调整达到样本门槛的分项`
    : `建立画像后开始累计七天分项证据。`;

  const assessment = settings.assessment || {};
  $("#profileAssessmentType").value = assessment.type || "IELTS";
  $("#profileAssessmentDate").value = assessment.date || "";
  $("#profileOverallScore").value = assessment.overall ?? "";
  document.querySelectorAll("[data-profile-section-score]").forEach(input => {
    input.value = assessment.sections?.[input.dataset.profileSectionScore] ?? "";
  });
  $("#profileTargetExam").value = settings.target_exam || "IELTS";
  $("#profileTargetScore").value = settings.target_score ?? "";
  $("#profileTargetDate").value = settings.target_date || "";
  document.querySelectorAll("[data-self-level]").forEach(select => {
    select.value = settings.self_levels?.[select.dataset.selfLevel] || "";
  });
  document.querySelectorAll("[data-profile-weak]").forEach(input => { input.checked = (settings.weak_areas || []).includes(input.dataset.profileWeak); });
  document.querySelectorAll("[data-profile-interest]").forEach(input => { input.checked = (settings.interest_topics || []).includes(input.dataset.profileInterest); });
  document.querySelectorAll("[data-profile-content]").forEach(input => { input.checked = (settings.interest_content_types || []).includes(input.dataset.profileContent); });
  if (!state.profileSource || !profile.completed) state.profileSource = settings.profile_source === "self_assessment" ? "self_assessment" : settings.profile_source === "quick_test" ? "quick_test" : "score";
  setProfileSource(state.profileSource);
  renderUserCenter();
}

function renderUserCenter() {
  const settings = state.learnerSettings || {};
  const profile = state.learnerProfile || {};
  const target = profile.target_exam ? `${profile.target_exam}${profile.target_score != null ? ` ${profile.target_score}` : ""}${profile.target_date ? ` · ${profile.target_date}` : ""}` : "未设置";
  const weak = (profile.weak_areas || []).map(value => profileWeakLabels[value] || value);
  const sourceLabels = { score: "已有成绩", quick_test: "快速基线", self_assessment: "自评" };
  const domainLabels = { reading: "阅读", listening: "听力", vocabulary: "词汇", writing: "写作", speaking: "口语" };
  const domains = Object.entries(profile.domains || {});
  $("#userProfileStatus").textContent = profile.completed ? `${profile.cefr} · ${profileConfidenceLabels[profile.confidence] || "待校准"}` : "待建立";
  $("#userProfileSummary").innerHTML = `
    <div><span>当前基线</span><strong>${escapeHtml(profile.cefr || "B1")}</strong><small>${escapeHtml(sourceLabels[settings.profile_source] || profile.evidence || "默认起点")}</small></div>
    <div><span>目标</span><strong>${escapeHtml(target)}</strong><small>${escapeHtml(settings.target_date || "未设置目标日期")}</small></div>
    <div><span>推荐难度</span><strong>${escapeHtml((profile.recommended_levels || ["B1", "B2"]).join(" / "))}</strong><small>依据画像与有效训练证据</small></div>
  `;
  $("#userDomainList").innerHTML = domains.length
    ? domains.map(([domain, value]) => `<div><span>${escapeHtml(domainLabels[domain] || domain)}</span><strong>${escapeHtml(value.cefr || "--")}</strong><small>${escapeHtml(value.evidence_count ? `${value.evidence_count} 条证据` : "等待训练证据")}</small></div>`).join("")
    : `<div class="muted">完成画像并积累训练后显示分项能力。</div>`;
  $("#userCalibrationSummary").innerHTML = $("#calibrationSummary").innerHTML;
  const interests = profile.interest_topics || settings.interest_topics || [];
  const contentTypeLabels = Object.fromEntries((state.articleContentTypes || []).map(item => [item.id, item.label]));
  const contentTypes = (settings.interest_content_types || []).map(value => contentTypeLabels[value] || value);
  $("#userPreferenceSummary").innerHTML = `
    <div><span>薄弱项</span><strong>${escapeHtml(weak.join("、") || "等待训练校准")}</strong></div>
    <div><span>兴趣主题</span><strong>${escapeHtml(interests.join("、") || "未设置")}</strong></div>
    <div><span>内容偏好</span><strong>${escapeHtml(contentTypes.join("、") || "未设置")}</strong></div>
  `;
  const tasks = (settings.daily_tasks || []).map(task => dailyTaskLabels[task] || task).join("、") || "未设置";
  $("#userPlanSummary").innerHTML = `
    <div><span>每日计划</span><strong>${escapeHtml(`${settings.daily_minutes || 15} 分钟 · ${tasks}`)}</strong></div>
    <div><span>近期目标</span><strong>${escapeHtml(settings.short_goal || "未设置")}</strong></div>
    <div><span>长期目标</span><strong>${escapeHtml(settings.long_goal || "未设置")}</strong></div>
  `;
  $("#userRecommendationStatus").textContent = settings.recommendations_enabled === false ? "已关闭" : "已开启";
}

function learnerProfilePayload() {
  return {
    profile_source: state.profileSource,
    assessment_type: $("#profileAssessmentType").value,
    assessment_date: $("#profileAssessmentDate").value,
    overall_score: $("#profileOverallScore").value,
    section_scores: Object.fromEntries([...document.querySelectorAll("[data-profile-section-score]")].map(input => [input.dataset.profileSectionScore, input.value])),
    target_exam: $("#profileTargetExam").value,
    target_score: $("#profileTargetScore").value,
    target_date: $("#profileTargetDate").value,
    self_levels: Object.fromEntries([...document.querySelectorAll("[data-self-level]")].map(input => [input.dataset.selfLevel, input.value])),
    weak_areas: [...document.querySelectorAll("[data-profile-weak]:checked")].map(input => input.dataset.profileWeak),
    interest_topics: [...document.querySelectorAll("[data-profile-interest]:checked")].map(input => input.dataset.profileInterest),
    interest_content_types: [...document.querySelectorAll("[data-profile-content]:checked")].map(input => input.dataset.profileContent),
  };
}

async function saveLearnerProfile() {
  const data = await api("/api/learner-profile", { method: "POST", body: JSON.stringify(learnerProfilePayload()) });
  state.learnerSettings = data.settings;
  state.learnerProfile = data.profile;
  await loadToday();
  renderLearnerSettings();
  renderDashboard();
  $("#profileEditor").close();
  toast("学习画像已保存");
  maybeOpenAssistant();
}

function renderQuickTest() {
  $("#quickTestItems").innerHTML = state.quickTestItems.map((item, index) => `
    <fieldset class="quick-test-item">
      <legend>${index + 1}. ${escapeHtml(item.prompt)}</legend>
      ${item.options.map(option => `<label><input type="radio" name="quick-${escapeHtml(item.id)}" value="${escapeHtml(option)}" />${escapeHtml(option)}</label>`).join("")}
    </fieldset>
  `).join("");
  $("#submitQuickTestBtn").hidden = !state.quickTestItems.length;
}

async function loadQuickTest() {
  const data = await api("/api/profile/quick-test");
  state.quickTestItems = data.items || [];
  renderQuickTest();
}

async function submitQuickTest() {
  const responses = Object.fromEntries(state.quickTestItems.map(item => {
    const selected = document.querySelector(`input[name="quick-${CSS.escape(item.id)}"]:checked`);
    return [item.id, selected?.value || ""];
  }));
  const data = await api("/api/profile/quick-test", { method: "POST", body: JSON.stringify({ ...learnerProfilePayload(), responses }) });
  state.learnerSettings = data.settings;
  state.learnerProfile = data.profile;
  await loadToday();
  renderLearnerSettings();
  renderDashboard();
  $("#profileEditor").close();
  toast(`快速基线完成：${data.result.cefr}`);
  maybeOpenAssistant();
}

function renderDailyPlan() {
  const plan = state.today.plan || { minutes: state.learnerSettings.daily_minutes, tasks: [], items: [] };
  $("#dailyPlanSummary").textContent = plan.completed ? "今日已完成" : `${plan.minutes || 15} 分钟 · ${plan.summary || "待开始"}`;
  $("#dailyPlanTasks").innerHTML = (plan.tasks || []).map(item => `
    <div class="daily-plan-task ${item.done ? "done" : ""}">
      <div class="daily-plan-task-head"><strong>${escapeHtml(dailyTaskLabels[item.task] || item.task)}</strong><span>${item.completed}/${item.target}</span></div>
      <div class="ability-meter"><span style="width:${item.percent}%"></span></div>
      ${item.done ? `<small>已完成</small>` : `<button data-complete-daily-task="${item.task}" data-daily-target-count="${item.target}">标记完成</button>`}
    </div>
  `).join("") || `<span class="muted">保存计划后生成今日任务。</span>`;
  $("#dailyPlanQueue").innerHTML = (plan.items || []).map(item => `
    <div class="daily-plan-queue-item ${item.completed ? "completed" : ""}">
      <span>${badge(dailyTaskLabels[item.task] || item.task, item.completed ? "" : "teal")} ${escapeHtml(item.title || `${item.item_type} #${item.item_id}`)}</span>
      ${item.completed ? `<small>已完成</small>` : `<button data-complete-plan-item="${item.id}">完成</button>`}
    </div>
  `).join("");
}

function renderDashboard() {
  const interest = state.learningMode === "interest";
  const activeGoal = state.learnerSettings.short_goal || state.learnerSettings.long_goal || "";
  document.querySelectorAll("[data-learning-mode]").forEach(button => {
    button.classList.toggle("active", button.dataset.learningMode === state.learningMode);
    button.setAttribute("aria-pressed", String(button.dataset.learningMode === state.learningMode));
  });
  $("#modeEyebrow").textContent = interest ? "Interest mode" : `${state.style} exam mode`;
  $("#modeHeading").textContent = interest ? "从喜欢的内容进入英语" : `今天为 ${state.style} 目标训练`;
  $("#modeBrief").classList.toggle("interest-focus", interest);
  $("#modeDescription").textContent = interest
    ? `优先推荐订阅、新闻与文化内容；今日计划 ${state.learnerSettings.daily_minutes} 分钟。${activeGoal ? ` 当前目标：${activeGoal}` : ""}`
    : `优先匹配考试难度、证据定位与同义替换；今日计划 ${state.learnerSettings.daily_minutes} 分钟。${activeGoal ? ` 当前目标：${activeGoal}` : ""}`;
  $("#modePrimaryAction").textContent = interest ? "开始轻松阅读" : "开始今日训练";
  const modeFocus = state.today.mode_focus || {};
  $("#modeHeading").textContent = modeFocus.title || (interest ? "从喜欢的内容进入英语" : `今天为 ${state.style} 目标训练`);
  $("#modePrimaryAction").textContent = modeFocus.primary || (interest ? "开始轻松阅读" : "开始今日训练");
  $("#modeInsights").innerHTML = (modeFocus.signals || []).map(value => `<span>${escapeHtml(value)}</span>`).join("");
  $("#examReviewSection").hidden = interest;
  $("#prescriptionBand").hidden = interest;
  $("#globalStyle").title = interest ? "兴趣素材生成题目时参照的考试难度" : "当前备考目标";
  $("#globalStyle").hidden = interest;
  renderDailyPlan();
  renderResumePractice();
  renderPrescription();

  $("#recentArticles").innerHTML = (state.today.lanes || []).map(lane => {
    const article = lane.article;
    return `
    <div class="item">
      <div class="badge-row">${badge(lane.label, "amber")}${badge(article.content_type_label || "学术解释", "teal")}${badge(article.source || "manual")}</div>
      <h3>${escapeHtml(article.title)}</h3>
      <p>${escapeHtml(lane.reason)} · ${escapeHtml(excerpt(article.highlight || article.body, 120))}</p>
      <div class="toolbar">
        <button data-open-article="${article.id}">${interest ? "沉浸阅读" : "精读原文"}</button>
        ${interest
          ? `<button data-add-plan-item="article" data-plan-task="reading" data-plan-item-id="${article.id}" data-plan-item-title="${escapeHtml(article.title)}">加入兴趣清单</button>`
          : articleTrainingAction(article, "按此文训练")}
      </div>
    </div>
  `;
  }).join("") || `<div class="item muted">文章池中还没有可推荐内容</div>`;

  $("#recentMistakes").innerHTML = state.mistakes.filter(item => !item.solved).slice(0, 4).map(item => `
    <div class="item">
      <div class="badge-row">${badge("错题", "red")}</div>
      <h3>${escapeHtml(excerpt(item.prompt, 90))}</h3>
      <p>你的答案：${escapeHtml(item.user_answer || "")}</p>
      <p>正确答案：${escapeHtml(item.answer || "")}</p>
      <button data-add-plan-item="mistake" data-plan-task="review" data-plan-item-id="${item.id}" data-plan-item-title="${escapeHtml(excerpt(item.prompt, 100))}">加入今日复盘</button>
    </div>
  `).join("") || `<div class="item muted">暂无错题</div>`;
  $("#browserLearningQueue").innerHTML = state.browserClips.slice(0, 6).map(clip => `
    <div class="item">
      <div class="badge-row">${badge(clip.kind === "article" ? "网页正文" : clip.kind === "word" ? "划词" : "网页摘录", "teal")}${clip.page_title ? badge(clip.page_title) : ""}</div>
      <h3>${escapeHtml(excerpt(clip.source_text, 100))}</h3>
      ${clip.context && clip.context !== clip.source_text ? `<p>${escapeHtml(excerpt(clip.context, 130))}</p>` : ""}
      <div class="toolbar">
        ${clip.article_id ? `<button data-open-article="${clip.article_id}">进入文章</button><button data-quiz-article="${clip.article_id}">生成练习</button>` : `<button data-search-query="${escapeHtml(excerpt(clip.source_text, 70))}" data-open-lexicon="true">继续查词</button>`}
        <button data-add-plan-item="clip" data-plan-task="${clip.kind === "word" ? "vocabulary" : "reading"}" data-plan-item-id="${clip.id}" data-plan-item-title="${escapeHtml(excerpt(clip.source_text, 100))}">加入今日计划</button>
        ${clip.page_url ? `<a class="button-link" href="${escapeHtml(clip.page_url)}" target="_blank" rel="noreferrer">返回网页</a>` : ""}
      </div>
    </div>
  `).join("") || `<div class="item muted">插件保存的划词、段落和正文会出现在这里。</div>`;
}

function renderResumePractice() {
  const band = $("#resumePracticeBand");
  if (!band) return;
  const run = state.practiceRun || state.activePracticeData?.run;
  band.hidden = !run;
  if (!run) return;
  const answers = run.answers || state.quizSession.answers || {};
  const answered = Object.values(answers).filter(value => String(value || "").trim()).length;
  const total = (run.quiz_ids || state.quizzes.map(quiz => quiz.id)).length;
  $("#resumePracticeTitle").textContent = `继续 ${run.style} ${run.question_type || "综合"}训练`;
  $("#resumePracticeSummary").textContent = `${answered}/${total} 题 · 已用 ${formatDuration(run.elapsed_seconds || 0)} · 上次保存 ${formatDateTime(run.updated_at)}`;
}

function prescriptionHtml(prescription, compact = false) {
  if (!prescription) return `<p class="muted">正在分析最近训练证据。</p>`;
  const metrics = prescription.metrics || {};
  const metricItems = [
    ["正确率", metrics.accuracy == null ? "待建立" : `${metrics.accuracy}%`],
    ["平均用时", metrics.average_seconds == null ? "暂无" : `${metrics.average_seconds} 秒`],
    ["平均改答", `${metrics.average_changes || 0} 次`],
    ["提示使用", `${Math.round((metrics.hint_rate || 0) * 100)}%`],
    ["确定但答错", `${Math.round((metrics.certain_wrong_rate || 0) * 100)}%`],
  ];
  return `
    <div class="prescription-headline">
      <div><strong>${escapeHtml(prescription.question_type || "基线训练")}</strong><span>${escapeHtml(prescription.skill || "阅读能力")}</span></div>
      ${badge(`${prescription.sample_count || 0} 次 / ${prescription.unique_quiz_count || 0} 题`, prescription.evidence_confidence === "high" ? "teal" : "amber")}
    </div>
    ${compact ? "" : `<div class="prescription-metrics">${metricItems.map(([label, value]) => `<div><span>${label}</span><strong>${value}</strong></div>`).join("")}</div>`}
    <ul class="prescription-reasons">${(prescription.reasons || []).map(reason => `<li>${escapeHtml(reason)}</li>`).join("")}</ul>
    <div class="toolbar prescription-actions">
      <button data-start-prescription="5" data-prescription-type="${escapeHtml(prescription.question_type || "")}">练 5 题</button>
      <button class="primary" data-start-prescription="${prescription.recommended_count || 10}" data-prescription-type="${escapeHtml(prescription.question_type || "")}">按建议练 ${prescription.recommended_count || 10} 题</button>
    </div>
    ${compact ? "" : `<p class="prescription-note">${escapeHtml(prescription.evidence_note || "")}</p>`}
  `;
}

function renderPrescription() {
  if (!$("#prescriptionBody")) return;
  if (state.learnerSettings.recommendations_enabled === false) {
    $("#prescriptionStatus").textContent = "已关闭";
    $("#prescriptionBody").innerHTML = `<p class="muted">你已关闭画像推荐；作答记录仍保留，但系统不会安排训练处方。</p>`;
    return;
  }
  const prescription = state.prescription;
  $("#prescriptionStatus").textContent = prescription?.status === "ready" ? `优先级 ${prescription.priority_score}` : "建立基线中";
  $("#prescriptionBody").innerHTML = prescriptionHtml(prescription);
}

function articleGridCard(article) {
  const minutes = Math.max(5, Math.min(30, Math.ceil((article.content_word_count || 1) / 120) * 5));
  const learningState = article.recommended_today ? `今日推荐 ${article.daily_rank}` : article.content_status === "full" ? "可完整精读" : "摘要速读";
  return `
    <article class="article-discovery-card">
      <div class="badge-row">
        ${badge(article.visibility === "private" ? "私人" : "公开", article.visibility === "private" ? "amber" : "teal")}
        ${badge(article.level, "teal")}
        ${article.exam_fit ? badge(`${state.style} ${article.exam_fit}%`) : ""}
        ${badge(`${article.content_quality_label} · ${article.content_quality_score}分`, article.content_quality_score >= 60 ? "teal" : "amber")}
        ${badge(`${article.exam_length_label} · ${article.content_word_count}词`, article.exam_length_status === "matched" ? "teal" : "amber")}
      </div>
      <h3>${escapeHtml(article.title)}</h3>
      <p>${escapeHtml(excerpt(article.highlight || article.body, 180))}</p>
      <div class="article-card-meta"><span>${escapeHtml(article.source || "manual")}</span><span>${minutes} 分钟</span><span>${learningState}</span></div>
      <div class="article-card-themes">${(article.theme_tags || []).slice(0, 3).map(theme => badge(theme, "amber")).join("")}</div>
      <div class="article-card-actions">
        <button data-open-article="${article.id}">阅读</button>
        ${articleTrainingAction(article, "转为训练")}
        <button data-add-plan-item="article" data-plan-task="reading" data-plan-item-id="${article.id}" data-plan-item-title="${escapeHtml(article.title)}">加入今日</button>
      </div>
    </article>`;
}

function articleTrainingAction(article, label = "生成题") {
  return article.training_eligible
    ? `<button class="primary" data-quiz-article="${article.id}">${label}</button>`
    : `<button disabled title="${escapeHtml(article.training_block_reason || "素材暂不符合训练要求")}">${article.content_status === "full" ? "暂不适合出题" : "摘要不可出题"}</button>`;
}

function sourceMetadataHtml(article) {
  if (!article.author && !article.image_caption && !article.disclosure && !article.extraction_version) return "";
  const sourceQuality = state.extractionQuality.sources.find(item =>
    item.source === article.source && item.extraction_version === article.extraction_version
  );
  const readiness = state.extractionQuality.classifier_readiness;
  return `<details class="source-metadata">
    <summary>来源信息</summary>
    ${article.author ? `<p><strong>作者</strong><span>${escapeHtml(article.author)}</span></p>` : ""}
    ${article.image_caption ? `<p><strong>图片说明</strong><span>${escapeHtml(article.image_caption)}</span></p>` : ""}
    ${article.disclosure ? `<p><strong>披露声明</strong><span>${escapeHtml(article.disclosure)}</span></p>` : ""}
    <p><strong>正文提取</strong><span>${escapeHtml(article.extraction_version || "未记录")} · ${Math.round(Number(article.extraction_confidence || 0) * 100)}%</span></p>
    ${sourceQuality ? `<p><strong>人工校验</strong><span>${sourceQuality.feedback_count} 条反馈 · ${sourceQuality.issue_count || 0} 条问题</span></p>` : ""}
    ${readiness ? `<p><strong>分类器数据</strong><span>${readiness.observed.block_labels}/${readiness.thresholds.block_labels} 个区块标签 · ${readiness.ready ? "达到评估门槛" : "继续积累"}</span></p>` : ""}
    <div class="toolbar extraction-feedback">
      <button data-open-extraction-labeler="${article.id}">区块标注</button>
      <button data-extraction-feedback="correct" data-article-id="${article.id}">准确</button>
      <button data-extraction-feedback="caption_in_body" data-article-id="${article.id}">图片说明混入</button>
      <button data-extraction-feedback="author_disclosure_in_body" data-article-id="${article.id}">作者/披露混入</button>
    </div>
  </details>`;
}

function renderArticles() {
  const list = $("#articleTitleList");
  const detail = $("#articleDetail");
  const layout = state.learnerSettings.article_layout || "split";
  const density = state.learnerSettings.article_density || "comfortable";
  $("#articlePoolLayout").className = `master-detail article-layout-${layout} article-density-${density}`;
  document.querySelectorAll("[data-article-layout]").forEach(button => button.classList.toggle("active", button.dataset.articleLayout === layout));
  document.querySelectorAll("[data-article-density]").forEach(button => button.classList.toggle("active", button.dataset.articleDensity === density));
  document.querySelectorAll("[data-article-visibility]").forEach(button => button.classList.toggle("active", button.dataset.articleVisibility === state.articleVisibility));
  const visibilityCounts = state.articleFacets.visibility || {};
  $("#articleCountAll").textContent = visibilityCounts.all || 0;
  $("#articleCountPublic").textContent = visibilityCounts.public || 0;
  $("#articleCountPrivate").textContent = visibilityCounts.private || 0;
  if (state.articleTopics.length) {
    const selectedTopic = state.articleTopic;
    $("#articleTopicFilter").innerHTML = `<option value="">全部主题</option>${state.articleTopics.map(topic => `<option value="${escapeHtml(topic)}">${escapeHtml(topic)} (${state.articleFacets.topics?.[topic] || 0})</option>`).join("")}`;
    $("#articleTopicFilter").value = selectedTopic;
  }
  const refreshStatus = state.feedStatus;
  const latestRun = refreshStatus?.latest_run;
  const failedSources = (refreshStatus?.sources || []).filter(source => source.consecutive_failures > 0).length;
  $("#feedRefreshStatus").innerHTML = refreshStatus ? `
    <div><strong>${refreshStatus.refreshing ? "正在更新" : latestRun ? `上次更新：${formatDateTime(latestRun.completed_at)}` : "尚未更新"}</strong><span>${latestRun ? `新增 ${latestRun.imported_count} · 更新 ${latestRun.updated_count} · 未变化 ${latestRun.unchanged_count}` : `启动后自动检查`}</span></div>
    <div class="badge-row">${badge(`${refreshStatus.interval_hours} 小时间隔`, "teal")}${failedSources ? badge(`${failedSources} 个来源异常`, "amber") : badge("来源正常")}</div>
  ` : "";
  if (!state.articles.length) {
    list.innerHTML = `<div class="empty-state">文章池为空</div>`;
    detail.innerHTML = `<div class="empty-state">更新 RSS 或导入一篇文章。</div>`;
  } else {
    if (!state.articles.some(article => article.id === state.selectedPoolArticleId)) {
      state.selectedPoolArticleId = state.articles[0].id;
    }
    const selected = state.articles.find(article => article.id === state.selectedPoolArticleId);
    if (layout === "grid") {
      list.innerHTML = state.articles.map(articleGridCard).join("");
      detail.innerHTML = "";
    } else {
      list.innerHTML = state.articles.map((article, index) => `
      <button class="master-list-item ${article.id === selected.id ? "active" : ""}" data-select-article="${article.id}">
        <span class="master-number">${String(index + 1).padStart(2, "0")}</span>
        <span class="master-copy">
          <strong>${escapeHtml(article.title)}</strong>
          <small>${article.recommended_today ? `推荐 ${article.daily_rank} · ` : ""}${escapeHtml(article.content_hub_label || "文化与生活")} · ${escapeHtml(article.content_type_label || "学术解释")} · ${escapeHtml(article.source || "manual")} · ${escapeHtml(article.level)}${article.published_at ? ` · ${formatDateTime(article.published_at)}` : ""}</small>
          ${article.recommended_today ? `<em>${escapeHtml((article.recommendation_reasons || []).join(" · "))}</em>` : ""}
        </span>
      </button>
    `).join("");
    detail.innerHTML = `
      <div class="detail-head">
        <div>
          <div class="badge-row">
            ${badge(selected.level, "teal")}
            ${badge(selected.source || "manual")}
            ${badge(selected.content_hub_label || "文化与生活", "teal")}
            ${badge(selected.content_type_label || "学术解释", selected.content_type === "opinion" ? "amber" : "teal")}
            ${selected.source_kind ? badge(selected.source_kind) : ""}
            ${badge(selected.content_status === "full" ? `完整正文 · ${selected.content_word_count}词` : `RSS摘要 · ${selected.content_word_count}词`, selected.content_status === "full" ? "teal" : "amber")}
            ${selected.source_tier ? badge(selected.source_tier, selected.source_tier === "核心" ? "teal" : "") : ""}
            ${selected.exam_fit ? badge(`${state.style} 匹配 ${selected.exam_fit}%`, selected.exam_fit >= 90 ? "amber" : "") : ""}
          </div>
          <h2>${escapeHtml(selected.title)}</h2>
          ${selected.author ? `<p class="article-byline">作者：${escapeHtml(selected.author)}</p>` : ""}
          ${selected.published_at ? `<p class="muted">发布于 ${formatDateTime(selected.published_at)}</p>` : ""}
        </div>
        <div class="toolbar">
          <button data-toggle-translation="true">${state.showTranslation ? "隐藏译文" : "显示译文"}</button>
          <button data-translate-article="${selected.id}">一键翻译</button>
          <button data-open-article="${selected.id}">进入阅读台</button>
          ${articleTrainingAction(selected)}
        </div>
      </div>
      ${selected.recommended_today ? `<div class="daily-recommendation"><strong>今日推荐 ${selected.daily_rank}</strong><span>${escapeHtml((selected.recommendation_reasons || []).join(" · "))}</span><small>推荐分 ${selected.recommendation_score}</small></div>` : ""}
      <div class="content-notice ${selected.training_eligible ? "quality-pass" : ""}"><div><strong>素材质量 ${selected.content_quality_score} · ${escapeHtml(selected.content_quality_label)}</strong><span>${escapeHtml(selected.exam_length_label)}：${selected.content_word_count} 词；${state.style} 建议 ${selected.exam_word_min}-${selected.exam_word_max} 词。${selected.training_eligible ? " 已通过训练门槛。" : ` ${selected.training_block_reason}`}</span></div></div>
      ${selected.content_status !== "full" ? `<div class="content-notice"><div><strong>当前保存的是 RSS 摘要</strong><span>阅读器已经显示全部本地内容，完整文章需要打开原始来源或补充正文。</span></div>${selected.source_url ? `<a href="${escapeHtml(selected.source_url)}" target="_blank" rel="noreferrer">打开完整原文</a>` : ""}</div>` : ""}
      ${selected.theme_tags?.length ? `<div class="article-themes"><span>文章主题</span>${selected.theme_tags.map(theme => badge(theme, "amber")).join("")}</div>` : ""}
      ${selected.source_topics?.length ? `<div class="source-topics"><span class="topic-label">来源领域</span>${selected.source_topics.map(topic => badge(topic)).join("")}</div>` : ""}
      ${sourceMetadataHtml(selected)}
      <article class="article-detail-body">${bilingualParagraphs(selected.body, selected.translation_zh, state.showTranslation)}</article>
      ${selected.source_url ? `<a class="source-link" href="${escapeHtml(selected.source_url)}" target="_blank" rel="noreferrer">打开原始来源</a>` : ""}
      <details class="content-editor"><summary>${selected.content_status === "full" ? "编辑完整正文" : "补充完整正文"}</summary><textarea id="articleContentInput">${escapeHtml(selected.body)}</textarea><button class="primary" data-save-article-content="${selected.id}">保存为完整正文</button></details>
    `;
    }
  }

  const visibleSources = state.sourceCatalog.filter(source => {
    if (!state.articleHub) return true;
    if (state.articleHub === "subscribed") return source.subscribed;
    return source.hub === state.articleHub;
  });
  const categorySubscriptions = new Set(state.subscriptions.filter(item => item.target_type === "category" && item.active).map(item => item.target_value));
  $("#feedList").innerHTML = `
    <div class="source-pool-head">
      <div><span class="muted">Exam-aligned sources</span><h2>${state.style} 来源池</h2></div>
      ${badge("仅保存摘要与链接", "teal")}
    </div>
    <div class="source-category-subscriptions">
      ${state.articleHubs.map(hub => `<button data-subscribe-category="${escapeHtml(hub.label)}" data-subscribe-active="${categorySubscriptions.has(hub.label) ? "false" : "true"}">${categorySubscriptions.has(hub.label) ? "已订阅" : "订阅"} ${escapeHtml(hub.label)}</button>`).join("")}
    </div>
    ${visibleSources.map(source => `
      <div class="source-row">
        <div><strong>${escapeHtml(source.name)}</strong><p>${escapeHtml(source.hub_label || source.category)} · ${escapeHtml(source.formats.join(" / "))} · ${escapeHtml(source.rights_mode)}</p></div>
        <div class="badge-row">${badge(source.automatic ? "自动更新" : source.access_mode, source.automatic ? "teal" : "")}${badge(source.cadence, "amber")}${badge(source.difficulty || "B2-C1")}${source.transcript_available ? badge("字幕/讲稿") : ""}${source.homepage ? `<a class="button-link" href="${escapeHtml(source.homepage)}" target="_blank" rel="noreferrer">来源</a>` : ""}<button data-subscribe-source="${escapeHtml(source.name)}" data-subscribe-active="${source.subscribed ? "false" : "true"}">${source.subscribed ? "取消订阅" : "订阅"}</button></div>
      </div>
    `).join("") || `<div class="empty-state">当前分类还没有已注册来源。</div>`}
  `;
}

function renderReader() {
  const article = state.selectedArticle;
  if (!article) {
    $("#readerTitle").textContent = "选择一篇文章";
    $("#readerMeta").innerHTML = "";
    $("#readerContentNotice").innerHTML = "";
    $("#readerBody").innerHTML = `<p class="muted">从文章池选择文章后开始。</p>`;
    $("#analysisPanel").innerHTML = "";
    return;
  }
  $("#readerTitle").textContent = `${article.content_status === "full" ? "" : "来源摘要 · "}${article.title}`;
  $("#readerMeta").innerHTML = `${badge(article.level, "teal")}${badge(article.content_type_label || "学术解释", article.content_type === "opinion" ? "amber" : "teal")}${badge(article.content_status === "full" ? `完整正文 · ${article.content_word_count}词` : `RSS摘要 · ${article.content_word_count}词`, article.content_status === "full" ? "teal" : "amber")}${badge(`${article.exam_length_label} · ${state.style} ${article.exam_word_min}-${article.exam_word_max}词`, article.exam_length_status === "matched" ? "teal" : "amber")}${badge(`质量 ${article.content_quality_score}`)}${(article.theme_tags || []).map(theme => badge(theme, "amber")).join("")}${badge(article.source || "manual")}`;
  $("#readerContentNotice").innerHTML = `${article.content_status !== "full" ? `<div class="content-notice compact"><div><strong>这是来源摘要，不是原文</strong><span>受版权与 feed 范围限制，系统只保存来源主动提供的摘要。可打开原站，或通过插件带回你有权使用的正文。</span></div>${article.source_url ? `<a href="${escapeHtml(article.source_url)}" target="_blank" rel="noreferrer">打开原文</a>` : ""}</div>` : article.training_eligible ? "" : `<div class="content-notice compact"><div><strong>暂不适合考试出题</strong><span>${escapeHtml(article.training_block_reason)}</span></div></div>`}${sourceMetadataHtml(article)}`;
  $("#readerBody").innerHTML = state.evidenceReplay
    ? evidenceBilingualParagraphs(article.body, article.translation_zh, state.showTranslation, state.evidenceReplay)
    : bilingualParagraphs(article.body, article.translation_zh, state.showTranslation);
  $("#articleTranslationInput").value = article.translation_zh || "";
  const translationPanel = $("#translationPanel");
  translationPanel.hidden = true;
  translationPanel.innerHTML = "";
  $("#toggleTranslationBtn").textContent = state.showTranslation ? "隐藏译文" : "显示译文";
  $("#toggleTranslationBtn").setAttribute("aria-pressed", String(state.showTranslation));
  $("#generateQuizBtn").disabled = !article.training_eligible;
  $("#generateQuizBtn").textContent = article.training_eligible ? "转为练习" : article.content_status === "full" ? "暂不适合出题" : "摘要不可出题";
  $("#generateQuizBtn").title = article.training_block_reason || "";
  renderAnalysis();
}

function renderQuizSource() {
  const article = state.selectedArticle;
  $("#quizSourceTitle").textContent = article?.title || "原文";
  $("#quizSourceText").innerHTML = article ? (state.evidenceReplay
    ? evidenceBilingualParagraphs(article.body, article.translation_zh, state.showTranslation, state.evidenceReplay)
    : bilingualParagraphs(article.body, article.translation_zh, state.showTranslation)) : `<p class="muted">先从文章池选择文章。</p>`;
  const translation = $("#quizTranslationPanel");
  translation.hidden = true;
  translation.innerHTML = "";
  $("#quizTranslationBtn").textContent = state.showTranslation ? "隐藏译文" : article?.translation_aligned ? "显示译文" : "一键翻译";
}

function renderAnalysis() {
  const analysis = state.analysis;
  if (!analysis) {
    $("#analysisPanel").innerHTML = `<div class="analysis-block muted">尚未分析</div>`;
    return;
  }
  $("#analysisPanel").innerHTML = `
    <div class="analysis-block">
      <strong>${escapeHtml(analysis.level)}</strong>
      <p>${analysis.word_count} words · ${analysis.sentence_count} sentences</p>
    </div>
    <div class="analysis-block">
      <strong>你可能不认识 · ${escapeHtml(analysis.learner_level || "B1")}</strong>
      <div class="badge-row">${(analysis.vocabulary_candidates || []).map(item => `<button data-word="${escapeHtml(item.term)}">${escapeHtml(item.term)} · ${escapeHtml(item.level)}</button>`).join("")}</div>
    </div>
    <div class="analysis-block">
      <strong>重点句</strong>
      ${analysis.focus_sentences.map(sentence => `<p>${searchableEnglish(sentence)}</p>`).join("")}
    </div>
  `;
}

async function renderLookup(word) {
  const clean = String(word || "").toLowerCase().replace(/^[^a-z]+|[^a-z]+$/g, "").replace(/\s+/g, " ").trim();
  if (!clean) return;
  const context = state.selectedArticle ? sentenceFor(state.selectedArticle.body, clean) : "";
  const data = await api(`/api/lexicon/search?q=${encodeURIComponent(clean)}`);
  const queryItem = data.results?.find(item => item.type === "query" && item.term.toLowerCase() === clean) || null;
  const info = data.results?.find(item => ["entry", "wordnet"].includes(item.type)) || null;
  const displayTerm = queryItem?.term || info?.headword || clean;
  const translation = state.lookupTranslations[clean] || queryItem?.translation_zh || info?.meaning_zh || "";
  const saved = queryItem?.saved || state.cards.some(card => card.term.toLowerCase() === clean);
  $("#lookupPanel").innerHTML = `
    <div class="lookup-heading"><div><h2>${escapeHtml(displayTerm)}</h2><span>${queryItem?.kind === "phrase" ? "短语" : info ? `${escapeHtml(info.ipa_uk)} · ${escapeHtml(info.pos)}` : "待补充词条"}</span></div><button data-speak="${escapeHtml(displayTerm)}" title="播放发音" aria-label="播放发音">▶</button></div>
    <p>${escapeHtml(translation || info?.core_meaning || "当前本地词库还没有完整释义，可以一键翻译并连同语境保存。")}</p>
    ${info?.breakdown ? `<div class="morph-line">${escapeHtml(info.breakdown)}</div>` : ""}
    <div class="badge-row">${(info?.collocations || []).slice(0, 3).map(item => `<button data-search-query="${escapeHtml(termText(item))}">${escapeHtml(termText(item))}</button>`).join("")}</div>
    ${context ? `<div class="answer-box">${searchableEnglish(context)}</div>` : ""}
    <div class="toolbar">
      <button class="primary" data-save-lookup="${escapeHtml(clean)}">${saved ? "更新生词语境" : "加入生词本"}</button>
      ${translation ? "" : `<button data-translate-term="${escapeHtml(clean)}">翻译</button>`}
      <button data-search-query="${escapeHtml(clean)}" data-open-lexicon="true">完整查询</button>
      <a class="button-link" href="https://dict.eudic.net/dicts/en/${encodeURIComponent(clean)}" target="_blank" rel="noreferrer">欧路</a>
    </div>
  `;
  $("#cardTerm").value = clean;
  $("#cardContext").value = context;
}

function lexicalLabel(item) {
  return ["entry", "wordnet", "open"].includes(item.type) ? item.headword : item.type === "query" ? item.term : item.form;
}

function lexicalSubtitle(item) {
  if (item.type === "entry") return `${item.pos} · ${item.meaning_zh}`;
  if (item.type === "wordnet") return `${item.pos} · ${item.meaning_zh || item.core_meaning}`;
  if (item.type === "open") return `${item.pos} · ${item.meaning_zh || item.core_meaning}`;
  if (item.type === "query") return `${item.kind === "phrase" ? "短语" : "单词"} · ${item.translation_zh || (item.saved ? "已在生词本" : "待补充释义")}`;
  return `${item.kind} · ${item.meaning_zh}`;
}

function matchesLexiconFilter(item) {
  if (state.lexiconFilter === "all") return true;
  if (state.lexiconFilter === "family") return ["entry", "wordnet", "open"].includes(item.type);
  if (state.lexiconFilter === "morpheme") return item.type === "morpheme";
  return item.type === "morpheme" && item.kind === state.lexiconFilter;
}

function termText(item) {
  if (typeof item === "string") return item.split("（")[0];
  return item?.term || item?.phrase || item?.form || item?.word || "";
}

function termChinese(item) {
  if (typeof item === "string") {
    const match = item.match(/（(.+)）/);
    return match?.[1] || "";
  }
  return item?.meaning_zh || "";
}

function termButtons(items, kind = "") {
  return (items || []).map(item => {
    const term = termText(item);
    const chinese = termChinese(item);
    return `<button class="term-link ${kind}" data-search-query="${escapeHtml(term)}"><strong>${escapeHtml(term)}</strong>${chinese ? `<small>${escapeHtml(chinese)}</small>` : ""}</button>`;
  }).join("");
}

function highlightLexicalText(text, item) {
  const terms = [item.headword, ...(item.forms || []), ...(item.family || [])]
    .map(termText)
    .filter(value => /^[A-Za-z][A-Za-z'-]*$/.test(value))
    .sort((a, b) => b.length - a.length);
  if (!terms.length) return escapeHtml(text);
  const escaped = terms.map(value => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const pattern = new RegExp(`\\b(${escaped.join("|")})\\b`, "gi");
  return String(text).split(pattern).map(part => terms.some(term => term.toLowerCase() === part.toLowerCase())
    ? `<strong class="query-highlight">${escapeHtml(part)}</strong>`
    : escapeHtml(part)).join("");
}

function phraseCards(items) {
  return (items || []).map(item => {
    const current = typeof item === "string" ? { phrase: item, meaning_zh: "", synonyms: [], antonyms: [] } : item;
    const source = current.source ? `${current.source}${current.observed_count ? ` · 出现 ${current.observed_count} 次` : ""}` : "";
    return `<article class="phrase-item">
      <div class="phrase-head"><div><button class="phrase-query" data-search-query="${escapeHtml(current.phrase)}"><strong>${escapeHtml(current.phrase)}</strong></button><p>${escapeHtml(current.meaning_zh || "")}</p></div><button data-save-phrase="${escapeHtml(current.phrase)}" title="加入生词本" aria-label="加入生词本">＋</button></div>
      ${source ? `<small class="phrase-source">${escapeHtml(source)}</small>` : ""}
      ${current.synonyms?.length ? `<div class="phrase-relation"><span>近义表达</span><div class="term-grid">${termButtons(current.synonyms, "synonym")}</div></div>` : ""}
      ${current.antonyms?.length ? `<div class="phrase-relation"><span>反义表达</span><div class="term-grid">${termButtons(current.antonyms, "antonym")}</div></div>` : ""}
    </article>`;
  }).join("");
}

function contextExamples(contexts) {
  return (contexts || []).map(context => `<article class="example-item">
    ${context.translation_zh ? `<p class="context-meaning">${escapeHtml(context.translation_zh)}</p>` : ""}
    <p class="example-en">${searchableEnglish(context.text)}</p>
    <p class="context-source">${escapeHtml(context.article_title || context.source)}</p>
    ${context.article_id ? `<button data-open-article="${context.article_id}">回到原文</button>` : ""}
  </article>`).join("");
}

function lexicalFrequencyPanel(item) {
  const frequency = item.frequency || item.lexical_layers?.primary_frequency;
  const corpus = item.corpus_frequency || {};
  if (!frequency && !corpus.occurrence_count) return "";
  return `
    <section class="lexical-frequency-panel" aria-label="词汇常用度">
      <div><span>通用常用度</span><strong>${frequency ? escapeHtml(frequency.frequency_band) : "待导入"}</strong><small>${frequency ? `Zipf ${Number(frequency.zipf_frequency).toFixed(2)} · ${escapeHtml(frequency.source_name || "wordfreq")}` : "尚未导入开放频率数据"}</small></div>
      <div><span>你的内容池</span><strong>${corpus.occurrence_count || 0} 次</strong><small>${corpus.article_count || 0} 篇文章出现；不冒充通用词频</small></div>
    </section>`;
}

function openExampleCards(examples, item) {
  return (examples || []).map(example => `
    <article class="example-item attributed-example">
      <p class="example-zh">${escapeHtml(example.target_text)}</p>
      <p class="example-en">${highlightLexicalText(example.source_text, item)}</p>
      <p class="context-source">${escapeHtml(example.source_name || "Tatoeba")} · ${escapeHtml(example.license)} · ${escapeHtml(example.source_author || "署名缺失")}${example.target_author ? ` / ${escapeHtml(example.target_author)}` : ""}</p>
    </article>`).join("");
}

function lexicalSources(sources) {
  return (sources || []).map(source => `<li><strong>${source.url ? `<a href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer">${escapeHtml(source.name)}</a>` : escapeHtml(source.name)}</strong><span>${escapeHtml(source.version || "")}</span><small>${escapeHtml(source.license)} · ${escapeHtml(source.attribution)}</small></li>`).join("");
}

function bilingualExamples(examples, item) {
  return (examples || []).map(example => {
    const current = typeof example === "string" ? { text: example, translation: "" } : example;
    return `<article class="example-item"><p class="example-en">${highlightLexicalText(current.text, item)}</p>${current.translation ? `<p class="example-zh">${escapeHtml(current.translation)}</p>` : ""}</article>`;
  }).join("");
}

function dialectPronunciations(values = []) {
  let uk = "";
  let us = "";
  let generic = "";
  values.forEach(value => {
    const pronunciation = typeof value === "string" ? value : (value.ipa || value.enpr || "");
    const tags = typeof value === "string" ? "" : (value.tags || []).join(" ").toLowerCase();
    if (!pronunciation) return;
    if (/\b(uk|british|rp)\b|received pronunciation/.test(tags)) uk ||= pronunciation;
    else if (/\b(us|american|ga)\b|general american/.test(tags)) us ||= pronunciation;
    else generic ||= pronunciation;
  });
  return { ipaUk: uk || generic, ipaUs: us || generic, generic: !uk && !us };
}

function pronunciationControls(term, ipaUk = "", ipaUs = "", generic = false) {
  const shared = generic && (ipaUk || ipaUs) ? `<span>通用 ${escapeHtml(ipaUk || ipaUs)}</span>` : "";
  const uk = !generic && ipaUk ? `<span>UK ${escapeHtml(ipaUk)}</span>` : "";
  const us = !generic && ipaUs ? `<span>US ${escapeHtml(ipaUs)}</span>` : "";
  return `<div class="pronunciation">${shared}${uk}<button data-speak="${escapeHtml(term)}" data-voice="en-GB" title="英式发音">▶ UK</button>${us}<button data-speak="${escapeHtml(term)}" data-voice="en-US" title="美式发音">▶ US</button></div>`;
}

function wordnetNeedsChinese(item) {
  if (!item?.headword_translation_zh) return true;
  if ((item.senses || []).some(sense =>
    (sense.definitions || []).some((_, index) => !sense.definition_translations?.[index])
    || (sense.examples || []).some((_, index) => !sense.example_translations?.[index])
  )) return true;
  const missingMeaning = values => (values || []).some(value => typeof value !== "string" && !value.meaning_zh);
  return missingMeaning(item.synonyms) || missingMeaning(item.antonyms)
    || missingMeaning(item.family) || missingMeaning(item.collocations)
    || (item.semantic_relations || []).some(relation => missingMeaning(relation.term_details || relation.terms));
}

function finalizeLexicalDetail(item) {
  const detail = $("#lexiconDetail");
  const term = lexicalLabel(item);
  const hero = detail.querySelector(".dictionary-hero");
  if (!hero || !term) return;
  let toolbar = hero.querySelector(".toolbar");
  if (!toolbar) {
    toolbar = document.createElement("div");
    toolbar.className = "toolbar";
    hero.append(toolbar);
  }
  toolbar.insertAdjacentHTML("beforeend", `
    <button data-copy-lexical="${escapeHtml(term)}" title="复制词头与当前释义">复制</button>
    <details class="external-dictionaries"><summary>更多词典</summary><div>
      <a href="https://dict.eudic.net/dicts/en/${encodeURIComponent(term)}" target="_blank" rel="noreferrer">欧路</a>
      <a href="https://dictionary.cambridge.org/dictionary/english/${encodeURIComponent(term)}" target="_blank" rel="noreferrer">Cambridge</a>
      <a href="https://www.collinsdictionary.com/dictionary/english/${encodeURIComponent(term)}" target="_blank" rel="noreferrer">Collins</a>
      <a href="https://www.merriam-webster.com/dictionary/${encodeURIComponent(term)}" target="_blank" rel="noreferrer">Merriam-Webster</a>
    </div></details>`);
  const sections = [...detail.querySelectorAll(".dictionary-section")].filter(section => section.querySelector("h3"));
  if (sections.length < 2) return;
  const links = sections.map((section, index) => {
    section.id = `lexical-section-${index}`;
    return `<button data-jump-lexical-section="${section.id}">${escapeHtml(section.querySelector("h3").textContent)}</button>`;
  }).join("");
  hero.insertAdjacentHTML("afterend", `<nav class="dictionary-section-nav" aria-label="词条分区">${links}</nav>`);
}

function renderLexicalDetail(item) {
  const detail = $("#lexiconDetail");
  if (!item) {
    detail.innerHTML = `<div class="empty-state">输入单词、中文、词根或拉丁词源开始查询。</div>`;
    return;
  }
  if (item.type === "morpheme") {
    const kindNames = { root: "词根", prefix: "前缀", suffix: "后缀" };
    detail.innerHTML = `
      <div class="dictionary-hero">
        <div><div class="badge-row">${badge(kindNames[item.kind] || item.kind, "teal")}${badge(item.matched_by || "构词成分")}</div><h2>${escapeHtml(item.form)}</h2><p class="core-definition">${escapeHtml(item.meaning_zh)}</p></div>
      </div>
      <div class="morph-origin"><span>来源</span><strong>${escapeHtml(item.origin)}</strong><p>${escapeHtml(item.note)}</p></div>
      <section class="dictionary-section"><h3>代表词</h3><div class="term-grid">${termButtons(item.examples, "family")}</div></section>
    `;
    finalizeLexicalDetail(item);
    return;
  }
  if (item.type === "query") {
    const translated = state.lookupTranslations[item.term.toLowerCase()] || item.translation_zh || "";
    detail.innerHTML = `
      <div class="dictionary-hero">
        <div><div class="badge-row">${badge(item.kind === "phrase" ? "短语" : "单词", item.kind === "phrase" ? "amber" : "teal")}${badge(item.saved ? `生词本 · ${item.card_status || "new"}` : "尚未保存")}${badge(item.matched_by)}</div><h2>${escapeHtml(item.term)}</h2>${pronunciationControls(item.term)}</div>
        <div class="toolbar"><button class="primary" data-save-lookup="${escapeHtml(item.term)}">${item.saved ? "更新生词语境" : "加入生词本"}</button>${translated ? "" : `<button data-translate-term="${escapeHtml(item.term)}">一键翻译</button>`}<a class="button-link" href="https://dict.eudic.net/dicts/en/${encodeURIComponent(item.term)}" target="_blank" rel="noreferrer">在欧路中查看</a></div>
      </div>
      <p class="core-definition">${escapeHtml(translated || "本地开放词典尚未收录完整释义。你仍可保存、翻译，并从个人文章语境继续学习。")}</p>
      <div class="dictionary-columns query-columns">
        <section class="dictionary-section"><h3>你的真实语境</h3>${item.contexts?.length ? contextExamples(item.contexts) : `<div class="empty-state">尚未在个人文章中找到这个表达。</div>`}</section>
        <section class="dictionary-section"><h3>下一步</h3><p>先确认当前语境含义，再保存整句。后续开放词典导入会补充高频义项、搭配、近义辨析和词源。</p></section>
      </div>
    `;
    finalizeLexicalDetail(item);
    return;
  }
  if (item.type === "open") {
    const layers = item.lexical_layers || {};
    const pronunciation = dialectPronunciations(layers.pronunciations || []);
    detail.innerHTML = `
      <div class="dictionary-hero">
        <div><div class="badge-row">${badge(item.source_name || "开放词典", "teal")}${badge(item.pos || "词条")}${layers.primary_frequency ? badge(layers.primary_frequency.frequency_band, "amber") : ""}</div><h2>${escapeHtml(item.headword)}</h2>${pronunciationControls(item.headword, pronunciation.ipaUk, pronunciation.ipaUs, pronunciation.generic)}</div>
        <div class="toolbar"><button class="primary" data-save-lookup="${escapeHtml(item.headword)}">加入生词本</button><a class="button-link" href="https://dict.eudic.net/dicts/en/${encodeURIComponent(item.headword)}" target="_blank" rel="noreferrer">在欧路中查看</a></div>
      </div>
      ${item.meaning_zh ? `<p class="headword-translation">${escapeHtml(item.meaning_zh)}</p>` : ""}
      <p class="core-definition">${escapeHtml(item.core_meaning || "暂无英文概念释义")}</p>
      ${lexicalFrequencyPanel(item)}
      <div class="dictionary-columns">
        <section class="dictionary-section"><h3>开放义项</h3><div class="sense-list">${(layers.entries || []).map(entry => `<article class="sense-item"><div class="sense-head"><strong>${escapeHtml(entry.pos || "词性未标")}</strong></div>${(entry.translations_zh || []).map(value => `<p class="sense-meaning">${escapeHtml(value)}</p>`).join("")}${(entry.glosses || []).map(value => `<p class="sense-definition-en">${escapeHtml(value)}</p>`).join("")}</article>`).join("")}</div></section>
        <section class="dictionary-section"><h3>词形与派生</h3><div class="term-grid">${termButtons(layers.forms || [], "family")}</div></section>
        <section class="dictionary-section"><h3>词源</h3>${(layers.etymologies || []).map(value => `<p class="etymology-text">${escapeHtml(value)}</p>`).join("") || `<div class="empty-state">当前开放词条没有词源记录</div>`}</section>
        <section class="dictionary-section"><h3>开放双语例句</h3>${openExampleCards(layers.examples, item) || `<div class="empty-state">尚未导入匹配句对</div>`}</section>
      </div>
      <details class="lexical-source-disclosure"><summary>数据来源与许可证</summary><ul>${lexicalSources(layers.sources)}</ul></details>
    `;
    finalizeLexicalDetail(item);
    return;
  }
  if (item.type === "wordnet") {
    const translated = state.lookupTranslations[item.headword.toLowerCase()] || item.meaning_zh || "";
    const relationSections = (item.semantic_relations || []).map(relation => `
      <div class="phrase-relation"><span>${escapeHtml(relation.label)}</span><div class="term-grid">${termButtons(relation.terms, relation.type === "antonym" ? "antonym" : "family")}</div></div>
    `).join("");
    detail.innerHTML = `
      <div class="dictionary-hero">
        <div><div class="badge-row">${badge("WordNet", "teal")}${badge(item.pos)}${badge(item.source_version || "2025")}${item.frequency ? badge(item.frequency.frequency_band, "amber") : ""}</div><h2>${escapeHtml(item.headword)}</h2>${pronunciationControls(item.headword, item.ipa_uk, item.ipa_us, item.pronunciation_scope === "generic")}</div>
        <div class="toolbar"><button class="primary" data-save-lookup="${escapeHtml(item.headword)}">${item.saved ? "更新生词语境" : "加入生词本"}</button>${item.headword_translation_zh ? "" : `<button data-translate-wordnet="${item.id}">翻译中文义项</button>`}<a class="button-link" href="https://dict.eudic.net/dicts/en/${encodeURIComponent(item.headword)}" target="_blank" rel="noreferrer">在欧路中查看</a></div>
      </div>
      ${translated ? `<p class="headword-translation">${escapeHtml(translated)}</p>` : `<p class="muted">${state.bridge?.translation?.verified === false ? escapeHtml(state.bridge.translation.last_error || "中文翻译服务验证失败，请检查 API 配置。") : "正在补齐中文义项；结果会缓存到本地。"}</p>`}
      <p class="core-definition">${escapeHtml(item.core_meaning || "")}</p>
      ${lexicalFrequencyPanel(item)}
      <div class="dictionary-columns">
        <section class="dictionary-section"><h3>义项与例句</h3><div class="sense-list">${(item.senses || []).map((sense, index) => `<article class="sense-item"><div class="sense-head"><strong>义项 ${index + 1}</strong>${sense.pos ? badge(sense.pos) : ""}</div>${(sense.definitions || []).map((definition, definitionIndex) => `${sense.definition_translations?.[definitionIndex] ? `<p class="sense-meaning">${escapeHtml(sense.definition_translations[definitionIndex])}</p>` : `<p class="muted">中文义项待翻译</p>`}<p class="sense-definition-en">${escapeHtml(definition)}</p>`).join("")}${(sense.examples || []).length ? `<div class="sense-examples">${(sense.examples || []).map((example, exampleIndex) => `<article>${sense.example_translations?.[exampleIndex] ? `<p class="example-zh">${escapeHtml(sense.example_translations[exampleIndex])}</p>` : `<p class="muted">例句译文待翻译</p>`}<p class="example-en">${searchableEnglish(example)}</p></article>`).join("")}</div>` : `<p class="muted">该义项暂无开放例句</p>`}</article>`).join("") || `<div class="empty-state">暂无义项</div>`}</div>${item.contexts?.length ? `<div class="supplemental-contexts"><h4>补充真实语境（未按义项归类）</h4>${contextExamples(item.contexts)}</div>` : ""}</section>
        <section class="dictionary-section"><h3>搭配（按个人语料排序）</h3><div class="phrase-list">${phraseCards(item.collocations) || `<div class="empty-state">个人语料中暂无可确认搭配；后续开放搭配词典会补充常见表达。</div>`}</div></section>
        <section class="dictionary-section"><h3>近义词</h3><div class="term-grid">${termButtons(item.synonyms, "synonym") || `<div class="empty-state">WordNet 未提供近义词</div>`}</div><h4>反义词</h4><div class="term-grid">${termButtons(item.antonyms, "antonym") || `<div class="empty-state">WordNet 未提供直接反义词</div>`}</div></section>
        <section class="dictionary-section"><h3>语义关系</h3>${relationSections || `<div class="empty-state">暂无关系数据</div>`}<p class="source-note">英文语义：${escapeHtml(item.source_name || "Open English WordNet")} · ${escapeHtml(item.license || "CC BY 4.0")}<br>中文：开放双语数据或本地翻译缓存；机器翻译不冒充出版词典释义。</p></section>
        <section class="dictionary-section"><h3>词形与开放词源</h3><div class="term-grid">${termButtons(item.forms || [], "family")}</div>${item.origin ? `<p class="etymology-text">${escapeHtml(item.origin)}</p>` : `<p class="muted">导入 Kaikki 精选词条后显示词源与更多词形。</p>`}</section>
        <section class="dictionary-section"><h3>开放双语例句</h3>${openExampleCards(item.open_examples, item) || `<div class="empty-state">导入 Tatoeba 英汉句对后显示署名例句。</div>`}</section>
      </div>
      ${item.open_sources?.length ? `<details class="lexical-source-disclosure"><summary>数据来源与许可证</summary><ul>${lexicalSources(item.open_sources)}</ul></details>` : ""}
    `;
    finalizeLexicalDetail(item);
    return;
  }
  const saved = state.cards.some(card => card.term.toLowerCase() === item.headword.toLowerCase());
  detail.innerHTML = `
    <div class="dictionary-hero">
      <div><div class="badge-row">${badge(item.level || "词条", "teal")}${badge(item.pos)}${badge(item.register_label)}</div><h2>${escapeHtml(item.headword)}</h2>${pronunciationControls(item.headword, item.ipa_uk, item.ipa_us)}</div>
      <div class="toolbar"><button class="primary" data-save-lookup="${escapeHtml(item.headword)}">${saved ? "更新生词语境" : "加入生词本"}</button><a class="button-link" href="https://dict.eudic.net/dicts/en/${encodeURIComponent(item.headword)}" target="_blank" rel="noreferrer">欧路</a></div>
    </div>
    <p class="core-definition">${escapeHtml(item.core_meaning)}</p><p class="zh-definition">${escapeHtml(item.meaning_zh)}</p>
    <div class="morph-origin"><span>构词拆解</span><strong>${escapeHtml(item.breakdown)}</strong><p>${escapeHtml(item.origin)}</p></div>
    <div class="dictionary-columns">
      <section class="dictionary-section"><h3>词形与词族</h3><div class="term-grid">${termButtons(item.forms)}${termButtons(item.family, "family")}</div></section>
      <section class="dictionary-section phrase-section"><h3>词组与搭配</h3><div class="phrase-list">${phraseCards(item.collocations)}</div></section>
      <section class="dictionary-section"><h3>近义词辨析</h3><div class="term-grid">${termButtons(item.synonyms, "synonym")}</div>${item.antonyms?.length ? `<h4>反义词</h4><div class="term-grid">${termButtons(item.antonyms)}</div>` : ""}</section>
      <section class="dictionary-section"><h3>真实语境</h3><div class="example-list">${bilingualExamples(item.examples, item)}</div></section>
    </div>
  `;
  finalizeLexicalDetail(item);
}

function renderLexiconGuidance() {
  const panel = $("#lexiconGuidance");
  const resolution = state.lexiconMeta.resolution;
  const suggestions = state.lexiconMeta.suggestions || [];
  panel.hidden = !resolution && !suggestions.length;
  panel.innerHTML = resolution
    ? `<span>已识别词形</span><button data-search-query="${escapeHtml(resolution.to)}"><strong>${escapeHtml(resolution.from)}</strong> → ${escapeHtml(resolution.to)}</button>`
    : suggestions.length
      ? `<span>你是不是想查</span><div>${suggestions.map(term => `<button data-search-query="${escapeHtml(term)}">${escapeHtml(term)}</button>`).join("")}</div>`
      : "";
}

function renderLexiconHistory() {
  const panel = $("#lexiconHistory");
  const items = state.lexiconHistory.recent || [];
  panel.innerHTML = items.length ? `
    <div class="history-query-list">${items.slice(0, 12).map(item => `<button data-search-query="${escapeHtml(item.query)}"><span>${escapeHtml(item.query)}</span>${item.lookup_count > 1 ? `<small>${item.lookup_count} 次</small>` : ""}</button>`).join("")}</div>
    <button class="text-action" id="clearLexiconHistoryBtn">清空本机记录</button>` : `<p class="muted">完整查词后会保存在本机，快速联想不计入。</p>`;
}

function renderLexicon() {
  document.querySelectorAll(".lexicon-tab").forEach(tab => tab.classList.toggle("active", tab.dataset.lexiconTab === state.lexiconFilter));
  const filtered = state.lexiconResults.filter(matchesLexiconFilter);
  if (!filtered.some(item => item.type === state.selectedLexicalItem?.type && item.id === state.selectedLexicalItem?.id)) {
    state.selectedLexicalItem = filtered[0] || null;
  }
  $("#lexiconResultCount").textContent = filtered.length;
  $("#lexiconResultList").innerHTML = filtered.map((item, index) => `
    <button class="master-list-item ${item.type === state.selectedLexicalItem?.type && item.id === state.selectedLexicalItem?.id ? "active" : ""}" data-lexical-type="${item.type}" data-lexical-id="${item.id}">
      <span class="master-number">${String(index + 1).padStart(2, "0")}</span><span class="master-copy"><strong>${escapeHtml(lexicalLabel(item))}</strong><small>${escapeHtml(lexicalSubtitle(item))}</small><em>${escapeHtml(item.matched_by || "")}</em></span>
    </button>`).join("") || `<div class="empty-state">没有匹配结果，换一个词形或中文含义试试。</div>`;
  $("#lexicalDataStatus").innerHTML = (state.lexicalDataStatus.layers || []).map(layer => `
    <div class="lexical-layer-row ${layer.installed ? "installed" : "missing"}">
      <span>${escapeHtml(layer.label)}</span><strong>${layer.installed ? Number(layer.count).toLocaleString("zh-CN") : "未导入"}</strong>
    </div>`).join("");
  renderLexiconGuidance();
  renderLexiconHistory();
  renderLexicalDetail(state.selectedLexicalItem);
}

async function loadDictionaryStatus() {
  const data = await api("/api/dictionary/status");
  state.lexicalDataStatus = data;
}

async function loadLexiconHistory() {
  state.lexiconHistory = await api("/api/lexicon/history");
}

async function clearLexiconHistory() {
  state.lexiconHistory = await api("/api/lexicon/history/clear", { method: "POST", body: "{}" });
  renderLexiconHistory();
  toast("本机查词记录已清空");
}

async function searchLexicon(query, { open = true, quick = false, history = true, track = true } = {}) {
  const value = String(query || "").trim();
  const data = await api(`/api/lexicon/search?q=${encodeURIComponent(value)}${quick || !track || !value ? "" : "&track=1"}`);
  if (quick) {
    renderQuickResults(data.results || [], value);
    return data.results || [];
  }
  state.lexiconResults = data.results || [];
  state.lexiconMeta = { resolution: data.resolution || null, suggestions: data.suggestions || [] };
  state.selectedLexicalItem = state.lexiconResults[0] || null;
  $("#lexiconSearch").value = value;
  $("#globalLexiconSearch").value = value;
  if (open) setView("lexicon", { pushHistory: false });
  if (!quick && history) {
    const params = new URLSearchParams(window.location.search);
    const currentQuery = params.get("q") || "";
    if (params.get("view") !== "lexicon" || currentQuery !== value) {
      params.set("view", "lexicon");
      value ? params.set("q", value) : params.delete("q");
      window.history.pushState({ view: "lexicon", q: value }, "", `${window.location.pathname}?${params.toString()}`);
    }
  }
  renderLexicon();
  if (value) {
    await loadLexiconHistory();
    renderLexiconHistory();
  }
  const wordnet = state.lexiconResults.find(item => item.type === "wordnet" && wordnetNeedsChinese(item));
  if (wordnet && state.bridge?.translation?.verified === true && !state.wordnetAutoTranslationFailed) {
    await translateWordNetEntry(wordnet, { silent: true }).catch(error => {
      state.wordnetAutoTranslationFailed = true;
      toast(error.message);
    });
  }
  return state.lexiconResults;
}

function renderQuickResults(results, query) {
  const panel = $("#quickLexiconResults");
  const items = results.slice(0, 4);
  panel.hidden = false;
  panel.innerHTML = items.length ? `${items.map(item => `<button data-search-query="${escapeHtml(lexicalLabel(item))}" data-open-lexicon="true"><strong>${escapeHtml(lexicalLabel(item))}</strong><span>${escapeHtml(lexicalSubtitle(item))}</span></button>`).join("")}<button class="quick-more" data-search-query="${escapeHtml(query)}" data-open-lexicon="true">查看全部结果</button>` : `<div class="quick-empty">没有可查询内容</div>`;
}

function speak(text, lang = "en-US") {
  speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = lang;
  speechSynthesis.speak(utterance);
}

function fallbackMistakeExplanation(item) {
  const type = item.quiz_type || item.type || "reading";
  const answer = item.answer || "";
  const selected = item.user_answer || "";
  const guides = {
    reading: ["证据定位与同义替换", "正确答案必须与证据句保持同一个主体、动作、范围和语气强度。", ["圈出题干主体和限定词", "回原文定位同义表达", "排除范围、方向或因果被改动的选项"]],
    "main-idea": ["主旨概括与信息层级", "正确答案覆盖核心对象和主要观点，不会只抓一个例子，也不会扩大原文结论。", ["概括每句功能", "区分主旨和支持细节", "选择覆盖完整且措辞不过强的选项"]],
    paraphrase: ["句意改写与逻辑保真", "正确改写保留原句逻辑、条件和态度，只改变表达方式。", ["拆出句子主干", "标记转折、因果和条件", "核对改写是否改变语气和方向"]],
    cloze: ["语境词义、词性与搭配", `把 ${answer} 放回空格后，词义、词性和上下文搭配能够同时成立。`, ["判断空格词性", "读取前后搭配", "用整句含义排除近义干扰词"]],
    initial: ["语境提取与完整拼写", `语境、首字母和词长共同指向 ${answer}。`, ["根据句意回忆目标词", "用首字母和词长核对", "检查词形和拼写"]],
  };
  const guide = guides[type] || guides.reading;
  const lower = selected.toLowerCase();
  let trap = "语义相近但逻辑不等价";
  let whyWrong = "你的答案与主题相关，但没有完整保留证据中的主体、范围、条件或逻辑关系。";
  if (!selected) {
    trap = "未作答";
    whyWrong = "先写出一个候选答案，再用原文证据排除，比直接跳过更能暴露判断卡点。";
  } else if (["cloze", "initial"].includes(type)) {
    trap = "词义或词形未同时满足";
    whyWrong = `${selected} 放回原句后，在语境、词性、搭配或拼写上不能全部成立。`;
  } else if (["only", "all", "never", "broader", "stronger"].some(word => lower.includes(word))) {
    trap = "范围扩大或措辞过强";
    whyWrong = "这个答案把原文有限、带条件的表达改成了更绝对的结论。";
  } else if (["detail", "example", "minor", "narrow"].some(word => lower.includes(word))) {
    trap = "用细节冒充主旨";
    whyWrong = "这个答案可能对应一个细节，但覆盖不了题目要求的中心观点。";
  }
  return {
    test_point: item.quiz_note || item.note || guide[0],
    trap,
    why_wrong: whyWrong,
    why_correct: guide[1],
    evidence: item.evidence || "",
    evidence_guide: "确认谁做什么，再核对否定、转折、因果、程度词和范围词。",
    steps: guide[2],
    retry: `遮住答案，把“${answer}”换成自己的话复述一次，再重新作答。`,
  };
}

function explanationHtml(explanation, compact = false, correct = false, replayArticleId = null) {
  if (!explanation) return "";
  const steps = explanation.steps || [];
  const options = explanation.option_analysis || [];
  const signals = explanation.location_signals || {};
  return `
    <div class="explanation-panel ${compact ? "compact" : ""}">
      <div class="explanation-title">
        <strong>${correct ? "答题解析" : "错题讲解"}</strong>
        <div class="badge-row">
          ${badge(explanation.test_point || "语境判断", "teal")}
          ${!correct ? badge(explanation.trap || "干扰项", "amber") : ""}
        </div>
      </div>
      <div class="explanation-grid">
        ${!correct ? `
          <section class="wrong-reason">
            <h4>为什么错</h4>
            <p>${escapeHtml(explanation.why_wrong || "")}</p>
          </section>
        ` : ""}
        <section class="correct-reason">
          <h4>为什么对</h4>
          <p>${escapeHtml(explanation.why_correct || "")}</p>
        </section>
      </div>
      ${options.length ? `
        <details class="option-analysis" ${compact ? "" : "open"}>
          <summary>逐项排除：${options.length} 个选项</summary>
          <div class="option-analysis-list">
            ${options.map(item => `
              <div class="option-analysis-row ${escapeHtml(item.status || "distractor")}">
                <strong>${searchableEnglish(item.option || "")}</strong>
                <p>${escapeHtml(item.reason || "")}</p>
              </div>
            `).join("")}
          </div>
        </details>
      ` : ""}
      ${signals.locator ? `
        <div class="location-signals">
          <strong>定位与同义替换</strong>
          <p>${signals.shared_terms?.length ? `共同定位词：${escapeHtml(signals.locator)}` : escapeHtml(signals.locator)}</p>
          <small>检查点：${escapeHtml(signals.paraphrase_check || explanation.test_point || "主体、范围与逻辑关系")}</small>
        </div>
      ` : ""}
      ${compact && explanation.evidence && replayArticleId ? `<button class="evidence-replay-compact" data-replay-evidence="${replayArticleId}" data-replay-text="${escapeHtml(explanation.evidence)}">回到原文证据</button>` : ""}
      ${!compact ? `
        <div class="evidence-box">
          <span>原文证据</span>
          <p class="quiz-evidence-text">${searchableEnglish(explanation.evidence || "暂无证据句")}</p>
          <small>${escapeHtml(explanation.evidence_guide || "")}</small>
          ${explanation.evidence && replayArticleId ? `<button data-replay-evidence="${replayArticleId}" data-replay-text="${escapeHtml(explanation.evidence)}">回到原文并高亮</button>` : ""}
        </div>
        <div class="method-block">
          <strong>下次这样做</strong>
          <ol>${steps.map(step => `<li>${escapeHtml(step)}</li>`).join("")}</ol>
          <p class="retry-line">${escapeHtml(explanation.retry || "")}</p>
        </div>
      ` : ""}
    </div>
  `;
}

function quizResultHtml(result) {
  if (!result) return "";
  const session = result.session || result;
  const total = session.question_count || state.quizzes.length;
  const correct = session.correct_count || 0;
  const answered = session.answered_count ?? Object.values(state.quizSession.answers).filter(Boolean).length;
  const skills = session.skill_summary || {};
  const errors = session.error_summary || {};
  const confidence = session.confidence_summary || {};
  return `
    <div class="result-overview">
      <div><span>正确率</span><strong>${session.score ?? Math.round(correct / Math.max(1, total) * 100)}%</strong></div>
      <div><span>答对</span><strong>${correct}/${total}</strong></div>
      <div><span>完成</span><strong>${answered}/${total}</strong></div>
      <div><span>用时</span><strong>${formatDuration(session.elapsed_seconds ?? quizElapsedSeconds())}</strong></div>
    </div>
    <div class="result-diagnosis">
      <div>
        <h3>能力表现</h3>
        ${Object.entries(skills).map(([skill, stats]) => `
          <div class="diagnosis-row"><span>${escapeHtml(skill)}</span><strong>${stats.correct}/${stats.total}</strong></div>
        `).join("") || `<p class="muted">完成更多题目后生成能力统计。</p>`}
      </div>
      <div>
        <h3>需要复盘</h3>
        ${Object.entries(errors).map(([error, count]) => `
          <div class="diagnosis-row"><span>${escapeHtml(error)}</span><strong>${count} 题</strong></div>
        `).join("") || `<p class="muted">本轮没有记录到错因。</p>`}
      </div>
      <div>
        <h3>信心校准</h3>
        ${Object.entries(confidence).map(([label, stats]) => `
          <div class="diagnosis-row"><span>${escapeHtml(label)}</span><strong>${stats.correct}/${stats.total}</strong></div>
        `).join("") || `<p class="muted">作答时选择信心后，这里会区分“会做”和“蒙对”。</p>`}
        ${confidence.确定 && confidence.确定.total > confidence.确定.correct ? `<p class="calibration-note">有 ${confidence.确定.total - confidence.确定.correct} 道“确定但答错”，优先复盘。</p>` : ""}
      </div>
    </div>
    <div class="toolbar result-actions">
      ${Object.keys(errors).length ? `<button data-view-jump="mistakes">查看错题解析</button>` : ""}
      ${state.quizzes[0]?.question_type ? `<button data-next-set-type-only="${escapeHtml(state.quizzes[0].question_type)}">只练本题型</button>` : ""}
      ${Object.entries(errors).filter(([error]) => error !== "未作答").map(([error]) => `<button data-next-set-error="${escapeHtml(error)}" data-next-set-type="${escapeHtml(state.quizzes[0]?.question_type || "")}">继续练：${escapeHtml(error)}</button>`).join("")}
      <button data-next-set="true">下一组 10 题</button>
      <button data-retry-session="true">再练一次</button>
    </div>
  `;
}

function renderQuizzes() {
  const session = state.quizSession;
  updateQuizScopeControls();
  const answered = state.quizzes.filter(quiz => String(session.answers[quiz.id] || "").trim()).length;
  const flagged = state.quizzes.filter(quiz => session.flagged[quiz.id]).length;
  const validated = state.quizzes.filter(quiz => quiz.validation?.valid).length;
  const activeType = state.quizzes[0]?.question_type || $("#quizPracticeType")?.value || "";
  const typeLabel = state.examTypes.find(item => item.id === activeType)?.label || activeType || "当前训练";
  const scope = $("#quizScope")?.value || "specialty";
  const scopeLabel = scope === "full-paper" ? "整套模拟" : scope === "passage" ? "单篇组合" : typeLabel;
  session.activeIndex = Math.max(0, Math.min(session.activeIndex, Math.max(0, state.quizzes.length - 1)));
  $("#quizSessionMode").value = session.mode;
  $("#finishQuizSessionBtn").textContent = session.mode === "mock" ? "交卷" : "结束训练";
  $("#finishQuizSessionBtn").disabled = !state.quizzes.length || session.submitted;
  document.querySelectorAll("[data-quiz-display]").forEach(button => {
    button.classList.toggle("active", button.dataset.quizDisplay === session.display);
  });
  $("#quizSessionSummary").innerHTML = `
    <div><span>训练范围</span><strong>${escapeHtml(scopeLabel)}</strong></div>
    <div><span>进度</span><strong>${answered}/${state.quizzes.length}</strong></div>
    <div><span>标记</span><strong>${flagged}</strong></div>
    <div><span>题目校验</span><strong>${validated}/${state.quizzes.length}</strong></div>
  `;
  $("#quizTimer").textContent = formatDuration(quizElapsedSeconds());
  $("#quizNavigator").innerHTML = state.quizzes.map((quiz, index) => {
    const feedback = state.answerFeedback[quiz.id];
    const status = feedback ? (feedback.correct ? "correct" : "wrong") : session.answers[quiz.id] ? "answered" : "unanswered";
    return `<button class="quiz-nav-button ${status} ${session.flagged[quiz.id] ? "flagged" : ""} ${index === session.activeIndex ? "active" : ""}" data-quiz-nav="${index}" title="第 ${index + 1} 题">${index + 1}</button>`;
  }).join("");
  const resultPanel = $("#quizSessionResult");
  resultPanel.hidden = !session.result;
  resultPanel.innerHTML = quizResultHtml(session.result);
  const visible = session.display === "single"
    ? state.quizzes.map((quiz, index) => ({ quiz, index })).filter(item => item.index === session.activeIndex)
    : state.quizzes.map((quiz, index) => ({ quiz, index }));
  $("#quizList").innerHTML = visible.map(({ quiz, index }) => {
    if (!session.questionStartedAt[quiz.id]) session.questionStartedAt[quiz.id] = Date.now();
    const feedback = state.answerFeedback[quiz.id];
    const selected = session.answers[quiz.id] || feedback?.userAnswer || "";
    const confidence = session.confidence[quiz.id] || feedback?.confidence || 0;
    const locked = Boolean(feedback || session.submitted);
    return `
    <div class="item quiz-item" data-quiz-card="${quiz.id}">
      <div class="quiz-item-head">
        <div class="badge-row">
          ${badge(`${index + 1}/${state.quizzes.length}`, "teal")}
          ${badge(quiz.question_type || quiz.type)}
          ${quiz.skill ? badge(quiz.skill) : ""}
          ${quiz.difficulty ? badge(quiz.difficulty, "amber") : ""}
          ${quiz.validation?.valid ? badge("证据已校验", "teal") : ""}
        </div>
        <button class="flag-button ${session.flagged[quiz.id] ? "active" : ""}" data-flag-quiz="${quiz.id}" aria-pressed="${Boolean(session.flagged[quiz.id])}">${session.flagged[quiz.id] ? "已标记" : "标记"}</button>
      </div>
      <h3>${index + 1}. ${searchableEnglish(quiz.prompt)}</h3>
      <div class="confidence-picker" aria-label="答题信心">
        <span>答题信心</span>
        ${[[1, "猜测"], [2, "犹豫"], [3, "确定"]].map(([value, label]) => `<button class="confidence-button ${Number(confidence) === value ? "active" : ""}" data-confidence-quiz="${quiz.id}" data-confidence="${value}" ${locked ? "disabled" : ""}>${label}</button>`).join("")}
      </div>
      <div class="quiz-hint-row">
        <button data-toggle-quiz-hint="${quiz.id}" ${locked ? "disabled" : ""}>定位提示</button>
        ${session.hintUsed[quiz.id] ? `<span>先锁定主体和限定词，再比较证据中的同义表达；提示不会显示答案。</span>` : ""}
      </div>
      ${(quiz.options || []).length ? `
        <div class="options">
          ${quiz.options.map(option => {
            const answerClass = feedback && option === quiz.answer ? "correct" : feedback && option === feedback.userAnswer && !feedback.correct ? "wrong" : !feedback && option === selected ? "selected" : "";
            return `<button class="option ${answerClass}" data-select-quiz-answer="${quiz.id}" data-answer="${escapeHtml(option)}" ${locked ? "disabled" : ""}>${searchableEnglish(option, false)}</button>`;
          }).join("")}
        </div>
      ` : `
        <div class="answer-row">
          <input data-typed-quiz="${quiz.id}" value="${escapeHtml(selected)}" placeholder="${quiz.question_type === "complete-words" ? "输入完整单词" : "输入完整答案"}" autocomplete="off" spellcheck="false" ${locked ? "disabled" : ""} />
          ${session.mode === "practice" && !locked ? `<button data-submit-typed="${quiz.id}">确认答案</button>` : ""}
        </div>
      `}
      ${state.showAnswers && (session.mode === "practice" || session.submitted) ? `
        <div class="answer-box">
          <strong>Answer:</strong> ${escapeHtml(quiz.answer)}<br>
          <strong>Evidence:</strong> ${escapeHtml(quiz.evidence || "")}
        </div>
      ` : ""}
      ${feedback ? explanationHtml(feedback.explanation, true, feedback.correct, quiz.article_id) : ""}
      ${session.display === "single" ? `
        <div class="quiz-step-actions">
          <button data-quiz-nav="${Math.max(0, index - 1)}" ${index === 0 ? "disabled" : ""}>上一题</button>
          <span>${selected ? "已作答" : "尚未作答"}${session.flagged[quiz.id] ? " · 已标记" : ""}</span>
          <button data-quiz-nav="${Math.min(state.quizzes.length - 1, index + 1)}" ${index === state.quizzes.length - 1 ? "disabled" : ""}>下一题</button>
        </div>
      ` : ""}
    </div>
  `;
  }).join("") || `<div class="item muted">暂无题目</div>`;
  if (state.quizDraftRestored) {
    state.quizDraftRestored = false;
    toast("已恢复上次未完成训练");
  }
  persistQuizDraft();
}

function renderCards() {
  $("#cardList").innerHTML = state.cards.map(card => `
    <div class="item">
      <div class="badge-row">${badge(card.kind === "phrase" ? "短语" : "单词", card.kind === "phrase" ? "amber" : "teal")}${badge(reviewStateLabel(card.review_state || card.status || "new"))}</div>
      <h3><button class="card-term-link" data-search-query="${escapeHtml(card.term)}">${escapeHtml(card.term)}</button></h3>
      <p>${card.context ? searchableEnglish(card.context) : "尚未保存语境"}</p>
      ${card.note ? `<p>${escapeHtml(card.note)}</p>` : ""}
      <div class="toolbar"><button data-search-query="${escapeHtml(card.term)}" data-open-lexicon="true">查看查询</button>${card.source_article_id ? `<button data-open-article="${card.source_article_id}">回到原文</button>` : ""}<a class="button-link" href="https://dict.eudic.net/dicts/en/${encodeURIComponent(card.term)}" target="_blank" rel="noreferrer">欧路</a></div>
    </div>
  `).join("") || `<div class="item muted">暂无生词</div>`;
}

function reviewStateLabel(stateName) {
  return { new: "新项目", learning: "学习中", review: "复习", relearning: "重学" }[stateName] || stateName;
}

function renderReviews() {
  const data = state.reviews || { items: [], summary: {} };
  const items = data.items || [];
  const summary = data.summary || {};
  document.querySelectorAll("[data-review-kind]").forEach(button => {
    button.classList.toggle("active", button.dataset.reviewKind === state.reviewKind);
  });
  $("#reviewDueCount").textContent = summary.due || 0;
  $("#undoReviewBtn").disabled = !state.canUndoReview;
  $("#reviewSummary").innerHTML = `
    <div><span>今日到期</span><strong>${summary.due || 0}</strong></div>
    <div><span>新项目</span><strong>${summary.new || 0}</strong></div>
    <div><span>学习 / 重学</span><strong>${(summary.learning || 0) + (summary.relearning || 0)}</strong></div>
    <div><span>长期复习</span><strong>${summary.review || 0}</strong></div>`;
  if (!items.some(item => item.id === state.selectedReviewId)) {
    state.selectedReviewId = items[0]?.id || null;
    state.reviewAnswerRevealed = false;
  }
  const selected = items.find(item => item.id === state.selectedReviewId);
  $("#reviewQueue").innerHTML = items.map((item, index) => `
    <button class="master-list-item ${item.id === state.selectedReviewId ? "active" : ""}" data-select-review="${item.id}">
      <span class="master-number">${String(index + 1).padStart(2, "0")}</span>
      <span class="master-copy"><strong>${escapeHtml(excerpt(item.front, 58))}</strong><small>${escapeHtml(item.kind === "mistake" ? "已掌握错题" : item.kind === "phrase" ? "短语" : "单词")} · ${escapeHtml(reviewStateLabel(item.state))}</small><em>${item.lapses ? `遗忘 ${item.lapses} 次` : item.repetitions ? `已复习 ${item.repetitions} 次` : "首次复习"}</em></span>
    </button>`).join("") || `<div class="empty-state">当前没有到期项目</div>`;
  const detail = $("#reviewDetail");
  if (!selected) {
    detail.innerHTML = `<div class="review-complete"><span class="eyebrow">Queue complete</span><h2>本轮复习完成</h2><p>${summary.next_due ? `下一项预计 ${escapeHtml(formatDateTime(summary.next_due))} 到期。` : "保存新的单词、短语或掌握错题后，它们会自动进入记忆队列。"}</p></div>`;
    return;
  }
  detail.innerHTML = `
    <div class="review-card-head"><div><div class="badge-row">${badge(selected.kind === "mistake" ? "错题" : selected.kind === "phrase" ? "短语" : "单词", selected.kind === "phrase" ? "amber" : "teal")}${badge(reviewStateLabel(selected.state))}</div><h2>${escapeHtml(selected.front)}</h2></div><span class="review-position">${items.findIndex(item => item.id === selected.id) + 1} / ${items.length}</span></div>
    ${state.reviewAnswerRevealed ? `
      <section class="review-answer"><span>答案与语境</span><p>${searchableEnglish(selected.answer, false)}</p>${selected.context && selected.context !== selected.answer ? `<blockquote>${searchableEnglish(selected.context, false)}</blockquote>` : ""}${selected.note ? `<small>${escapeHtml(selected.note)}</small>` : ""}</section>
      <div class="review-rating-grid">${(selected.choices || []).map(choice => `<button class="review-rating ${choice.rating}" data-rate-review="${choice.rating}" data-review-id="${selected.id}"><strong>${escapeHtml(choice.label)}</strong><small>${escapeHtml(choice.interval)}</small></button>`).join("")}</div>
      <div class="toolbar review-source-actions">${selected.kind === "mistake" ? "" : `<button data-search-query="${escapeHtml(selected.front)}" data-open-lexicon="true">查词</button>`}${selected.source_article_id ? `<button data-open-article="${selected.source_article_id}">回到原文</button>` : ""}</div>`
      : `<div class="review-recall"><p>${selected.kind === "mistake" ? "先重新作答并回想原文证据。" : "回想含义、搭配和原句，再查看答案。"}</p><button class="primary" id="revealReviewAnswerBtn">显示答案</button></div>`}
  `;
}

function remedialQuizHtml(quiz, index) {
  const feedback = state.answerFeedback[quiz.id];
  return `
    <div class="remedial-item">
      <div class="badge-row">${badge(`练习 ${index + 1}`, "teal")}${badge(quiz.type)}</div>
      <h4>${escapeHtml(quiz.prompt)}</h4>
      ${(quiz.options || []).length ? `
        <div class="options">
          ${quiz.options.map(option => {
            const answerClass = feedback && option === quiz.answer ? "correct" : feedback && option === feedback.userAnswer && !feedback.correct ? "wrong" : "";
            return `<button class="option ${answerClass}" data-answer-quiz="${quiz.id}" data-answer="${escapeHtml(option)}">${escapeHtml(option)}</button>`;
          }).join("")}
        </div>
      ` : `
        <div class="answer-row">
          <input data-typed-quiz="${quiz.id}" placeholder="输入完整答案" />
          <button data-submit-typed="${quiz.id}">提交</button>
        </div>
      `}
      ${feedback ? explanationHtml(feedback.explanation, true, feedback.correct) : ""}
    </div>
  `;
}

function renderMistakes() {
  const list = $("#mistakeList");
  const coach = $("#mistakeCoach");
  if (!state.mistakes.length) {
    list.innerHTML = `<div class="empty-state">暂无错题</div>`;
    coach.innerHTML = `<div class="empty-state">完成题目后，错题会在这里进行实时讲解。</div>`;
    return;
  }
  if (!state.mistakes.some(item => item.id === state.selectedMistakeId)) {
    state.selectedMistakeId = (state.mistakes.find(item => !item.solved) || state.mistakes[0]).id;
  }
  const selected = state.mistakes.find(item => item.id === state.selectedMistakeId);
  const explanation = selected.explanation || fallbackMistakeExplanation(selected);
  const similar = state.similarByMistake[selected.id] || [];

  list.innerHTML = state.mistakes.map((item, index) => `
    <button class="master-list-item ${item.id === selected.id ? "active" : ""}" data-select-mistake="${item.id}">
      <span class="master-number">${String(index + 1).padStart(2, "0")}</span>
      <span class="master-copy">
        <strong>${escapeHtml(excerpt(item.prompt, 72))}</strong>
        <small>${escapeHtml(item.question_type || item.quiz_type || "阅读理解")} · ${escapeHtml(item.error_type || item.skill || "待诊断")} · ${item.solved ? "已懂" : "待学"}</small>
      </span>
    </button>
  `).join("");

  coach.innerHTML = `
    <div class="detail-head">
      <div>
        <div class="badge-row">${badge(selected.solved ? "已掌握" : "正在讲解", selected.solved ? "teal" : "red")}${badge(selected.style || "通用")}${badge(selected.question_type || selected.quiz_type || "reading")}${selected.skill ? badge(selected.skill) : ""}${selected.error_type ? badge(selected.error_type, "red") : ""}</div>
        <h2>${escapeHtml(selected.prompt)}</h2>
      </div>
      ${selected.article_id ? `<button data-open-article="${selected.article_id}">回到原文</button>` : ""}
    </div>
    <div class="answer-compare">
      <div class="answer-choice wrong-choice"><span>你的答案</span><strong>${escapeHtml(selected.user_answer || "未作答")}</strong></div>
      <div class="answer-choice correct-choice"><span>正确答案</span><strong>${escapeHtml(selected.answer)}</strong></div>
    </div>
    ${explanationHtml(explanation, false, false, selected.article_id)}
    <div class="mastery-progress">
      <div><span>同类训练</span><strong>${selected.remedial_attempts || 0} 次</strong></div>
      <div><span>连续正确</span><strong>${selected.remedial_correct_streak || 0}/2</strong></div>
      <div><span>掌握依据</span><strong>${selected.mastery_source === "remedial-streak" ? "同类题验证" : selected.mastery_source === "self-confirmed" ? "自我确认" : "尚未掌握"}</strong></div>
    </div>
    <div class="toolbar mistake-actions">
      <button class="primary" data-generate-similar="${selected.id}">${similar.length ? "换一组同类题" : "生成 3 道同类题"}</button>
      <button data-solve-mistake="${selected.id}">${selected.solved ? "重新标记待学" : "自我确认已掌握"}</button>
    </div>
    <section class="remedial-section">
      <div class="remedial-head"><div><span class="muted">Same skill, new evidence</span><h3>同考点巩固</h3></div>${similar.length ? badge(`${similar.length} 题`, "teal") : ""}</div>
      ${similar.length ? `<div class="remedial-list">${similar.map(remedialQuizHtml).join("")}</div>` : `<div class="empty-state">讲解看懂后，再用新证据做一组；连续做对才算真正掌握。</div>`}
    </section>
  `;
}

function renderPracticeHistory() {
  const analytics = state.practiceAnalytics || { summary: {}, skills: [], recommendation: {} };
  const summary = analytics.summary || {};
  $("#historyExamTitle").textContent = `${state.style} 训练趋势`;
  $("#historyOverview").innerHTML = `
    <div><span>累计作答</span><strong>${summary.attempts || 0}</strong></div>
    <div><span>累计答对</span><strong>${summary.correct || 0}</strong></div>
    <div><span>正确率</span><strong>${summary.accuracy || 0}%</strong></div>
    <div><span>已记录训练</span><strong>${state.practiceSessions.length}</strong></div>
  `;
  $("#historyRecommendation").innerHTML = prescriptionHtml(state.prescription, true);
  $("#abilityTrendList").innerHTML = (analytics.skills || []).map(item => {
    const trend = item.trend;
    const trendText = trend === null || trend === undefined ? "样本积累中" : trend > 0 ? `近期 +${trend}` : trend < 0 ? `近期 ${trend}` : "近期持平";
    const trendClass = trend > 0 ? "trend-up" : trend < 0 ? "trend-down" : "";
    return `
      <div class="ability-trend-row">
        <div><strong>${escapeHtml(item.label)}</strong><small> ${item.correct}/${item.total}</small></div>
        <strong class="${trendClass}">${item.accuracy}% · ${trendText}</strong>
        <div class="ability-meter"><span style="width:${Math.max(0, Math.min(100, item.accuracy))}%"></span></div>
      </div>
    `;
  }).join("") || `<p class="muted">完成训练后生成能力趋势。</p>`;
  $("#historySessionCount").textContent = `${state.practiceSessions.length} 次`;
  $("#practiceSessionList").innerHTML = state.practiceSessions.map(session => `
    <button class="master-list-item ${state.selectedPracticeSession?.session?.id === session.id ? "active" : ""}" data-practice-session="${session.id}">
      <span class="master-number">${session.score}%</span>
      <span class="master-copy">
        <strong>${escapeHtml(session.article_title || session.question_type || "综合训练")}</strong>
        <small>${escapeHtml(session.session_mode === "mock" ? "模考" : "训练")} · ${session.correct_count}/${session.question_count} · ${formatDuration(session.elapsed_seconds)}</small>
        <em>${escapeHtml(session.completed_at.replace("T", " ").slice(0, 16))}</em>
      </span>
    </button>
  `).join("") || `<div class="empty-state">尚无已完成训练</div>`;
  const detail = state.selectedPracticeSession;
  if (!detail) {
    $("#practiceSessionDetail").innerHTML = `<div class="empty-state">选择一条训练记录查看题目、答案和证据。</div>`;
    return;
  }
  const session = detail.session;
  $("#practiceSessionDetail").innerHTML = `
    <div class="detail-head">
      <div><span class="eyebrow">${escapeHtml(session.style)} · ${session.session_mode === "mock" ? "模考" : "训练"}</span><h2>${escapeHtml(session.article_title || session.question_type || "训练详情")}</h2></div>
      <div class="badge-row">${badge(`${session.score}%`, session.score >= 70 ? "teal" : "amber")}${badge(`${session.correct_count}/${session.question_count}`)}</div>
    </div>
    <div class="toolbar"><button data-history-next-type="${escapeHtml(session.question_type === "mixed" ? "" : session.question_type)}">再练本题型</button></div>
    ${(detail.attempts || []).map((attempt, index) => `
      <section class="history-attempt">
        <div class="badge-row">${badge(`第 ${index + 1} 题`)}${badge(attempt.correct ? "正确" : "错误", attempt.correct ? "teal" : "red")}${badge(attempt.question_type)}${attempt.elapsed_seconds ? badge(`${attempt.elapsed_seconds} 秒`) : ""}${attempt.answer_changes ? badge(`改答 ${attempt.answer_changes} 次`, "amber") : ""}${attempt.hint_used ? badge("使用提示", "amber") : ""}</div>
        <h3>${searchableEnglish(attempt.prompt)}</h3>
        <p><strong>你的答案：</strong>${searchableEnglish(attempt.user_answer || "未作答", false)}</p>
        <p><strong>正确答案：</strong>${searchableEnglish(attempt.answer, false)}</p>
        <p><strong>原文证据：</strong>${searchableEnglish(attempt.evidence || "暂无证据")}</p>
        ${attempt.article_id ? `<button data-replay-evidence="${attempt.article_id}" data-replay-text="${escapeHtml(attempt.evidence || "")}">回到原文</button>` : ""}
      </section>
    `).join("")}
  `;
}

function renderAll() {
  renderStats();
  renderDashboard();
  renderArticles();
  renderReader();
  renderQuizzes();
  renderQuizSource();
  renderCards();
  renderReviews();
  renderMistakes();
  renderPracticeHistory();
  renderLexicon();
}

function renderExamTypes() {
  const practiceSelect = $("#quizPracticeType");
  if (practiceSelect) {
    const practicePrevious = practiceSelect.value;
    practiceSelect.innerHTML = `<option value="">选择专项题型</option>${state.examTypes.map(item => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`).join("")}`;
    if (state.examTypes.some(item => item.id === practicePrevious)) practiceSelect.value = practicePrevious;
    else if (state.examTypes[0]) practiceSelect.value = state.examTypes[0].id;
  }
  updateQuizScopeControls();
}

async function loadHealth() {
  const data = await api("/api/health");
  state.runtime = data;
  $("#serverStatus").textContent = "后端已连接";
  $("#serverStatus").classList.add("ok");
  const backendVersion = String(data.app_version || "旧版后端");
  const apiCompatible = String(data.api_version || "") === SUPPORTED_API_VERSION;
  const compatible = apiCompatible && data.compatible !== false && backendVersion === FRONTEND_APP_VERSION;
  $("#runtimeVersion").textContent = `${backendVersion} · API ${data.api_version || "未知"}`;
  $("#compatibilityBanner").hidden = compatible;
  if (!compatible) {
    $("#compatibilityMessage").textContent = data.app_version
      ? `页面 ${FRONTEND_APP_VERSION}，后端 ${backendVersion}。请重启后端后刷新页面。`
      : "当前仍是旧版后端，请重启 Language Coach 后刷新页面。";
  }
  return data;
}

function renderBackups() {
  const select = $("#backupSelect");
  if (!select) return;
  select.innerHTML = state.backups.length
    ? state.backups.map(item => `<option value="${escapeHtml(item.filename)}">${escapeHtml(item.created_at.replace("T", " "))} · ${Math.max(1, Math.round(item.size_bytes / 1024))} KB</option>`).join("")
    : '<option value="">暂无备份</option>';
  $("#restoreBackupBtn").disabled = !state.backups.length;
  $("#backupStatus").textContent = state.backups.length
    ? `本机已有 ${state.backups.length} 个备份，恢复前会自动再创建安全备份。`
    : "备份仅保存在本机数据目录。";
}

async function loadBackups() {
  try {
    const data = await api("/api/backups");
    state.backups = data.backups || [];
  } catch (_error) {
    state.backups = [];
  }
  renderBackups();
}

async function createDataBackup() {
  const data = await api("/api/backups", { method: "POST", body: "{}" });
  state.backups = data.backups || [];
  renderBackups();
  toast(`备份完成：${data.backup.filename}`);
}

async function restoreDataBackup() {
  const filename = $("#backupSelect").value;
  if (!filename || !window.confirm(`恢复 ${filename}？当前数据会先自动备份。`)) return;
  await api("/api/backups/restore", { method: "POST", body: JSON.stringify({ filename }) });
  window.location.reload();
}

async function loadProgress() {
  const data = await api("/api/progress");
  state.progress = data.progress;
}

async function loadLearnerSettings() {
  const data = await api("/api/learner-settings");
  state.learnerSettings = data.settings;
  state.learnerProfile = data.profile;
  renderLearnerSettings();
}

async function saveArticlePreferences(changes) {
  const payload = {
    article_layout: changes.article_layout || state.learnerSettings.article_layout || "split",
    article_density: changes.article_density || state.learnerSettings.article_density || "comfortable",
  };
  const data = await api("/api/article-preferences", { method: "POST", body: JSON.stringify(payload) });
  state.learnerSettings = data.settings;
  renderArticles();
}

async function saveLearnerSettings() {
  const dailyTasks = [...document.querySelectorAll("[data-daily-task]:checked")].map(input => input.dataset.dailyTask);
  if (!dailyTasks.length) return toast("每天至少选择一项学习内容");
  const data = await api("/api/learner-settings", {
    method: "POST",
    body: JSON.stringify({
      daily_minutes: Number($("#dailyMinutes").value),
      daily_tasks: dailyTasks,
      daily_targets: Object.fromEntries(
        [...document.querySelectorAll("[data-daily-target]")].map(input => [input.dataset.dailyTarget, Number(input.value) || 1]),
      ),
      short_goal: $("#shortGoal").value.trim(),
      short_goal_date: $("#shortGoalDate").value,
      long_goal: $("#longGoal").value.trim(),
      long_goal_date: $("#longGoalDate").value,
      recommendations_enabled: $("#recommendationsEnabled").checked,
    }),
  });
  state.learnerSettings = data.settings;
  await loadToday();
  renderLearnerSettings();
  renderDashboard();
  toast("学习计划和目标已保存");
}

function applyDailyPlan(plan) {
  state.today.plan = { ...(state.today.plan || {}), ...plan };
  renderDailyPlan();
}

async function setDailyTaskComplete(task, completedCount) {
  const data = await api("/api/daily-plan/progress", {
    method: "POST",
    body: JSON.stringify({ task, completed_count: completedCount }),
  });
  applyDailyPlan(data.plan);
  toast(data.plan.completed ? "今日计划已完成" : `${dailyTaskLabels[task] || task}已更新`);
}

async function addDailyPlanItem({ task, itemType, itemId, title }) {
  const data = await api("/api/daily-plan/items", {
    method: "POST",
    body: JSON.stringify({ task, item_type: itemType, item_id: itemId, title }),
  });
  applyDailyPlan(data.plan);
  toast("已加入今日计划");
}

async function completeDailyPlanItem(id) {
  const data = await api(`/api/daily-plan/items/${id}/complete`, { method: "POST", body: "{}" });
  applyDailyPlan(data.plan);
  toast(data.plan.completed ? "今日计划已完成" : "任务已完成");
}

async function loadExamTypes() {
  const data = await api(`/api/exam-types?style=${encodeURIComponent(state.style)}`);
  state.examTypes = data.types || [];
  renderExamTypes();
}

function renderBookLibrary() {
  const bookSelect = $("#epubBookSelect");
  const chapterSelect = $("#epubChapterSelect");
  if (!bookSelect || !chapterSelect) return;
  bookSelect.innerHTML = `<option value="">选择已导入书籍</option>${state.books.map(book => `<option value="${book.id}">${escapeHtml(book.title)} · ${book.chapter_count} 章</option>`).join("")}`;
  if (state.selectedBook && state.books.some(book => book.id === state.selectedBook.id)) {
    bookSelect.value = String(state.selectedBook.id);
  }
  chapterSelect.innerHTML = state.selectedBook?.chapters?.length
    ? state.selectedBook.chapters.map(chapter => `<option value="${chapter.id}">${chapter.position}. ${escapeHtml(chapter.title)} · ${chapter.word_count} 词${chapter.article_id ? " · 已进入阅读台" : ""}</option>`).join("")
    : `<option value="">先选择一本书</option>`;
  $("#epubBookSummary").textContent = state.selectedBook
    ? `${state.selectedBook.author || "作者未标注"} · ${state.selectedBook.language || "语言未标注"} · ${state.selectedBook.chapter_count} 个正文单元 · 私人本地素材`
    : state.books.length ? `已导入 ${state.books.length} 本私人书籍` : "尚未导入 EPUB";
}

async function loadBooks() {
  const data = await api("/api/books");
  state.books = data.books || [];
  if (state.selectedBook && !state.books.some(book => book.id === state.selectedBook.id)) state.selectedBook = null;
  renderBookLibrary();
}

async function loadBook(id) {
  if (!id) {
    state.selectedBook = null;
    return renderBookLibrary();
  }
  const data = await api(`/api/books/${id}`);
  state.selectedBook = data.book;
  renderBookLibrary();
}

async function importEpub() {
  const path = $("#epubPath").value.trim();
  if (!path) return toast("先填写本地 EPUB 路径");
  toast("正在读取 EPUB 目录与章节");
  const data = await api("/api/import/epub", { method: "POST", body: JSON.stringify({ path }) });
  await loadBooks();
  await loadBook(data.book.id);
  toast(data.created ? `已导入 ${data.book.chapter_count} 个正文单元` : "这本书已经在私人书库中");
}

async function openEpubChapter() {
  const chapterId = Number($("#epubChapterSelect").value);
  if (!chapterId) return toast("先选择章节");
  const data = await api(`/api/book-chapters/${chapterId}/article`, {
    method: "POST",
    body: JSON.stringify({ exam: state.style }),
  });
  await Promise.all([loadArticles(), loadBook(state.selectedBook.id)]);
  state.selectedPoolArticleId = data.article.id;
  await openArticle(data.article.id);
  toast("章节已进入阅读台，可查词、翻译或生成练习");
}

async function loadExamLibrary() {
  const [resources, papers] = await Promise.all([
    api(`/api/exam-resources?exam=${encodeURIComponent(state.style)}`),
    api(`/api/exam-papers?exam=${encodeURIComponent(state.style)}`),
  ]);
  state.examResources = resources.resources || [];
  state.examPapers = papers.papers || [];
  renderExamLibrary();
}

function renderExamLibrary() {
  const paperSelect = $("#quizPaperSelect");
  if (paperSelect) {
    paperSelect.innerHTML = `<option value="">选择已生成套题</option>${state.examPapers.map(paper => `<option value="${paper.id}">${escapeHtml(paper.title)} · ${paper.question_count} 题</option>`).join("")}`;
  }
  const library = $("#examResourceList");
  if (!library) return;
  library.innerHTML = state.examResources.map(resource => `
    <li><span>${escapeHtml(resource.exam)} · ${escapeHtml(resource.provider)}</span><a href="${escapeHtml(resource.source_url)}" target="_blank" rel="noreferrer">${escapeHtml(resource.title)}</a><small>${escapeHtml(resource.rights_status === "link_only" ? "官方链接，不复制原题" : "用户自行提供")}</small></li>
  `).join("") || `<li class="muted">暂无来源</li>`;
}

function updateQuizScopeControls() {
  const scopeSelect = $("#quizScope");
  const fullPaperOption = scopeSelect?.querySelector('option[value="full-paper"]');
  if (fullPaperOption) fullPaperOption.disabled = state.style !== "IELTS";
  if (state.style !== "IELTS" && scopeSelect?.value === "full-paper") scopeSelect.value = "specialty";
  const scope = scopeSelect?.value || "specialty";
  const isFull = scope === "full-paper";
  $("#quizPracticeType").hidden = isFull || scope === "passage";
  $("#generatePracticeBtn").hidden = isFull;
  $("#quizPaperSelect").hidden = !isFull;
  $("#generateFullPaperBtn").hidden = !isFull;
  $("#loadPaperBtn").hidden = !isFull;
  $("#generatePracticeBtn").textContent = scope === "passage" ? "生成单篇组合题" : "按当前文章出题";
}

async function applyQuizControlChange() {
  updateQuizScopeControls();
  const scope = $("#quizScope").value;
  if (scope === "full-paper") {
    state.quizzes = state.selectedPaper ? flattenPaperQuizzes(state.selectedPaper) : [];
    resetQuizSession();
    if (state.quizzes.length) await syncPracticeRunNow({ newRun: true });
    renderQuizzes();
    renderQuizSource();
    return;
  }
  if (!state.selectedArticle) {
    state.quizzes = [];
    renderQuizzes();
    return toast("先选择一篇文章");
  }
  if (scope === "passage") {
    await generateQuizzes(state.selectedArticle.id, { open: false, startRun: true });
    return;
  }
  await loadQuizzes();
  if (!state.quizzes.length) await generateQuizzes(state.selectedArticle.id, { open: false });
  else {
    resetQuizSession();
    await syncPracticeRunNow({ newRun: true });
    renderQuizzes();
    renderQuizSource();
    toast(`已切换到 ${$("#quizPracticeType").selectedOptions[0]?.textContent || "当前题型"}`);
  }
}

function flattenPaperQuizzes(paper) {
  return (paper?.sections || []).flatMap(section => section.quizzes || []);
}

function applyPaper(paper) {
  state.selectedPaper = paper;
  state.quizzes = flattenPaperQuizzes(paper);
  if (paper?.sections?.[0]?.article) state.selectedArticle = paper.sections[0].article;
  resetQuizSession();
  renderAll();
  renderExamLibrary();
}

async function loadPaper(id) {
  if (!id) return toast("先选择一套模拟题");
  const data = await api(`/api/exam-papers/${id}`);
  $("#quizScope").value = "full-paper";
  applyPaper(data.paper);
  await syncPracticeRunNow({ newRun: true });
  setView("quiz");
  toast(`已载入 ${data.paper.question_count} 题整套模拟`);
}

async function generateFullPaper() {
  const data = await api("/api/exam-papers/generate", {
    method: "POST",
    body: JSON.stringify({ exam: state.style }),
  });
  $("#quizScope").value = "full-paper";
  applyPaper(data.paper);
  await syncPracticeRunNow({ newRun: true });
  await loadExamLibrary();
  setView("quiz");
  toast("已生成 3 篇 / 40 题 IELTS 模拟套题");
}

function syncPaperSourceForQuestion() {
  if (!state.selectedPaper) return;
  const quiz = state.quizzes[state.quizSession.activeIndex];
  const section = state.selectedPaper.sections.find(item => item.quizzes.some(question => question.id === quiz?.id));
  if (section?.article) {
    state.selectedArticle = section.article;
    renderQuizSource();
  }
}

async function loadArticles(q = "") {
  const params = new URLSearchParams({ exam: state.style });
  if (q) params.set("q", q);
  if (state.articleTopic) params.set("topic", state.articleTopic);
  if (state.articleContentType) params.set("content_type", state.articleContentType);
  if (state.articleHub) params.set("hub", state.articleHub);
  if (state.recommendedOnly) params.set("recommended", "1");
  if (state.articleVisibility) params.set("visibility", state.articleVisibility);
  const data = await api(`/api/articles?${params.toString()}`);
  state.articles = data.articles || [];
  state.articleFacets = data.facets || state.articleFacets;
}

async function loadArticleHubs() {
  try {
    const data = await api("/api/content-hubs");
    state.articleHubs = data.hubs || [];
  } catch (_error) {
    state.articleHubs = [
      ["news", "新闻"], ["opinion", "观点"], ["research", "研究"], ["science", "科学与自然"],
      ["culture-life", "文化与生活"], ["media", "影视与听力"], ["books", "小说与图书"],
    ].map(([id, label]) => ({ id, label }));
  }
  $("#articleHubFilter").innerHTML = `<option value="">全部内容</option>${state.articleHubs.map(item => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`).join("")}<option value="subscribed">我的订阅</option>`;
  $("#articleHubFilter").value = state.articleHub;
}

async function loadArticleTopics() {
  const data = await api("/api/article-topics");
  state.articleTopics = data.topics || [];
  $("#articleTopicFilter").innerHTML = `<option value="">全部主题</option>${state.articleTopics.map(topic => `<option value="${escapeHtml(topic)}">${escapeHtml(topic)}</option>`).join("")}`;
  $("#articleTopicFilter").value = state.articleTopic;
  $("#recommendedOnly").checked = state.recommendedOnly;
}

async function loadArticleContentTypes() {
  const data = await api("/api/article-content-types");
  state.articleContentTypes = data.types || [];
  $("#articleContentTypeFilter").innerHTML = `<option value="">全部类型</option>${state.articleContentTypes.map(item => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`).join("")}`;
  $("#articleContentTypeFilter").value = state.articleContentType;
}

async function loadCards() {
  const data = await api("/api/cards");
  state.cards = data.cards || [];
}

async function loadReviews() {
  state.reviews = await api(`/api/reviews?kind=${encodeURIComponent(state.reviewKind)}&limit=30`);
  state.canUndoReview = Boolean(state.reviews.undo?.available);
}

async function rateReview(reviewId, rating) {
  const data = await api(`/api/reviews/${reviewId}/rate`, {
    method: "POST",
    body: JSON.stringify({ rating, kind: state.reviewKind }),
  });
  state.reviews = data.queue;
  state.selectedReviewId = state.reviews.items?.[0]?.id || null;
  state.reviewAnswerRevealed = false;
  state.canUndoReview = Boolean(state.reviews.undo?.available);
  await Promise.all([loadToday(), loadCards()]);
  renderReviews();
  renderCards();
  renderDashboard();
  toast(`${{ again: "忘记", hard: "困难", good: "记得", easy: "轻松" }[rating]} · ${data.interval}后复习`);
}

async function undoReview() {
  const data = await api("/api/reviews/undo", {
    method: "POST",
    body: JSON.stringify({ kind: state.reviewKind }),
  });
  state.reviews = data.queue;
  state.selectedReviewId = data.review_item_id;
  state.reviewAnswerRevealed = true;
  state.canUndoReview = Boolean(state.reviews.undo?.available);
  await Promise.all([loadToday(), loadCards()]);
  renderReviews();
  renderCards();
  renderDashboard();
  toast("已恢复上次评分前的排期");
}

async function loadBridgeConfig() {
  const data = await api("/api/browser/token");
  state.bridge = data;
  $("#bridgeToken").value = data.token || "";
  try {
    const clips = await api("/api/browser/clips", { headers: { "X-Language-Coach-Token": data.token } });
    state.browserClips = clips.clips || [];
  } catch (_error) {
    state.browserClips = [];
  }
  if (data.translation?.provider_id === "deepl" && data.translation.configured) {
    try {
      const verified = await api("/api/browser/translation-verify", {
        method: "POST",
        headers: { "X-Language-Coach-Token": data.token },
        body: "{}",
      });
      state.bridge.translation = verified.translation || data.translation;
    } catch (error) {
      state.bridge.translation = { ...data.translation, verified: false, last_error: error.message };
    }
  }
  const translation = state.bridge.translation || {};
  const translationLabel = !translation.configured
    ? `${translation.provider || "翻译服务"} 未配置`
    : translation.verified === true
      ? `${translation.provider} 已验证`
      : translation.verified === false
        ? `${translation.provider} 验证失败`
        : `${translation.provider} 待验证`;
  $("#bridgeStatus").innerHTML = `${badge("本地桥接已启用", "teal")}${badge(
    translationLabel,
    translation.verified === true ? "teal" : "amber",
  )}${badge("手动译文可用")}${translation.last_error ? `<p class="bridge-error">${escapeHtml(translation.last_error)}</p>` : ""}`;
}

async function loadMistakes() {
  const data = await api("/api/mistakes");
  state.mistakes = data.mistakes || [];
}

async function loadPracticeHistory({ selectFirst = false } = {}) {
  const params = new URLSearchParams({ style: state.style });
  const [sessions, analytics] = await Promise.all([
    api(`/api/practice-sessions?${params.toString()}`),
    api(`/api/practice/analytics?${params.toString()}`),
  ]);
  state.practiceSessions = sessions.sessions || [];
  state.practiceAnalytics = analytics;
  const selectedId = state.selectedPracticeSession?.session?.id;
  if (selectedId && !state.practiceSessions.some(session => session.id === selectedId)) {
    state.selectedPracticeSession = null;
  }
  if (selectFirst && !state.selectedPracticeSession && state.practiceSessions[0]) {
    await selectPracticeSession(state.practiceSessions[0].id, { render: false });
  }
}

async function loadPracticePrescription() {
  const data = await api(`/api/practice/prescription?style=${encodeURIComponent(state.style)}`);
  state.prescription = data.prescription;
}

async function selectPracticeSession(id, { render = true } = {}) {
  state.selectedPracticeSession = await api(`/api/practice-sessions/${id}`);
  if (render) renderPracticeHistory();
}

async function loadFeeds() {
  const data = await api(`/api/feeds?exam=${encodeURIComponent(state.style)}`);
  state.feeds = data.feeds || [];
}

async function loadFeedStatus() {
  state.feedStatus = await api("/api/feeds/status");
}

async function loadExtractionQuality() {
  state.extractionQuality = await api("/api/extraction/quality");
}

async function loadSourceCatalog() {
  const data = await api("/api/source-catalog");
  state.sourceCatalog = data.sources || [];
}

async function loadSubscriptions() {
  const data = await api("/api/subscriptions");
  state.subscriptions = data.subscriptions || [];
}

async function loadToday() {
  const params = new URLSearchParams({ exam: state.style, mode: state.learningMode });
  state.today = await api(`/api/today?${params.toString()}`);
}

async function setLearningMode(mode) {
  if (!['interest', 'exam'].includes(mode) || mode === state.learningMode) return;
  state.learningMode = mode;
  localStorage.setItem("lc-v2-learning-mode", mode);
  await loadToday();
  renderDashboard();
  toast(mode === "interest" ? "已切换到兴趣模式" : `已切换到 ${state.style} 备考模式`);
}

async function startDailyPlan() {
  const firstTask = state.learnerSettings.daily_tasks?.[0] || "reading";
  if (firstTask === "review") {
    setView("mistakes");
    renderMistakes();
    return;
  }
  if (firstTask === "vocabulary") {
    setView("cards");
    renderCards();
    return;
  }
  if (firstTask === "practice") {
    if (!state.quizzes.length) await loadQuizzes();
    if (!state.quizzes.length && state.selectedArticle) await generateQuizzes(state.selectedArticle.id, { open: false });
    setView("quiz");
    renderQuizzes();
    renderQuizSource();
    return;
  }
  const first = state.today.lanes?.[0]?.article;
  if (first) await openArticle(first.id);
  else setView("articles");
}

async function startModeFocus() {
  if (state.learningMode === "interest") {
    const first = state.today.lanes?.[0]?.article;
    if (first) await openArticle(first.id);
    else setView("articles");
    return;
  }
  const questionType = state.today.mode_focus?.recommended_question_type || "";
  if (questionType && [...$("#quizPracticeType").options].some(option => option.value === questionType)) {
    $("#quizPracticeType").value = questionType;
  }
  const article = state.today.lanes?.find(lane => lane.article)?.article || state.selectedArticle;
  if (article) await generateQuizzes(article.id);
  else await startDailyPlan();
}

async function setSubscription(targetType, targetValue, active) {
  await api("/api/subscriptions", {
    method: "POST",
    body: JSON.stringify({ target_type: targetType, target_value: targetValue, active }),
  });
  await Promise.all([loadSourceCatalog(), loadSubscriptions(), loadToday(), loadArticles($("#articleSearch").value.trim())]);
  renderDashboard();
  renderArticles();
  toast(active ? `已订阅 ${targetValue}` : `已取消订阅 ${targetValue}`);
}

async function setSourceSubscription(name, active) {
  await setSubscription("source", name, active);
}

async function loadQuizzes() {
  const params = new URLSearchParams();
  if (state.selectedArticle) params.set("article_id", state.selectedArticle.id);
  params.set("style", state.style);
  const questionType = $("#quizScope")?.value === "specialty" ? $("#quizPracticeType")?.value || "" : "";
  if (questionType) params.set("question_type", questionType);
  const data = await api(`/api/quizzes?${params.toString()}`);
  state.quizzes = data.quizzes || [];
  resetQuizSession();
  restoreQuizDraft();
}

async function openArticle(id) {
  const data = await api(`/api/articles/${id}?exam=${encodeURIComponent(state.style)}`);
  state.selectedArticle = data.article;
  state.evidenceReplay = "";
  state.analysis = data.analysis;
  await loadQuizzes();
  setView("reader");
  renderAll();
}

async function replayEvidence(articleId, evidence) {
  if (!articleId || !evidence) return toast("这道题没有可定位的原文证据");
  if (Number(state.selectedArticle?.id) !== Number(articleId)) {
    const data = await api(`/api/articles/${articleId}?exam=${encodeURIComponent(state.style)}`);
    state.selectedArticle = data.article;
    state.analysis = data.analysis;
  }
  state.evidenceReplay = evidence;
  setView("reader");
  renderReader();
  setTimeout(() => {
    const target = $("#readerEvidenceTarget");
    target?.scrollIntoView({ behavior: "smooth", block: "center" });
    if (!target) toast("已打开原文，当前证据需要手动定位");
  }, 50);
}

async function analyzeArticle() {
  if (!state.selectedArticle) return toast("先选文章");
  const data = await api(`/api/articles/${state.selectedArticle.id}/analyze`, { method: "POST", body: "{}" });
  state.analysis = data.analysis;
  renderReader();
  toast("分析完成");
}

async function generateQuizzes(id = state.selectedArticle?.id, { open = true, startRun = open } = {}) {
  if (!id) return toast("先选文章");
  const mode = "mixed";
  const questionType = $("#quizScope")?.value === "passage"
    ? "mixed"
    : $("#quizPracticeType")?.value || "";
  const data = await api(`/api/articles/${id}/quizzes`, {
    method: "POST",
    body: JSON.stringify({ mode, style: state.style, question_type: questionType }),
  });
  state.quizzes = data.quizzes || [];
  clearQuizDraft();
  resetQuizSession();
  if (startRun && state.quizzes.length) await syncPracticeRunNow({ newRun: true });
  if (open) setView("quiz");
  renderAll();
  toast("题目已生成");
}

async function generatePassagePractice(id = state.selectedArticle?.id) {
  $("#quizScope").value = "passage";
  state.selectedPaper = null;
  updateQuizScopeControls();
  await generateQuizzes(id);
}

async function submitAnswer(quizId, answer, button = null, confidence = state.quizSession.confidence[quizId] || null) {
  state.quizSession.answers[quizId] = String(answer || "").trim();
  state.quizSession.confidence[quizId] = normalizeConfidenceValue(confidence);
  const data = await api("/api/attempts", {
    method: "POST",
    body: JSON.stringify({
      quiz_id: quizId,
      answer,
      confidence: normalizeConfidenceValue(confidence),
      elapsed_seconds: Math.max(0, Math.round((Date.now() - (state.quizSession.questionStartedAt[quizId] || Date.now())) / 1000)),
      answer_changes: state.quizSession.answerChanges[quizId] || 0,
      hint_used: Boolean(state.quizSession.hintUsed[quizId]),
    }),
  });
  const similarQuizzes = Object.values(state.similarByMistake).flat();
  const quiz = state.quizzes.find(item => item.id === quizId) || similarQuizzes.find(item => item.id === quizId) || {};
  const explanation = data.explanation || fallbackMistakeExplanation({
    ...quiz,
    quiz_type: quiz.type,
    quiz_note: quiz.note,
    user_answer: answer,
    answer: data.answer || quiz.answer,
    evidence: data.evidence || quiz.evidence,
  });
  state.answerFeedback[quizId] = { ...data, explanation, userAnswer: answer };
  if (data.progress) state.progress = data.progress;
  await loadMistakes();
  renderQuizzes();
  renderMistakes();
  renderStats();
  renderDashboard();
  await syncPracticeRunNow();
  const rewardText = data.points ? `，+${data.points} XP` : "（本题积分已结算）";
  if (data.mastery?.mastered) toast(`连续答对，原错题已掌握${rewardText}`);
  else if (data.mastery) toast(data.correct ? `同类题答对，连续 ${data.mastery.streak}/2` : "同类题答错，连续正确重新计算");
  else toast(data.correct ? `答对了${rewardText}` : `错了：${data.answer}${rewardText}`);
}

async function selectQuizAnswer(quizId, answer) {
  if (state.quizSession.submitted || state.answerFeedback[quizId]) return;
  const previous = state.quizSession.committedAnswers[quizId];
  if (previous && previous !== answer) state.quizSession.answerChanges[quizId] = (state.quizSession.answerChanges[quizId] || 0) + 1;
  state.quizSession.committedAnswers[quizId] = answer;
  state.quizSession.answers[quizId] = answer;
  schedulePracticeRunSync();
  if (state.quizSession.mode === "practice") {
    if (!state.quizSession.confidence[quizId]) return renderQuizzes();
    await submitAnswer(quizId, answer, null, state.quizSession.confidence[quizId]);
  } else {
    renderQuizzes();
  }
}

function localPracticeResult() {
  const results = state.quizzes
    .map(quiz => ({ quiz, feedback: state.answerFeedback[quiz.id] }))
    .filter(item => item.feedback);
  const skillSummary = {};
  const errorSummary = {};
  const confidenceSummary = {};
  results.forEach(({ quiz, feedback }) => {
    const skill = feedback.skill || quiz.skill || "阅读理解";
    const stats = skillSummary[skill] || { total: 0, correct: 0 };
    stats.total += 1;
    stats.correct += feedback.correct ? 1 : 0;
    skillSummary[skill] = stats;
    if (feedback.error_type) errorSummary[feedback.error_type] = (errorSummary[feedback.error_type] || 0) + 1;
    const confidence = normalizeConfidenceValue(feedback.confidence || state.quizSession.confidence[quiz.id]);
    if (confidence) {
      const label = { 1: "猜测", 2: "犹豫", 3: "确定" }[confidence];
      const confidenceStats = confidenceSummary[label] || { total: 0, correct: 0 };
      confidenceStats.total += 1;
      confidenceStats.correct += feedback.correct ? 1 : 0;
      confidenceSummary[label] = confidenceStats;
    }
  });
  const unanswered = state.quizzes.length - results.length;
  if (unanswered) errorSummary.未作答 = unanswered;
  const correctCount = results.filter(item => item.feedback.correct).length;
  return {
    question_count: state.quizzes.length,
    answered_count: results.length,
    correct_count: correctCount,
    elapsed_seconds: quizElapsedSeconds(),
    score: Math.round(correctCount / Math.max(1, state.quizzes.length) * 100),
    skill_summary: skillSummary,
    error_summary: errorSummary,
    confidence_summary: confidenceSummary,
  };
}

async function finishQuizSession() {
  const session = state.quizSession;
  if (!state.quizzes.length || session.submitted) return;
  const answered = state.quizzes.filter(quiz => String(session.answers[quiz.id] || "").trim()).length;
  if (!answered) return toast("至少完成一题再结束训练");
  const unanswered = state.quizzes.length - answered;
  if (unanswered && !window.confirm(`还有 ${unanswered} 题未作答，仍要${session.mode === "mock" ? "交卷" : "结束训练"}吗？`)) return;
  const elapsedSeconds = quizElapsedSeconds();
  if (session.mode === "mock") {
    const data = await api("/api/practice-sessions", {
      method: "POST",
      body: JSON.stringify({
        session_mode: "mock",
        elapsed_seconds: elapsedSeconds,
         answers: state.quizzes.map(quiz => ({
           quiz_id: quiz.id,
           answer: session.answers[quiz.id] || "",
           confidence: session.confidence[quiz.id] || null,
           elapsed_seconds: Math.max(0, Math.round((Date.now() - (session.questionStartedAt[quiz.id] || Date.now())) / 1000)),
           answer_changes: session.answerChanges[quiz.id] || 0,
           hint_used: Boolean(session.hintUsed[quiz.id]),
         })),
      }),
    });
    (data.results || []).forEach(result => {
      state.answerFeedback[result.quiz_id] = { ...result, userAnswer: result.user_answer };
    });
    session.result = data;
    if (data.progress) state.progress = data.progress;
    await loadMistakes();
    renderMistakes();
    renderStats();
    renderDashboard();
  } else {
    const attemptIds = state.quizzes
      .map(quiz => state.answerFeedback[quiz.id]?.attempt_id)
      .filter(Boolean);
    if (attemptIds.length) {
      session.result = await api("/api/practice-sessions/record", {
        method: "POST",
        body: JSON.stringify({
          attempt_ids: attemptIds,
          question_count: state.quizzes.length,
          elapsed_seconds: elapsedSeconds,
        }),
      });
    } else {
      session.result = localPracticeResult();
    }
  }
  session.elapsedSeconds = elapsedSeconds;
  state.showAnswers = true;
  clearQuizDraft();
  await finishServerPracticeRun("complete", session.result?.session?.id || null);
  session.submitted = true;
  await Promise.all([loadPracticeHistory(), loadPracticePrescription(), loadToday()]);
  renderPracticeHistory();
  renderDashboard();
  renderQuizzes();
  toast(session.mode === "mock" ? "交卷完成，已生成能力与错因分析" : "训练结束，已生成本轮总结");
}

async function saveTranslation() {
  if (!state.selectedArticle) return toast("先选文章");
  const data = await api(`/api/articles/${state.selectedArticle.id}/translation`, {
    method: "POST",
    body: JSON.stringify({ translation_zh: $("#articleTranslationInput").value.trim() }),
  });
  state.selectedArticle = data.article;
  state.showTranslation = true;
  const poolItem = state.articles.find(item => item.id === data.article.id);
  if (poolItem) Object.assign(poolItem, data.article);
  renderReader();
  renderArticles();
  toast(data.article.translation_aligned ? "译文已保存并完成段落对齐" : "译文已保存，部分段落仍缺少对应译文");
}

async function translateArticle(id = state.selectedArticle?.id) {
  if (!id) return toast("先选文章");
  toast("正在翻译并对齐段落");
  const data = await api(`/api/articles/${id}/translate`, {
    method: "POST",
    body: JSON.stringify({ exam: state.style }),
  });
  const index = state.articles.findIndex(item => item.id === data.article.id);
  if (index >= 0) state.articles[index] = data.article;
  if (state.selectedArticle?.id === data.article.id) state.selectedArticle = data.article;
  state.showTranslation = true;
  renderArticles();
  renderReader();
  renderQuizSource();
  toast(data.cached ? "已载入缓存译文" : "翻译完成并已保存");
}

async function toggleArticleTranslation() {
  const article = state.selectedArticle;
  if (!article) return toast("先选文章");
  if (!state.showTranslation && !article.translation_aligned) {
    await translateArticle(article.id);
    return;
  }
  state.showTranslation = !state.showTranslation;
  renderReader();
  renderArticles();
  renderQuizSource();
}

async function saveArticleContent(id) {
  const body = $("#articleContentInput")?.value.trim();
  if (!body) return toast("正文不能为空");
  const data = await api(`/api/articles/${id}/content`, {
    method: "POST",
    body: JSON.stringify({ body, exam: state.style }),
  });
  state.selectedPoolArticleId = data.article.id;
  const index = state.articles.findIndex(item => item.id === data.article.id);
  if (index >= 0) state.articles[index] = data.article;
  if (state.selectedArticle?.id === data.article.id) {
    state.selectedArticle = data.article;
    state.analysis = data.analysis;
  }
  renderAll();
  toast("已保存完整正文");
}

async function saveExtractionFeedback(articleId, verdict) {
  await api(`/api/articles/${articleId}/extraction-feedback`, {
    method: "POST",
    body: JSON.stringify({ verdict }),
  });
  await loadExtractionQuality();
  renderArticles();
  if (state.selectedArticle?.id === articleId && $("#view-reader").classList.contains("active")) renderReader();
  toast(verdict === "correct" ? "已记录正文准确" : "已记录正文混入问题");
}

function renderExtractionLabeler() {
  const data = state.extractionAnnotation;
  if (!data) return;
  const blocks = data.blocks || [];
  const current = blocks[state.extractionBlockIndex];
  $("#extractionLabelTitle").textContent = data.article.title;
  $("#extractionLabelMeta").textContent = `${data.article.source} · ${data.article.extraction_version || "未记录规则"}`;
  $("#extractionLabelProgress").textContent = `${data.summary.labeled} / ${data.summary.total}`;
  $("#extractionUsableCount").textContent = `可用标签 ${data.summary.usable}`;
  $("#previousExtractionBlockBtn").disabled = state.extractionBlockIndex <= 0;
  $("#nextExtractionBlockBtn").disabled = state.extractionBlockIndex >= blocks.length - 1;
  $("#extractionBlockList").innerHTML = blocks.map((block, index) => `
    <button class="extraction-block-item ${index === state.extractionBlockIndex ? "active" : ""}" data-extraction-block-index="${index}">
      <strong>${String(index + 1).padStart(2, "0")}</strong>
      <span><b>${escapeHtml(block.label ? `已标：${data.labels.find(item => item.id === block.label)?.label || block.label}` : `建议：${data.labels.find(item => item.id === block.suggested_label)?.label || block.suggested_label}`)}</b><small>${escapeHtml(block.text)}</small></span>
    </button>`).join("");
  if (!current) {
    $("#extractionBlockDetail").innerHTML = `<div class="empty-state">没有可标注区块</div>`;
    return;
  }
  const suggestedName = data.labels.find(item => item.id === current.suggested_label)?.label || current.suggested_label;
  $("#extractionBlockDetail").innerHTML = `
    <div class="extraction-block-detail-head">
      <div><span class="eyebrow">区块 ${state.extractionBlockIndex + 1}</span><h3>建议：${escapeHtml(suggestedName)}</h3></div>
      ${badge(`${Math.round(Number(current.suggestion_confidence || 0) * 100)}%`)}
    </div>
    <div class="extraction-block-text">${escapeHtml(current.text)}</div>
    <div class="extraction-label-options" role="group" aria-label="区块标签">
      ${data.labels.map(item => `<button class="${current.label === item.id ? "active" : ""}" data-save-extraction-label="${item.id}" data-block-hash="${current.block_hash}">${escapeHtml(item.label)}</button>`).join("")}
    </div>`;
  $("#extractionBlockList").querySelector(".active")?.scrollIntoView({ block: "nearest" });
}

async function openExtractionLabeler(articleId) {
  state.extractionAnnotation = await api(`/api/articles/${articleId}/extraction-blocks`);
  const firstRemaining = state.extractionAnnotation.blocks.findIndex(block => !block.label);
  state.extractionBlockIndex = firstRemaining >= 0 ? firstRemaining : 0;
  renderExtractionLabeler();
  const dialog = $("#extractionLabelDialog");
  if (!dialog.open) dialog.showModal();
}

async function saveExtractionBlockLabel(blockHash, label) {
  const articleId = state.extractionAnnotation?.article?.id;
  if (!articleId) return;
  const currentIndex = state.extractionBlockIndex;
  state.extractionAnnotation = await api(`/api/articles/${articleId}/extraction-block-labels`, {
    method: "POST",
    body: JSON.stringify({ block_hash: blockHash, label }),
  });
  await loadExtractionQuality();
  const blocks = state.extractionAnnotation.blocks;
  const nextRemaining = blocks.findIndex((block, index) => index > currentIndex && !block.label);
  state.extractionBlockIndex = nextRemaining >= 0 ? nextRemaining : currentIndex;
  renderExtractionLabeler();
  toast("区块标签已保存");
}

async function saveArticle() {
  const body = $("#newArticleBody").value.trim();
  if (!body) return toast("正文不能为空");
  const data = await api("/api/articles", {
    method: "POST",
    body: JSON.stringify({
      title: $("#newArticleTitle").value.trim() || "Untitled",
      body,
      level: $("#newArticleLevel").value,
      content_type: $("#newArticleContentType").value,
      source: "manual",
      topic: "personal",
    }),
  });
  state.articles.unshift(data.article);
  state.selectedArticle = data.article;
  state.selectedPoolArticleId = data.article.id;
  state.analysis = data.analysis;
  await loadToday();
  renderAll();
  toast("已存入文章库");
}

async function saveCard(term = $("#cardTerm").value.trim(), context = $("#cardContext").value.trim()) {
  if (!term) return toast("词不能为空");
  const selectedBody = state.selectedArticle?.body?.toLowerCase() || "";
  const belongsToSelectedArticle = Boolean(context && state.selectedArticle && selectedBody.includes(term.toLowerCase()));
  const data = await api("/api/cards", {
    method: "POST",
    body: JSON.stringify({
      term,
      kind: term.includes(" ") ? "phrase" : "word",
      context,
      source_article_id: belongsToSelectedArticle ? state.selectedArticle.id : null,
    }),
  });
  await Promise.all([loadCards(), loadReviews()]);
  if (data.created) await loadToday();
  renderCards();
  renderReviews();
  renderLexicon();
  renderStats();
  renderDashboard();
  toast(data.created ? "已加入生词本" : "已更新已有生词的语境");
}

async function translateLexicalTerm(term) {
  if (!state.bridge?.token) return toast("本地翻译连接尚未就绪");
  const clean = String(term || "").trim();
  const data = await api("/api/browser/translate", {
    method: "POST",
    headers: { "X-Language-Coach-Token": state.bridge.token },
    body: JSON.stringify({ text: clean, source_lang: "EN", target_lang: "ZH-HANS" }),
  });
  state.lookupTranslations[clean.toLowerCase()] = data.translated_text;
  const queryItem = state.lexiconResults.find(item => item.type === "query" && item.term.toLowerCase() === clean.toLowerCase());
  if (queryItem) queryItem.translation_zh = data.translated_text;
  renderLexicon();
  await renderLookup(clean);
  toast(data.cached ? "已载入词语翻译" : "翻译完成");
}

async function translateWordNetEntry(item, { silent = false } = {}) {
  if (!item || item.type !== "wordnet" || !state.bridge?.token) return;
  if (state.bridge?.translation?.verified !== true) {
    throw new Error(state.bridge?.translation?.last_error || "中文翻译服务尚未通过验证，请先检查 API 配置。");
  }
  const key = `${item.headword.toLowerCase()}:${item.pos}`;
  if (state.wordnetTranslationsInFlight.has(key)) return;
  const segments = [...new Set((item.senses || []).flatMap(sense => [
    ...(sense.definitions || []),
    ...(sense.examples || []),
  ]).concat([
    item.headword,
    ...(item.synonyms || []).map(value => typeof value === "string" ? value : value.term),
    ...(item.antonyms || []).map(value => typeof value === "string" ? value : value.term),
    ...(item.family || []).map(value => typeof value === "string" ? value : value.term),
    ...(item.collocations || []).map(value => typeof value === "string" ? value : value.phrase),
    ...(item.semantic_relations || []).flatMap(relation => (relation.term_details || relation.terms || []).map(value => typeof value === "string" ? value : value.term)),
    ...(item.contexts || []).map(context => context.text),
  ]).filter(Boolean))];
  if (!segments.length) return;
  state.wordnetTranslationsInFlight.add(key);
  try {
    const data = await api("/api/browser/translate-segments", {
      method: "POST",
      headers: { "X-Language-Coach-Token": state.bridge.token },
      body: JSON.stringify({ segments, source_lang: "EN", target_lang: "ZH-HANS" }),
    });
    const translated = Object.fromEntries(data.source_segments.map((source, index) => [source, data.translated_segments[index]]));
    item.senses = (item.senses || []).map(sense => ({
      ...sense,
      definition_translations: (sense.definitions || []).map(value => translated[value] || ""),
      example_translations: (sense.examples || []).map(value => translated[value] || ""),
    }));
    item.headword_translation_zh = translated[item.headword] || item.headword_translation_zh || "";
    item.synonyms = (item.synonyms || []).map(value => {
      const term = typeof value === "string" ? value : value.term;
      return { ...(typeof value === "string" ? {} : value), term, meaning_zh: translated[term] || value.meaning_zh || "" };
    });
    item.antonyms = (item.antonyms || []).map(value => {
      const term = typeof value === "string" ? value : value.term;
      return { ...(typeof value === "string" ? {} : value), term, meaning_zh: translated[term] || value.meaning_zh || "" };
    });
    item.family = (item.family || []).map(value => {
      const term = typeof value === "string" ? value : value.term;
      return { ...(typeof value === "string" ? {} : value), term, meaning_zh: translated[term] || value.meaning_zh || "" };
    });
    item.collocations = (item.collocations || []).map(value => ({
      ...value,
      meaning_zh: translated[value.phrase] || value.meaning_zh || "",
    }));
    item.semantic_relations = (item.semantic_relations || []).map(relation => ({
      ...relation,
      terms: (relation.term_details || relation.terms || []).map(value => {
        const term = typeof value === "string" ? value : value.term;
        return { ...(typeof value === "string" ? {} : value), term, meaning_zh: translated[term] || value.meaning_zh || "" };
      }),
      term_details: (relation.term_details || relation.terms || []).map(value => {
        const term = typeof value === "string" ? value : value.term;
        return { ...(typeof value === "string" ? {} : value), term, meaning_zh: translated[term] || value.meaning_zh || "" };
      }),
    }));
    item.examples = (item.examples || []).map(example => ({ ...example, translation: translated[example.text] || example.translation || "" }));
    item.contexts = (item.contexts || []).map(context => ({ ...context, translation_zh: translated[context.text] || context.translation_zh || "" }));
    item.meaning_zh = translated[item.core_meaning] || Object.values(translated)[0] || "";
    state.lookupTranslations[item.headword.toLowerCase()] = item.meaning_zh;
    state.wordnetAutoTranslationFailed = false;
    renderLexicon();
    if (!silent) toast(data.cached ? "已载入中文义项" : "中文义项翻译完成");
  } finally {
    state.wordnetTranslationsInFlight.delete(key);
  }
}

async function refreshFeeds() {
  toast("开始更新 RSS");
  const result = await api("/api/feeds/refresh", { method: "POST", body: "{}" });
  await Promise.all([loadArticles(), loadToday(), loadFeedStatus()]);
  renderAll();
  const errorText = result.errors?.length ? `，${result.errors.length} 个源失败` : "";
  toast(`新增 ${result.imported || 0} · 更新 ${result.updated || 0}${errorText}`);
}

async function toggleMistake(id) {
  const data = await api(`/api/mistakes/${id}/solve`, { method: "POST", body: "{}" });
  if (data.progress) state.progress = data.progress;
  await Promise.all([loadMistakes(), loadToday(), loadReviews()]);
  renderAll();
  if (data.points) toast(`错题复盘完成，+${data.points} XP`);
}

async function generateSimilar(mistakeId) {
  const data = await api(`/api/mistakes/${mistakeId}/similar`, {
    method: "POST",
    body: JSON.stringify({ count: 3 }),
  });
  state.similarByMistake[mistakeId] = data.quizzes || [];
  renderMistakes();
  toast(`已生成 ${state.similarByMistake[mistakeId].length} 道同类题`);
}

async function generateNextSet({ questionType = "", errorType = "", limit = 10 } = {}) {
  const data = await api("/api/practice/next-set", {
    method: "POST",
    body: JSON.stringify({ style: state.style, limit, question_type: questionType, error_type: errorType }),
  });
  if (!(data.quizzes || []).length) return toast("当前还没有足够的题目或错题生成下一组");
  state.quizzes = data.quizzes;
  state.selectedPaper = null;
  resetQuizSession();
  await syncPracticeRunNow({ newRun: true });
  setView("quiz");
  renderQuizzes();
  renderQuizSource();
  toast(errorType ? `已载入专项巩固：${errorType}` : data.focus?.length ? `下一组聚焦：${data.focus.slice(0, 2).join("、")}` : "已载入下一组训练");
}

document.addEventListener("click", async event => {
  const button = event.target.closest("button");
  if (!button) return;
  try {
    if (button.dataset.articleLayout) {
      await saveArticlePreferences({ article_layout: button.dataset.articleLayout });
      return;
    }
    if (button.dataset.articleDensity) {
      await saveArticlePreferences({ article_density: button.dataset.articleDensity });
      return;
    }
    if (button.dataset.articleVisibility !== undefined) {
      state.articleVisibility = button.dataset.articleVisibility;
      await loadArticles($("#articleSearch").value.trim());
      renderArticles();
      return;
    }
    if (button.id === "openProfileDialogBtn" || button.dataset.openProfileDialog !== undefined) openProfileDialog();
    if (button.id === "closeProfileDialogBtn" || button.id === "cancelProfileDialogBtn") closeProfileDialog();
    if (button.id === "openAssistantBtn") openAssistant();
    if (button.id === "closeAssistantBtn") closeAssistant();
    if (button.dataset.assistantMode) {
      closeAssistant();
      await setLearningMode(button.dataset.assistantMode);
      setView("dashboard");
      renderDashboard();
    }
    if (button.dataset.assistantView) {
      closeAssistant();
      setView(button.dataset.assistantView);
      renderAll();
    }
    if (button.dataset.lexiconFilter) state.lexiconFilter = button.dataset.lexiconFilter;
    if (button.dataset.learningMode) await setLearningMode(button.dataset.learningMode);
    if (button.dataset.view) setView(button.dataset.view);
    if (button.id === "backBtn") {
      if (window.history.length > 1) window.history.back();
      else setView("dashboard");
      return;
    }
    if (button.dataset.lexiconFilter) renderLexicon();
    if (button.dataset.viewJump) setView(button.dataset.viewJump);
    if (button.dataset.editPlan !== undefined) {
      setView("dashboard");
      const settings = $(".plan-settings");
      settings.open = true;
      settings.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    if (button.dataset.view === "quiz") {
      if (!state.quizzes.length) await loadQuizzes();
      if (!state.quizzes.length && state.selectedArticle) await generateQuizzes(state.selectedArticle.id, { open: false });
      if (state.quizzes.length && !state.practiceRun) await syncPracticeRunNow({ newRun: true });
      renderQuizzes();
      renderQuizSource();
    }
    if (button.id === "refreshAllBtn") await boot();
    if (button.id === "saveLearnerSettingsBtn") await saveLearnerSettings();
    if (button.id === "createBackupBtn") await createDataBackup();
    if (button.id === "restoreBackupBtn") await restoreDataBackup();
    if (button.dataset.profileSource) setProfileSource(button.dataset.profileSource);
    if (button.id === "saveLearnerProfileBtn") await saveLearnerProfile();
    if (button.id === "loadQuickTestBtn") await loadQuickTest();
    if (button.id === "submitQuickTestBtn") await submitQuickTest();
    if (button.dataset.completeDailyTask) {
      await setDailyTaskComplete(
        button.dataset.completeDailyTask,
        Number(button.dataset.dailyTargetCount),
      );
    }
    if (button.dataset.addPlanItem) {
      await addDailyPlanItem({
        task: button.dataset.planTask,
        itemType: button.dataset.addPlanItem,
        itemId: Number(button.dataset.planItemId),
        title: button.dataset.planItemTitle || "",
      });
    }
    if (button.dataset.completePlanItem) {
      await completeDailyPlanItem(Number(button.dataset.completePlanItem));
    }
    if (button.id === "refreshPracticeHistoryBtn") {
      await loadPracticeHistory({ selectFirst: true });
      renderPracticeHistory();
    }
    if (button.id === "modePrimaryAction") {
      await startModeFocus();
    }
    if (button.id === "resumePracticeBtn") {
      setView("quiz");
      renderQuizzes();
      renderQuizSource();
    }
    if (button.id === "abandonPracticeBtn" && window.confirm("放弃当前未完成训练？已完成的单题作答记录不会删除。")) {
      await finishServerPracticeRun("abandon");
      clearQuizDraft();
      resetQuizSession();
      renderAll();
    }
    if (button.dataset.startPrescription) {
      await generateNextSet({
        questionType: button.dataset.prescriptionType || "",
        limit: Number(button.dataset.startPrescription) || 5,
      });
    }
    if (button.id === "toggleTranslationBtn" || button.id === "quizTranslationBtn" || button.dataset.toggleTranslation) await toggleArticleTranslation();
    if (button.id === "saveTranslationBtn") await saveTranslation();
    if (button.id === "translateArticleBtn") await translateArticle();
    if (button.dataset.translateArticle) await translateArticle(Number(button.dataset.translateArticle));
    if (button.dataset.openExtractionLabeler) await openExtractionLabeler(Number(button.dataset.openExtractionLabeler));
    if (button.dataset.extractionBlockIndex !== undefined) {
      state.extractionBlockIndex = Number(button.dataset.extractionBlockIndex);
      renderExtractionLabeler();
    }
    if (button.dataset.saveExtractionLabel) await saveExtractionBlockLabel(button.dataset.blockHash, button.dataset.saveExtractionLabel);
    if (button.id === "closeExtractionLabelBtn") $("#extractionLabelDialog").close();
    if (button.id === "previousExtractionBlockBtn" && state.extractionBlockIndex > 0) {
      state.extractionBlockIndex -= 1;
      renderExtractionLabeler();
    }
    if (button.id === "nextExtractionBlockBtn" && state.extractionBlockIndex < (state.extractionAnnotation?.blocks.length || 1) - 1) {
      state.extractionBlockIndex += 1;
      renderExtractionLabeler();
    }
    if (button.dataset.extractionFeedback) await saveExtractionFeedback(Number(button.dataset.articleId), button.dataset.extractionFeedback);
    if (button.dataset.saveArticleContent) await saveArticleContent(Number(button.dataset.saveArticleContent));
    if (button.id === "searchArticlesBtn") {
      await loadArticles($("#articleSearch").value.trim());
      renderAll();
    }
    if (button.id === "refreshFeedsBtn") await refreshFeeds();
    if (button.dataset.subscribeSource) await setSourceSubscription(button.dataset.subscribeSource, button.dataset.subscribeActive === "true");
    if (button.dataset.subscribeCategory) await setSubscription("category", button.dataset.subscribeCategory, button.dataset.subscribeActive === "true");
    if (button.id === "saveArticleBtn") await saveArticle();
    if (button.id === "importEpubBtn") await importEpub();
    if (button.id === "openEpubChapterBtn") await openEpubChapter();
    if (button.id === "analyzeBtn") await analyzeArticle();
    if (button.id === "generateQuizBtn") await generatePassagePractice();
    if (button.id === "generatePracticeBtn") await generateQuizzes();
    if (button.id === "generateFullPaperBtn") await generateFullPaper();
    if (button.id === "nextSetBtn" || button.dataset.nextSet) await generateNextSet();
    if (button.dataset.nextSetTypeOnly) await generateNextSet({ questionType: button.dataset.nextSetTypeOnly });
    if (button.dataset.nextSetError) await generateNextSet({ questionType: button.dataset.nextSetType || "", errorType: button.dataset.nextSetError });
    if (button.dataset.historyNextType !== undefined) await generateNextSet({ questionType: button.dataset.historyNextType || "" });
    if (button.id === "loadPaperBtn") await loadPaper(Number($("#quizPaperSelect").value));
    if (button.id === "restartQuizSessionBtn" || button.dataset.retrySession) {
      resetQuizSession();
      await syncPracticeRunNow({ newRun: true });
      renderQuizzes();
      toast("已重新开始本轮训练");
    }
    if (button.id === "finishQuizSessionBtn") await finishQuizSession();
    if (button.dataset.quizDisplay) {
      state.quizSession.display = button.dataset.quizDisplay;
      localStorage.setItem("lc-v2-quiz-display", state.quizSession.display);
      schedulePracticeRunSync();
      renderQuizzes();
    }
    if (button.dataset.quizNav !== undefined) {
      state.quizSession.activeIndex = Number(button.dataset.quizNav);
      schedulePracticeRunSync();
      syncPaperSourceForQuestion();
      renderQuizzes();
      document.querySelector(`[data-quiz-card]`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    if (button.dataset.flagQuiz) {
      const quizId = Number(button.dataset.flagQuiz);
      state.quizSession.flagged[quizId] = !state.quizSession.flagged[quizId];
      schedulePracticeRunSync();
      renderQuizzes();
    }
    if (button.dataset.toggleQuizHint) {
      const quizId = Number(button.dataset.toggleQuizHint);
      state.quizSession.hintUsed[quizId] = true;
      schedulePracticeRunSync();
      renderQuizzes();
      return;
    }
    if (button.id === "showAnswersBtn") {
      state.showAnswers = !state.showAnswers;
      renderQuizzes();
    }
    if (button.id === "saveCardBtn") await saveCard();
    if (button.id === "loadCardsBtn") {
      await Promise.all([loadCards(), loadReviews()]);
      renderAll();
    }
    if (button.dataset.reviewKind) {
      state.reviewKind = button.dataset.reviewKind;
      state.selectedReviewId = null;
      state.reviewAnswerRevealed = false;
      await loadReviews();
      renderReviews();
    }
    if (button.dataset.selectReview) {
      state.selectedReviewId = Number(button.dataset.selectReview);
      state.reviewAnswerRevealed = false;
      renderReviews();
    }
    if (button.id === "revealReviewAnswerBtn") {
      state.reviewAnswerRevealed = true;
      renderReviews();
    }
    if (button.dataset.rateReview) await rateReview(Number(button.dataset.reviewId), button.dataset.rateReview);
    if (button.id === "undoReviewBtn") await undoReview();
    if (button.id === "copyBridgeTokenBtn") {
      await navigator.clipboard.writeText($("#bridgeToken").value);
      toast("连接令牌已复制");
    }
    if (button.id === "clearLexiconHistoryBtn") await clearLexiconHistory();
    if (button.dataset.copyLexical) {
      const item = state.selectedLexicalItem;
      const meaning = item?.meaning_zh || item?.headword_translation_zh || item?.translation_zh || item?.core_meaning || "";
      await navigator.clipboard.writeText([button.dataset.copyLexical, meaning].filter(Boolean).join("\n"));
      toast("词头与释义已复制");
    }
    if (button.dataset.jumpLexicalSection) {
      document.getElementById(button.dataset.jumpLexicalSection)?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    if (button.id === "loadMistakesBtn") {
      await loadMistakes();
      renderAll();
    }
    if (button.dataset.openArticle) await openArticle(button.dataset.openArticle);
    if (button.dataset.replayEvidence) await replayEvidence(Number(button.dataset.replayEvidence), button.dataset.replayText || "");
    if (button.dataset.selectArticle) {
      state.selectedPoolArticleId = Number(button.dataset.selectArticle);
      renderArticles();
    }
    if (button.dataset.quizArticle) {
      await openArticle(button.dataset.quizArticle);
      await generatePassagePractice(button.dataset.quizArticle);
    }
    if (button.dataset.word) await renderLookup(button.dataset.word);
    if (button.dataset.lexiconTab) {
      state.lexiconFilter = button.dataset.lexiconTab;
      renderLexicon();
      setView("lexicon");
    }
    if (button.dataset.searchQuery !== undefined) {
      state.lexiconFilter = button.dataset.openLexicon ? "all" : state.lexiconFilter;
      await searchLexicon(button.dataset.searchQuery);
      $("#quickLexiconResults").hidden = true;
    }
    if (button.dataset.lexicalId) {
      state.selectedLexicalItem = state.lexiconResults.find(item => item.type === button.dataset.lexicalType && item.id === Number(button.dataset.lexicalId));
      renderLexicon();
    }
    if (button.dataset.speak) speak(button.dataset.speak, button.dataset.voice || "en-US");
    if (button.dataset.translateTerm) await translateLexicalTerm(button.dataset.translateTerm);
    if (button.dataset.translateWordnet) {
      const item = state.lexiconResults.find(result => result.type === "wordnet" && result.id === Number(button.dataset.translateWordnet));
      await translateWordNetEntry(item);
    }
    if (button.dataset.savePhrase) {
      const example = state.selectedLexicalItem?.examples?.[0];
      await saveCard(button.dataset.savePhrase, typeof example === "string" ? example : example?.text || "");
    }
    if (button.dataset.saveLookup) {
      const articleBody = state.selectedArticle?.body || "";
      const context = articleBody.toLowerCase().includes(button.dataset.saveLookup.toLowerCase()) ? sentenceFor(articleBody, button.dataset.saveLookup) : "";
      await saveCard(button.dataset.saveLookup, context);
    }
    if (button.dataset.confidenceQuiz) {
      state.quizSession.confidence[Number(button.dataset.confidenceQuiz)] = normalizeConfidenceValue(button.dataset.confidence);
      schedulePracticeRunSync();
      renderQuizzes();
      return;
    }
    if (button.dataset.answerQuiz) {
      await submitAnswer(Number(button.dataset.answerQuiz), button.dataset.answer, button);
    }
    if (button.dataset.selectQuizAnswer) {
      await selectQuizAnswer(Number(button.dataset.selectQuizAnswer), button.dataset.answer);
    }
    if (button.dataset.submitTyped) {
      const input = document.querySelector(`[data-typed-quiz="${button.dataset.submitTyped}"]`);
      if (state.quizSession.mode === "practice" && !state.quizSession.confidence[Number(button.dataset.submitTyped)]) {
        toast("先选择答题信心，再提交答案");
      } else {
        await submitAnswer(Number(button.dataset.submitTyped), input.value.trim(), button);
      }
    }
    if (button.dataset.selectMistake) {
      state.selectedMistakeId = Number(button.dataset.selectMistake);
      renderMistakes();
    }
    if (button.dataset.practiceSession) await selectPracticeSession(Number(button.dataset.practiceSession));
    if (button.dataset.generateSimilar) await generateSimilar(Number(button.dataset.generateSimilar));
    if (button.dataset.solveMistake) await toggleMistake(button.dataset.solveMistake);
  } catch (error) {
    toast(error.message);
  }
});

document.addEventListener("click", event => {
  const word = event.target.closest(".reader-word");
  if (word) renderLookup(word.dataset.word).catch(error => toast(error.message));
  if (!event.target.closest(".global-search-wrap")) $("#quickLexiconResults").hidden = true;
});

document.addEventListener("dblclick", event => {
  if (event.target.closest("input, textarea, select, button")) return;
  const selected = window.getSelection()?.toString().trim().replace(/\s+/g, " ") || "";
  if (!/^[A-Za-z][A-Za-z' -]{0,79}$/.test(selected) || selected.split(" ").length > 6) return;
  $("#globalLexiconSearch").value = selected;
  if (selected.includes(" ")) renderLookup(selected).catch(error => toast(error.message));
  searchLexicon(selected, { quick: true }).catch(error => toast(error.message));
  $("#globalLexiconSearch").focus();
});

$("#globalStyle").addEventListener("change", async event => {
  state.style = event.target.value;
  localStorage.setItem("lc-v2-style", state.style);
  state.selectedPaper = null;
  state.selectedPracticeSession = null;
  await Promise.all([loadArticles(), loadFeeds(), loadExamTypes(), loadExamLibrary(), loadToday(), loadPracticeHistory(), loadPracticePrescription()]);
  await applyQuizControlChange();
  renderAll();
  toast(`文章池已切换为 ${state.style} 来源`);
});

$("#quizPracticeType").addEventListener("change", applyQuizControlChange);

$("#quizScope").addEventListener("change", async event => {
  if (event.target.value !== "full-paper") {
    state.selectedPaper = null;
  }
  await applyQuizControlChange();
});

$("#quizPaperSelect").addEventListener("change", async event => {
  if (event.target.value) await loadPaper(Number(event.target.value));
});

$("#epubBookSelect").addEventListener("change", async event => {
  await loadBook(Number(event.target.value));
});

$("#quizSessionMode").addEventListener("change", async event => {
  state.quizSession.mode = event.target.value === "mock" ? "mock" : "practice";
  localStorage.setItem("lc-v2-quiz-session-mode", state.quizSession.mode);
  resetQuizSession();
  await syncPracticeRunNow({ newRun: true });
  renderQuizzes();
  toast(state.quizSession.mode === "mock" ? "模考模式：交卷后统一显示解析" : "训练模式：作答后立即讲解");
});

document.addEventListener("input", event => {
  if (!event.target.matches("[data-typed-quiz]")) return;
  const quizId = Number(event.target.dataset.typedQuiz);
  state.quizSession.answers[quizId] = event.target.value;
  schedulePracticeRunSync();
  const answered = state.quizzes.filter(quiz => String(state.quizSession.answers[quiz.id] || "").trim()).length;
  const progress = $("#quizSessionSummary")?.querySelectorAll("strong")[1];
  if (progress) progress.textContent = `${answered}/${state.quizzes.length}`;
  const index = state.quizzes.findIndex(quiz => quiz.id === quizId);
  const nav = document.querySelector(`.quiz-nav-button[data-quiz-nav="${index}"]`);
  if (nav) {
    nav.classList.toggle("answered", Boolean(event.target.value.trim()));
    nav.classList.toggle("unanswered", !event.target.value.trim());
  }
});

document.addEventListener("change", event => {
  if (!event.target.matches("[data-typed-quiz]")) return;
  const quizId = Number(event.target.dataset.typedQuiz);
  const answer = event.target.value.trim();
  const previous = state.quizSession.committedAnswers[quizId] || "";
  if (previous && previous !== answer) state.quizSession.answerChanges[quizId] = (state.quizSession.answerChanges[quizId] || 0) + 1;
  state.quizSession.committedAnswers[quizId] = answer;
});

$("#articleSearch").addEventListener("keydown", async event => {
  if (event.key === "Enter") {
    await loadArticles(event.target.value.trim());
    renderAll();
  }
});

$("#articleTopicFilter").addEventListener("change", async event => {
  state.articleTopic = event.target.value;
  await loadArticles($("#articleSearch").value.trim());
  renderAll();
});

$("#articleHubFilter").addEventListener("change", async event => {
  state.articleHub = event.target.value;
  await loadArticles($("#articleSearch").value.trim());
  renderArticles();
});

$("#articleContentTypeFilter").addEventListener("change", async event => {
  state.articleContentType = event.target.value;
  await loadArticles($("#articleSearch").value.trim());
  renderAll();
});

$("#recommendedOnly").addEventListener("change", async event => {
  state.recommendedOnly = event.target.checked;
  await loadArticles($("#articleSearch").value.trim());
  renderAll();
});

$("#globalSearchForm").addEventListener("submit", async event => {
  event.preventDefault();
  await searchLexicon($("#globalLexiconSearch").value);
  $("#quickLexiconResults").hidden = true;
});

$("#lexiconSearchForm").addEventListener("submit", async event => {
  event.preventDefault();
  await searchLexicon($("#lexiconSearch").value, { open: false });
});

let quickSearchTimer;
$("#globalLexiconSearch").addEventListener("input", event => {
  clearTimeout(quickSearchTimer);
  const query = event.target.value.trim();
  if (!query) {
    $("#quickLexiconResults").hidden = true;
    return;
  }
  quickSearchTimer = setTimeout(() => searchLexicon(query, { quick: true }).catch(error => toast(error.message)), 180);
});

$("#globalLexiconSearch").addEventListener("focus", event => {
  if (event.target.value.trim() && $("#quickLexiconResults").innerHTML) $("#quickLexiconResults").hidden = false;
});

async function boot() {
  await loadHealth();
  await loadActivePracticeData();
  await Promise.all([loadArticles(), loadBooks(), loadCards(), loadReviews(), loadMistakes(), loadFeeds(), loadFeedStatus(), loadExtractionQuality(), loadSourceCatalog(), loadSubscriptions(), loadToday(), loadProgress(), loadLearnerSettings(), loadPracticeHistory(), loadPracticePrescription(), loadExamTypes(), loadExamLibrary(), loadArticleTopics(), loadArticleHubs(), loadArticleContentTypes(), loadDictionaryStatus(), loadLexiconHistory(), loadBridgeConfig(), loadBackups(), searchLexicon("", { open: false, history: false })]);
  const restoredServerRun = await restoreServerPracticeRun();
  if (!restoredServerRun && !state.selectedArticle && state.articles[0]) {
    const data = await api(`/api/articles/${state.articles[0].id}?exam=${encodeURIComponent(state.style)}`);
    state.selectedArticle = data.article;
    state.analysis = data.analysis;
  }
  if (!restoredServerRun) {
    await loadQuizzes();
    if (!state.quizzes.length && state.selectedArticle) {
      await generateQuizzes(state.selectedArticle.id, { open: false, startRun: false });
    }
  }
  renderAll();
  if (!state.learnerProfile?.completed) openProfileDialog();
  else maybeOpenAssistant();
  const startupParams = new URLSearchParams(window.location.search);
  if (startupParams.get("view") === "lexicon" || startupParams.get("q")) {
    await searchLexicon(startupParams.get("q") || "", { open: true, history: false, track: false });
  }
}

$("#globalStyle").value = state.style;
$("#newArticleBody").value = sampleImport;

setInterval(() => {
  if (state.quizSession.submitted || !state.quizzes.length || !$("#view-quiz")?.classList.contains("active")) return;
  const timer = $("#quizTimer");
  if (timer) timer.textContent = formatDuration(quizElapsedSeconds());
}, 1000);

setInterval(() => {
  if (state.practiceRun?.id && !state.quizSession.submitted) {
    practiceRunSyncChain = practiceRunSyncChain.then(() => syncPracticeRunNow()).catch(() => null);
  }
}, 15000);

window.addEventListener("pagehide", () => {
  const snapshot = practiceRunSnapshot();
  if (!snapshot || !state.practiceRun?.id) return;
  fetch("/api/practice-runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(snapshot),
    keepalive: true,
  }).catch(() => null);
});

boot().catch(error => {
  $("#serverStatus").textContent = "后端未连接";
  toast(error.message);
});

window.addEventListener("popstate", async () => {
  const params = new URLSearchParams(window.location.search);
  const view = params.get("view") || "dashboard";
  if (view === "lexicon") {
    await searchLexicon(params.get("q") || "", { open: false, history: false, track: false });
  } else {
    setView(view, { pushHistory: false });
    renderAll();
  }
});
