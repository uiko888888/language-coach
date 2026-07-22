from __future__ import annotations


# A correction task is publishable only when replacing the distractor with the
# reviewed answer repairs a genuine lexical, grammatical, or collocational error.
# Natural alternatives that merely express a different nuance remain candidates.
CORRECTION_AUDIT_REVIEWS: tuple[dict, ...] = (
    {"task_id": "acquire-obtain-gain:correction:acquire", "decision": "approved", "reason": "Acquire is the established verb for vocabulary developing through exposure."},
    {"task_id": "affect-effect-influence:correction:effect", "decision": "revise", "reason": "Influence and effect are both natural nouns in this sentence."},
    {"task_id": "bring-take-fetch:correction:fetch", "decision": "revise", "reason": "Bring can be correct when the destination is the speaker's location."},
    {"task_id": "common-ordinary-normal-usual:correction:ordinary", "decision": "revise", "reason": "Normal and ordinary are both plausible descriptions of the device."},
    {"task_id": "compose-comprise-constitute-consist-of:correction:constitute", "decision": "approved", "reason": "A part cannot consist of a fraction of the whole in this structure."},
    {"task_id": "cordial-keen-zeal:correction:zeal", "decision": "approved", "reason": "Cordial is not a noun and cannot follow with remarkable here."},
    {"task_id": "effective-efficient:correction:effective", "decision": "approved", "reason": "Effective against is the required result-focused collocation."},
    {"task_id": "job-work-career:correction:job", "decision": "approved", "reason": "Countable a job is required after applied for in this context."},
    {"task_id": "look-see-watch:correction:see", "decision": "approved", "reason": "See expresses noticing smoke; watch requires sustained attention."},
    {"task_id": "possible-probable-likely:correction:likely", "decision": "approved", "reason": "A person subject followed by to-infinitive selects likely, not possible."},
    {"task_id": "problem-issue-question:correction:issue", "decision": "revise", "reason": "The question of unequal access is also natural and meaningful."},
    {"task_id": "purpose-goal-objective-aim:correction:objective", "decision": "revise", "reason": "Aim and objective are both natural for a first research goal."},
    {"task_id": "remember-remind:correction:remind", "decision": "approved", "reason": "Remind licenses the person plus to-infinitive frame."},
    {"task_id": "say-tell-speak-talk:correction:tell", "decision": "approved", "reason": "Tell directly licenses the recipient before the embedded question."},
    {"task_id": "advice-advise:correction:advice", "decision": "approved", "reason": "The noun advice is required after useful; advise is a verb."},
    {"task_id": "conscience-conscious:correction:conscience", "decision": "approved", "reason": "Matter of conscience requires the moral-judgment noun."},
    {"task_id": "device-devise:correction:device", "decision": "approved", "reason": "The subject is a recording instrument, requiring the noun device."},
    {"task_id": "loose-lose:correction:loose", "decision": "approved", "reason": "The attributive adjective loose is required before cable."},
    {"task_id": "precede-proceed:correction:precede", "decision": "approved", "reason": "Precede is transitive and means occur before; proceed does not fit."},
    {"task_id": "quiet-quite:correction:quiet", "decision": "approved", "reason": "The adjective quiet is required after is; quite is an adverb."},
    {"task_id": "stationary-stationery:correction:stationery", "decision": "approved", "reason": "Office writing materials are stationery, not stationary."},
    {"task_id": "ielts-amount-number-quantity:correction:amount", "decision": "approved", "reason": "Electricity is uncountable and rejects number of in this use."},
    {"task_id": "ielts-approximately-roughly-about:correction:about", "decision": "revise", "reason": "Approximately and about are both valid before 500 units."},
    {"task_id": "ielts-average-mean-median:correction:mean", "decision": "revise", "reason": "Mean and median are both possible statistics without source data."},
    {"task_id": "ielts-difference-gap-disparity:correction:disparity", "decision": "revise", "reason": "Difference and disparity are both natural; the distinction is evaluative."},
    {"task_id": "ielts-minimum-lowest-nadir:correction:nadir", "decision": "revise", "reason": "Minimum and nadir can both describe the confidence low point."},
    {"task_id": "ielts-overall-generally-on-the-whole:correction:overall", "decision": "revise", "reason": "Generally and overall both introduce this broad summary."},
    {"task_id": "ielts-proportion-percentage-rate-ratio:correction:percentage", "decision": "revise", "reason": "Employment rate is a valid interpretation of the 74 percent figure."},
    {"task_id": "ielts-reach-hit-attain:correction:hit", "decision": "revise", "reason": "Attain a record high is grammatical, though less direct than hit."},
    {"task_id": "ielts-sharp-steep-dramatic:correction:dramatic", "decision": "revise", "reason": "Sharp and dramatic are both natural descriptions of the shift."},
    {"task_id": "ielts-slight-marginal-modest:correction:modest", "decision": "revise", "reason": "Whether six percent is slight or modest requires a comparison baseline."},
    {"task_id": "ielts-stable-steady-constant:correction:stable", "decision": "revise", "reason": "Steady and stable are both natural with remained around five percent."},
    {"task_id": "ielts-total-sum-aggregate:correction:total", "decision": "approved", "reason": "A total of applications is the standard count frame; a sum is for quantities being added."},
    {"task_id": "ielts-trend-pattern-tendency:correction:trend", "decision": "revise", "reason": "A downward pattern and a downward trend are both defensible readings."},
    {"task_id": "ielts-advantage-benefit-merit:correction:advantage", "decision": "revise", "reason": "Lower energy use can be both a benefit and a comparative advantage."},
    {"task_id": "ielts-also-moreover-furthermore:correction:also", "decision": "revise", "reason": "Moreover is formal but grammatical in medial position here."},
    {"task_id": "ielts-although-despite-in-spite-of:correction:despite", "decision": "revise", "reason": "Despite and in spite of take the same complement and are interchangeable here."},
    {"task_id": "ielts-because-because-of-due-to:correction:because of", "decision": "revise", "reason": "Because of and due to are both accepted with the noun phrase here."},
    {"task_id": "ielts-believe-think-consider:correction:consider", "decision": "approved", "reason": "Consider licenses the gerund complement; believe does not in this frame."},
    {"task_id": "ielts-choice-option-alternative:correction:choice", "decision": "revise", "reason": "A genuine option between providers is natural English."},
    {"task_id": "ielts-disadvantage-drawback-limitation:correction:disadvantage", "decision": "approved", "reason": "At a disadvantage is the fixed frame; at a drawback is not idiomatic."},
    {"task_id": "ielts-example-instance-illustration:correction:example", "decision": "revise", "reason": "For example and for instance are interchangeable in this sentence."},
    {"task_id": "ielts-false-incorrect-invalid:correction:false", "decision": "revise", "reason": "False and incorrect can both reject this factual claim."},
    {"task_id": "ielts-freedom-liberty-independence:correction:freedom", "decision": "revise", "reason": "Freedom and liberty are both possible, with register rather than correctness separating them."},
    {"task_id": "ielts-however-nevertheless-nonetheless:correction:nonetheless", "decision": "revise", "reason": "Nevertheless is equally valid after but in this frame."},
    {"task_id": "ielts-responsibility-duty-obligation:correction:duty", "decision": "approved", "reason": "The unchanged article a makes duty the only grammatical option."},
    {"task_id": "ielts-right-entitlement-permission:correction:entitlement", "decision": "approved", "reason": "An entitlement to a benefit is the grammatical institutional frame."},
    {"task_id": "ielts-solution-measure-remedy:correction:remedy", "decision": "revise", "reason": "Solution and remedy are both natural for addressing inequality."},
    {"task_id": "ielts-true-correct-valid:correction:true", "decision": "revise", "reason": "It is correct that is less common but remains grammatical and meaningful."},
    {"task_id": "ielts-while-whereas:correction:while", "decision": "revise", "reason": "While and whereas both express the intended contrast."},
)


CORRECTION_AUDIT_BY_TASK = {review["task_id"]: review for review in CORRECTION_AUDIT_REVIEWS}


def correction_audit_summary(candidate_ids: set[str] | None = None) -> dict:
    reviews = CORRECTION_AUDIT_REVIEWS
    if candidate_ids is not None:
        reviews = tuple(review for review in reviews if review["task_id"] in candidate_ids)
    approved = sum(review["decision"] == "approved" for review in reviews)
    revise = sum(review["decision"] == "revise" for review in reviews)
    return {"reviewed": len(reviews), "approved": approved, "revise": revise}
