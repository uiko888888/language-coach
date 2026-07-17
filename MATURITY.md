# Product Maturity Benchmark

This is a product benchmark against established interaction patterns, not a live audit of every competitor release. Scores describe the current Language Coach implementation.

## Current Maturity

| Area | Current | Mature reference pattern | Main gap | Next leverage point |
| --- | ---: | --- | --- | --- |
| Real content to training | 7.5/10 | Read Frog, LUTE | Generated-question quality is still rule-limited | Evidence-aware AI generation with rejection rules |
| Reading exam training | 6.5/10 | IELTS/TOEFL practice platforms | Formal scoring, timing and complete papers are incomplete | Finish official-format interaction models |
| Learning profile | 6.5/10 | EF SET onboarding, adaptive learning apps | Weekly domain calibration exists; timing and hint evidence are missing | Add richer event evidence and recommendation feedback |
| Dictionary and word chunks | 4.5/10 | Eudic, commercial learner dictionaries | Open coverage, frequency and bilingual examples are limited | Kaikki, Tatoeba and wordfreq layers |
| Review scheduling | 3/10 | Anki/FSRS | Cards and mistakes exist without memory scheduling | Shared FSRS queue for words, mistakes and listening lines |
| Listening and clip study | 2/10 | Eudic clips, asbplayer, Language Reactor | No timed subtitle player or repeat loop yet | User-authorized subtitle and media clip workspace |
| Content discovery | 5/10 | News readers and Eudic daily content | Collections, event tracking and feedback are incomplete | Profile-aware collections and explicit feedback |
| Universal delivery | 3/10 | Hosted PWA products | Current edition is local and single-user | Accounts, cloud database, worker queue and PWA |
| Engineering operations | 5/10 | Production SaaS | Monolithic backend, partial E2E and no cloud observability | Module split, migrations, monitoring and backups |

## Differentiation

The defensible product is not a larger dictionary or another generic AI question generator. It is the traceable loop:

```text
legal article / webpage / subtitle
-> readable source and optional translation
-> vocabulary, chunks and evidence
-> exam-shaped or interest-shaped training
-> mistake diagnosis
-> targeted next task and spaced review
-> profile calibration
```

Current strengths are source traceability, one-material-many-uses, evidence replay, contextual lookup and the browser extension intake. The product does not yet have a moat in dictionary coverage, adaptive modeling, listening interaction or public delivery.

Interest and exam modes now use different home workflows: immersion and expression collection versus target, weakness and question-type prescription. They still share one profile so interest activity can later contribute domain evidence without masquerading as exam-score gains.

## Universal Product Requirements

To serve more than one local user, the product must support:

- Optional onboarding paths: existing score, quick baseline or self-assessment.
- Editable goals and recommendations; no mandatory fixed course sequence.
- Separate ability evidence, effort XP and plan completion.
- Accessible mobile layouts and PWA installation.
- Accounts, export, deletion, backups and cross-device sync.
- Source rights, privacy controls and provider-independent AI configuration.
- Useful no-AI fallback paths for reading, dictionary and rule-based practice.

## Clip Study Direction

Clip study remains a core `v0.9.0` direction. It should improve on rigid clip lessons by making every layer optional and profile-aware.

### Inputs

- User-authorized local video/audio and SRT/VTT/ASS subtitles.
- Public-domain or openly licensed media.
- User-selected streaming context through the browser extension where platform rules permit it.
- Source URL and short quoted context, without downloading or redistributing protected media.

### Workspace

```text
left: episode / clip list and subtitle cues
right: media player and current bilingual cue
bottom: words, chunks, notes and training actions
```

Expected controls:

- 15-60 second, 1-5 minute, 5-20 minute and long-content filters.
- Previous/next cue, repeat, auto-pause, speed and subtitle visibility.
- Current-word or current-cue highlighting synchronized to playback.
- One-click loop range and difficult-line collection.
- Listening without subtitles, dictation, reconstruction, shadowing and retelling.
- Send a cue to vocabulary, phrase review, a daily plan or exam-shaped questions.

### Adaptation

- Interest mode emphasizes comprehension, culture, pronunciation and reusable expressions.
- Exam mode keeps the original clip but generates questions at the learner's target difficulty.
- Listening failures update listening evidence; simply watching a clip does not increase ability.
- Users can turn translation, hints, pausing and generated exercises on or off.

### Delivery Order

1. Subtitle parser, cue timeline and local media playback.
2. Cue repeat, speed, auto-pause and bilingual display.
3. Phrase capture and daily-plan integration.
4. Dictation, reconstruction and shadowing records.
5. Profile-aware recommendations and exam-shaped generation.
6. Browser-extension integration for permitted streaming contexts.

## Efficiency Principles

- The home screen should offer one recommended next action while preserving direct navigation.
- Every saved word, phrase, mistake or cue should retain its source context.
- A learner should not enter the same goal, level or preference in multiple places.
- Recommendations must explain their evidence and remain dismissible.
- New exam and media modules must reuse profile, evidence, review and history contracts rather than create isolated progress systems.
