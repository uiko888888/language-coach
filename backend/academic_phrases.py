from __future__ import annotations

import re


SOURCE = {
    "key": "language-coach-academic-phrases-v1",
    "name": "Language Coach 学术词组编辑集",
    "version": "2026.07-v1",
    "attribution": "常见表达经本地编辑整理；双语例句为项目原创",
    "copyright_status": "通用短语与原创例句，不复制商业词典正文",
}

CATEGORY_META = {
    "evidence": ("证据与研究", "present or connect evidence in academic reasoning", ("IELTS", "TOEFL", "考研")),
    "cause": ("因果与影响", "describe causes, consequences, risks, or influence", ("IELTS", "TOEFL", "考研")),
    "comparison": ("比较与关系", "compare entities or specify the dimension of a relationship", ("IELTS", "TOEFL", "考研")),
    "data": ("数据与趋势", "report quantities, movement, and time-series patterns precisely", ("IELTS", "TOEFL")),
    "stance": ("论证与立场", "state, qualify, or frame an academic position", ("IELTS", "TOEFL", "考研")),
    "limitations": ("限制与审慎", "mark uncertainty, limitations, and boundaries of interpretation", ("IELTS", "TOEFL", "考研")),
    "method": ("方法与过程", "describe research design, data collection, and analytical procedure", ("IELTS", "TOEFL", "研究生")),
    "structure": ("篇章组织", "organize sections, findings, references, and conclusions", ("IELTS", "TOEFL", "考研")),
    "policy": ("政策与方案", "describe policy action, responsibility, access, and resource decisions", ("IELTS", "TOEFL", "考研")),
    "learning": ("学习与应用", "describe knowledge building, engagement, and practical application", ("TOEFL", "考研", "研究生")),
}


