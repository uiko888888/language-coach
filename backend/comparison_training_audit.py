from __future__ import annotations


# A correction task is publishable only when replacing the distractor with the
# reviewed answer repairs a genuine lexical, grammatical, or collocational error.
# Natural alternatives that merely express a different nuance remain candidates.
INITIAL_CORRECTION_AUDIT_REVIEWS: tuple[dict, ...] = (
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


INITIAL_CORRECTION_AUDIT_REVIEWS += (
    {"batch": 2, "task_id": "acquire-obtain-gain:correction:gain", "decision": "revise", "reason": "Acquire practical experience is also natural, so the context needs a fixed gain collocation."},
    {"batch": 2, "task_id": "borrow-lend:correction:borrow", "decision": "approved", "reason": "The speaker receives the charger temporarily, which requires borrow rather than lend."},
    {"batch": 2, "task_id": "bring-take-fetch:correction:take", "decision": "revise", "reason": "Fetch to the office can be interpreted as retrieving and delivering, so the direction needs a stricter frame."},
    {"batch": 2, "task_id": "common-ordinary-normal-usual:correction:normal", "decision": "approved", "reason": "Return to normal is the established frame for restored expected operation."},
    {"batch": 2, "task_id": "cordial-keen-zeal:correction:cordial", "decision": "approved", "reason": "Cordial welcome expresses formal warmth; keen does not modify welcome naturally here."},
    {"batch": 2, "task_id": "economic-economical:correction:economic", "decision": "approved", "reason": "Economic growth concerns the economy; economical means avoiding waste."},
    {"batch": 2, "task_id": "effective-efficient:correction:efficient", "decision": "revise", "reason": "Faster and effective can coexist, so the prompt needs an explicit resource-efficiency collocation."},
    {"batch": 2, "task_id": "job-work-career:correction:career", "decision": "approved", "reason": "Build a career is the established long-term professional-development frame."},
    {"batch": 2, "task_id": "look-see-watch:correction:look", "decision": "approved", "reason": "The imperative directing attention to an object requires look at."},
    {"batch": 2, "task_id": "method-approach-way:correction:method", "decision": "approved", "reason": "Mixed-method is the established research-design compound."},
    {"batch": 2, "task_id": "problem-issue-question:correction:problem", "decision": "rejected", "reason": "A serious issue and a serious problem are both natural descriptions of missing data."},
    {"batch": 2, "task_id": "purpose-goal-objective-aim:correction:goal", "decision": "rejected", "reason": "Long-term goal and long-term objective are both valid."},
    {"batch": 2, "task_id": "remember-remind:correction:remember", "decision": "approved", "reason": "Remember directly licenses the to-infinitive when the subject must retain the task."},
    {"batch": 2, "task_id": "say-tell-speak-talk:correction:speak", "decision": "revise", "reason": "Talk at a conference is possible, so the prompt needs a language-ability frame."},
    {"batch": 2, "task_id": "cite-site-sight:correction:sight", "decision": "approved", "reason": "A viewed scene is a sight; cite is a verb or reference."},
    {"batch": 2, "task_id": "compliment-complement:correction:complement", "decision": "approved", "reason": "The examples complete the explanation, requiring complement."},
    {"batch": 2, "task_id": "later-latter:correction:later", "decision": "approved", "reason": "A subsequent version is later; latter selects the second of two named items."},
    {"batch": 2, "task_id": "loose-lose:correction:lose", "decision": "approved", "reason": "May requires the base verb lose; loose is an adjective or different verb."},
    {"batch": 2, "task_id": "personal-personnel:correction:personnel", "decision": "approved", "reason": "Authorized staff as a group are personnel, not personal."},
    {"batch": 2, "task_id": "principal-principle:correction:principle", "decision": "approved", "reason": "A guiding rule is a principle; principal does not name the rule."},
    {"batch": 2, "task_id": "stationary-stationery:correction:stationary", "decision": "approved", "reason": "A vehicle not moving is stationary; stationery means writing materials."},
    {"batch": 2, "task_id": "ielts-amount-number-quantity:correction:number", "decision": "revise", "reason": "Quantity of visitors is possible in technical prose, so the prompt needs the clearly invalid amount of people."},
    {"batch": 2, "task_id": "ielts-approximately-roughly-about:correction:approximately", "decision": "rejected", "reason": "Roughly and approximately are both valid before the percentage."},
    {"batch": 2, "task_id": "ielts-average-mean-median:correction:median", "decision": "approved", "reason": "The contrast with arithmetic mean identifies the median as the distinct distribution midpoint."},
    {"batch": 2, "task_id": "ielts-difference-gap-disparity:correction:gap", "decision": "rejected", "reason": "Employment gap and employment disparity can both describe the group difference."},
    {"batch": 2, "task_id": "ielts-minimum-lowest-nadir:correction:minimum", "decision": "revise", "reason": "Lowest charge is possible, so the rule-based lower bound needs a statutory-minimum frame."},
    {"batch": 2, "task_id": "ielts-peak-maximum-high:correction:high", "decision": "approved", "reason": "Remain high is grammatical; peak requires a different frame such as at its peak."},
    {"batch": 2, "task_id": "ielts-proportion-percentage-rate-ratio:correction:proportion", "decision": "rejected", "reason": "Proportion and percentage are both valid when the share is expressed as 32 percent."},
    {"batch": 2, "task_id": "ielts-proportion-percentage-rate-ratio:correction:ratio", "decision": "approved", "reason": "A three-to-two comparison between two quantities is a ratio."},
    {"batch": 2, "task_id": "ielts-sharp-steep-dramatic:correction:sharp", "decision": "rejected", "reason": "Sharp decline and steep decline are both natural without a defined visual slope."},
    {"batch": 2, "task_id": "ielts-slight-marginal-modest:correction:marginal", "decision": "rejected", "reason": "Marginal and modest both plausibly characterize a small improvement."},
    {"batch": 2, "task_id": "ielts-stable-steady-constant:correction:constant", "decision": "rejected", "reason": "Stable at 18 percent and constant at 18 percent are both valid summaries."},
    {"batch": 2, "task_id": "ielts-total-sum-aggregate:correction:sum", "decision": "rejected", "reason": "Sum and aggregate can both name the combined value of categories."},
    {"batch": 2, "task_id": "ielts-trend-pattern-tendency:correction:tendency", "decision": "rejected", "reason": "Trend to invest and tendency to invest are both possible in this context."},
    {"batch": 2, "task_id": "ielts-advantage-benefit-merit:correction:benefit", "decision": "approved", "reason": "Benefit directly takes the people receiving an improvement; merit does not fit this beneficiary frame."},
    {"batch": 2, "task_id": "ielts-also-moreover-furthermore:correction:furthermore", "decision": "rejected", "reason": "Also and furthermore both validly add the supporting sentence, differing mainly in register."},
    {"batch": 2, "task_id": "ielts-although-despite-in-spite-of:correction:although", "decision": "approved", "reason": "The full finite clause requires although; despite takes a noun phrase or gerund."},
    {"batch": 2, "task_id": "ielts-because-because-of-due-to:correction:due to", "decision": "rejected", "reason": "Due to and because of both correctly introduce the noun-phrase cause."},
    {"batch": 2, "task_id": "ielts-believe-think-consider:correction:think", "decision": "rejected", "reason": "Consider that is valid, especially in formal British English."},
    {"batch": 2, "task_id": "ielts-choice-option-alternative:correction:option", "decision": "rejected", "reason": "Practical option and practical alternative are both natural here."},
    {"batch": 2, "task_id": "ielts-claim-argue-assert-maintain:correction:maintain", "decision": "rejected", "reason": "Claim and maintain can both introduce the authors' position without explicit challenge history."},
    {"batch": 2, "task_id": "ielts-disadvantage-drawback-limitation:correction:limitation", "decision": "rejected", "reason": "Small sample size can be both a survey limitation and a disadvantage."},
    {"batch": 2, "task_id": "ielts-false-incorrect-invalid:correction:incorrect", "decision": "rejected", "reason": "Incorrect total and invalid total can both describe an unacceptable calculated value."},
    {"batch": 2, "task_id": "ielts-freedom-liberty-independence:correction:independence", "decision": "rejected", "reason": "Transport can increase both freedom and independence for older people."},
    {"batch": 2, "task_id": "ielts-however-nevertheless-nonetheless:correction:nevertheless", "decision": "rejected", "reason": "Nonetheless and nevertheless are interchangeable in this concessive sentence."},
    {"batch": 2, "task_id": "ielts-oppose-object-resist:correction:resist", "decision": "rejected", "reason": "Firms may naturally oppose or resist adopting costly equipment."},
    {"batch": 2, "task_id": "ielts-responsibility-duty-obligation:correction:responsibility", "decision": "approved", "reason": "Take responsibility for is the fixed accountability frame."},
    {"batch": 2, "task_id": "ielts-solution-measure-remedy:correction:solution", "decision": "approved", "reason": "Solution to is the required frame; measure does not take to a problem in this construction."},
    {"batch": 2, "task_id": "ielts-true-correct-valid:correction:correct", "decision": "rejected", "reason": "A calculation can be both correct and valid while its source data are outdated."},
    {"batch": 2, "task_id": "ielts-while-whereas:correction:whereas", "decision": "rejected", "reason": "While and whereas both contrast the two transport preferences."},
)


CORRECTION_TASK_REVISIONS: dict[str, dict] = {
    "affect-effect-influence:correction:effect": {
        "decision": "approved", "prompt": "The new regulations took influence immediately.",
        "corrected_text": "The new regulations took effect immediately.",
        "reason": "The fixed phrase take effect makes effect the only valid option.",
    },
    "bring-take-fetch:correction:fetch": {
        "decision": "approved", "prompt": "Could you take the parcel from reception and return here with it?",
        "corrected_text": "Could you fetch the parcel from reception?",
        "reason": "Fetch uniquely packages going to collect something and bringing it back.",
    },
    "common-ordinary-normal-usual:correction:ordinary": {
        "decision": "approved", "prompt": "The scan found nothing out of the normal.",
        "corrected_text": "The scan found nothing out of the ordinary.",
        "reason": "Out of the ordinary is the established phrase for something unusual.",
    },
    "problem-issue-question:correction:issue": {
        "decision": "approved", "prompt": "Several residents took question with the revised boundary.",
        "corrected_text": "Several residents took issue with the revised boundary.",
        "reason": "Take issue with is the fixed frame for expressing disagreement.",
    },
    "purpose-goal-objective-aim:correction:objective": {
        "decision": "approved", "prompt": "The trial used an aim measure of sleep quality.",
        "corrected_text": "The trial used an objective measure of sleep quality.",
        "reason": "Only objective functions as the adjective meaning independently measurable.",
    },
    "ielts-approximately-roughly-about:correction:about": {
        "decision": "rejected", "reason": "No faithful numerical context makes about uniquely correct over approximately or roughly.",
    },
    "ielts-average-mean-median:correction:mean": {
        "decision": "approved", "prompt": "The researchers added all scores, divided by the number of participants, and reported the median.",
        "corrected_text": "The researchers added all scores, divided by the number of participants, and reported the mean.",
        "reason": "The calculation explicitly defines the arithmetic mean, not the median.",
    },
    "ielts-difference-gap-disparity:correction:disparity": {
        "decision": "rejected", "reason": "Difference, gap and disparity require evaluative context rather than a uniquely repairable sentence.",
    },
    "ielts-minimum-lowest-nadir:correction:nadir": {
        "decision": "rejected", "reason": "Minimum and nadir can both denote the same low point in a natural sentence.",
    },
    "ielts-overall-generally-on-the-whole:correction:overall": {
        "decision": "approved", "prompt": "The generally trend was upward despite two brief declines.",
        "corrected_text": "The overall trend was upward despite two brief declines.",
        "reason": "Overall is the only option that can directly modify the noun trend.",
    },
    "ielts-proportion-percentage-rate-ratio:correction:percentage": {
        "decision": "approved", "prompt": "The employment rate rose by five rate points.",
        "corrected_text": "The employment rate rose by five percentage points.",
        "reason": "Percentage point is the required unit for an absolute difference between percentages.",
    },
    "ielts-reach-hit-attain:correction:hit": {
        "decision": "approved", "prompt": "Monthly sales reach a record high last December.",
        "corrected_text": "Monthly sales hit a record high last December.",
        "reason": "Hit supplies the required past form without inflection and preserves the record-high collocation.",
    },
    "ielts-sharp-steep-dramatic:correction:dramatic": {
        "decision": "rejected", "reason": "Sharp and dramatic can both naturally characterize a major shift without an external magnitude rule.",
    },
    "ielts-slight-marginal-modest:correction:modest": {
        "decision": "rejected", "reason": "Slight, marginal and modest depend on a domain-specific comparison baseline.",
    },
    "ielts-stable-steady-constant:correction:stable": {
        "decision": "rejected", "reason": "Stable and steady overlap too strongly in chart descriptions for a strict correction item.",
    },
    "ielts-trend-pattern-tendency:correction:trend": {
        "decision": "rejected", "reason": "A downward trend and downward pattern can both be valid summaries of time-series data.",
    },
    "ielts-advantage-benefit-merit:correction:advantage": {
        "decision": "approved", "prompt": "Rail has a benefit over air travel in city-centre access.",
        "corrected_text": "Rail has an advantage over air travel in city-centre access.",
        "reason": "Have an advantage over is the comparative frame required by the second option.",
    },
    "ielts-also-moreover-furthermore:correction:also": {
        "decision": "approved", "prompt": "The policy not only cuts emissions but moreover lowers household bills.",
        "corrected_text": "The policy not only cuts emissions but also lowers household bills.",
        "reason": "The correlative construction requires not only ... but also.",
    },
    "ielts-although-despite-in-spite-of:correction:despite": {
        "decision": "rejected", "reason": "Despite and in spite of share the same complement and cannot be separated by correction alone.",
    },
    "ielts-because-because-of-due-to:correction:because of": {
        "decision": "rejected", "reason": "Because of and due to are both accepted before the relevant noun phrase.",
    },
    "ielts-choice-option-alternative:correction:choice": {
        "decision": "approved", "prompt": "After reviewing both offers, she made an option.",
        "corrected_text": "After reviewing both offers, she made a choice.",
        "reason": "Make a choice is the established decision frame; make an option is not idiomatic.",
    },
    "ielts-example-instance-illustration:correction:example": {
        "decision": "approved", "prompt": "Senior staff should set an instance for new employees.",
        "corrected_text": "Senior staff should set an example for new employees.",
        "reason": "Set an example is the fixed expression for providing a model to follow.",
    },
    "ielts-false-incorrect-invalid:correction:false": {
        "decision": "approved", "prompt": "Smoke from the kitchen triggered an incorrect alarm.",
        "corrected_text": "Smoke from the kitchen triggered a false alarm.",
        "reason": "False alarm is the fixed collocation for a warning without the expected danger.",
    },
    "ielts-freedom-liberty-independence:correction:freedom": {
        "decision": "approved", "prompt": "The journalist filed a Liberty of Information request.",
        "corrected_text": "The journalist filed a Freedom of Information request.",
        "reason": "Freedom of Information is the established institutional name.",
    },
    "ielts-however-nevertheless-nonetheless:correction:nonetheless": {
        "decision": "rejected", "reason": "Nonetheless and nevertheless remain interchangeable in the intended concessive function.",
    },
    "ielts-solution-measure-remedy:correction:remedy": {
        "decision": "approved", "prompt": "The claimant had no adequate solution at law.",
        "corrected_text": "The claimant had no adequate remedy at law.",
        "reason": "Remedy at law is the established legal frame for available judicial relief.",
    },
    "ielts-true-correct-valid:correction:true": {
        "decision": "approved", "prompt": "Her ambition to study abroad finally came correct.",
        "corrected_text": "Her ambition to study abroad finally came true.",
        "reason": "Come true is the fixed frame for a hope or ambition becoming reality.",
    },
    "ielts-while-whereas:correction:while": {
        "decision": "approved", "prompt": "Whereas the survey was running, interviewers logged each refusal.",
        "corrected_text": "While the survey was running, interviewers logged each refusal.",
        "reason": "Only while expresses the simultaneous time relationship intended here.",
    },
    "acquire-obtain-gain:correction:gain": {
        "decision": "approved", "prompt": "The new diet caused several participants to obtain weight.",
        "corrected_text": "The new diet caused several participants to gain weight.",
        "reason": "Gain weight is the established collocation for an increase in body mass.",
    },
    "bring-take-fetch:correction:take": {
        "decision": "approved", "prompt": "Please fetch these files with you when you leave for the office.",
        "corrected_text": "Please take these files with you when you leave for the office.",
        "reason": "Take with you expresses movement away with the person; fetch implies retrieval and return.",
    },
    "effective-efficient:correction:efficient": {
        "decision": "approved", "prompt": "The laboratory installed an energy-effective cooling system.",
        "corrected_text": "The laboratory installed an energy-efficient cooling system.",
        "reason": "Energy-efficient is the established resource-use compound.",
    },
    "say-tell-speak-talk:correction:speak": {
        "decision": "approved", "prompt": "She can talk three languages fluently.",
        "corrected_text": "She can speak three languages fluently.",
        "reason": "Speak is the verb used for ability in a language.",
    },
    "ielts-amount-number-quantity:correction:number": {
        "decision": "approved", "prompt": "The amount of international visitors exceeded two million.",
        "corrected_text": "The number of international visitors exceeded two million.",
        "reason": "Countable visitors require number rather than amount.",
    },
    "ielts-minimum-lowest-nadir:correction:minimum": {
        "decision": "approved", "prompt": "The regulation establishes a statutory lowest of twelve dollars.",
        "corrected_text": "The regulation establishes a statutory minimum of twelve dollars.",
        "reason": "Statutory minimum is the legal lower-bound frame; lowest cannot fill the noun slot here.",
    },
}


def _current_review(review: dict) -> dict:
    revision = CORRECTION_TASK_REVISIONS.get(review["task_id"])
    if not revision:
        return {"batch": review.get("batch", 1), **review}
    return {
        "batch": review.get("batch", 1), **review,
        "initial_decision": review["decision"],
        "decision": revision["decision"],
        "reason": revision["reason"],
    }


CORRECTION_AUDIT_REVIEWS = tuple(_current_review(review) for review in INITIAL_CORRECTION_AUDIT_REVIEWS)
CORRECTION_AUDIT_BY_TASK = {review["task_id"]: review for review in CORRECTION_AUDIT_REVIEWS}


def correction_audit_summary(candidate_ids: set[str] | None = None) -> dict:
    reviews = CORRECTION_AUDIT_REVIEWS
    if candidate_ids is not None:
        reviews = tuple(review for review in reviews if review["task_id"] in candidate_ids)
    approved = sum(review["decision"] == "approved" for review in reviews)
    revise = sum(review["decision"] == "revise" for review in reviews)
    rejected = sum(review["decision"] == "rejected" for review in reviews)
    rewritten = sum(review.get("initial_decision") == "revise" and review["decision"] == "approved" for review in reviews)
    return {
        "reviewed": len(reviews), "approved": approved, "revise": revise,
        "rejected": rejected, "rewritten": rewritten,
    }
