# Changelog

All notable changes to this project are documented in this file.

The format follows Keep a Changelog, and the project uses Semantic Versioning.

## [Unreleased]

- Researched legally distributable English dictionary sources and staged the import order for Open English WordNet, Kaikki/Wiktionary, Tatoeba, FreeDict, Moby Thesaurus, and wordfreq.
- Verified the per-user Windows sign-in task on port `8766`; the task is running and the backend health endpoint responds successfully.

## [0.8.0-alpha.12] - 2026-07-18

### Added

- Added optional profile paths for an existing score, a six-question reading/vocabulary baseline, or CEFR self-assessment.
- Added validated IELTS, TOEFL, EF SET, CET, KAOYAN and custom score anchors with optional section scores and assessment dates.
- Added target exam, target score, target date, weak areas, interest topics and preferred content types.
- Added a profile summary with CEFR baseline, evidence source, confidence, target and recommended reading levels.
- Added profile-aware article ranking and explicit difficulty, interest and goal recommendation reasons.
- Added a maturity benchmark covering current competitiveness, universal delivery gaps, efficiency principles and the clip-study roadmap.
- Added automated coverage for score validation, quick-test answer privacy, profile persistence and recommendation linkage.

### Changed

- Learner-plan updates now preserve profile fields instead of rebuilding only daily-plan settings.
- Assessment confidence now accounts for evidence type and score age.
- Ability evidence remains separate from XP and daily-plan completion.

### Known limits

- The quick baseline covers reading and vocabulary only; it is not an IELTS, TOEFL, listening, speaking or full CEFR certification.
- Profile calibration currently uses explicit scores, self-assessment and the quick baseline; weekly longitudinal updates are not implemented yet.
- Clip study is planned for `v0.9.0`; timed subtitle playback and media controls are not included in this release.

## [0.8.0-alpha.11.4] - 2026-07-18

### Added

- Added a per-user Windows sign-in task installer that starts the backend after a 30-second delay.
- Added task settings for missed-run recovery, single-instance execution, and three startup retries.
- Added dedicated task status and uninstall scripts; uninstall leaves running Python processes untouched.
- Added post-install backend health verification and configurable `LANGUAGE_COACH_PORT` / `LANGUAGE_COACH_PYTHON` support.
- Added deployment guidance for a hosted Web/PWA primary product and an optional privacy-preserving local companion.
- Added automated checks for task behavior, path portability, health verification, and uninstall scope.

### Changed

- The backend, PowerShell launcher, batch launcher, scheduler and documentation now share port `8765` by default while allowing explicit overrides.

### Known limits

- Windows cannot fetch while powered off, sleeping, or before the user signs in; a missed refresh is recovered after the next sign-in.
- The Codex sandbox denied access to the Windows Scheduled Tasks API, so installation on this machine still needs one normal PowerShell invocation and status verification.
- Public multi-user delivery still requires cloud deployment, accounts, a durable scheduler, permissions and operational monitoring.

## [0.8.0-alpha.11.3] - 2026-07-18

### Added

- Added asynchronous stale-content refresh on startup and a six-hour in-process scheduler.
- Added feed refresh runs and per-source logs with status, HTTP code, counts, duration, and errors.
- Added source health fields, consecutive-failure tracking, and exponential retry backoff with manual override.
- Added `ETag`, `Last-Modified`, and HTTP 304 handling.
- Added article publication time, feed GUID, and normalized content hash persistence.
- Added URL, source/GUID, and source/content-hash identity fallback.
- Added article-page refresh status, counts, interval, failure count, and publication time.
- Added automated coverage for metadata, health logs, caching, 304, deduplication, retry readiness, and failure isolation.

### Changed

- Feed requests no longer keep a database transaction open during network I/O.
- Recommendation freshness now uses article publication time when available.
- Manual refresh reports new, updated, and failed counts separately.

### Known limits

- Scheduling runs only while the local backend is running; it cannot fetch while the computer is off.
- Repeatedly failing sources are backed off but not automatically disabled.
- Full-page extraction remains limited to user-authorized browser imports; RSS summaries are not presented as full articles.

## [0.8.0-alpha.11.2] - 2026-07-17

### Added

