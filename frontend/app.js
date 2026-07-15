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
  cards: [],
  quizzes: [],
  mistakes: [],
  feeds: [],
  selectedArticle: null,
  analysis: null,
  showAnswers: false,
  style: localStorage.getItem("lc-v2-style") || "IELTS",
};

const titles = {
  dashboard: ["今日训练", "文章、词汇、题目和错题都走本地数据库。"],
  articles: ["文章池", "每日来源、个人导入和分级文章会进入这里。"],
  reader: ["阅读台", "一篇文章可以拆成阅读、选词填空、首字母和证据定位。"],
  quiz: ["题目", "先做题，再看证据和解析，错题会自动收集。"],
  cards: ["生词本", "主动添加或从文章里点词添加，后面可做词块复习。"],
  mistakes: ["错题", "保存你的错误答案、正确答案和原文证据。"],
};

const miniLexicon = {
  privacy: { cn: "隐私；个人信息边界", family: ["private", "privately"], collocations: ["privacy policy", "privacy concern"] },
  concern: { cn: "担忧；关切；涉及", family: ["concerning", "concerned"], collocations: ["raise concerns", "privacy concerns"] },
  evidence: { cn: "证据；根据", family: ["evident", "evidently"], collocations: ["strong evidence", "evidence suggests"] },
  significant: { cn: "显著的；重要的", family: ["significance", "significantly"], collocations: ["significant impact", "significant difference"] },
  convenience: { cn: "便利；省事", family: ["convenient", "inconvenient"], collocations: ["for convenience", "consumer convenience"] },
  surveillance: { cn: "监控；监督", family: ["survey", "surveil"], collocations: ["mass surveillance", "digital surveillance"] },
  consent: { cn: "同意；许可", family: ["consensual"], collocations: ["informed consent", "without consent"] },
  policy: { cn: "政策；规则", family: ["politics", "policymaker"], collocations: ["privacy policy", "public policy"] },
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

function setView(name) {
  document.querySelectorAll(".view").forEach(view => view.classList.toggle("active", view.id === `view-${name}`));
  document.querySelectorAll(".nav-item").forEach(item => item.classList.toggle("active", item.dataset.view === name));
  $("#viewTitle").textContent = titles[name]?.[0] || "Language Coach";
  $("#viewSubtitle").textContent = titles[name]?.[1] || "";
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

function renderStats() {
  $("#statArticles").textContent = state.articles.length;
  $("#statCards").textContent = state.cards.length;
  $("#statQuizzes").textContent = state.quizzes.length;
  $("#statMistakes").textContent = state.mistakes.filter(item => !item.solved).length;
}

function renderDashboard() {
  $("#recentArticles").innerHTML = state.articles.slice(0, 4).map(article => `
    <div class="item">
      <div class="badge-row">${badge(article.level, "teal")}${badge(article.source || "manual")}</div>
      <h3>${escapeHtml(article.title)}</h3>
      <p>${escapeHtml(excerpt(article.body, 120))}</p>
      <button data-open-article="${article.id}">阅读</button>
    </div>
  `).join("") || `<div class="item muted">暂无文章</div>`;

  $("#recentMistakes").innerHTML = state.mistakes.filter(item => !item.solved).slice(0, 4).map(item => `
    <div class="item">
      <div class="badge-row">${badge("错题", "red")}</div>
      <h3>${escapeHtml(excerpt(item.prompt, 90))}</h3>
      <p>你的答案：${escapeHtml(item.user_answer || "")}</p>
      <p>正确答案：${escapeHtml(item.answer || "")}</p>
    </div>
  `).join("") || `<div class="item muted">暂无错题</div>`;
}

function renderArticles() {
  $("#articleList").innerHTML = state.articles.map(article => `
    <div class="item">
      <div class="badge-row">
        ${badge(article.level, "teal")}
        ${badge(article.language)}
        ${badge(article.source || "manual")}
      </div>
      <h3>${escapeHtml(article.title)}</h3>
      <p>${escapeHtml(excerpt(article.body))}</p>
      <div class="toolbar">
        <button data-open-article="${article.id}">阅读</button>
        <button data-quiz-article="${article.id}">生成题</button>
        ${article.source_url ? `<a href="${escapeHtml(article.source_url)}" target="_blank" rel="noreferrer">来源</a>` : ""}
      </div>
    </div>
  `).join("") || `<div class="item muted">文章池为空</div>`;

  $("#feedList").innerHTML = `
    <h2>RSS 源</h2>
    ${state.feeds.map(feed => `
      <div class="item">
        <strong>${escapeHtml(feed.name)}</strong>
        <p>${escapeHtml(feed.url)}</p>
        <div class="badge-row">${badge(feed.language)}${badge(feed.level_hint, "amber")}</div>
      </div>
    `).join("")}
  `;
}

function renderReader() {
  const article = state.selectedArticle;
  if (!article) {
    $("#readerTitle").textContent = "选择一篇文章";
    $("#readerMeta").innerHTML = "";
    $("#readerBody").innerHTML = `<p class="muted">从文章池选择文章后开始。</p>`;
    $("#analysisPanel").innerHTML = "";
    return;
  }
  $("#readerTitle").textContent = article.title;
  $("#readerMeta").innerHTML = `${badge(article.level, "teal")}${badge(article.topic || "general")}${badge(article.source || "manual")}`;
  const tokens = article.body.split(/(\b[A-Za-z][A-Za-z'-]*\b)/g);
  $("#readerBody").innerHTML = tokens.map(token => {
    if (/^[A-Za-z][A-Za-z'-]*$/.test(token)) {
      return `<span class="reader-word" data-word="${escapeHtml(token)}">${escapeHtml(token)}</span>`;
    }
    return escapeHtml(token).replace(/\n/g, "<br>");
  }).join("");
  renderAnalysis();
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
      <strong>重点词</strong>
      <div class="badge-row">${analysis.keywords.map(word => `<button data-word="${escapeHtml(word)}">${escapeHtml(word)}</button>`).join("")}</div>
    </div>
    <div class="analysis-block">
      <strong>重点句</strong>
      ${analysis.focus_sentences.map(sentence => `<p>${escapeHtml(sentence)}</p>`).join("")}
    </div>
  `;
}

function renderLookup(word) {
  const clean = word.toLowerCase().replace(/^[^a-z]+|[^a-z]+$/g, "");
  const info = miniLexicon[clean] || {
    cn: "先按语境保存，后面接词典 API 后会补全释义。",
    family: [],
    collocations: [],
  };
  const context = state.selectedArticle ? sentenceFor(state.selectedArticle.body, clean) : "";
  $("#lookupPanel").innerHTML = `
    <h2>${escapeHtml(clean)}</h2>
    <p>${escapeHtml(info.cn)}</p>
    <div class="badge-row">
      ${info.family.map(item => badge(item, "teal")).join("")}
      ${info.collocations.map(item => badge(item, "amber")).join("")}
    </div>
    ${context ? `<div class="answer-box">${escapeHtml(context)}</div>` : ""}
    <button class="primary" data-save-lookup="${escapeHtml(clean)}">加入生词本</button>
  `;
  $("#cardTerm").value = clean;
  $("#cardContext").value = context;
}

function renderQuizzes() {
  $("#quizList").innerHTML = state.quizzes.map((quiz, index) => `
    <div class="item" data-quiz-card="${quiz.id}">
      <div class="badge-row">
        ${badge(quiz.style || state.style, "teal")}
        ${badge(quiz.type)}
        ${badge(quiz.note || "")}
      </div>
      <h3>${index + 1}. ${escapeHtml(quiz.prompt)}</h3>
      ${(quiz.options || []).length ? `
        <div class="options">
          ${quiz.options.map(option => `<button class="option" data-answer-quiz="${quiz.id}" data-answer="${escapeHtml(option)}">${escapeHtml(option)}</button>`).join("")}
        </div>
      ` : `
        <div class="answer-row">
          <input data-typed-quiz="${quiz.id}" placeholder="输入完整答案" />
          <button data-submit-typed="${quiz.id}">提交</button>
        </div>
      `}
      ${state.showAnswers ? `
        <div class="answer-box">
          <strong>Answer:</strong> ${escapeHtml(quiz.answer)}<br>
          <strong>Evidence:</strong> ${escapeHtml(quiz.evidence || "")}
        </div>
      ` : ""}
    </div>
  `).join("") || `<div class="item muted">暂无题目</div>`;
}

function renderCards() {
  $("#cardList").innerHTML = state.cards.map(card => `
    <div class="item">
      <div class="badge-row">${badge(card.status || "new", "teal")}</div>
      <h3>${escapeHtml(card.term)}</h3>
      <p>${escapeHtml(card.context || "")}</p>
      ${card.note ? `<p>${escapeHtml(card.note)}</p>` : ""}
    </div>
  `).join("") || `<div class="item muted">暂无生词</div>`;
}

function renderMistakes() {
  $("#mistakeList").innerHTML = state.mistakes.map(item => `
    <div class="item">
      <div class="badge-row">
        ${badge(item.solved ? "已处理" : "待复盘", item.solved ? "teal" : "red")}
      </div>
      <h3>${escapeHtml(item.prompt)}</h3>
      <p>你的答案：${escapeHtml(item.user_answer)}</p>
      <p>正确答案：${escapeHtml(item.answer)}</p>
      <div class="answer-box">${escapeHtml(item.evidence || "")}</div>
      <button data-solve-mistake="${item.id}">${item.solved ? "重新标记" : "标为处理"}</button>
    </div>
  `).join("") || `<div class="item muted">暂无错题</div>`;
}

function renderAll() {
  renderStats();
  renderDashboard();
  renderArticles();
  renderReader();
  renderQuizzes();
  renderCards();
  renderMistakes();
}

async function loadHealth() {
  const data = await api("/api/health");
  $("#serverStatus").textContent = "后端已连接";
  $("#serverStatus").classList.add("ok");
  return data;
}

async function loadArticles(q = "") {
  const query = q ? `?q=${encodeURIComponent(q)}` : "";
  const data = await api(`/api/articles${query}`);
  state.articles = data.articles || [];
}

async function loadCards() {
  const data = await api("/api/cards");
  state.cards = data.cards || [];
}

async function loadMistakes() {
  const data = await api("/api/mistakes");
  state.mistakes = data.mistakes || [];
}

async function loadFeeds() {
  const data = await api("/api/feeds");
  state.feeds = data.feeds || [];
}

async function loadQuizzes() {
  const suffix = state.selectedArticle ? `?article_id=${state.selectedArticle.id}` : "";
  const data = await api(`/api/quizzes${suffix}`);
  state.quizzes = data.quizzes || [];
}

async function openArticle(id) {
  const data = await api(`/api/articles/${id}`);
  state.selectedArticle = data.article;
  state.analysis = data.analysis;
  await loadQuizzes();
  setView("reader");
  renderAll();
}

async function analyzeArticle() {
  if (!state.selectedArticle) return toast("先选文章");
  const data = await api(`/api/articles/${state.selectedArticle.id}/analyze`, { method: "POST", body: "{}" });
  state.analysis = data.analysis;
  renderReader();
  toast("分析完成");
}

async function generateQuizzes(id = state.selectedArticle?.id) {
  if (!id) return toast("先选文章");
  const data = await api(`/api/articles/${id}/quizzes`, {
    method: "POST",
    body: JSON.stringify({ mode: $("#quizMode").value, style: state.style }),
  });
  state.quizzes = data.quizzes || [];
  setView("quiz");
  renderAll();
  toast("题目已生成");
}

async function submitAnswer(quizId, answer, button = null) {
  const data = await api("/api/attempts", {
    method: "POST",
    body: JSON.stringify({ quiz_id: quizId, answer }),
  });
  if (button) button.classList.add(data.correct ? "correct" : "wrong");
  await loadMistakes();
  renderStats();
  renderDashboard();
  toast(data.correct ? "答对了" : `错了：${data.answer}`);
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
      source: "manual",
      topic: "personal",
    }),
  });
  state.articles.unshift(data.article);
  state.selectedArticle = data.article;
  state.analysis = data.analysis;
  renderAll();
  toast("已存入文章库");
}

async function saveCard(term = $("#cardTerm").value.trim(), context = $("#cardContext").value.trim()) {
  if (!term) return toast("词不能为空");
  const data = await api("/api/cards", {
    method: "POST",
    body: JSON.stringify({
      term,
      context,
      source_article_id: state.selectedArticle?.id || null,
      status: "new",
    }),
  });
  state.cards.unshift(data.card);
  renderCards();
  renderStats();
  toast("已加入生词本");
}

async function refreshFeeds() {
  toast("开始更新 RSS");
  const result = await api("/api/feeds/refresh", { method: "POST", body: "{}" });
  await loadArticles();
  renderAll();
  const errorText = result.errors?.length ? `，${result.errors.length} 个源失败` : "";
  toast(`导入 ${result.imported || 0} 条${errorText}`);
}

async function toggleMistake(id) {
  await api(`/api/mistakes/${id}/solve`, { method: "POST", body: "{}" });
  await loadMistakes();
  renderAll();
}

document.addEventListener("click", async event => {
  const button = event.target.closest("button");
  if (!button) return;
  try {
    if (button.dataset.view) setView(button.dataset.view);
    if (button.dataset.viewJump) setView(button.dataset.viewJump);
    if (button.id === "refreshAllBtn") await boot();
    if (button.id === "searchArticlesBtn") {
      await loadArticles($("#articleSearch").value.trim());
      renderAll();
    }
    if (button.id === "refreshFeedsBtn") await refreshFeeds();
    if (button.id === "saveArticleBtn") await saveArticle();
    if (button.id === "analyzeBtn") await analyzeArticle();
    if (button.id === "generateQuizBtn") await generateQuizzes();
    if (button.id === "loadQuizzesBtn") {
      await loadQuizzes();
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
    if (button.id === "loadMistakesBtn") {
      await loadMistakes();
      renderAll();
    }
    if (button.dataset.openArticle) await openArticle(button.dataset.openArticle);
    if (button.dataset.quizArticle) {
      await openArticle(button.dataset.quizArticle);
      await generateQuizzes(button.dataset.quizArticle);
    }
    if (button.dataset.word) renderLookup(button.dataset.word);
    if (button.dataset.saveLookup) {
      const context = state.selectedArticle ? sentenceFor(state.selectedArticle.body, button.dataset.saveLookup) : "";
      await saveCard(button.dataset.saveLookup, context);
    }
    if (button.dataset.answerQuiz) {
      await submitAnswer(Number(button.dataset.answerQuiz), button.dataset.answer, button);
    }
    if (button.dataset.submitTyped) {
      const input = document.querySelector(`[data-typed-quiz="${button.dataset.submitTyped}"]`);
      await submitAnswer(Number(button.dataset.submitTyped), input.value.trim(), button);
    }
    if (button.dataset.solveMistake) await toggleMistake(button.dataset.solveMistake);
  } catch (error) {
    toast(error.message);
  }
});

document.addEventListener("click", event => {
  const word = event.target.closest(".reader-word");
  if (word) renderLookup(word.dataset.word);
});

$("#globalStyle").addEventListener("change", event => {
  state.style = event.target.value;
  localStorage.setItem("lc-v2-style", state.style);
});

$("#articleSearch").addEventListener("keydown", async event => {
  if (event.key === "Enter") {
    await loadArticles(event.target.value.trim());
    renderAll();
  }
});

async function boot() {
  await loadHealth();
  await Promise.all([loadArticles(), loadCards(), loadMistakes(), loadFeeds()]);
  if (!state.selectedArticle && state.articles[0]) {
    const data = await api(`/api/articles/${state.articles[0].id}`);
    state.selectedArticle = data.article;
    state.analysis = data.analysis;
  }
  await loadQuizzes();
  renderAll();
}

$("#globalStyle").value = state.style;
$("#newArticleBody").value = sampleImport;

boot().catch(error => {
  $("#serverStatus").textContent = "后端未连接";
  toast(error.message);
});