# phrase, Chinese meaning, grammar frame, English example, Chinese example
RAW_PHRASES = {
    "evidence": (
        ("provide evidence for", "为……提供证据", "provide evidence for + noun", "The survey provides evidence for a link between sleep and concentration.", "该调查为睡眠与专注力之间的联系提供了证据。"),
        ("support the claim that", "支持……这一主张", "support the claim that + clause", "The results support the claim that early feedback improves revision.", "结果支持早期反馈能够改善修改这一主张。"),
        ("draw on evidence from", "利用来自……的证据", "draw on evidence from + source", "The report draws on evidence from three national datasets.", "该报告利用了三个全国性数据集的证据。"),
        ("be based on", "以……为依据", "be based on + noun", "The recommendation is based on interviews with local residents.", "该建议以对当地居民的访谈为依据。"),
        ("be consistent with", "与……一致", "be consistent with + noun", "These findings are consistent with previous research on memory.", "这些发现与先前关于记忆的研究一致。"),
        ("be associated with", "与……相关", "be associated with + noun", "Regular exercise is associated with lower stress levels.", "规律运动与较低的压力水平相关。"),
        ("account for", "解释；占据", "account for + noun or percentage", "Income differences account for part of the variation in outcomes.", "收入差异解释了结果变化的一部分。"),
        ("contribute to", "促成；有助于", "contribute to + noun or gerund", "Clear instructions contribute to reducing avoidable errors.", "清晰的说明有助于减少可避免的错误。"),
        ("result in", "导致……结果", "result in + noun or gerund", "A delayed response can result in higher repair costs.", "延迟响应可能导致更高的维修成本。"),
        ("lead to", "引起；导致", "lead to + noun or gerund", "Limited access to childcare may lead to lower employment rates.", "托育服务不足可能导致较低的就业率。"),
    ),
    "cause": (
        ("have an impact on", "对……产生影响", "have an impact on + noun", "Transport costs have an impact on household spending.", "交通成本会影响家庭支出。"),
        ("play a role in", "在……中发挥作用", "play a role in + noun or gerund", "Trust plays a role in encouraging public participation.", "信任在鼓励公众参与方面发挥作用。"),
        ("give rise to", "引起；造成", "give rise to + noun", "Rapid expansion may give rise to new safety concerns.", "快速扩张可能引发新的安全问题。"),
        ("stem from", "源于……", "stem from + noun", "The disagreement stems from different definitions of fairness.", "这一分歧源于对公平的不同定义。"),
        ("arise from", "由……产生", "arise from + noun", "Most delays arise from incomplete application forms.", "大多数延误由申请表不完整造成。"),
        ("be attributed to", "被归因于……", "be attributed to + noun", "The decline was attributed to weaker overseas demand.", "这一下降被归因于海外需求减弱。"),
        ("have implications for", "对……具有影响或启示", "have implications for + noun", "The findings have implications for teacher training.", "这些发现对教师培训具有启示。"),
        ("pose a risk to", "对……构成风险", "pose a risk to + noun", "Unverified data pose a risk to sound decision-making.", "未经核实的数据会对可靠决策构成风险。"),
        ("bring about", "带来；促成", "bring about + change or result", "The reform brought about a gradual change in hiring practice.", "这项改革逐步改变了招聘惯例。"),
        ("exert pressure on", "对……施加压力", "exert pressure on + noun", "Population growth exerts pressure on urban housing.", "人口增长给城市住房带来压力。"),
    ),
    "comparison": (
        ("in contrast to", "与……形成对比", "in contrast to + noun", "In contrast to the control group, participants received weekly feedback.", "与对照组不同，参与者每周都会收到反馈。"),
        ("compared with", "与……相比", "compared with + noun", "Compared with 2019, online enrolment doubled in 2025.", "与2019年相比，2025年的在线注册人数翻了一番。"),
        ("differ from", "不同于……", "differ from + noun + in + dimension", "The two regions differ from each other in population density.", "这两个地区在人口密度方面彼此不同。"),
        ("be similar to", "与……相似", "be similar to + noun", "The second pattern is similar to the trend observed in Canada.", "第二种模式与加拿大观察到的趋势相似。"),
        ("in relation to", "关于；相对于", "in relation to + noun", "Costs were examined in relation to household income.", "研究结合家庭收入考察了成本。"),
        ("with respect to", "就……而言", "with respect to + noun", "The groups were comparable with respect to age and education.", "两组在年龄和教育程度方面具有可比性。"),
        ("in terms of", "在……方面", "in terms of + noun", "The programme performed well in terms of learner retention.", "该项目在学习者留存方面表现良好。"),
        ("on the other hand", "另一方面", "sentence; on the other hand, sentence", "Private cars are convenient; on the other hand, they increase congestion.", "私家车很方便；另一方面，它们会加剧拥堵。"),
        ("by comparison", "相比之下", "sentence. By comparison, sentence", "Urban demand rose quickly. By comparison, rural demand remained stable.", "城市需求迅速上升。相比之下，农村需求保持稳定。"),
        ("as opposed to", "而不是；相对于", "as opposed to + noun or gerund", "The study measures actual use as opposed to stated preference.", "该研究衡量的是实际使用情况，而不是口头偏好。"),
    ),
    "data": (
        ("show an increase in", "显示……有所增加", "show an increase in + noun", "The chart shows an increase in renewable energy use.", "图表显示可再生能源使用量有所增加。"),
        ("remain stable at", "稳定在……", "remain stable at + value", "The unemployment rate remained stable at about five percent.", "失业率稳定在约5%。"),
        ("reach a peak of", "达到……的峰值", "reach a peak of + value", "Monthly demand reached a peak of 8,400 units in July.", "月度需求在7月达到8400件的峰值。"),
        ("fall to a low of", "降至……的低点", "fall to a low of + value", "Attendance fell to a low of 62 percent in winter.", "冬季出勤率降至62%的低点。"),
        ("fluctuate between", "在……之间波动", "fluctuate between + value + and + value", "Prices fluctuated between 40 and 55 dollars throughout the year.", "全年价格在40至55美元之间波动。"),
        ("represent a proportion of", "占……的一部分", "represent a proportion of + whole", "Part-time workers represent a proportion of the total workforce.", "兼职员工占总劳动力的一部分。"),
        ("make up", "构成；占据", "make up + percentage + of + whole", "International students make up 28 percent of the cohort.", "国际学生占该年级的28%。"),
        ("stand at", "数值为；处于", "stand at + value", "The final figure stood at 1.6 million households.", "最终数字为160万户。"),
        ("be projected to", "预计将……", "be projected to + verb", "Demand is projected to grow by 12 percent next year.", "预计明年需求将增长12%。"),
        ("over the period", "在该时期内", "verb + over the period", "Average waiting time declined steadily over the period.", "平均等待时间在该时期内稳步下降。"),
    ),
    "stance": (
        ("it can be argued that", "可以认为……", "it can be argued that + clause", "It can be argued that public space benefits the whole community.", "可以认为公共空间使整个社区受益。"),
        ("there is evidence that", "有证据表明……", "there is evidence that + clause", "There is evidence that shorter forms improve response rates.", "有证据表明较短的表格能提高回复率。"),
        ("it is important to", "……很重要", "it is important to + verb", "It is important to distinguish correlation from causation.", "区分相关关系和因果关系很重要。"),
        ("it should be noted that", "应当注意……", "it should be noted that + clause", "It should be noted that the sample excludes temporary workers.", "应当注意，样本不包括临时工。"),
        ("a key point is that", "一个关键点是……", "a key point is that + clause", "A key point is that access alone does not guarantee participation.", "一个关键点是，仅有使用渠道并不能保证参与。"),
        ("from this perspective", "从这个角度来看", "from this perspective, + clause", "From this perspective, prevention is more efficient than repair.", "从这个角度来看，预防比修复更高效。"),
        ("to some extent", "在某种程度上", "clause + to some extent", "The two explanations overlap to some extent.", "这两种解释在某种程度上有所重叠。"),
        ("in many cases", "在许多情况下", "in many cases, + clause", "In many cases, users need guidance rather than more options.", "在许多情况下，用户需要的是指导，而不是更多选项。"),
        ("in practice", "在实践中", "in practice, + clause", "In practice, the rule is difficult to enforce consistently.", "在实践中，这项规则很难得到一致执行。"),
        ("in principle", "原则上", "in principle, + clause", "In principle, all applicants have equal access to support.", "原则上，所有申请者都能平等获得支持。"),
    ),
    "limitations": (
        ("a limitation of", "……的一个局限", "a limitation of + noun + is + noun", "A limitation of the survey is its small rural sample.", "该调查的一个局限是农村样本较小。"),
        ("be subject to", "受……影响或约束", "be subject to + noun", "Self-reported measures are subject to recall bias.", "自报测量会受到回忆偏差的影响。"),
        ("fail to account for", "未能考虑……", "fail to account for + noun", "The model fails to account for seasonal migration.", "该模型未能考虑季节性迁移。"),
        ("be interpreted with caution", "应谨慎解释", "result + should be interpreted with caution", "The regional estimate should be interpreted with caution.", "这一地区估计值应谨慎解释。"),
        ("beyond the scope of", "超出……的范围", "beyond the scope of + study or report", "Long-term health effects are beyond the scope of this study.", "长期健康影响超出了本研究的范围。"),
        ("raise questions about", "引发对……的疑问", "raise questions about + noun", "The missing records raise questions about data completeness.", "缺失记录引发了对数据完整性的疑问。"),
        ("remain unclear", "仍不清楚", "it remains unclear whether + clause", "It remains unclear whether the effect lasts beyond one year.", "这种影响能否持续一年以上仍不清楚。"),
        ("cannot be ruled out", "不能排除", "noun + cannot be ruled out", "A selection effect cannot be ruled out.", "不能排除选择效应。"),
        ("there is little evidence for", "几乎没有证据支持……", "there is little evidence for + noun", "There is little evidence for a permanent decline in demand.", "几乎没有证据支持需求出现永久性下降。"),
        ("be difficult to determine", "难以确定", "noun + be difficult to determine", "The direction of causality is difficult to determine.", "因果关系的方向难以确定。"),
    ),
    "method": (
        ("carry out a study", "开展一项研究", "carry out a study on + topic", "The team carried out a study on commuter behaviour.", "该团队开展了一项关于通勤行为的研究。"),
        ("conduct an analysis", "进行分析", "conduct an analysis of + data", "Researchers conducted an analysis of hospital waiting times.", "研究人员分析了医院等待时间。"),
        ("collect data from", "从……收集数据", "collect data from + source", "The project collected data from 320 secondary-school students.", "该项目从320名中学生处收集了数据。"),
        ("draw a sample from", "从……抽取样本", "draw a sample from + population", "The researchers drew a sample from the national register.", "研究人员从全国登记系统中抽取了样本。"),
        ("control for", "控制……变量", "control for + variable", "The regression controls for age, income, and education.", "该回归分析控制了年龄、收入和教育程度。"),
        ("measure the effect of", "测量……的影响", "measure the effect of + noun + on + noun", "The experiment measures the effect of noise on recall.", "该实验测量噪声对回忆的影响。"),
        ("test the hypothesis that", "检验……假设", "test the hypothesis that + clause", "The study tests the hypothesis that reminders improve attendance.", "该研究检验提醒能够提高出勤率这一假设。"),
        ("adopt an approach to", "采用……的方法", "adopt an approach to + noun or gerund", "The council adopted an approach to funding based on local need.", "委员会采用了以当地需求为基础的资助方法。"),
        ("use a combination of", "结合使用……", "use a combination of + plural nouns", "The evaluation uses a combination of interviews and administrative data.", "该评估结合使用访谈和行政数据。"),
        ("focus on", "聚焦于……", "focus on + noun or gerund", "The second phase focuses on improving access in rural areas.", "第二阶段聚焦于改善农村地区的服务可及性。"),
    ),
    "structure": (
        ("the purpose of this study is to", "本研究旨在……", "the purpose of this study is to + verb", "The purpose of this study is to compare two feedback methods.", "本研究旨在比较两种反馈方法。"),
        ("this section examines", "本节考察……", "this section examines + noun", "This section examines the costs of delayed maintenance.", "本节考察延迟维护的成本。"),
        ("the results indicate that", "结果表明……", "the results indicate that + clause", "The results indicate that travel time affects participation.", "结果表明出行时间会影响参与度。"),
        ("the findings suggest that", "研究发现提示……", "the findings suggest that + clause", "The findings suggest that flexible scheduling improves retention.", "研究发现提示弹性安排能够提高留存率。"),
        ("as shown in", "如……所示", "as shown in + figure or table", "As shown in Figure 2, demand rises sharply after May.", "如图2所示，需求在5月后急剧上升。"),
        ("as discussed above", "如上文所述", "as discussed above, + clause", "As discussed above, the measure excludes informal work.", "如上文所述，该指标不包括非正规工作。"),
        ("with regard to", "关于；就……而言", "with regard to + noun", "With regard to cost, the two systems perform similarly.", "就成本而言，这两个系统表现相近。"),
        ("in addition to", "除……之外还", "in addition to + noun or gerund", "In addition to reducing cost, the change improved reliability.", "这项变化除了降低成本，还提高了可靠性。"),
        ("for example", "例如", "claim; for example, instance", "Several services improved; for example, waiting times fell by 20 percent.", "多项服务有所改善；例如，等待时间下降了20%。"),
        ("in conclusion", "总之；最后", "in conclusion, + summary", "In conclusion, early intervention offers the most reliable benefit.", "总之，早期干预能带来最可靠的收益。"),
    ),
    "policy": (
        ("address the issue of", "处理……问题", "address the issue of + noun", "The proposal addresses the issue of unequal digital access.", "该提案处理数字接入不平等的问题。"),
        ("take measures to", "采取措施以……", "take measures to + verb", "Local authorities took measures to improve road safety.", "地方政府采取措施改善道路安全。"),
        ("meet the needs of", "满足……的需求", "meet the needs of + group", "The service must meet the needs of older residents.", "该服务必须满足老年居民的需求。"),
        ("ensure access to", "确保能够获得……", "ensure access to + service or resource", "The policy aims to ensure access to affordable childcare.", "该政策旨在确保人们能够获得负担得起的托育服务。"),
        ("place emphasis on", "重视；强调", "place emphasis on + noun or gerund", "The strategy places emphasis on prevention and early support.", "该战略重视预防和早期支持。"),
        ("allocate resources to", "向……分配资源", "allocate resources to + noun", "The council allocated resources to neighbourhood health centres.", "委员会向社区卫生中心分配了资源。"),
        ("be responsible for", "负责……", "be responsible for + noun or gerund", "Employers are responsible for providing safe equipment.", "雇主负责提供安全设备。"),
        ("comply with", "遵守……", "comply with + rule or standard", "All providers must comply with national safety standards.", "所有服务提供者都必须遵守国家安全标准。"),
        ("take into account", "把……考虑在内", "take + noun + into account", "The formula takes regional price differences into account.", "该公式把地区价格差异考虑在内。"),
        ("strike a balance between", "在……之间取得平衡", "strike a balance between + noun + and + noun", "Regulators must strike a balance between innovation and safety.", "监管者必须在创新与安全之间取得平衡。"),
    ),
    "learning": (
        ("develop an understanding of", "形成对……的理解", "develop an understanding of + noun", "Students develop an understanding of how evidence supports an argument.", "学生逐步理解证据如何支撑论点。"),
        ("gain insight into", "深入了解……", "gain insight into + noun", "Interviews help researchers gain insight into user frustration.", "访谈帮助研究人员深入了解用户的挫败感。"),
        ("apply knowledge to", "把知识应用于……", "apply knowledge to + noun", "Learners apply knowledge to unfamiliar case studies.", "学习者把知识应用于不熟悉的案例研究。"),
        ("engage in", "参与；从事", "engage in + noun or gerund", "Participants engage in weekly discussion and peer review.", "参与者每周参加讨论和同伴评审。"),
        ("build on", "以……为基础继续发展", "build on + prior work or knowledge", "The advanced course builds on skills developed in the first term.", "高级课程以第一学期培养的技能为基础。"),
        ("make use of", "利用……", "make use of + resource", "Writers should make use of feedback during revision.", "写作者应在修改时利用反馈。"),
        ("keep track of", "持续记录；跟踪", "keep track of + noun", "Learners keep track of recurring errors in a review log.", "学习者在复习日志中跟踪反复出现的错误。"),
        ("be exposed to", "接触到……", "be exposed to + language or experience", "Students are exposed to several academic writing styles.", "学生会接触到多种学术写作风格。"),
        ("make progress in", "在……方面取得进步", "make progress in + noun or gerund", "Regular retrieval helps learners make progress in vocabulary use.", "规律提取练习帮助学习者在词汇使用方面取得进步。"),
        ("put into practice", "付诸实践", "put + knowledge or plan + into practice", "The workshop helps teachers put new assessment ideas into practice.", "该工作坊帮助教师把新的评估理念付诸实践。"),
    ),
}