- Added a private local EPUB library with OPF metadata, manifest, spine, chapter, word-count, and file-fingerprint parsing.
- Added safe ZIP limits for file size, entry count, expanded size, and individual entries without extracting files to disk.
- Added book and chapter persistence, idempotent re-import, chapter-body deduplication, and private-material rights labels.
- Added on-demand chapter materialization so only selected chapters enter the article reader and exercise workflow.
- Added article-page controls for local EPUB paths, book selection, chapter selection, and opening a chapter in the reader.
- Added synthetic EPUB tests for parsing, privacy-safe listing, idempotency, materialization, and invalid archive rejection.

### Changed

- EPUB files no longer need to be manually copied into the article textarea.
- Book listings return the source filename and chapter metadata, not chapter bodies or the full local path.

### Security and rights

- Imported books are marked `private_user_material`; files and text remain in the ignored local SQLite database.
- The application does not upload, redistribute, or commit imported book content.
- Importing a local file does not establish distribution rights; users remain responsible for lawful access and use.

## [0.8.0-alpha.11.1] - 2026-07-17

### Added

- Added a typed `Complete the Words` single-blank simulation for the 2026 TOEFL task family.
- Added traceable target-word, visible-prefix, missing-letter, masked-context, full-answer, and no-option validation.
- Added spelling, word-form, incomplete-answer, and contextual-meaning error diagnosis.
- Added automatic wrong-word capture with the source sentence in the vocabulary notebook without duplicate cards.
- Added persistent quiz metadata so generated tasks remain auditable after reload.
- Added API and migration coverage for generation, persistence, typed grading, and review capture.

### Changed

- Article and remedial question creation now share the structured quiz persistence path.
- TOEFL exposes ten training specialties; `Complete the Words` uses `toefl-2026-sim-v1` provenance.

### Known limits

- This is a one-blank training unit, not a reproduction of the official multi-blank screen or scoring model.
- ETS pages were unreachable from the development environment during this release; exact current display and timing parameters require re-verification against an official public sample.
- No ETS or commercial question text is bundled.

## [0.8.0-alpha.11] - 2026-07-17

### Added

- Added independent TOEFL negative factual, rhetorical purpose, sentence insertion, and prose-summary foundations.
- Added three-supported-one-absent validation for negative factual questions.
- Added sentence-function validation for rhetorical purpose questions and paragraph reconstruction for insertion questions.
- Added cross-paragraph idea coverage validation for prose summaries.
- Added dedicated skills, coaching methods, error types, and same-type remedial generation for all four question types.
- Added positive and negative test coverage for advanced TOEFL evidence contracts.

### Changed

- TOEFL now exposes nine independent reading specialties and uses `toefl-rule-v2` generation provenance.

### Known limits

- Prose summary is currently a four-option best-summary foundation; the official-style choose-three-from-six interaction is not implemented.
- A complete TOEFL reading section, official timing/scoring, listening, speaking, and writing remain pending.
- Generated questions are evidence-validated simulations and do not copy ETS questions.

## [0.8.0-alpha.10] - 2026-07-17

### Added

- Added persistent daily completion counts for reading, practice, mistake review, and vocabulary.
- Added editable per-task targets, overall progress, estimated remaining time, and a completion summary.
- Added an idempotent Today queue for recommended articles, mistakes, and browser-extension clips.
- Added automatic progress updates when practice is archived, a mistake is first solved, or a new word or phrase is saved.
- Added manual completion controls for reading and other work completed outside an automatically measured action.
- Added integration coverage for settings, manual progress, queue deduplication, one-time completion, and automatic progress hooks.

### Changed

- Finishing a practice session, saving a new card, and solving a mistake now refresh the Today dashboard immediately.
- Daily plans are executable learning checklists rather than category-only recommendations.

### Known limits

- Reading completion remains manual so opening an article does not falsely count as learning.
- Daily progress is local and calendar-day based; streak repair, timezone settings, weekly summaries, and cross-device sync are not implemented.
- Plan completion summarizes workload only and does not increase ability scores.

## [0.8.0-alpha.9] - 2026-07-17

### Added

