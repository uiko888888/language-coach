# Product Maturity Benchmark

This is a product benchmark against established interaction patterns, not a live audit of every competitor release. Scores describe the current Language Coach implementation.

## Current Maturity

| Area | Current | Mature reference pattern | Main gap | Next leverage point |
| --- | ---: | --- | --- | --- |
| Real content to training | 7.5/10 | Read Frog, LUTE | Generated-question quality is still rule-limited | Evidence-aware AI generation with rejection rules |
| Reading exam training | 7.4/10 | IELTS/TOEFL practice platforms | Complete the Words now has traceable card review, but formal scoring and several complete-paper models remain incomplete | Validate prescriptions and card review against later performance |
| Learning profile | 7.2/10 | EF SET onboarding, adaptive learning apps | Behavior evidence now drives prescriptions but not validated CEFR changes | Add prescription feedback and outcome evidence |
| Contextual output | 6.8/10 | Writing assistants and output-first language apps | Academic phrase production now has form-gated cloze, translation and personal-sentence attempts, but semantic quality and repeated-output gains remain unvalidated | Add evidence-aware semantic checks and seven-day reattempts |
| Speaking output | 6.2/10 | Eudic speaking drills, language coaching apps | Local recording, retelling, opinion, fallback transcript and review capture work; pronunciation, validated grammar feedback and cross-day calibration do not | Audit real recordings and validate repeat-task gains before profile updates |
| Dictionary and word chunks | 8.4/10 local, 8.2/10 distributable | Eudic, Cambridge, Collins, Merriam-Webster | A reviewed 100-phrase academic layer improves usable public coverage, but private Oxford content cannot be bundled and active phrase production is absent | Add phrase completion, translation and personal-sentence recall |
| Review scheduling | 6.8/10 | Anki/FSRS | Validated FSRS now powers general memory, exam-item and boundary-error loops; long-term retention fitting and management controls remain | Collect real logs, calibrate retention, add pause/reset/new-card limits |
| Listening and clip study | 2/10 | Eudic clips, asbplayer, Language Reactor | No timed subtitle player or repeat loop yet | User-authorized subtitle and media clip workspace |
| Content discovery | 6.2/10 | News readers and Eudic daily content | Two layouts and public/private scopes exist; collections, reading state and feedback are incomplete | Persist filters, track reading state and add collections |
| Universal delivery | 3/10 | Hosted PWA products | Current edition is local and single-user | Accounts, cloud database, worker queue and PWA |
| Engineering operations | 7.4/10 | Production SaaS | Versioned editorial promotion and browser E2E exist, but HTTP/business code remains concentrated and SQLite resource cleanup is incomplete | Continue domain extraction, connection cleanup and observability |

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

`alpha.24.4` crosses the 6/10 threshold for review scheduling: FSRS 6.3.1 is isolated behind an opt-in adapter, schema 17 persists its card state, legacy items migrate without deleting history, and a real database copy passed rating/undo replay. The score is still below mature spaced-repetition products because long-term personal retention has not been calibrated and pause/reset/new-card controls are not yet complete.

`alpha.24.5` adds a narrow but complete exam-item review loop: only attempted Complete the Words questions become cards, formal exam attempts remain untouched, evidence and lexical meaning stay visible, and FSRS rating/undo are isolated from general memory review. This improves efficiency and traceability, not content breadth. It remains below mature exam platforms until real retention gains, larger validated question coverage and full browser E2E are demonstrated.

`alpha.24.0` closes the first active-output loop: one article becomes comprehension translation, reconstruction, summary and personal expression; answers, behavior signals, self-review and history persist; a matched English chunk can enter spaced review. Contextual output starts at 5.8/10 rather than crossing 6 because deterministic checks cannot judge open semantics or naturalness, arbitrary error capture is incomplete, and no seven-day reattempt evidence exists. Differentiation remains about traceable one-material-many-uses, not about claiming automated writing assessment.

