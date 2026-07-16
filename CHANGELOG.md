# Changelog

All notable changes to this project are documented in this file.

The format follows Keep a Changelog, and the project uses Semantic Versioning.

## [Unreleased]

## [0.7.0-alpha.8] - 2026-07-16

### Added

- Added a source registry covering automatic RSS, summary/link sources, user-authorized browser excerpts, local subtitle workflows, academic indexes, and public-domain books.
- Added persistent source subscriptions with subscribe/unsubscribe controls in the article source drawer.
- Added a Today content API and dashboard with distinct 5-minute, 15-minute, and 30-minute learning lanes.
- Added subscription-aware recommendation boosts while preserving source diversity.
- Added `STATUS.md` with a factual completed/partial/missing capability audit and current engineering risks.

### Changed

- Narrowed the alpha.8 scope to source registration, subscriptions, and Today content.
- Deferred event clustering until deduplication and source-volume quality are sufficient.

## [0.7.0-alpha.7] - 2026-07-16

### Added

- Added CET-4, CET-6, and Chinese postgraduate entrance English as first-class exam styles.
- Added independent question-type labels, prompt profiles, distractor guidance, coaching notes, and article-source matching for the three domestic exams.
- Added BBC World, BBC Business, Guardian World, Guardian Opinion, The Conversation Politics, NPR World, and UN News feeds.
- Added persistent article content types for reports, opinions, explainers, research summaries, institutional updates, and cultural content.
- Added article content-type filtering, visible type/source labels, and a content-type selector for manual imports.

### Changed

- Existing article databases migrate in place and receive source-backed content classifications without requiring a reset.
- Source profiles now distinguish news media, public media, academic explainers, research services, cultural commentary, institutions, and personal imports.

### Documentation

- Defined Language Coach as a dynamic-profile AI coach spanning interest-led learning and IELTS/TOEFL preparation.
- Documented separate onboarding paths for users with an existing score and users without one.
- Established subscribable subtitle, interview, news, novel, and blog content categories.
- Specified the reusable material pipeline from source validation through vocabulary extraction, exercises, review, and profile updates.
- Added version scopes and acceptance criteria for `v0.7.0`, `v0.8.0`, `v0.9.0`, and `v1.0.0`.
- Recorded durable product decisions in `PRODUCT.md`, `ROADMAP.md`, and `DECISIONS.md`.
- Defined selectable score entry with at least one required total or section score.
- Added Today content as the first subscription surface and deferred browser nudges to explicit opt-in.
- Classified streaming material by format and duration.
- Added evidence-based exam-fit and question-rejection criteria that prohibit copied or deliberately extreme questions.
- Documented open-source research, reusable ideas, license boundaries, and copyrighted-content risks in `RESEARCH.md`.

## [0.7.0-alpha.6] - 2026-07-16

### Added

- WXT + TypeScript browser-extension foundation inspired by the architecture evaluated in Read Frog.
- Defuddle-based full-page article extraction through the browser context menu.
- Direct import of extracted webpage originals into the full-content article pool.
- Third-party license notices separating MIT foundations from Read Frog's GPL-3.0 business code.

### Changed

- The native Manifest V3 prototype is replaced by a reproducible WXT build while preserving lookup, translation, clipping, local tokens, and options.

### Licensing

- WXT and Defuddle are used under MIT licenses.
- No GPL-3.0 Read Frog business-logic source is copied into Language Coach.

## [0.7.0-alpha.5] - 2026-07-16

### Added

- Installable Chrome/Edge Manifest V3 extension for webpage selection lookup, translation, and clipping.
- Token-protected local browser bridge with restricted extension CORS support.
- DeepL paragraph translation with SQLite caching and explicit unconfigured-provider errors.
- Browser clip history preserving source text, translation, surrounding context, page title, and URL.
- One-click saving from a webpage selection into the Language Coach vocabulary book.
- Local app panel for copying the extension token and checking translation-provider status.

### Security

- Ordinary webpages cannot write to browser bridge endpoints without the generated local token.
- Translation credentials remain in the backend environment and are never stored in the extension.

## [0.7.0-alpha.4] - 2026-07-16

### Added

- Explicit RSS-summary and full-content states with visible word counts.
- Prominent original-article links and an editor for supplementing a summary with full text.
- Automatic upgrades when an RSS feed legally provides a longer full-content field.

### Fixed

- Short RSS summaries no longer appear to be truncated full articles.
- Feed refresh can replace an existing summary with longer feed-provided content.

## [0.7.0-alpha.3] - 2026-07-16

### Fixed

