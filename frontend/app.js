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
  lexiconResults: [],
  selectedLexicalItem: null,
  lexiconFilter: "all",
  progress: { xp: 0, level: 1, level_xp: 0, streak: 0 },
  examTypes: [],
  showTranslation: false,
  articleTopics: [],
  articleTopic: "",
  articleContentTypes: [],
  articleContentType: "",
  recommendedOnly: false,
  bridge: null,
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

function setView(name) {
  document.querySelectorAll(".view").forEach(view => view.classList.toggle("active", view.id === `view-${name}`));
  document.querySelectorAll(".nav-item").forEach(item => {
    const matchesView = item.dataset.view === name;
    const matchesLexicon = name !== "lexicon" || item.dataset.lexiconFilter === state.lexiconFilter;
    item.classList.toggle("active", matchesView && matchesLexicon);
  });
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

function searchableEnglish(text, clickable = true) {
  return String(text || "").split(/(\b[A-Za-z][A-Za-z'-]*\b)/g).map(token => {
    if (!/^[A-Za-z][A-Za-z'-]*$/.test(token)) return escapeHtml(token).replace(/\n/g, "<br>");
    return clickable ? `<span class="reader-word universal-word" data-word="${escapeHtml(token)}">${escapeHtml(token)}</span>` : escapeHtml(token);
  }).join("");
}

function articleParagraphs(text, className = "") {
  return String(text || "").split(/\n\s*\n/).filter(Boolean).map(paragraph => `<p class="${className}">${searchableEnglish(paragraph)}</p>`).join("");
}

function renderStats() {
  $("#statArticles").textContent = state.articles.length;
  $("#statCards").textContent = state.cards.length;
  $("#statQuizzes").textContent = state.quizzes.length;
  $("#statMistakes").textContent = state.mistakes.filter(item => !item.solved).length;
  $("#progressLevel").textContent = `Lv.${state.progress.level || 1}`;
  $("#progressXp").textContent = `${state.progress.level_xp || 0}/100 XP · ${state.progress.streak || 0} 天`;
}

function renderDashboard() {
  $("#recentArticles").innerHTML = state.articles.slice(0, 4).map(article => `
    <div class="item">
      <div class="badge-row">${article.recommended_today ? badge(`今日推荐 ${article.daily_rank}`, "amber") : ""}${badge(article.level, "teal")}${(article.theme_tags || []).slice(0, 2).map(theme => badge(theme)).join("")}</div>
      <h3>${escapeHtml(article.title)}</h3>
      <p>${escapeHtml(excerpt(article.highlight || article.body, 145))}</p>
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
          <small>${article.recommended_today ? `推荐 ${article.daily_rank} · ` : ""}${escapeHtml(article.content_type_label || "学术解释")} · ${escapeHtml(article.source || "manual")} · ${escapeHtml(article.level)}</small>
          ${article.recommended_today ? `<em>${escapeHtml((article.recommendation_reasons || []).join(" · "))}</em>` : ""}
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
          <button data-open-article="${selected.id}">进入阅读台</button>
          <button class="primary" data-quiz-article="${selected.id}">生成题</button>
        </div>
      </div>
      ${selected.recommended_today ? `<div class="daily-recommendation"><strong>今日推荐 ${selected.daily_rank}</strong><span>${escapeHtml((selected.recommendation_reasons || []).join(" · "))}</span><small>推荐分 ${selected.recommendation_score}</small></div>` : ""}
      ${selected.content_status !== "full" ? `<div class="content-notice"><div><strong>当前保存的是 RSS 摘要</strong><span>阅读器已经显示全部本地内容，完整文章需要打开原始来源或补充正文。</span></div>${selected.source_url ? `<a href="${escapeHtml(selected.source_url)}" target="_blank" rel="noreferrer">打开完整原文</a>` : ""}</div>` : ""}
      ${selected.theme_tags?.length ? `<div class="article-themes"><span>文章主题</span>${selected.theme_tags.map(theme => badge(theme, "amber")).join("")}</div>` : ""}
      ${selected.source_topics?.length ? `<div class="source-topics"><span class="topic-label">来源领域</span>${selected.source_topics.map(topic => badge(topic)).join("")}</div>` : ""}
      <article class="article-detail-body">${paragraphs.map(paragraph => `<p class="article-paragraph">${searchableEnglish(paragraph)}</p>`).join("")}</article>
      ${state.showTranslation ? `<section class="translation-panel">${selected.translation_zh ? selected.translation_zh.split(/\n\s*\n/).map(paragraph => `<p>${escapeHtml(paragraph)}</p>`).join("") : `<p class="muted">这篇文章还没有可靠译文。</p>`}</section>` : ""}
      ${selected.source_url ? `<a class="source-link" href="${escapeHtml(selected.source_url)}" target="_blank" rel="noreferrer">打开原始来源</a>` : ""}
      <details class="content-editor"><summary>${selected.content_status === "full" ? "编辑完整正文" : "补充完整正文"}</summary><textarea id="articleContentInput">${escapeHtml(selected.body)}</textarea><button class="primary" data-save-article-content="${selected.id}">保存为完整正文</button></details>
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
        <div class="badge-row">${badge(feed.source_tier || "其他", feed.source_tier === "核心" ? "teal" : "")}${badge(feed.source_kind || "其他来源")}${badge(feed.default_content_type_label || "学术解释")}${badge(feed.level_hint, "amber")}${badge(`${feed.exam_fit || 0}%`)}</div>
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
  $("#readerBody").innerHTML = articleParagraphs(article.body, "article-paragraph");
  $("#articleTranslationInput").value = article.translation_zh || "";
  const translationPanel = $("#translationPanel");
  translationPanel.hidden = !state.showTranslation;
  translationPanel.innerHTML = article.translation_zh ? article.translation_zh.split(/\n\s*\n/).map(paragraph => `<p>${escapeHtml(paragraph)}</p>`).join("") : `<p class="muted">这篇文章还没有可靠译文，可以在下方补充。</p>`;
  $("#toggleTranslationBtn").textContent = state.showTranslation ? "隐藏译文" : "显示译文";
  $("#toggleTranslationBtn").setAttribute("aria-pressed", String(state.showTranslation));
  renderAnalysis();
}

function renderQuizSource() {
  const article = state.selectedArticle;
  $("#quizSourceTitle").textContent = article?.title || "原文";
  $("#quizSourceText").innerHTML = article ? articleParagraphs(article.body, "article-paragraph") : `<p class="muted">先从文章池选择文章。</p>`;
  const translation = $("#quizTranslationPanel");
  translation.hidden = !state.showTranslation;
  translation.innerHTML = article?.translation_zh ? article.translation_zh.split(/\n\s*\n/).map(value => `<p>${escapeHtml(value)}</p>`).join("") : `<p class="muted">暂无可靠译文。</p>`;
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
      <strong>重点词</strong>
      <div class="badge-row">${analysis.keywords.map(word => `<button data-word="${escapeHtml(word)}">${escapeHtml(word)}</button>`).join("")}</div>
    </div>
    <div class="analysis-block">
      <strong>重点句</strong>
      ${analysis.focus_sentences.map(sentence => `<p>${escapeHtml(sentence)}</p>`).join("")}
    </div>
  `;
}

async function renderLookup(word) {
  const clean = word.toLowerCase().replace(/^[^a-z]+|[^a-z]+$/g, "");
  const context = state.selectedArticle ? sentenceFor(state.selectedArticle.body, clean) : "";
  const data = await api(`/api/lexicon/search?q=${encodeURIComponent(clean)}`);
  const info = data.results?.find(item => item.type === "entry") || null;
  $("#lookupPanel").innerHTML = `
    <div class="lookup-heading"><div><h2>${escapeHtml(info?.headword || clean)}</h2>${info ? `<span>${escapeHtml(info.ipa_uk)} · ${escapeHtml(info.pos)}</span>` : ""}</div><button data-speak="${escapeHtml(info?.headword || clean)}" title="播放发音" aria-label="播放发音">▶</button></div>
    <p>${escapeHtml(info?.meaning_zh || "当前本地词库还没有完整词条，可以先连同语境保存。")}</p>
    ${info?.breakdown ? `<div class="morph-line">${escapeHtml(info.breakdown)}</div>` : ""}
    <div class="badge-row">${(info?.collocations || []).map(item => badge(termText(item), "amber")).join("")}</div>
    ${context ? `<div class="answer-box">${escapeHtml(context)}</div>` : ""}
    <div class="toolbar"><button class="primary" data-save-lookup="${escapeHtml(clean)}">加入生词本</button><button data-search-query="${escapeHtml(clean)}" data-open-lexicon="true">完整词条</button></div>
  `;
  $("#cardTerm").value = clean;
  $("#cardContext").value = context;
}

function lexicalLabel(item) {
  return item.type === "entry" ? item.headword : item.form;
}

function lexicalSubtitle(item) {
  return item.type === "entry" ? `${item.pos} · ${item.meaning_zh}` : `${item.kind} · ${item.meaning_zh}`;
}

function matchesLexiconFilter(item) {
  if (state.lexiconFilter === "all" || state.lexiconFilter === "family") return item.type === "entry" || state.lexiconFilter === "all";
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
      <div class="phrase-head"><div><strong>${escapeHtml(current.phrase)}</strong><p>${escapeHtml(current.meaning_zh || "")}</p></div><button data-save-phrase="${escapeHtml(current.phrase)}" title="加入生词本" aria-label="加入生词本">＋</button></div>
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
  detail.innerHTML = `
    <div class="dictionary-hero">
      <div><div class="badge-row">${badge(item.level || "词条", "teal")}${badge(item.pos)}${badge(item.register_label)}</div><h2>${escapeHtml(item.headword)}</h2><div class="pronunciation"><span>UK ${escapeHtml(item.ipa_uk)}</span><button data-speak="${escapeHtml(item.headword)}" data-voice="en-GB" title="英式发音">▶ UK</button><span>US ${escapeHtml(item.ipa_us)}</span><button data-speak="${escapeHtml(item.headword)}" data-voice="en-US" title="美式发音">▶ US</button></div></div>
      <button class="primary" data-save-lookup="${escapeHtml(item.headword)}">加入生词本</button>
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

async function searchLexicon(query, { open = true, quick = false } = {}) {
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
  if (open) setView("lexicon");
  renderLexicon();
  return state.lexiconResults;
}

function renderQuickResults(results, query) {
  const panel = $("#quickLexiconResults");
  const items = results.slice(0, 4);
  panel.hidden = false;
  panel.innerHTML = items.length ? `${items.map(item => `<button data-search-query="${escapeHtml(lexicalLabel(item))}" data-open-lexicon="true"><strong>${escapeHtml(lexicalLabel(item))}</strong><span>${escapeHtml(lexicalSubtitle(item))}</span></button>`).join("")}<button class="quick-more" data-search-query="${escapeHtml(query)}" data-open-lexicon="true">查看全部结果</button>` : `<div class="quick-empty">本地词库暂未收录，仍可加入生词本。</div>`;
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
      <h3>${index + 1}. ${searchableEnglish(quiz.prompt)}</h3>
      ${(quiz.options || []).length ? `
        <div class="options">
          ${quiz.options.map(option => {
            const answerClass = feedback && option === quiz.answer ? "correct" : feedback && option === feedback.userAnswer && !feedback.correct ? "wrong" : "";
            return `<button class="option ${answerClass}" data-answer-quiz="${quiz.id}" data-answer="${escapeHtml(option)}">${searchableEnglish(option, false)}</button>`;
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
  renderQuizSource();
  renderCards();
  renderMistakes();
  renderLexicon();
}

function renderExamTypes() {
  const select = $("#examQuestionType");
  const previous = select.value;
  select.innerHTML = `<option value="">全部对应题型</option>${state.examTypes.map(item => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`).join("")}`;
  if (state.examTypes.some(item => item.id === previous)) select.value = previous;
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

async function loadExamTypes() {
  const data = await api(`/api/exam-types?style=${encodeURIComponent(state.style)}`);
  state.examTypes = data.types || [];
  renderExamTypes();
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
  $("#bridgeStatus").innerHTML = `${badge("本地桥接已启用", "teal")}${badge(data.translation?.configured ? "DeepL 已配置" : "DeepL 未配置", data.translation?.configured ? "teal" : "amber")}`;
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
  const data = await api(`/api/articles/${id}?exam=${encodeURIComponent(state.style)}`);
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
    body: JSON.stringify({ mode: $("#quizMode").value, style: state.style, question_type: $("#examQuestionType").value }),
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
  if (data.progress) state.progress = data.progress;
  await loadMistakes();
  renderQuizzes();
  renderMistakes();
  renderStats();
  renderDashboard();
  const rewardText = data.points ? `，+${data.points} XP` : "（本题积分已结算）";
  toast(data.correct ? `答对了${rewardText}` : `错了：${data.answer}${rewardText}`);
}

async function saveTranslation() {
  if (!state.selectedArticle) return toast("先选文章");
  const data = await api(`/api/articles/${state.selectedArticle.id}/translation`, {
    method: "POST",
    body: JSON.stringify({ translation_zh: $("#articleTranslationInput").value.trim() }),
  });
  state.selectedArticle = data.article;
  const poolItem = state.articles.find(item => item.id === data.article.id);
  if (poolItem) Object.assign(poolItem, data.article);
  renderReader();
  renderArticles();
  toast("译文已保存");
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
  const data = await api(`/api/mistakes/${id}/solve`, { method: "POST", body: "{}" });
  if (data.progress) state.progress = data.progress;
  await loadMistakes();
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

document.addEventListener("click", async event => {
  const button = event.target.closest("button");
  if (!button) return;
  try {
    if (button.dataset.lexiconFilter) state.lexiconFilter = button.dataset.lexiconFilter;
    if (button.dataset.view) setView(button.dataset.view);
    if (button.dataset.lexiconFilter) renderLexicon();
    if (button.dataset.viewJump) setView(button.dataset.viewJump);
    if (button.id === "refreshAllBtn") await boot();
    if (button.id === "toggleTranslationBtn" || button.id === "quizTranslationBtn" || button.dataset.toggleTranslation) {
      state.showTranslation = !state.showTranslation;
      renderReader();
      renderArticles();
      renderQuizSource();
    }
    if (button.id === "saveTranslationBtn") await saveTranslation();
    if (button.dataset.saveArticleContent) await saveArticleContent(Number(button.dataset.saveArticleContent));
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
    if (button.id === "copyBridgeTokenBtn") {
      await navigator.clipboard.writeText($("#bridgeToken").value);
      toast("连接令牌已复制");
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
    if (button.dataset.savePhrase) {
      const example = state.selectedLexicalItem?.examples?.[0];
      await saveCard(button.dataset.savePhrase, typeof example === "string" ? example : example?.text || "");
    }
    if (button.dataset.saveLookup) {
      const articleBody = state.selectedArticle?.body || "";
      const context = articleBody.toLowerCase().includes(button.dataset.saveLookup.toLowerCase()) ? sentenceFor(articleBody, button.dataset.saveLookup) : "";
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
  if (word) renderLookup(word.dataset.word).catch(error => toast(error.message));
  if (!event.target.closest(".global-search-wrap")) $("#quickLexiconResults").hidden = true;
});

document.addEventListener("dblclick", event => {
  if (event.target.closest("input, textarea, select, button")) return;
  const selected = window.getSelection()?.toString().trim().replace(/\s+/g, " ") || "";
  if (!/^[A-Za-z][A-Za-z' -]{0,79}$/.test(selected) || selected.split(" ").length > 6) return;
  $("#globalLexiconSearch").value = selected;
  searchLexicon(selected, { quick: true }).catch(error => toast(error.message));
  $("#globalLexiconSearch").focus();
});

$("#globalStyle").addEventListener("change", async event => {
  state.style = event.target.value;
  localStorage.setItem("lc-v2-style", state.style);
  await Promise.all([loadArticles(), loadFeeds(), loadExamTypes()]);
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
  await Promise.all([loadArticles(), loadCards(), loadMistakes(), loadFeeds(), loadProgress(), loadExamTypes(), loadArticleTopics(), loadArticleContentTypes(), loadBridgeConfig(), searchLexicon("", { open: false })]);
  if (!state.selectedArticle && state.articles[0]) {
    const data = await api(`/api/articles/${state.articles[0].id}?exam=${encodeURIComponent(state.style)}`);
    state.selectedArticle = data.article;
    state.analysis = data.analysis;
  }
  await loadQuizzes();
  renderAll();
  const startupParams = new URLSearchParams(window.location.search);
  if (startupParams.get("view") === "lexicon" || startupParams.get("q")) {
    await searchLexicon(startupParams.get("q") || "", { open: true });
  }
}

$("#globalStyle").value = state.style;
$("#newArticleBody").value = sampleImport;

boot().catch(error => {
  $("#serverStatus").textContent = "后端未连接";
  toast(error.message);
});
