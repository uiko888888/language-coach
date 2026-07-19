from __future__ import annotations


CONTRASTS = (
    {
        "slug": "say-tell-speak-talk", "terms": ["say", "tell", "speak", "talk"], "title": "say / tell / speak / talk",
        "dimensions": {
            "动作方式": "say 强调说出的内容；tell 通常带听者；speak 偏说话能力或正式发言；talk 强调交谈过程。",
            "搭配": "say something, tell someone something, speak English, talk to/with someone。",
            "语域": "speak 可更正式；talk 更口语；say 和 tell 在多数日常语境中中性。",
            "立场": "四者本身通常不表达赞同或反对。",
            "强度": "差异主要在结构和互动方式，不是强弱。",
        },
        "prompt": "The researcher will ___ the participants about the change before the interview.",
        "options": ["say", "tell", "speak", "talk"], "answer_index": 1,
        "explanation": "tell 可以直接接人：tell the participants about the change。say 不能直接使用 say someone。",
    },
    {
        "slug": "see-look-watch", "terms": ["see", "look", "watch"], "title": "see / look / watch",
        "dimensions": {
            "动作方式": "see 偏自然看见；look 是主动把视线投向；watch 是持续观察变化中的对象。",
            "搭配": "see a result, look at a chart, watch a film/a process。",
            "语域": "三者都常用；observe 更正式，但不在本组答案中。",
            "立场": "通常中性。",
            "强度": "watch 比 look 更强调持续时间，see 不保证主动。",
        },
        "prompt": "We ___ the temperature change throughout the entire experiment.",
        "options": ["saw", "looked", "watched"], "answer_index": 2,
        "explanation": "throughout 强调持续观察，因此 watched 最合适；looked 还需要 at。",
    },
    {
        "slug": "remember-remind-recall", "terms": ["remember", "remind", "recall"], "title": "remember / remind / recall",
        "dimensions": {
            "动作方式": "remember 是自己记得；remind 是使别人想起；recall 是主动从记忆中提取。",
            "搭配": "remember doing, remind someone to do, recall a detail。",
            "语域": "recall 略正式，remember/remind 日常更常见。",
            "立场": "通常中性。",
            "强度": "recall 更突出检索过程，不代表记忆更深。",
        },
        "prompt": "Please ___ me to submit the ethics form tomorrow.",
        "options": ["remember", "remind", "recall"], "answer_index": 1,
        "explanation": "remind someone to do 表示提醒某人做事。remember 是说话者自己记得。",
    },
    {
        "slug": "economic-economical", "terms": ["economic", "economical"], "title": "economic / economical",
        "dimensions": {
            "动作方式": "economic 与经济体系有关；economical 表示节省金钱、时间或资源。",
            "搭配": "economic growth/policy, an economical car/method。",
            "语域": "economic 常见于学术和新闻；economical 也用于日常评价。",
            "立场": "economic 多为描述；economical 往往带正面节约评价。",
            "强度": "不是强弱差异，而是义项边界。",
        },
        "prompt": "The new heating system is more ___ because it uses less electricity.",
        "options": ["economic", "economical"], "answer_index": 1,
        "explanation": "uses less electricity 表示节省资源，应使用 economical。",
    },
    {
        "slug": "job-work-career", "terms": ["job", "work", "career"], "title": "job / work / career",
        "dimensions": {
            "动作方式": "job 是具体职位；work 是工作活动或劳动，通常不可数；career 是长期职业路径。",
            "搭配": "apply for a job, do/find work, pursue a career。",
            "语域": "三者都中性，career 更常用于长期规划。",
            "立场": "通常中性。",
            "强度": "career 时间跨度最大，job 最具体。",
        },
        "prompt": "She hopes to build a ___ in public health over the next decade.",
        "options": ["job", "work", "career"], "answer_index": 2,
        "explanation": "over the next decade 指长期职业发展，因此 career 最合适。",
    },
    {
        "slug": "big-large-great", "terms": ["big", "large", "great"], "title": "big / large / great",
        "dimensions": {
            "动作方式": "big/large 可表示尺寸或数量；great 常表示重要、优秀或程度显著。",
            "搭配": "a big decision, a large sample, a great achievement。",
            "语域": "large 在数据和正式描述中更常见；big 更口语；great 常带评价。",
            "立场": "great 常带正面评价，big/large 多为中性描述。",
            "强度": "great 的重点常是重要性或评价，不只是物理尺寸。",
        },
        "prompt": "The study used a ___ sample of more than 20,000 participants.",
        "options": ["big", "large", "great"], "answer_index": 1,
        "explanation": "正式研究语境中通常使用 a large sample。",
    },
)


def contrast_catalog(query: str = "") -> list[dict]:
    clean = str(query or "").strip().casefold()
    if not clean:
        return [dict(item) for item in CONTRASTS]
    exact = [item for item in CONTRASTS if any(term.casefold() in clean or clean in term.casefold() for term in item["terms"])]
    return [dict(item) for item in (exact or CONTRASTS)]


def contrast_by_slug(slug: str) -> dict | None:
    return next((dict(item) for item in CONTRASTS if item["slug"] == slug), None)