- Environmental-protection collections no longer treat generic uses such as “political environment” as ecological content.

## [0.7.0-alpha.2] - 2026-07-16

### Added

- Article-level semantic themes such as environmental protection, space exploration, health, law, history, and technology.
- Homepage highlight sentences selected from article content instead of raw leading excerpts.
- Separate labels for article themes and broad source domains.

### Changed

- Existing and newly imported feed summaries remove duplicated titles and are grouped into readable paragraphs.
- Article pool, reader, and quiz source passages render semantic paragraphs with first-line indentation.
- Topic filtering now uses article content themes, forming the foundation for later automatic collections.

## [0.7.0-alpha.1] - 2026-07-16

### Added

- Article topic filtering based on curated source profiles.
- A daily top-three recommendation ranking using exam fit, source quality, freshness, level, and reading depth.
- Visible recommendation rank, score, and reasons in the article master-detail workspace.
- A one-click filter for showing only today's recommended articles.

### Notes

- This is the first feedback release for the content-library redesign. Collections, URL imports, and new current-affairs sources are intentionally deferred until the discovery workflow is validated.

## [0.6.0] - 2026-07-16

### Added

- Reader and article-pool translation toggles with persistent, editable Chinese translations.
- Sticky source passage beside questions so reading evidence remains available during practice.
- Exam-specific question type selectors for IELTS, TOEFL, TEM4, TEM8, GRE, GMAT, and general practice.
- Persistent XP, levels, daily streaks, correct-answer totals, and mistake-review rewards.
- Universal English lookup through clickable reading text and selection-based phrase search.
- End-to-end tests for translations, exam question generation, answer scoring, and progression.

### Changed

- Repeated submissions and repeated mistake toggles no longer award duplicate XP.
- The seeded privacy article includes a reviewed Chinese translation; untranslated articles clearly report that no reliable translation is available.

## [0.5.1] - 2026-07-15

### Added

- Chinese translations for every seeded collocation and lexical relation.
- Bilingual synonym and antonym phrases grouped under each collocation.
- Chinese translations below authentic example sentences.
- Highlighting for the queried headword, inflected forms, and visible family derivatives in context.

### Changed

- Seeded dictionary entries now update existing local databases without requiring a reset.
- Phrase cards preserve their English context when saved to the vocabulary book.

## [0.5.0] - 2026-07-15

### Added

- Persistent dictionary and morphology data for headwords, forms, Chinese aliases, roots, prefixes, suffixes, word families, collocations, synonyms, antonyms, etymology, IPA, and examples.
- Ranked mixed search for English headwords, inflected forms, Chinese meanings, morphemes, and Latin etymons.
- Always-available top search with lightweight suggestions and a full left-list/right-detail dictionary workspace.
- Root, prefix, suffix, word-family, pronunciation, phrase-saving, and article lookup interactions.
- Automated coverage for `inspect`, `inspection`, `inspected`, `观察`, `spect`, `specere`, `re-`, and `-tion`.

### Changed

- Global navigation is grouped into daily learning, vocabulary, and exam sections.
- Article word lookup now uses the persistent dictionary instead of a hard-coded browser-only mini lexicon.
- SQLite connections now close after each operation so repeated instant searches do not accumulate resources.

## [0.4.1] - 2026-07-15

### Added

- One-click Windows launcher that discovers Python from `PATH` and opens the app.
- Repository line-ending policy for stable cross-platform commits.

## [0.4.0] - 2026-07-15

### Changed

- Article pool now uses a title list on the left and selected article content on the right.
- Mistake review now uses a title list on the left and selected coaching content on the right.
- Desktop and in-app browser widths retain the original fixed global sidebar; panels collapse only on phone widths.

## [0.3.0] - 2026-07-15

### Added

- Curated RSS sources aligned with academic, humanities, science, and business exam passages.
- IELTS, TOEFL, TEM4, TEM8, GRE, and GMAT source-fit scoring and ordering.
- Source tier, topic, difficulty, summary-only notice, and original links in the article pool.

## [0.2.0] - 2026-07-15

### Added

- Immediate answer explanations based on question type and evidence.
- Structured mistake coaching with test point, distractor trap, evidence, and retry steps.
- Generation and scoring of three same-skill remedial questions.

## [0.1.0] - 2026-07-15

### Added

- Local Python HTTP API with SQLite persistence.
- Article pool, article import, reader analysis, vocabulary cards, quizzes, attempts, and mistakes.
- IELTS, TOEFL, TEM4, TEM8, GRE, GMAT, and general question styles.
- Initial v2 desktop interface and responsive layout.
