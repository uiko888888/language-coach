const api = async (path, options = {}) => {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
};

const state = {
  articles: [],
  books: [],
  selectedBook: null,
  cards: [],
  quizzes: [],
  mistakes: [],
  feeds: [],
  sourceCatalog: [],
  subscriptions: [],
  today: { lanes: [], subscription_count: 0 },
  lexiconResults: [],
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
  },
  examTypes: [],
  examResources: [],
  examPapers: [],
  selectedPaper: null,
  practiceSessions: [],
  practiceAnalytics: null,
  selectedPracticeSession: null,
  evidenceReplay: "",
  showTranslation: false,
  articleTopics: [],
  articleTopic: "",
  articleContentTypes: [],
  articleContentType: "",
  recommendedOnly: false,
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
  reader: ["阅读台", "一篇文章可以拆成阅读、选词填空、首字母和证据定位。"],
  quiz: ["题目", "先做题，再看证据和解析，错题会自动收集。"],
  cards: ["生词本", "主动添加或从文章里点词添加，后面可做词块复习。"],
  mistakes: ["错题", "保存你的错误答案、正确答案和原文证据。"],
  history: ["训练记录", "查看单次训练详情、能力趋势和下一步建议。"],
  lexicon: ["词汇中心", "从单词、中文、词形或词源进入同一张词汇网络。"],
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