`alpha.24.1` raises contextual output to 6.4/10: an optional provider returns five validated dimensions with traceable quotations, the learner can keep, accept or modify without losing the original, arbitrary English corrections enter review, and six curated synonym groups test usage boundaries without leaking answers. The score remains well below mature writing products because exact-quote validation does not prove the model's interpretation is sound, provider quality has not been sampled on real answers, and synonym coverage is intentionally small.

`alpha.24.6` moves synonym handling into the main dictionary workflow. A learner can compare two to five terms directly; reviewed groups explain grammar and pragmatic boundaries, while unreviewed groups expose only attributable evidence. This is more useful than merging words under one Chinese gloss, but one reviewed set is not broad editorial coverage, so the dictionary score rises only modestly.

`alpha.24.7` applies that clearer hierarchy to ordinary lookup: the first viewport now anchors a selected sense in an English concept, verified patterns, register, cautions and one bilingual example, while full polysemy stays available below. It also removes unverified open phrases from the common-collocation surface. The remaining structural gap is sense-aware saving and review; cards still do not persist the selected sense frame.

`alpha.24.8` improves scanability and provenance rather than raw coverage. Numbered part-of-speech meanings make polysemy easier to parse, and personal-corpus collocations now disclose exactly which private learning sources produced them. The dictionary score remains 7.5/10: this is a meaningful usability gain, but it does not create missing Chinese senses, editorial coverage or complete UK/US audio.

`alpha.24.9` removes two workflow breaks: double-click now reaches the full dictionary directly, and individual paragraph translations persist without positional drift. Simplified-Chinese normalization improves consistency but not lexical authority. Dictionary maturity rises only to 7.6/10 and real-content workflow to 7.7/10; DeepL reachability, licensed modern Chinese coverage and the uncompleted 20-article extraction audit remain material gaps.

`alpha.25.0` adds the first defensible general-collocation layer and closes sense-specific memory. General, personal and unverified phrase evidence are visibly separate; repeated open-corpus evidence is required before automatic candidates become common, and two senses of one headword can now remain distinct through review. Dictionary maturity rises to 7.9/10 and the vocabulary-review loop to 7.5/10. It remains below mature commercial dictionaries because the corpus is modest, Chinese editorial coverage is incomplete, private dictionary import is pending and no licensed Oxford/Longman content is embedded.

`alpha.25.1` adds private dictionary aggregation without pretending that user-owned commercial content is redistributable product data. Local lookup gains 39,108 Oxford bilingual entries and 30,268 clearly separated Britannica entries, exact phrase meanings can carry a private source label, and unsupported HUFF/CDIC input remains visibly pending. This raises local dictionary usefulness to 8.1/10, but distributable maturity only to 7.9/10: source controls are not yet editable in the UI, one supplied dictionary is not decoded, and private examples cannot support public question generation. The useful differentiation is now stronger for a personal desktop workspace, not yet for a hosted multi-user product.

`alpha.25.2` registers a high-value illustrated scan without awarding itself false coverage. The 1,263-page DK Oxford PDF is traceable and visible as pending OCR, but contributes zero searchable entries because dense columns and illustration panels have not passed alignment gates. Dictionary scores therefore stay at 8.1/10 local and 7.9/10 distributable. The maturity gain is operational: the product can now distinguish “owned source”, “searchable index” and “verified content” instead of treating file presence as successful integration.

`alpha.25.3` completes the first reusable private dictionary format rather than increasing bundled coverage. StarDict now has low-memory parsing, compound fingerprints, transactional refresh, synonym handling, token-protected APIs and user-facing source controls. Engineering operations rise from 6.7 to 7.0/10 and private dictionary maintainability improves, while dictionary coverage remains 8.1/10 local and 7.9/10 distributable until a real StarDict source is imported and sampled. The main self-critique is that format conformance from synthetic fixtures is necessary but not sufficient evidence for ecosystem compatibility.