- Added persistent session archiving for immediate-feedback practice without duplicating attempts or awarding points twice.
- Added style-filtered practice history, single-session detail, and cross-session analytics APIs.
- Added skill and question-type accuracy, recent-versus-previous trend, weakest-skill diagnosis, and next-question-type recommendation.
- Added a Training History view with session list, score/time metadata, per-question answers and evidence, ability meters, and source replay.
- Added direct continuation from history recommendations to focused remedial practice.
- Added integration coverage for practice-session archiving, unanswered denominators, detail retrieval, and analytics.

### Changed

- Both practice and mock modes now appear in the same history model.
- Immediate attempts expose their persistent attempt id so a completed practice can link existing records instead of submitting answers again.

### Known limits

- Trend compares the most recent five attempts with the previous five; it is a descriptive signal, not a calibrated ability score.
- History does not yet restore a completed session into editable mode or provide date-range filters and export.
- XP remains separate from performance trends and does not raise the displayed accuracy.

## [0.8.0-alpha.8] - 2026-07-17

### Added

- Added independent TOEFL reading generators for factual information, inference, paragraph main idea, sentence simplification, and vocabulary in context.
- Added TOEFL-specific skill, difficulty, paragraph-reference, option-count, essential-information, and vocabulary-context validation.
- Added `toefl-rule-v1` generation provenance and structured TOEFL error labels.
- Added mixed single-passage TOEFL generation and same-specialty remedial generation.
- Added unit and API coverage for every TOEFL template, mixed generation, wrong-answer diagnosis, and remedial question isolation.

### Changed

- The five current TOEFL specialties no longer use the shared `general-rule-v1` generator.
- TOEFL practice continues to reuse the shared session, confidence, evidence replay, mistake, and next-set infrastructure.

### Known limits

- Negative factual information, rhetorical purpose, text insertion, prose summary, and category completion are not implemented.
- A complete TOEFL reading section, official timing/scoring, listening, speaking, and writing remain pending.
- Current questions are rule-validated simulations, not official ETS questions.

## [0.8.0-alpha.7] - 2026-07-17

### Added

- Added editable 5 / 15 / 30 / 60 minute daily plans with reading, practice, mistake review, and vocabulary task combinations.
- Added persistent short-term and long-term goals with optional target dates.
- Added an explicit profile-recommendation switch and a generic fallback when personalization is disabled.
- Added goal and plan context to the Today API and goal-aware recommendation reasons.
- Added direct routing from “start today” to the first user-selected task.
- Added `PROJECT_PLAN.md` as the authoritative version objective, scope, non-goal, acceptance, and release ledger.
- Added integration coverage for settings persistence and Today API goal context.

### Changed

- Product documentation now separates application recommendations from future system/browser push notifications.
- Removed the obsolete initial-letter exercise claim from the product definition.

### Known limits

- The daily plan selects time and task categories but does not yet track per-task completion or custom question/card counts.
- Goals influence recommendation context and exam selection; semantic goal matching and dynamic ability modeling remain pending.
- System notifications, browser notifications, and cross-device push are not implemented.

## [0.8.0-alpha.6] - 2026-07-17

### Added

- Added local draft persistence for incomplete practice sessions, including answers, confidence, flags, active question, mode, and elapsed time.
- Added direct result actions to continue training by a specific mistake type and question type.
- Added backend filters for the weakness-driven next-set endpoint so remedial training does not silently mix unrelated question types.
- Made English evidence sentences in explanations clickable for immediate word or phrase lookup.
- Added API test coverage for focused next-set generation.

### Changed

- Refreshing the page can restore the same article and question set instead of discarding an unfinished session.
- This release is committed and tagged locally only; GitHub push is intentionally deferred until explicitly requested.

## [0.8.0-alpha.5] - 2026-07-17

### Added

- Added per-question confidence calibration with guessing, uncertain, and certain levels, plus confidence accuracy in session results.
- Added evidence replay from immediate explanations and the mistake center back to the matching source paragraph in the reader.
- Added a weakness-driven “next 10 questions” endpoint and interface action that prioritizes unresolved mistake types and fills the set with unanswered exam questions.
- Added a dashboard learning queue for browser-extension captures with direct routes to the imported article, generated practice, dictionary lookup, and source webpage.
- Added database migrations and integration coverage for confidence persistence, session summaries, and adaptive next-set generation.