function formatDuration(totalSeconds) {
  const seconds = Math.max(0, Number(totalSeconds) || 0);
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = Math.floor(seconds % 60);
  return hours
    ? `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`
    : `${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
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
  $("#modeDescription").textContent = interest
    ? `优先推荐订阅、新闻与文化内容；今日计划 ${state.learnerSettings.daily_minutes} 分钟。${activeGoal ? ` 当前目标：${activeGoal}` : ""}`
    : `优先匹配考试难度、证据定位与同义替换；今日计划 ${state.learnerSettings.daily_minutes} 分钟。${activeGoal ? ` 当前目标：${activeGoal}` : ""}`;
  $("#modePrimaryAction").textContent = interest ? "开始轻松阅读" : "开始今日训练";
  $("#globalStyle").title = interest ? "兴趣素材生成题目时参照的考试难度" : "当前备考目标";
  renderDailyPlan();

  $("#recentArticles").innerHTML = (state.today.lanes || []).map(lane => {
    const article = lane.article;
    return `
    <div class="item">
      <div class="badge-row">${badge(lane.label, "amber")}${badge(article.content_type_label || "学术解释", "teal")}${badge(article.source || "manual")}</div>
      <h3>${escapeHtml(article.title)}</h3>
      <p>${escapeHtml(lane.reason)} · ${escapeHtml(excerpt(article.highlight || article.body, 120))}</p>
      <div class="toolbar"><button data-open-article="${article.id}">阅读</button><button data-add-plan-item="article" data-plan-task="reading" data-plan-item-id="${article.id}" data-plan-item-title="${escapeHtml(article.title)}">加入今日阅读</button></div>
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

function renderArticles() {
  const list = $("#articleTitleList");
  const detail = $("#articleDetail");
  if (!state.articles.length) {
    list.innerHTML = `<div class="empty-state">文章池为空</div>`;
    detail.innerHTML = `<div class="empty-state">更新 RSS 或导入一篇文章。</div>`;
  } else {
    if (!state.articles.some(article => article.id === state.selectedPoolArticleId)) {
      state.selectedPoolArticleId = state.articles[0].id;
    }
    const selected = state.articles.find(article => article.id === state.selectedPoolArticleId);
    list.innerHTML = state.articles.map((article, index) => `
      <button class="master-list-item ${article.id === selected.id ? "active" : ""}" data-select-article="${article.id}">
        <span class="master-number">${String(index + 1).padStart(2, "0")}</span>
        <span class="master-copy">
          <strong>${escapeHtml(article.title)}</strong>
          <small>${article.recommended_today ? `推荐 ${article.daily_rank} · ` : ""}${escapeHtml(article.content_type_label || "学术解释")} · ${escapeHtml(article.source || "manual")} · ${escapeHtml(article.level)}</small>
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
            ${badge(selected.content_type_label || "学术解释", selected.content_type === "opinion" ? "amber" : "teal")}
            ${selected.source_kind ? badge(selected.source_kind) : ""}
            ${badge(selected.content_status === "full" ? `完整正文 · ${selected.content_word_count}词` : `RSS摘要 · ${selected.content_word_count}词`, selected.content_status === "full" ? "teal" : "amber")}
            ${selected.source_tier ? badge(selected.source_tier, selected.source_tier === "核心" ? "teal" : "") : ""}
            ${selected.exam_fit ? badge(`${state.style} 匹配 ${selected.exam_fit}%`, selected.exam_fit >= 90 ? "amber" : "") : ""}
          </div>
          <h2>${escapeHtml(selected.title)}</h2>
        </div>
        <div class="toolbar">
          <button data-toggle-translation="true">${state.showTranslation ? "隐藏译文" : "显示译文"}</button>
          <button data-translate-article="${selected.id}">一键翻译</button>
          <button data-open-article="${selected.id}">进入阅读台</button>
          <button class="primary" data-quiz-article="${selected.id}">生成题</button>
        </div>
      </div>
      ${selected.recommended_today ? `<div class="daily-recommendation"><strong>今日推荐 ${selected.daily_rank}</strong><span>${escapeHtml((selected.recommendation_reasons || []).join(" · "))}</span><small>推荐分 ${selected.recommendation_score}</small></div>` : ""}
      ${selected.content_status !== "full" ? `<div class="content-notice"><div><strong>当前保存的是 RSS 摘要</strong><span>阅读器已经显示全部本地内容，完整文章需要打开原始来源或补充正文。</span></div>${selected.source_url ? `<a href="${escapeHtml(selected.source_url)}" target="_blank" rel="noreferrer">打开完整原文</a>` : ""}</div>` : ""}
      ${selected.theme_tags?.length ? `<div class="article-themes"><span>文章主题</span>${selected.theme_tags.map(theme => badge(theme, "amber")).join("")}</div>` : ""}
      ${selected.source_topics?.length ? `<div class="source-topics"><span class="topic-label">来源领域</span>${selected.source_topics.map(topic => badge(topic)).join("")}</div>` : ""}
      <article class="article-detail-body">${bilingualParagraphs(selected.body, selected.translation_zh, state.showTranslation)}</article>
      ${selected.source_url ? `<a class="source-link" href="${escapeHtml(selected.source_url)}" target="_blank" rel="noreferrer">打开原始来源</a>` : ""}
      <details class="content-editor"><summary>${selected.content_status === "full" ? "编辑完整正文" : "补充完整正文"}</summary><textarea id="articleContentInput">${escapeHtml(selected.body)}</textarea><button class="primary" data-save-article-content="${selected.id}">保存为完整正文</button></details>
    `;
  }

  $("#feedList").innerHTML = `
    <div class="source-pool-head">
      <div><span class="muted">Exam-aligned sources</span><h2>${state.style} 来源池</h2></div>
      ${badge("仅保存摘要与链接", "teal")}
    </div>
    ${state.sourceCatalog.map(source => `
      <div class="source-row">
        <div><strong>${escapeHtml(source.name)}</strong><p>${escapeHtml(source.category)} · ${escapeHtml(source.formats.join(" / "))} · ${escapeHtml(source.rights_mode)}</p></div>
        <div class="badge-row">${badge(source.automatic ? "自动更新" : source.access_mode, source.automatic ? "teal" : "")}${badge(source.cadence, "amber")}<button data-subscribe-source="${escapeHtml(source.name)}" data-subscribe-active="${source.subscribed ? "false" : "true"}">${source.subscribed ? "取消订阅" : "订阅"}</button></div>
      </div>
    `).join("")}
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
  $("#readerTitle").textContent = article.title;
  $("#readerMeta").innerHTML = `${badge(article.level, "teal")}${badge(article.content_type_label || "学术解释", article.content_type === "opinion" ? "amber" : "teal")}${badge(article.content_status === "full" ? `完整正文 · ${article.content_word_count}词` : `RSS摘要 · ${article.content_word_count}词`, article.content_status === "full" ? "teal" : "amber")}${(article.theme_tags || []).map(theme => badge(theme, "amber")).join("")}${badge(article.source || "manual")}`;
  $("#readerContentNotice").innerHTML = article.content_status !== "full" ? `<div class="content-notice compact"><div><strong>当前为 RSS 摘要</strong><span>完整内容请打开原文，或在文章池补充正文。</span></div>${article.source_url ? `<a href="${escapeHtml(article.source_url)}" target="_blank" rel="noreferrer">打开原文</a>` : ""}</div>` : "";
  $("#readerBody").innerHTML = state.evidenceReplay
    ? evidenceBilingualParagraphs(article.body, article.translation_zh, state.showTranslation, state.evidenceReplay)
    : bilingualParagraphs(article.body, article.translation_zh, state.showTranslation);
  $("#articleTranslationInput").value = article.translation_zh || "";
  const translationPanel = $("#translationPanel");
  translationPanel.hidden = true;
  translationPanel.innerHTML = "";
  $("#toggleTranslationBtn").textContent = state.showTranslation ? "隐藏译文" : "显示译文";
  $("#toggleTranslationBtn").setAttribute("aria-pressed", String(state.showTranslation));
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
  $("#quizTranslationBtn").textContent = state.showTranslation ? "隐藏译文" : "显示译文";
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
  return ["entry", "wordnet"].includes(item.type) ? item.headword : item.type === "query" ? item.term : item.form;
}

function lexicalSubtitle(item) {
  if (item.type === "entry") return `${item.pos} · ${item.meaning_zh}`;
  if (item.type === "wordnet") return `${item.pos} · ${item.meaning_zh || item.core_meaning}`;
  if (item.type === "query") return `${item.kind === "phrase" ? "短语" : "单词"} · ${item.translation_zh || (item.saved ? "已在生词本" : "待补充释义")}`;
  return `${item.kind} · ${item.meaning_zh}`;
}

function matchesLexiconFilter(item) {
  if (state.lexiconFilter === "all") return true;
  if (state.lexiconFilter === "family") return ["entry", "wordnet"].includes(item.type);
  if (state.lexiconFilter === "morpheme") return item.type === "morpheme";
  return item.type === "morpheme" && item.kind === state.lexiconFilter;
}

function termText(item) {
  if (typeof item === "string") return item.split("（")[0];
  return item?.term || item?.phrase || "";
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
    return `<article class="phrase-item">
      <div class="phrase-head"><div><button class="phrase-query" data-search-query="${escapeHtml(current.phrase)}"><strong>${escapeHtml(current.phrase)}</strong></button><p>${escapeHtml(current.meaning_zh || "")}</p></div><button data-save-phrase="${escapeHtml(current.phrase)}" title="加入生词本" aria-label="加入生词本">＋</button></div>
      ${current.synonyms?.length ? `<div class="phrase-relation"><span>近义表达</span><div class="term-grid">${termButtons(current.synonyms, "synonym")}</div></div>` : ""}
      ${current.antonyms?.length ? `<div class="phrase-relation"><span>反义表达</span><div class="term-grid">${termButtons(current.antonyms, "antonym")}</div></div>` : ""}
    </article>`;
  }).join("");
}

function bilingualExamples(examples, item) {
  return (examples || []).map(example => {
    const current = typeof example === "string" ? { text: example, translation: "" } : example;
    return `<article class="example-item"><p class="example-en">${highlightLexicalText(current.text, item)}</p>${current.translation ? `<p class="example-zh">${escapeHtml(current.translation)}</p>` : ""}</article>`;
  }).join("");
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
    return;
  }
  if (item.type === "query") {
    const translated = state.lookupTranslations[item.term.toLowerCase()] || item.translation_zh || "";
    detail.innerHTML = `
      <div class="dictionary-hero">
        <div><div class="badge-row">${badge(item.kind === "phrase" ? "短语" : "单词", item.kind === "phrase" ? "amber" : "teal")}${badge(item.saved ? `生词本 · ${item.card_status || "new"}` : "尚未保存")}${badge(item.matched_by)}</div><h2>${escapeHtml(item.term)}</h2><div class="pronunciation"><button data-speak="${escapeHtml(item.term)}" data-voice="en-US" title="播放发音">▶ US</button></div></div>
        <div class="toolbar"><button class="primary" data-save-lookup="${escapeHtml(item.term)}">${item.saved ? "更新生词语境" : "加入生词本"}</button>${translated ? "" : `<button data-translate-term="${escapeHtml(item.term)}">一键翻译</button>`}<a class="button-link" href="https://dict.eudic.net/dicts/en/${encodeURIComponent(item.term)}" target="_blank" rel="noreferrer">在欧路中查看</a></div>
      </div>
      <p class="core-definition">${escapeHtml(translated || "本地开放词典尚未收录完整释义。你仍可保存、翻译，并从个人文章语境继续学习。")}</p>
      <div class="dictionary-columns query-columns">
        <section class="dictionary-section"><h3>你的真实语境</h3>${item.contexts?.length ? item.contexts.map(context => `<article class="example-item"><p class="example-en">${searchableEnglish(context.text)}</p><p class="example-zh">${escapeHtml(context.article_title || context.source)}</p>${context.article_id ? `<button data-open-article="${context.article_id}">回到原文</button>` : ""}</article>`).join("") : `<div class="empty-state">尚未在个人文章中找到这个表达。</div>`}</section>
        <section class="dictionary-section"><h3>下一步</h3><p>先确认当前语境含义，再保存整句。后续开放词典导入会补充高频义项、搭配、近义辨析和词源。</p></section>
      </div>
    `;
    return;
  }
  if (item.type === "wordnet") {
    const translated = state.lookupTranslations[item.headword.toLowerCase()] || item.meaning_zh || "";
    const relationSections = (item.semantic_relations || []).map(relation => `
      <div class="phrase-relation"><span>${escapeHtml(relation.label)}</span><div class="term-grid">${termButtons(relation.terms, relation.type === "antonym" ? "antonym" : "family")}</div></div>
    `).join("");
    detail.innerHTML = `
      <div class="dictionary-hero">
        <div><div class="badge-row">${badge("WordNet", "teal")}${badge(item.pos)}${badge(item.source_version || "2025")}</div><h2>${escapeHtml(item.headword)}</h2><div class="pronunciation">${item.ipa_uk ? `<span>${escapeHtml(item.ipa_uk)}</span>` : ""}<button data-speak="${escapeHtml(item.headword)}" data-voice="en-US" title="播放发音">▶ US</button></div></div>
        <div class="toolbar"><button class="primary" data-save-lookup="${escapeHtml(item.headword)}">${item.saved ? "更新生词语境" : "加入生词本"}</button>${item.headword_translation_zh ? "" : `<button data-translate-wordnet="${item.id}">翻译中文义项</button>`}<a class="button-link" href="https://dict.eudic.net/dicts/en/${encodeURIComponent(item.headword)}" target="_blank" rel="noreferrer">在欧路中查看</a></div>
      </div>
      ${item.headword_translation_zh ? `<p class="headword-translation">${escapeHtml(item.headword_translation_zh)}</p>` : ""}
      <p class="core-definition">${escapeHtml(item.core_meaning || "")}</p>
      ${translated ? `<p class="zh-definition">${escapeHtml(translated)}</p>` : `<p class="muted">${state.bridge?.translation?.verified === false ? escapeHtml(state.bridge.translation.last_error || "中文翻译服务验证失败，请检查 API 配置。") : "WordNet 提供英文义项；中文确认可使用上方翻译，结果会缓存到本地。"}</p>`}
      <div class="dictionary-columns">
        <section class="dictionary-section"><h3>义项与例句</h3><div class="sense-list">${(item.senses || []).map((sense, index) => `<article class="example-item"><strong>Sense ${index + 1}</strong>${(sense.definitions || []).map((definition, definitionIndex) => `<p class="example-en">${escapeHtml(definition)}</p>${sense.definition_translations?.[definitionIndex] ? `<p class="example-zh">${escapeHtml(sense.definition_translations[definitionIndex])}</p>` : ""}`).join("")}${(sense.examples || []).map((example, exampleIndex) => `<p class="example-en">${searchableEnglish(example)}</p>${sense.example_translations?.[exampleIndex] ? `<p class="example-zh">${escapeHtml(sense.example_translations[exampleIndex])}</p>` : ""}`).join("")}</article>`).join("") || `<div class="empty-state">暂无义项</div>`}</div></section>
        <section class="dictionary-section"><h3>词组与搭配</h3><div class="phrase-list">${phraseCards(item.collocations) || `<div class="empty-state">当前文章中暂无可确认搭配</div>`}</div></section>
        <section class="dictionary-section"><h3>近义词</h3><div class="term-grid">${termButtons(item.synonyms, "synonym") || `<div class="empty-state">WordNet 未提供近义词</div>`}</div><h4>反义词</h4><div class="term-grid">${termButtons(item.antonyms, "antonym") || `<div class="empty-state">WordNet 未提供直接反义词</div>`}</div></section>
        <section class="dictionary-section"><h3>语义关系</h3>${relationSections || `<div class="empty-state">暂无关系数据</div>`}<p class="source-note">来源：${escapeHtml(item.source_name || "Open English WordNet")} · ${escapeHtml(item.license || "CC BY 4.0")}</p></section>
      </div>
      ${item.contexts?.length ? `<section class="dictionary-section"><h3>你的真实语境</h3>${item.contexts.map(context => `<article class="example-item"><p class="example-en">${searchableEnglish(context.text)}</p><p class="example-zh">${escapeHtml(context.article_title || context.source)}</p>${context.article_id ? `<button data-open-article="${context.article_id}">回到原文</button>` : ""}</article>`).join("")}</section>` : ""}
    `;
    return;
  }
  const saved = state.cards.some(card => card.term.toLowerCase() === item.headword.toLowerCase());
  detail.innerHTML = `
    <div class="dictionary-hero">
      <div><div class="badge-row">${badge(item.level || "词条", "teal")}${badge(item.pos)}${badge(item.register_label)}</div><h2>${escapeHtml(item.headword)}</h2><div class="pronunciation"><span>UK ${escapeHtml(item.ipa_uk)}</span><button data-speak="${escapeHtml(item.headword)}" data-voice="en-GB" title="英式发音">▶ UK</button><span>US ${escapeHtml(item.ipa_us)}</span><button data-speak="${escapeHtml(item.headword)}" data-voice="en-US" title="美式发音">▶ US</button></div></div>
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
  renderLexicalDetail(state.selectedLexicalItem);
}

async function searchLexicon(query, { open = true, quick = false, history = true } = {}) {
  const value = String(query || "").trim();
  const data = await api(`/api/lexicon/search?q=${encodeURIComponent(value)}`);
  if (quick) {
    renderQuickResults(data.results || [], value);
    return data.results || [];
  }
  state.lexiconResults = data.results || [];
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
  const wordnet = state.lexiconResults.find(item => item.type === "wordnet" && (!item.headword_translation_zh || (item.synonyms || []).some(value => !value.meaning_zh)));
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
      <div class="badge-row">${badge(card.kind === "phrase" ? "短语" : "单词", card.kind === "phrase" ? "amber" : "teal")}${badge(card.status || "new")}</div>
      <h3><button class="card-term-link" data-search-query="${escapeHtml(card.term)}">${escapeHtml(card.term)}</button></h3>
      <p>${card.context ? searchableEnglish(card.context) : "尚未保存语境"}</p>
      ${card.note ? `<p>${escapeHtml(card.note)}</p>` : ""}
      <div class="toolbar"><button data-search-query="${escapeHtml(card.term)}" data-open-lexicon="true">查看查询</button>${card.source_article_id ? `<button data-open-article="${card.source_article_id}">回到原文</button>` : ""}<a class="button-link" href="https://dict.eudic.net/dicts/en/${encodeURIComponent(card.term)}" target="_blank" rel="noreferrer">欧路</a></div>
    </div>
  `).join("") || `<div class="item muted">暂无生词</div>`;
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
    <div class="toolbar mistake-actions">
      <button class="primary" data-generate-similar="${selected.id}">${similar.length ? "换一组同类题" : "生成 3 道同类题"}</button>
      <button data-solve-mistake="${selected.id}">${selected.solved ? "重新标记待学" : "这题我学会了"}</button>
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
  const recommendation = analytics.recommendation || {};
  $("#historyRecommendation").innerHTML = `<strong>下一步建议</strong><p>${escapeHtml(recommendation.reason || "完成一次训练后生成建议。")}</p>${recommendation.question_type ? `<button data-history-next-type="${escapeHtml(recommendation.question_type)}">练习 ${escapeHtml(recommendation.question_type)}</button>` : ""}`;
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
        <div class="badge-row">${badge(`第 ${index + 1} 题`)}${badge(attempt.correct ? "正确" : "错误", attempt.correct ? "teal" : "red")}${badge(attempt.question_type)}</div>
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
  renderMistakes();
  renderPracticeHistory();
  renderLexicon();
}

function renderExamTypes() {
  const select = $("#examQuestionType");
  const previous = select.value;
  select.innerHTML = `<option value="">全部对应题型</option>${state.examTypes.map(item => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`).join("")}`;
  if (state.examTypes.some(item => item.id === previous)) select.value = previous;
  const practiceSelect = $("#quizPracticeType");
  const practiceMode = $("#quizPracticeMode");
  if (practiceMode) practiceMode.hidden = state.style !== "general";
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
  $("#serverStatus").textContent = "后端已连接";
  $("#serverStatus").classList.add("ok");
  return data;
}

async function loadProgress() {
  const data = await api("/api/progress");
  state.progress = data.progress;
}

async function loadLearnerSettings() {
  const data = await api("/api/learner-settings");
  state.learnerSettings = data.settings;
  renderLearnerSettings();
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
  $("#quizPracticeType").hidden = isFull;
  $("#quizPracticeMode").hidden = isFull;
  $("#generatePracticeBtn").hidden = isFull;
  $("#quizPaperSelect").hidden = !isFull;
  $("#generateFullPaperBtn").hidden = !isFull;
  $("#loadPaperBtn").hidden = !isFull;
  $("#generatePracticeBtn").textContent = scope === "passage" ? "生成单篇组合题" : "按当前文章出题";
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
  if (state.recommendedOnly) params.set("recommended", "1");
  const data = await api(`/api/articles?${params.toString()}`);
  state.articles = data.articles || [];
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

async function selectPracticeSession(id, { render = true } = {}) {
  state.selectedPracticeSession = await api(`/api/practice-sessions/${id}`);
  if (render) renderPracticeHistory();
}

async function loadFeeds() {
  const data = await api(`/api/feeds?exam=${encodeURIComponent(state.style)}`);
  state.feeds = data.feeds || [];
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

async function setSourceSubscription(name, active) {
  await api("/api/subscriptions", {
    method: "POST",
    body: JSON.stringify({ target_type: "source", target_value: name, active }),
  });
  await Promise.all([loadSourceCatalog(), loadSubscriptions(), loadToday()]);
  renderDashboard();
  renderArticles();
  toast(active ? `已订阅 ${name}` : `已取消订阅 ${name}`);
}

async function loadQuizzes() {
  const params = new URLSearchParams();
  if (state.selectedArticle) params.set("article_id", state.selectedArticle.id);
  params.set("style", state.style);
  const questionType = $("#quizPracticeType")?.value || "";
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

async function generateQuizzes(id = state.selectedArticle?.id, { open = true } = {}) {
  if (!id) return toast("先选文章");
  const mode = $("#quizPracticeMode")?.value || $("#quizMode")?.value || "mixed";
  const questionType = $("#quizScope")?.value === "passage"
    ? "mixed"
    : $("#quizPracticeType")?.value || $("#examQuestionType")?.value || "";
  const data = await api(`/api/articles/${id}/quizzes`, {
    method: "POST",
    body: JSON.stringify({ mode, style: state.style, question_type: questionType }),
  });
  state.quizzes = data.quizzes || [];
  clearQuizDraft();
  resetQuizSession();
  if (open) setView("quiz");
  renderAll();
  toast("题目已生成");
}

async function submitAnswer(quizId, answer, button = null, confidence = state.quizSession.confidence[quizId] || null) {
  state.quizSession.answers[quizId] = String(answer || "").trim();
  state.quizSession.confidence[quizId] = normalizeConfidenceValue(confidence);
  const data = await api("/api/attempts", {
    method: "POST",
    body: JSON.stringify({ quiz_id: quizId, answer, confidence: normalizeConfidenceValue(confidence) }),
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
  const rewardText = data.points ? `，+${data.points} XP` : "（本题积分已结算）";
  toast(data.correct ? `答对了${rewardText}` : `错了：${data.answer}${rewardText}`);
}

async function selectQuizAnswer(quizId, answer) {
  if (state.quizSession.submitted || state.answerFeedback[quizId]) return;
  state.quizSession.answers[quizId] = answer;
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
         answers: state.quizzes.map(quiz => ({ quiz_id: quiz.id, answer: session.answers[quiz.id] || "", confidence: session.confidence[quiz.id] || null })),
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
  session.submitted = true;
  state.showAnswers = true;
  clearQuizDraft();
  await Promise.all([loadPracticeHistory(), loadToday()]);
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
  state.cards = [data.card, ...state.cards.filter(card => card.id !== data.card.id)];
  if (data.created) await loadToday();
  renderCards();
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
  await Promise.all([loadArticles(), loadToday()]);
  renderAll();
  const errorText = result.errors?.length ? `，${result.errors.length} 个源失败` : "";
  toast(`导入 ${result.imported || 0} 条${errorText}`);
}

async function toggleMistake(id) {
  const data = await api(`/api/mistakes/${id}/solve`, { method: "POST", body: "{}" });
  if (data.progress) state.progress = data.progress;
  await Promise.all([loadMistakes(), loadToday()]);
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

async function generateNextSet({ questionType = "", errorType = "" } = {}) {
  const data = await api("/api/practice/next-set", {
    method: "POST",
    body: JSON.stringify({ style: state.style, limit: 10, question_type: questionType, error_type: errorType }),
  });
  if (!(data.quizzes || []).length) return toast("当前还没有足够的题目或错题生成下一组");
  state.quizzes = data.quizzes;
  state.selectedPaper = null;
  resetQuizSession();
  setView("quiz");
  renderQuizzes();
  renderQuizSource();
  toast(errorType ? `已载入专项巩固：${errorType}` : data.focus?.length ? `下一组聚焦：${data.focus.slice(0, 2).join("、")}` : "已载入下一组训练");
}

document.addEventListener("click", async event => {
  const button = event.target.closest("button");
  if (!button) return;
  try {
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
    if (button.dataset.view === "quiz") {
      if (!state.quizzes.length) await loadQuizzes();
      if (!state.quizzes.length && state.selectedArticle) await generateQuizzes(state.selectedArticle.id, { open: false });
      renderQuizzes();
      renderQuizSource();
    }
    if (button.id === "refreshAllBtn") await boot();
    if (button.id === "saveLearnerSettingsBtn") await saveLearnerSettings();
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
      await startDailyPlan();
    }
    if (button.id === "toggleTranslationBtn" || button.id === "quizTranslationBtn" || button.dataset.toggleTranslation) {
      state.showTranslation = !state.showTranslation;
      renderReader();
      renderArticles();
      renderQuizSource();
    }
    if (button.id === "saveTranslationBtn") await saveTranslation();
    if (button.id === "translateArticleBtn") await translateArticle();
    if (button.dataset.translateArticle) await translateArticle(Number(button.dataset.translateArticle));
    if (button.dataset.saveArticleContent) await saveArticleContent(Number(button.dataset.saveArticleContent));
    if (button.id === "searchArticlesBtn") {
      await loadArticles($("#articleSearch").value.trim());
      renderAll();
    }
    if (button.id === "refreshFeedsBtn") await refreshFeeds();
    if (button.dataset.subscribeSource) await setSourceSubscription(button.dataset.subscribeSource, button.dataset.subscribeActive === "true");
    if (button.id === "saveArticleBtn") await saveArticle();
    if (button.id === "importEpubBtn") await importEpub();
    if (button.id === "openEpubChapterBtn") await openEpubChapter();
    if (button.id === "analyzeBtn") await analyzeArticle();
    if (button.id === "generateQuizBtn") await generateQuizzes();
    if (button.id === "loadQuizzesBtn") {
      await loadQuizzes();
      renderQuizzes();
    }
    if (button.id === "generatePracticeBtn") await generateQuizzes();
    if (button.id === "generateFullPaperBtn") await generateFullPaper();
    if (button.id === "nextSetBtn" || button.dataset.nextSet) await generateNextSet();
    if (button.dataset.nextSetError) await generateNextSet({ questionType: button.dataset.nextSetType || "", errorType: button.dataset.nextSetError });
    if (button.dataset.historyNextType !== undefined) await generateNextSet({ questionType: button.dataset.historyNextType || "" });
    if (button.id === "loadPaperBtn") await loadPaper(Number($("#quizPaperSelect").value));
    if (button.id === "restartQuizSessionBtn" || button.dataset.retrySession) {
      resetQuizSession();
      renderQuizzes();
      toast("已重新开始本轮训练");
    }
    if (button.id === "finishQuizSessionBtn") await finishQuizSession();
    if (button.dataset.quizDisplay) {
      state.quizSession.display = button.dataset.quizDisplay;
      localStorage.setItem("lc-v2-quiz-display", state.quizSession.display);
      renderQuizzes();
    }
    if (button.dataset.quizNav !== undefined) {
      state.quizSession.activeIndex = Number(button.dataset.quizNav);
      syncPaperSourceForQuestion();
      renderQuizzes();
      document.querySelector(`[data-quiz-card]`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    if (button.dataset.flagQuiz) {
      const quizId = Number(button.dataset.flagQuiz);
      state.quizSession.flagged[quizId] = !state.quizSession.flagged[quizId];
      renderQuizzes();
    }
    if (button.id === "showAnswersBtn") {
      state.showAnswers = !state.showAnswers;
      renderQuizzes();
    }
    if (button.id === "saveCardBtn") await saveCard();
    if (button.id === "loadCardsBtn") {
      await loadCards();
      renderAll();
    }
    if (button.id === "copyBridgeTokenBtn") {
      await navigator.clipboard.writeText($("#bridgeToken").value);
      toast("连接令牌已复制");
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
      await generateQuizzes(button.dataset.quizArticle);
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
  await Promise.all([loadArticles(), loadFeeds(), loadExamTypes(), loadExamLibrary(), loadToday(), loadPracticeHistory()]);
  await loadQuizzes();
  renderAll();
  toast(`文章池已切换为 ${state.style} 来源`);
});

$("#quizPracticeType").addEventListener("change", async () => {
  await loadQuizzes();
  renderQuizzes();
});

$("#quizScope").addEventListener("change", event => {
  updateQuizScopeControls();
  if (event.target.value !== "full-paper") {
    state.selectedPaper = null;
    state.quizSession.activeIndex = 0;
  }
  renderQuizzes();
});

$("#quizPaperSelect").addEventListener("change", async event => {
  if (event.target.value) await loadPaper(Number(event.target.value));
});

$("#epubBookSelect").addEventListener("change", async event => {
  await loadBook(Number(event.target.value));
});

$("#quizSessionMode").addEventListener("change", event => {
  state.quizSession.mode = event.target.value === "mock" ? "mock" : "practice";
  localStorage.setItem("lc-v2-quiz-session-mode", state.quizSession.mode);
  resetQuizSession();
  renderQuizzes();
  toast(state.quizSession.mode === "mock" ? "模考模式：交卷后统一显示解析" : "训练模式：作答后立即讲解");
});

document.addEventListener("input", event => {
  if (!event.target.matches("[data-typed-quiz]")) return;
  const quizId = Number(event.target.dataset.typedQuiz);
  state.quizSession.answers[quizId] = event.target.value;
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
  await Promise.all([loadArticles(), loadBooks(), loadCards(), loadMistakes(), loadFeeds(), loadSourceCatalog(), loadSubscriptions(), loadToday(), loadProgress(), loadLearnerSettings(), loadPracticeHistory(), loadExamTypes(), loadExamLibrary(), loadArticleTopics(), loadArticleContentTypes(), loadBridgeConfig(), searchLexicon("", { open: false, history: false })]);
  if (!state.selectedArticle && state.articles[0]) {
    const data = await api(`/api/articles/${state.articles[0].id}?exam=${encodeURIComponent(state.style)}`);
    state.selectedArticle = data.article;
    state.analysis = data.analysis;
  }
  await loadQuizzes();
  if (!state.quizzes.length && state.selectedArticle) {
    await generateQuizzes(state.selectedArticle.id, { open: false });
  }
  renderAll();
  const startupParams = new URLSearchParams(window.location.search);
  if (startupParams.get("view") === "lexicon" || startupParams.get("q")) {
    await searchLexicon(startupParams.get("q") || "", { open: true, history: false });
  }
}

$("#globalStyle").value = state.style;
$("#newArticleBody").value = sampleImport;

setInterval(() => {
  if (state.quizSession.submitted || !state.quizzes.length || !$("#view-quiz")?.classList.contains("active")) return;
  const timer = $("#quizTimer");
  if (timer) timer.textContent = formatDuration(quizElapsedSeconds());
}, 1000);

boot().catch(error => {
  $("#serverStatus").textContent = "后端未连接";
  toast(error.message);
});

window.addEventListener("popstate", async () => {
  const params = new URLSearchParams(window.location.search);
  const view = params.get("view") || "dashboard";
  if (view === "lexicon") {
    await searchLexicon(params.get("q") || "", { open: false, history: false });
  } else {
    setView(view, { pushHistory: false });
    renderAll();
  }
});
