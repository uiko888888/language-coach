# Exam Question Research

This document records question structures to study. It does not authorize copying commercial or copyrighted question text.

## Source policy

- Use official public sample questions to understand format, instructions, answer rules, timing, and scoring.
- Use openly licensed datasets only when their question and passage licenses are explicit.
- Store imported source URL, license, exam family, section, question type, answer, evidence, and explanation metadata.
- Generated questions must be labelled as simulations and must not imitate an official question by superficial word replacement.

## Official structures

### IELTS Reading

Reference: <https://ielts.org/take-a-test/preparation-resources/sample-test-questions>

- True / False / Not Given and Yes / No / Not Given
- Matching headings, information, features, and sentence endings
- Sentence, summary, note, table, flow-chart, and diagram completion
- Multiple choice and short answer

Required validation: exact evidence span, contradiction versus absence distinction, word-limit enforcement, and heading coverage.

### TOEFL iBT Reading

Reference: <https://www.ets.org/toefl/test-takers/ibt/prepare/toefl-testready.html>

- Factual and negative factual information
- Inference and rhetorical purpose
- Vocabulary in context
- Sentence simplification and text insertion
- Prose summary and category completion

Required validation: paragraph reference, essential-information preservation, discourse relation, and multi-point summary coverage.

### CET-4 and CET-6

Reference: <https://cet.neea.edu.cn/>

- Banked cloze
- Long-passage information matching
- Careful reading multiple choice

Required validation: word-form compatibility, section-to-statement evidence, and distractors drawn from neighboring sections rather than unrelated text.

### Chinese Postgraduate Entrance English

Reference: <https://yz.chsi.com.cn/>

- Cloze with discourse and collocation constraints
- Traditional reading comprehension
- New question types such as headings, ordering, and paragraph matching
- English-to-Chinese sentence translation

Required validation: author stance, long-sentence logical structure, cross-paragraph coherence, and translation scoring points.

## Open dataset candidates

- RACE: exam-style reading comprehension research corpus. License and redistribution terms must be reviewed before import.
- ReClor: logical reading comprehension. Use only after confirming dataset terms and passage redistribution rights.
- SciQ: science multiple-choice questions under an open dataset license; useful for distractor and evidence-validator experiments, not as an IELTS or TOEFL substitute.

## Implementation order

1. IELTS True / False / Not Given with contradiction and absence validation.
2. IELTS heading matching and summary completion.
3. TOEFL factual, inference, vocabulary, and sentence simplification.
4. CET banked cloze, information matching, and careful reading.
5. Postgraduate entrance reading, author attitude, long-sentence interpretation, and cloze.
6. TEM, GRE, and GMAT after the shared evidence and distractor validators are stable.

## Model strategy

The current rule generator is the baseline. A future model pipeline should generate structured candidates, run deterministic validators, record rejection reasons, and collect human ratings. Fine-tuning starts only after enough licensed, validated examples exist.
