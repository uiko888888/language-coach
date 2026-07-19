# Product Maturity Benchmark

This is a product benchmark against established interaction patterns, not a live audit of every competitor release. Scores describe the current Language Coach implementation.

## Current Maturity

| Area | Current | Mature reference pattern | Main gap | Next leverage point |
| --- | ---: | --- | --- | --- |
| Real content to training | 7.5/10 | Read Frog, LUTE | Generated-question quality is still rule-limited | Evidence-aware AI generation with rejection rules |
| Reading exam training | 7.2/10 | IELTS/TOEFL practice platforms | Formal scoring and several complete-paper models remain incomplete | Validate prescriptions against next-set improvement |
| Learning profile | 7.2/10 | EF SET onboarding, adaptive learning apps | Behavior evidence now drives prescriptions but not validated CEFR changes | Add prescription feedback and outcome evidence |
| Contextual output | 6.4/10 | Writing assistants and output-first language apps | Five-dimension feedback, decisions, editable error capture and audited synonym basics now close the workflow, but real-model quality and repeated-output gains are unvalidated | Audit real feedback and run seven-day reattempt analysis |
| Speaking output | 6.2/10 | Eudic speaking drills, language coaching apps | Local recording, retelling, opinion, fallback transcript and review capture work; pronunciation, validated grammar feedback and cross-day calibration do not | Audit real recordings and validate repeat-task gains before profile updates |
| Dictionary and word chunks | 7.1/10 | Eudic, Cambridge, Collins, Merriam-Webster | Three validated open layers are active with attribution; commercial dictionary breadth, editorial sense ranking and audio coverage remain below Eudic level | Improve sense ranking, phrase presentation and audio without weakening provenance |
| Review scheduling | 5.8/10 | Anki/FSRS | Unified scheduling loop exists, but the current versioned baseline is not validated FSRS and has no retention fitting | Validated FSRS adapter, retention target and real-log calibration |
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

`alpha.22.1` borrows mature query interaction patterns without copying commercial content: verified inflection recovery, bounded spelling candidates, private recent/repeated searches, section jumps, copy and external verification. Query usability improves, but content coverage only moves to 5.9/10 because navigation cannot replace missing Chinese senses, curated collocations or audited examples.

`alpha.23.0` turns static saved material into an executable memory loop: words, phrases and mastered mistakes share a due queue, users recall before revealing, four ratings produce distinct intervals, lapses enter relearning, and a recent rating can be transactionally undone. This raises review maturity from 3.0 to 5.8. It does not cross 6 because `adaptive-interval-v1` is a conservative versioned baseline rather than validated FSRS, and no personal retention evidence has been fitted yet.

`alpha.24.0` closes the first active-output loop: one article becomes comprehension translation, reconstruction, summary and personal expression; answers, behavior signals, self-review and history persist; a matched English chunk can enter spaced review. Contextual output starts at 5.8/10 rather than crossing 6 because deterministic checks cannot judge open semantics or naturalness, arbitrary error capture is incomplete, and no seven-day reattempt evidence exists. Differentiation remains about traceable one-material-many-uses, not about claiming automated writing assessment.

`alpha.24.1` raises contextual output to 6.4/10: an optional provider returns five validated dimensions with traceable quotations, the learner can keep, accept or modify without losing the original, arbitrary English corrections enter review, and six curated synonym groups test usage boundaries without leaking answers. The score remains well below mature writing products because exact-quote validation does not prove the model's interpretation is sound, provider quality has not been sampled on real answers, and synonym coverage is intentionally small.

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
