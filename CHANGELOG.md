# Changelog

All notable changes to this project are documented in this file.

The format follows Keep a Changelog, and the project uses Semantic Versioning.

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
