# Product Maturity Benchmark

This is a product benchmark against established interaction patterns, not a live audit of every competitor release. Scores describe the current Language Coach implementation.

## Current Maturity

| Area | Current | Mature reference pattern | Main gap | Next leverage point |
| --- | ---: | --- | --- | --- |
| Real content to training | 7.5/10 | Read Frog, LUTE | Generated-question quality is still rule-limited | Evidence-aware AI generation with rejection rules |
| Reading exam training | 7.2/10 | IELTS/TOEFL practice platforms | Formal scoring and several complete-paper models remain incomplete | Validate prescriptions against next-set improvement |
| Learning profile | 7.2/10 | EF SET onboarding, adaptive learning apps | Behavior evidence now drives prescriptions but not validated CEFR changes | Add prescription feedback and outcome evidence |
| Dictionary and word chunks | 5.8/10 | Eudic, commercial learner dictionaries | Layered import and UI are ready, but the real database still lacks Kaikki, Tatoeba and wordfreq data | Import licensed subsets and validate polysemy, phrases and Chinese recall |
| Review scheduling | 3/10 | Anki/FSRS | Cards and mistakes exist without memory scheduling | Shared FSRS queue for words, mistakes and listening lines |
| Listening and clip study | 2/10 | Eudic clips, asbplayer, Language Reactor | No timed subtitle player or repeat loop yet | User-authorized subtitle and media clip workspace |
| Content discovery | 6.2/10 | News readers and Eudic daily content | Two layouts and public/private scopes exist; collections, reading state and feedback are incomplete | Persist filters, track reading state and add collections |
| Universal delivery | 3/10 | Hosted PWA products | Current edition is local and single-user | Accounts, cloud database, worker queue and PWA |
| Engineering operations | 6.7/10 | Production SaaS | Versioned material migration exists, but HTTP/business code remains concentrated and browser E2E is partial | Continue domain extraction, conflict control and observability |

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

`alpha.20` adds a stronger adaptive candidate: an unfinished run survives refresh/browser changes, and the next prescription explains accuracy, time, answer changes, hints, confidence errors and independent-question coverage. This is more differentiated than a generic recommendation card because it remains connected to evidence replay, error diagnosis and immediate targeted practice. It is not yet a moat until real usage proves that following the prescription improves the next set.

`alpha.21` improves discovery without replacing the efficient split reader: users can scan a grid, distinguish public sources from private imports, and move each card directly into reading, training or today's plan. This makes one-material-many-uses more visible, but layout choice alone is not differentiation; it must later be measured by faster selection and higher training completion.

`alpha.22` changes the dictionary from a WordNet-specific page into a layered open-data system. It separates semantic definitions, etymology/forms, attributable examples, general frequency and personal corpus evidence. The architecture and learning presentation exceed the 6/10 threshold, but the actual dictionary product remains 5.8/10 until licensed real subsets are imported and quality-audited; importer fixtures are not coverage.

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
