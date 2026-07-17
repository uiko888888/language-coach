# Changelog

All notable changes to this project are documented in this file.

The format follows Keep a Changelog, and the project uses Semantic Versioning.

## [Unreleased]

- Researched legally distributable English dictionary sources and staged the import order for Open English WordNet, Kaikki/Wiktionary, Tatoeba, FreeDict, Moby Thesaurus, and wordfreq.

## [0.8.0-alpha.1] - 2026-07-17

### Added

- Added independent IELTS generators for True / False / Not Given, heading matching, paragraph information matching, and one-word summary completion.
- Added structured question metadata for exam question type, skill, difficulty, generation source, and validation report.
- Added pre-save validation for source evidence, option uniqueness, answer membership, TFNG evidence relation, heading coverage, paragraph matching, and gap-fill word limits.
- Added practice-session summaries for specialty, question count, answered count, and validation status.
- Added structured attempt and mistake records with skill and error type, including TFNG confusion diagnosis.
- Added integration tests covering generation, validation, persistence, wrong-answer diagnosis, and mistake retrieval.

### Changed

- IELTS specialty training no longer falls back to generic reading, main-idea, paraphrase, or cloze items.
- Legacy questions remain stored, but current practice loading filters by exam and question type.
- IELTS remedial generation now reuses the original IELTS specialty template and validator.

### Known limits

- This release is a validated rule baseline, not an official IELTS paper or an AI-generated question service.
- Full three-passage, 40-question papers, timing, scoring conversion, richer distractors, and human-rated quality evaluation remain pending.

## [0.7.0-alpha.17] - 2026-07-17

### Added

- Added an exam-question research policy covering official IELTS, TOEFL, CET, and postgraduate entrance structures and open dataset candidates.
- Added a dedicated IELTS True / False / Not Given template with the official answer format and evidence field.
- Added TOEFL inference as a separate selectable question type.

### Removed

- Removed initial-letter fill-in from the reader, practice center, general question catalog, and mixed generation engine.

### Changed

- Practice-center question types now default to the first exam-specific specialty instead of an undifferentiated mixed type.
- Moved article import and collections to `v0.7.0-alpha.18`; Kaikki/Tatoeba/wordfreq integration moves to `v0.7.0-alpha.19`.

## [0.7.0-alpha.16] - 2026-07-17

### Added

- Added a clearer practice-center control bar for combined, reading, cloze, and initial-letter training.
- Added exam question-type selection and current-article generation from the practice center.

### Changed

- Kept current rule-based generation explicit as a baseline for the future AI question model and validator.
- Moved article import and collections to `v0.7.0-alpha.17`; Kaikki/Tatoeba/wordfreq integration moves to `v0.7.0-alpha.18`.

## [0.7.0-alpha.15] - 2026-07-17

### Added

- Added a direct Chinese headword gloss for WordNet entries.
- Added Chinese translations for WordNet synonyms, antonyms, family terms, and semantic relation terms.
- Added conservative phrase extraction from the learner's own article contexts, with source labels and translation caching.
- Restored separate phrase, synonym, and antonym sections in the WordNet detail view.

### Fixed

- Restored the richer lexical detail workflow that was missing after the WordNet migration.
- Kept the existing string-based semantic relation API while exposing translated `term_details` for the frontend.

### Changed

- Moved article import and collections to `v0.7.0-alpha.16`; Kaikki/Tatoeba/wordfreq integration moves to `v0.7.0-alpha.17`.

## [0.7.0-alpha.14] - 2026-07-17

### Fixed

- WordNet translation now finds WordNet results even when another dictionary result appears first, and waits for automatic Chinese translation before showing the completed lookup.
- Added browser history synchronization, a visible back action, and route restoration for lexicon searches.
- Prevented stale frontend assets from hiding the latest fixes with development no-cache headers.
- The exercise center reloads the current article's questions and generates a starter set when none exists.

### Changed

- Moved article import and collections to `v0.7.0-alpha.15`; Kaikki/Tatoeba/wordfreq integration moves to `v0.7.0-alpha.16`.

## [0.7.0-alpha.13] - 2026-07-17

### Added

- Added batch translation and local per-segment caching for WordNet definitions and examples.
- Added Chinese translations directly below their matching English definitions and examples.
- Added runtime DeepL credential verification without exposing the API key.

### Fixed

- Stopped treating a non-empty but rejected DeepL key as a working translation service.
- Added clear pending, verified, and failed translation states with actionable error messages.
- Preserved cached Chinese WordNet translations when the external provider is unavailable.

### Changed

- Moved article import and collections to `v0.7.0-alpha.14`; Kaikki/Tatoeba/wordfreq integration moves to `v0.7.0-alpha.15`.

## [0.7.0-alpha.12] - 2026-07-17

### Added

- Added a repeatable Open English WordNet 2025 importer with checksum, license, attribution, version, and source URL metadata.
- Added local WordNet synsets, senses, pronunciations, examples, semantic relations, and indexes to SQLite.
- Added WordNet-backed query results with English definitions, examples, synonyms, semantic relations, personal contexts, translation, and Eudic lookup.
- Added third-party data attribution documentation and importer tests.

### Changed

- Prioritized the open dictionary foundation before article import and collections; those tasks move to `v0.7.0-alpha.13`.

## [0.7.0-alpha.11] - 2026-07-17

### Added

- Added actionable fallback results for every valid English word or phrase, even when the local dictionary has no full entry.
- Added personal article contexts, cached translations, wordbook state, pronunciation, DeepL translation, and Eudic external lookup to fallback results.
- Added direct query and source-article actions to wordbook cards.
- Added continued lookup from collocation headings, related phrases, examples, analysis sentences, and saved contexts.

### Changed

- Saving an existing word or phrase now updates its context instead of creating duplicate cards.
- Phrase queries remain the primary result while still showing related dictionary headwords.
- Moved import and collections to `v0.7.0-alpha.12` after prioritizing the broken vocabulary loop.

## [0.7.0-alpha.10] - 2026-07-16

### Added

- Added an always-visible Interest/Exam mode switch with local persistence and a clear daily starting action.
- Added mode-aware Today recommendations: interest mode favors subscriptions, approachable news/culture, and shorter sessions; exam mode favors exam fit and deeper evidence-based practice.
- Added private `.env.local` loading with a tracked `.env.example` for translation configuration.
- Added configurable DeepL and self-hosted LibreTranslate providers while retaining manual paragraph translation.

### Changed

- Translation status now reports the selected provider and available fallback paths.
- Moved URL/file/subtitle import and user collections to `v0.7.0-alpha.11` after prioritizing the missing dual-mode entry.

## [0.7.0-alpha.9] - 2026-07-16

### Added

- Added one-click article translation with paragraph batching, per-segment caching, persistence, and clear unconfigured-provider errors.
- Added paragraph-aligned bilingual rendering in the article pool, reader, and quiz source passage.
- Added manual paragraph-aligned translation editing as a fallback.
- Added provisional unfamiliar-vocabulary candidates ranked by saved learning records, dictionary levels, learner-level threshold, and article relevance.
- Added persistent word/phrase card types and automatic phrase detection for manual, browser, and lookup saves.

### Changed

- Replaced the generic “key words” analysis section with “possibly unfamiliar” vocabulary candidates.
- Moved URL/file/subtitle import and user collections past `v0.7.0-alpha.9` so bilingual reading could be fixed first.

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
