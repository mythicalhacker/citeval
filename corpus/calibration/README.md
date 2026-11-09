# Calibration reference and evaluation sets

## Original 30 cases

[graded_reference_v2.jsonl](graded_reference_v2.jsonl) records the reference grade in
`substantive_grade`, together with a rationale, evidence span, confidence and `grade_provenance`.
Of the 30 records, 27 identify a Claude Science reading and three identify a blind Claude Science
re-read. The [adjudication notes](adjudication_notes.md) identify the grader as
`claude-opus-4-8` and explain three case-level changes. Citeval also uses Opus 4.8 in its
adjudicator. These are model-generated reference grades. Human validation remains open.

The [saved predictions](graded_predictions_cal30.jsonl) include 27 graded cases, two abstentions
(Ch05 and Ce11) and one non-substantive citation (Ch15). Of 28 cases with an ordinal reference,
27 received a grade. After a grading prompt was revised using cases from this set,
16 of 27 predictions matched the reference exactly and all 27 were within one level. The offline
gate scores the committed predictions against this reference. Run `make eval` from the repository
root. The [evaluation procedure](../../docs/EVAL_SOP.md) reports the earlier and revised results.

## Separate 45-case extension

The [extension documentation](README_corpus_ext.md) distinguishes the published metadata used
to confirm retractions and establish the paper's scope from the model judgment about the citing
claim. The [extension's substantive reference](graded_reference_ext.jsonl) records 24 model reads
of full texts and 21 of abstracts.

The [45 saved objective results](results_ext_objective.jsonl) contain retraction and scope decisions.
They record 12 retractions correctly flagged and 33 cases correctly left unflagged on that axis.
The first scope checker found 5 of 17 mismatches. Those cases informed a repair, and its evaluation
on the same set found 12 of 17. See the [repair report](../../outputs/wo_c3_scope_report.md).
The revised score describes this development set.