def academic_phrase_catalog() -> list[dict]:
    items = []
    for category, rows in RAW_PHRASES.items():
        label, purpose, exam_tags = CATEGORY_META[category]
        for phrase, meaning_zh, grammar_frame, example, example_zh in rows:
            items.append({
                "id": len(items) + 1,
                "phrase_id": f"academic-phrase:{category}:{re.sub(r'[^a-z0-9]+', '-', phrase).strip('-')}",
                "type": "academic_phrase",
                "term": phrase,
                "kind": "phrase",
                "category": category,
                "category_label": label,
                "meaning_zh": meaning_zh,
                "concept_en": f'Use "{phrase}" to {purpose}.',
                "grammar_frame": grammar_frame,
                "register": "学术中性",
                "exam_tags": list(exam_tags),
                "example": example,
                "example_zh": example_zh,
                "usage_note_zh": f"按“{grammar_frame}”使用，保留完整搭配，不按中文逐词替换。",
                "source_key": SOURCE["key"],
                "source_name": SOURCE["name"],
                "source_version": SOURCE["version"],
                "source_attribution": SOURCE["attribution"],
                "copyright_status": SOURCE["copyright_status"],
                "sense_key": f"academic-phrase:{phrase}",
            })
    return items


IRREGULAR_FORMS = {
    "be": {"am", "is", "are", "was", "were", "been", "being"},
    "bring": {"brought"}, "draw": {"drew", "drawn"}, "fall": {"fell", "fallen"},
    "give": {"gave", "given"}, "lead": {"led"}, "make": {"made"},
    "rise": {"rose", "risen"}, "stand": {"stood"}, "take": {"took", "taken"},
}