`alpha.25.4` turns scanned-dictionary OCR from an intention into a reproducible, fail-closed experiment. The representative sample, source fingerprint, isolated dependency plan, raw-result retention and quantitative promotion gate raise OCR engineering readiness to 6.2/10 and engineering operations to 7.1/10. Dictionary coverage remains 8.1/10 local and 7.9/10 distributable because the Paddle runtime is not yet available, all 20 gold pages are pending and zero OCR entries are searchable. The main self-critique is that deterministic scoring code cannot substitute for human gold labels or real inference; the 98% and 99% targets remain acceptance criteria, not measured performance.

`alpha.25.5` expands synonym teaching from a single demonstration into a small but coherent high-frequency layer. Eleven groups now connect Chinese overlap to English concepts, syntax, collocation, register and non-interchangeable boundaries, so the feature begins to support English-first memory rather than parallel translation lists. Synonym-boundary teaching rises from 5.5 to 6.5/10 and the vocabulary learning loop from 7.5 to 7.8/10. Overall dictionary coverage stays at 8.1/10 local and 7.9/10 distributable because 29 curated terms are pedagogically useful but statistically narrow. The main self-critique is that expansion is still editorially selected rather than driven by observed learner errors, and boundary mistakes do not yet enter spaced review.

`alpha.25.6` broadens the curated layer to 31 groups and 88 terms and makes every group discoverable from the dictionary workspace. Coverage now spans daily verbs, academic composition, probability, causality, methods, objectives and outcomes; whole/part direction is explicitly modeled for `compose/comprise/constitute/consist of`. Synonym-boundary teaching rises from 6.5 to 7.3/10 and dictionary interaction from 7.2 to 7.6/10. Overall dictionary coverage remains 8.1/10 local and 7.9/10 distributable because the improvement is pedagogical depth, not broad licensed lexical coverage. The main self-critique is that 88 terms are still manually selected, catalog order is static, and no production evidence yet proves that these explanations reduce repeated errors.

`alpha.25.7` separates spelling/form confusion from Chinese-semantic overlap and adds 14 reviewed groups with spelling anchors and grammatical checks. Confusion teaching rises from 7.3 to 7.6/10 and dictionary interaction from 7.6 to 7.8/10 because learners can now browse the problem they actually have instead of treating every similar-looking word as a synonym. Dictionary coverage remains 8.1/10 local and 7.9/10 distributable: 29 additional editorial terms improve pedagogy, not licensed lexical breadth. The main self-critique is that static selection still reflects editorial judgment; without candidate evidence, error recurrence and later-task outcomes, this release cannot claim adaptive confusion prevention.

`alpha.25.8` creates a maintainable route past 100 groups without pretending all content has equal authority. The catalog contains 105 groups, while only 45 retain reviewed teaching status and 60 remain evidence-only candidates. Discoverability and roadmap coverage improve, but confusion teaching stays at 7.6/10 because unreviewed titles are not learning content. Engineering maintainability rises modestly through validated candidate metadata and explicit promotion boundaries. The central self-critique is numerical: crossing 100 is a planning milestone, not a quality milestone; the next score increase requires reviewed promotion and measured reduction in repeat errors.

`alpha.25.9` expands planning coverage to 200 groups and adds a 95-group IELTS-priority view. It also repairs the evidence path so attributed Tatoeba examples survive private-dictionary aggregation. Discoverability rises, but confusion teaching remains 7.6/10 and reviewed completion falls proportionally to 45/200: catalog breadth is not editorial maturity. The useful gain is a lawful, attributable route to examples for 128/150 audited terms. The main gap is now collocation and boundary review, not raw group discovery.

