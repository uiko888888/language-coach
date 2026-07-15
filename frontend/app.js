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
  selectedPoolArticleId: null,
  selectedMistakeId: null,
  similarByMistake: {},
  analysis: null,
  answerFeedback: {},
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
          <small>${escapeHtml(article.source || "manual")} · ${escapeHtml(article.level)}</small>
        </span>
      </button>
    `).join("");
    const paragraphs = String(selected.body || "").split(/\n\s*\n/).filter(Boolean);
    detail.innerHTML = `
      <div class="detail-head">
        <div>
          <div class="badge-row">
            ${badge(selected.level, "teal")}
            ${badge(selected.source || "manual")}
            ${selected.source_tier ? badge(selected.source_tier, selected.source_tier === "核心" ? "teal" : "") : ""}
            ${selected.exam_fit ? badge(`${state.style} 匹配 ${selected.exam_fit}%`, selected.exam_fit >= 90 ? "amber" : "") : ""}
          </div>
          <h2>${escapeHtml(selected.title)}</h2>
        </div>
        <div class="toolbar">
          <button data-open-article="${selected.id}">进入阅读台</button>
          <button class="primary" data-quiz-article="${selected.id}">生成题</button>
        </div>
      </div>
      ${selected.source_topics?.length ? `<div class="source-topics">${selected.source_topics.map(topic => badge(topic)).join("")}</div>` : ""}
      <article class="article-detail-body">${paragraphs.map(paragraph => `<p>${escapeHtml(paragraph)}</p>`).join("")}</article>
      ${selected.source_url ? `<a class="source-link" href="${escapeHtml(selected.source_url)}" target="_blank" rel="noreferrer">打开原始来源</a>` : ""}
    `;
  }

  $("#feedList").innerHTML = `
    <div class="source-pool-head">
      <div><span class="muted">Exam-aligned sources</span><h2>${state.style} 来源池</h2></div>
      ${badge("仅保存摘要与链接", "teal")}
    </div>
    ${state.feeds.map(feed => `
      <div class="source-row">
        <div><strong>${escapeHtml(feed.name)}</strong><p>${escapeHtml((feed.source_topics || []).join(" · "))}</p></div>
        <div class="badge-row">${badge(feed.source_tier || "其他", feed.source_tier === "核心" ? "teal" : "")}${badge(feed.level_hint, "amber")}${badge(`${feed.exam_fit || 0}%`)}</div>
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

function explanationHtml(explanation, compact = false, correct = false) {
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
      ${!compact ? `
        <div class="evidence-box">
          <span>原文证据</span>
          <p>${escapeHtml(explanation.evidence || "暂无证据句")}</p>
          <small>${escapeHtml(explanation.evidence_guide || "")}</small>
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

function renderQuizzes() {
  $("#quizList").innerHTML = state.quizzes.map((quiz, index) => {
    const feedback = state.answerFeedback[quiz.id];
    return `
    <div class="item" data-quiz-card="${quiz.id}">
      <div class="badge-row">
        ${badge(quiz.style || state.style, "teal")}
        ${badge(quiz.type)}
        ${badge(quiz.note || "")}
      </div>
      <h3>${index + 1}. ${escapeHtml(quiz.prompt)}</h3>
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
      ${state.showAnswers ? `
        <div class="answer-box">
          <strong>Answer:</strong> ${escapeHtml(quiz.answer)}<br>
          <strong>Evidence:</strong> ${escapeHtml(quiz.evidence || "")}
        </div>
      ` : ""}
      ${feedback ? explanationHtml(feedback.explanation, true, feedback.correct) : ""}
    </div>
  `;
  }).join("") || `<div class="item muted">暂无题目</div>`;
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
        <small>${escapeHtml(item.quiz_note || item.quiz_type || "阅读理解")} · ${item.solved ? "已懂" : "待学"}</small>
      </span>
    </button>
  `).join("");

  coach.innerHTML = `
    <div class="detail-head">
      <div>
        <div class="badge-row">${badge(selected.solved ? "已掌握" : "正在讲解", selected.solved ? "teal" : "red")}${badge(selected.style || "通用")}${badge(selected.quiz_type || "reading")}</div>
        <h2>${escapeHtml(selected.prompt)}</h2>
      </div>
      ${selected.article_id ? `<button data-open-article="${selected.article_id}">回到原文</button>` : ""}
    </div>
    <div class="answer-compare">
      <div class="answer-choice wrong-choice"><span>你的答案</span><strong>${escapeHtml(selected.user_answer || "未作答")}</strong></div>
      <div class="answer-choice correct-choice"><span>正确答案</span><strong>${escapeHtml(selected.answer)}</strong></div>
    </div>
    ${explanationHtml(explanation)}
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
  const params = new URLSearchParams({ exam: state.style });
  if (q) params.set("q", q);
  const data = await api(`/api/articles?${params.toString()}`);
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
  const data = await api(`/api/feeds?exam=${encodeURIComponent(state.style)}`);
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
  await loadMistakes();
  renderQuizzes();
  renderMistakes();
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
  state.selectedPoolArticleId = data.article.id;
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

async function generateSimilar(mistakeId) {
  const data = await api(`/api/mistakes/${mistakeId}/similar`, {
    method: "POST",
    body: JSON.stringify({ count: 3 }),
  });
  state.similarByMistake[mistakeId] = data.quizzes || [];
  renderMistakes();
  toast(`已生成 ${state.similarByMistake[mistakeId].length} 道同类题`);
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
    if (button.dataset.selectArticle) {
      state.selectedPoolArticleId = Number(button.dataset.selectArticle);
      renderArticles();
    }
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
    if (button.dataset.selectMistake) {
      state.selectedMistakeId = Number(button.dataset.selectMistake);
      renderMistakes();
    }
    if (button.dataset.generateSimilar) await generateSimilar(Number(button.dataset.generateSimilar));
    if (button.dataset.solveMistake) await toggleMistake(button.dataset.solveMistake);
  } catch (error) {
    toast(error.message);
  }
});

document.addEventListener("click", event => {
  const word = event.target.closest(".reader-word");
  if (word) renderLookup(word.dataset.word);
});

$("#globalStyle").addEventListener("change", async event => {
  state.style = event.target.value;
  localStorage.setItem("lc-v2-style", state.style);
  await Promise.all([loadArticles(), loadFeeds()]);
  renderArticles();
  renderDashboard();
  toast(`文章池已切换为 ${state.style} 来源`);
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