### Changed

- Practice mode now requires confidence selection before immediate answer submission so calibration data is intentional rather than inferred.
- The post-session diagnosis now separates correct answers from confident misconceptions and provides a direct continuation path.

### Known limits

- Evidence replay uses exact or paragraph-level text matching; NOT GIVEN explanations without a literal source sentence may still require manual location.
- The next set is rule-based and uses unresolved mistakes plus available unanswered questions; it is not yet a probabilistic knowledge-tracing model.
- Plugin captures are surfaced in the main app, but background sync, deduplication, and cross-device queues are not implemented.

## [0.8.0-alpha.4] - 2026-07-17

### Added

- Added independent postgraduate entrance English generators for detail/inference, main idea/attitude, complex sentence meaning, and cloze logic.
- Added KAOYAN-specific skill, difficulty, generation-source, validation, and structured mistake labels.
- Added mixed single-passage KAOYAN generation and same-specialty remedial generation.
- Added the CHSI postgraduate admissions portal to the traceable exam-resource catalog.
- Added tests covering every KAOYAN template, mixed generation, error classification, and official-resource visibility.

### Changed

- KAOYAN no longer uses the shared generic question generator for its four current specialties.
- Full-paper generation is disabled in the interface for exams that do not yet have a real full-paper engine.

### Known limits

- English I and English II are not separated yet.
- New question types, translation, writing, and complete past-paper structure remain pending.
- Current KAOYAN questions are validated rule simulations, not official past papers.

## [0.8.0-alpha.3] - 2026-07-17

### Added

- Added distinct practice scopes: specialty practice, single-passage combination, and full-paper simulation.
- Single-passage combination now actually mixes validated IELTS specialty items instead of silently using the selected single type.
- Added exam-resource provenance records with exam, provider, source type, external URL, access mode, and rights status.
- Added official IELTS, British Council, IDP, ETS, and CET portal links without copying protected question text.
- Added private user-resource registration for materials the user owns or is authorized to use.
- Added IELTS full mock generation from three eligible full articles with a fixed 13 / 13 / 14 distribution and 40-question metadata.
- Added paper, passage, and question relations so a full mock keeps the source passage aligned with each question.
- Added a practice-center source and rights panel so external official materials are visibly distinct from local simulations.

### Changed

- Separated question scope from feedback mode: a full mock can independently run in practice or mock feedback mode.
- Improved controlled contradiction fallback so eligible IELTS passages do not silently lose the FALSE item during validation.

### Known limits

- Full-paper generation currently supports IELTS only and requires three locally stored, paragraph-complete English articles.
- Generated papers are rule-based simulations, not official past papers; the score is not an IELTS band conversion.
- External links are not automatically fetched, parsed, or redistributed.

## [0.8.0-alpha.2] - 2026-07-17

### Added

- Added separate practice and mock-session behavior: practice reveals evidence immediately, while mock sessions defer scoring and explanations until submission.
- Added question navigation with answered, unanswered, correct, wrong, active, and flagged states.
- Added elapsed-time tracking, single-question and all-question views, restart controls, incomplete-answer confirmation, and unified submission.
- Added persistent mock-session results with score, completion, elapsed time, skill summaries, error summaries, and linked attempts; practice mode continues to persist each immediate attempt.
- Added a post-session result panel with direct mistake-review and retry actions.
- Added a Playwright browser smoke test covering desktop split layout, mock submission, diagnosis rendering, and mobile horizontal overflow.

### Changed

- Kept the source passage visible beside the question workspace on desktop and stacked it before questions on narrow screens.
- Refactored single-answer and batch-session scoring to share one persistence and diagnosis path.
- Practice loading no longer resets an active session whenever the user returns to the practice-center view.

### Fixed

- Unanswered mock questions are now included in the denominator and recorded with the `未作答` diagnosis instead of disappearing from results.
- Removed the obsolete initial-letter exercise claim from current documentation.

### Known limits

- The session score is percentage correct, not an official IELTS band conversion.
- Full IELTS three-passage papers, section-level time allocation, pause recovery, and calibrated distractor quality remain pending.

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