def _word_forms(word: str) -> set[str]:
    forms = {word, f"{word}s", f"{word}ed", f"{word}ing", *IRREGULAR_FORMS.get(word, set())}
    if word.endswith(("s", "x", "z", "ch", "sh", "o")):
        forms.add(f"{word}es")
    if word.endswith("e"):
        forms.update({f"{word}d", f"{word[:-1]}ing"})
    if word.endswith("y"):
        forms.update({f"{word[:-1]}ies", f"{word[:-1]}ied"})
    return forms


def _example_contains_phrase(phrase: str, example: str) -> bool:
    phrase_tokens = re.findall(r"[a-z]+", phrase.casefold())
    example_tokens = re.findall(r"[a-z]+", example.casefold())
    position = 0
    for token in phrase_tokens:
        accepted = _word_forms(token)
        while position < len(example_tokens) and example_tokens[position] not in accepted:
            position += 1
        if position >= len(example_tokens):
            return False
        position += 1
    return True


def validate_academic_phrases() -> None:
    items = academic_phrase_catalog()
    if len(items) != 100:
        raise ValueError(f"Academic phrase catalog must contain 100 entries, got {len(items)}")
    if len({item["term"].casefold() for item in items}) != len(items):
        raise ValueError("Academic phrase catalog contains duplicate phrases")
    for category in CATEGORY_META:
        if sum(item["category"] == category for item in items) != 10:
            raise ValueError(f"Academic phrase category must contain 10 entries: {category}")
    required = {"meaning_zh", "concept_en", "grammar_frame", "example", "example_zh", "usage_note_zh", "source_key"}
    for item in items:
        if not all(item.get(field) for field in required):
            raise ValueError(f"Academic phrase is incomplete: {item['term']}")
        if not _example_contains_phrase(item["term"], item["example"]):
            raise ValueError(f"Academic phrase example does not contain phrase: {item['term']}")
        if not 2 <= len(item["term"].split()) <= 8:
            raise ValueError(f"Academic phrase length is outside the supported range: {item['term']}")


def search_academic_phrases(query: str = "", category: str = "", exam: str = "", limit: int = 100) -> list[dict]:
    clean = re.sub(r"\s+", " ", str(query or "")).strip().casefold()
    category = str(category or "").strip().casefold()
    exam = str(exam or "").strip().casefold()
    if category and category not in CATEGORY_META:
        raise ValueError("Invalid academic phrase category")
    values = []
    for item in academic_phrase_catalog():
        haystack = " ".join((item["term"], item["meaning_zh"], item["concept_en"], item["grammar_frame"])).casefold()
        if clean and clean not in haystack:
            continue
        if category and item["category"] != category:
            continue
        if exam and exam not in {value.casefold() for value in item["exam_tags"]}:
            continue
        values.append(dict(item))
    values.sort(key=lambda item: (item["category"], item["term"]))
    return values[:max(1, min(int(limit), 100))]


validate_academic_phrases()
