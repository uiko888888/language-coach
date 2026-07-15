# Changelog

All notable changes to this project are documented in this file.

The format follows Keep a Changelog, and the project uses Semantic Versioning.

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