`alpha.25.10` turns the 200-group list into an auditable editorial system. Persistent workflow state, idempotent registry sync, explicit evidence counts and fail-closed publication raise engineering operations from 7.1 to 7.4/10. Confusion teaching remains 7.6/10 because no candidate was promoted. A polished queue organizes quality work but cannot substitute for the remaining 155 reviews or evidence that learners make fewer repeat errors.

`alpha.25.11` promotes the complete 20-group IELTS chart subset, bringing reviewed coverage to 65/200 and 176 term placements. Statistical boundaries prevent polished-looking but false substitutions such as treating a percentage, rate and ratio as equivalent or replacing a median with a mean. Confusion teaching rises from 7.6 to 8.0/10 and distributable dictionary/chunk maturity reaches 8.0/10. The score does not imply IELTS score gains: these are reviewed reference explanations and examples, not yet active boundary-choice tasks, FSRS items or evidence from later writing.

`alpha.25.12` promotes 20 IELTS argument and stance groups, bringing reviewed coverage to 85/200 and 236 term placements. It adds practical grammar and logic boundaries rather than a list of formal-looking connectors: clause versus noun-phrase complements, evidence distance in reporting verbs, and factual truth versus logical validity. Confusion teaching rises to 8.2/10, contextual output reference support to 6.5/10 and distributable dictionary/chunk maturity to 8.1/10. The next score should not come from another static batch; learners must first choose, correct, explain and later recall these boundaries through the existing FSRS loop.

`alpha.25.13` turns those reviewed boundaries into 393 active tasks and routes real errors into the same auditable FSRS scheduler used elsewhere. Confusion teaching rises from 8.2 to 8.5/10, contextual output to 6.6/10 and review scheduling to 6.8/10 because the product now supports choose/correct/explain/review/undo rather than reference reading alone. The remaining weakness is evidence, not another control: 157 generated correction tasks need a representative ambiguity audit, and only seven-day reattempt data can show whether error recurrence actually falls.

`alpha.25.14` tests that assumption and finds only 22 of the first 50 stratified correction candidates meet a strict unique-repair gate. The product deliberately publishes fewer tasks rather than preserving a misleading count: 236 reviewed concept choices remain active, while correction coverage falls to 22 approved tasks until revision continues. Confusion teaching stays at 8.5/10 and contextual output at 6.6/10; reliability improves, but breadth and outcome evidence do not. This is a maturity gain in epistemic discipline rather than feature volume.

`alpha.25.15` closes every first-batch revision: 18 tasks gain genuinely constraining contexts and 10 are rejected because their distinctions belong in concept comparison, not correction. Published correction coverage reaches 40 while the original 44% first-pass result remains visible. Scores stay at 8.5/10 for confusion teaching and 6.6/10 for contextual output: editorial reliability and breadth improve, but no learner outcome evidence has yet changed.

`alpha.25.16` repeats the stratified audit on another 50 candidates and reaches 100 reviewed tasks overall: 68 published after review or repair, 32 rejected and 57 still isolated. The second sample confirms that many fluent-looking substitutions are not valid correction questions. Confusion teaching remains 8.5/10 and contextual output 6.6/10; coverage and confidence in the editorial gate improve, but the product still lacks seven-day outcome evidence and broad phrase production.

`alpha.25.17` adds a distributable, reviewed layer of 100 academic phrases with balanced categories, simplified-Chinese meaning, English concepts, grammar frames, usage boundaries and original bilingual examples. Exact lookup, browsing, rich card capture and FSRS make this a complete reference-to-review loop, raising dictionary and chunk maturity modestly. It does not raise contextual output because learners still cannot complete, translate or produce these phrases in scored tasks, and no retention or transfer gain has been measured.

`alpha.25.18` closes the first active phrase-production loop: each reviewed phrase can generate cloze, Chinese-to-English and personal-sentence tasks, with persistent attempts and wrong-answer FSRS cards. This raises contextual output modestly, but deterministic form checks are intentionally weaker than semantic assessment, and personal recommendation plus seven-day transfer remain unproven.

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
