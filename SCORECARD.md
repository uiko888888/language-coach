# Maturity Score Program

The goal is to raise every major product dimension above 6/10 through evidence, not by adding labels or navigation entries. A dimension crosses 6 only when its user path, data model, tests and runtime evidence all exist.

## Current Gates

| Dimension | Current | 6/10 acceptance gate | Planned release |
| --- | ---: | --- | --- |
| Dictionary and chunks | 5.8 | Import licensed Kaikki, Tatoeba and frequency subsets; pass polysemy, phrase, Chinese-query and attribution audit | alpha.22.1 |
| Review scheduling | 3.0 | FSRS queue for words, phrases and mastered mistakes; due counts and rescheduling tests | alpha.23 |
| Listening and clip study | 2.0 | Local media plus SRT/VTT, cue sync, loop, speed, bilingual cue and phrase capture | alpha.24 |
| Interest and fun | 4.8 | Clip workflow, editable challenge intensity, meaningful mastery rewards and seven-day retention evidence | alpha.24 then validation |
| Other exams | 4.5 | At least CET and Kaoyan have independent paper structures, validated answer rules and official-format boundaries | alpha.25 |
| Accessibility | 4.8 | Keyboard-only core loop, visible focus, semantic labels, contrast audit and desktop/mobile browser checks | alpha.26 |
| Public delivery | 4.0 | Account ownership, server authorization, cloud database, migration, export/delete and deploy runbook | v0.10.0 |

## Execution Order

1. alpha.22.1: real open dictionary data and quality audit.
2. alpha.23: FSRS review scheduling and due queue.
3. alpha.24: subtitle clip workspace and interest-mode differentiation.
4. alpha.25: CET/Kaoyan independent exam structures and question validation.
5. alpha.26: accessibility, visual consistency and browser E2E baseline.
6. v0.10.0: multi-user cloud delivery and security boundary.

## Scoring Rules

- A schema or importer without real data improves engineering readiness, not content coverage.
- A page entry without a complete user loop does not increase product maturity.
- XP and decorative rewards do not increase learning effectiveness scores.
- Rule-generated exam questions are simulations and cannot be scored as official question-bank coverage.
- Local visibility labels do not count as cloud authorization.
- Scores are updated in MATURITY.md and REVIEWS.md only after acceptance evidence is recorded.
