from __future__ import annotations


SOURCE = "Language Coach 原创审核例句（v0.8.0-alpha.25.12）"


def item(pos, meaning_zh, focus_en, focus, patterns, register, avoid, example, example_zh):
    return {
        "pos": pos, "meaning_zh": meaning_zh, "focus_en": focus_en, "focus": focus,
        "patterns": patterns, "register": register, "avoid": avoid,
        "example": example, "example_zh": example_zh, "example_source": SOURCE,
    }


def comparison(slug, terms, shared_translation, summary, memory_rule, dimensions, items):
    return {
        "slug": slug, "terms": terms, "title": " / ".join(terms),
        "shared_translation": shared_translation, "summary": summary,
        "memory_rule": memory_rule,
        "dimensions": [{"label": label, "value": value} for label, value in dimensions],
        "items": items, "confusion_type": "semantic",
        "exam_tags": ["IELTS"], "topic": "argument",
    }


IELTS_ARGUMENT_CURATED_COMPARISONS = (
    comparison(
        "ielts-because-because-of-due-to", ("because", "because of", "due to"),
        "都可引出原因，但从句、名词短语和系表结构的句法不同。",
        "because 是连词，后接完整从句；because of 是介词短语，后接名词或动名词；due to 是形容词性介词短语，正式写作中最稳妥的核心结构是 be due to。",
        "because + 句子，because of + 名词，be due to + 名词。",
        (("补语", "because + subject + verb；because of/due to + noun phrase or -ing。"),
         ("句法角色", "because 连接从句；because of 直接作原因状语；due to 传统上补充说明主语所致原因。"),
         ("正式写作", "句首 due to 在现代用法中常见，但考试中用 be due to 可避免争议和悬垂。")),
        {
            "because": item("conjunction", "因为", "introduce a clause that gives a reason", "连接一个带主语和谓语的原因从句。", ["because + subject + verb", "not because ..., but because ..."], "中性，口语和正式写作都自然。", "后面不能只接名词：because the cost 应改为 because of the cost。", "Many commuters chose rail because fuel prices had risen.", "许多通勤者选择铁路，因为燃油价格上涨了。"),
            "because of": item("prepositional phrase", "因为；由于", "introduce a noun phrase as the cause", "把名词、代词或动名词短语作为原因。", ["because of the cost", "because of living expenses"], "中性，适用于各类写作。", "后接完整从句时需要 because，而不是 because of people pay more。", "The project was delayed because of a shortage of materials.", "该项目因材料短缺而延期。"),
            "due to": item("adjectival/prepositional phrase", "由于；归因于", "identify the cause of a state or result, especially after be", "正式地把结果归因于某个名词性原因。", ["be due to something", "largely due to"], "正式，学术写作常见。", "不要写 due to the government raised taxes；应接名词或改用 because。", "The decline was largely due to lower overseas demand.", "这一下降主要是由于海外需求减少。"),
        },
    ),
    comparison(
        "ielts-however-nevertheless-nonetheless", ("however", "nevertheless", "nonetheless"),
        "都可表示转折，但普通对比和承认阻碍后仍成立的让步力度不同。",
        "however 是最通用的句间转折；nevertheless 和 nonetheless 都表示尽管前述事实存在，后面的结论仍成立，二者意义非常接近。",
        "普通转折用 however，逆着阻碍仍成立用 nevertheless/nonetheless。",
        (("逻辑", "however 可连接一般对比；nevertheless/nonetheless 更明确表达 concessive contrast。"),
         ("标点", "三者作连接副词时通常用句号或分号分隔独立句，再加逗号。"),
         ("语域", "however 最通用；nevertheless 稍正式；nonetheless 正式而简洁。")),
        {
            "however": item("conjunctive adverb", "然而；不过", "mark a contrast with the previous statement", "最中性地转向不同或相反的信息。", ["However, + clause", "clause; however, clause"], "中性、正式，议论文高频。", "不能只用逗号连接两个完整句：..., however, ... 是逗号拼接。", "The scheme is expensive; however, it could reduce long-term costs.", "该方案成本高；然而，它可能降低长期成本。"),
            "nevertheless": item("conjunctive adverb", "尽管如此；然而", "show that a conclusion remains true despite an obstacle", "承认前述不利事实后，强调后项仍然成立。", ["Nevertheless, + clause", "but nevertheless"], "正式，论证语气较强。", "若只是并列两个不同数据而没有让步关系，however 更自然。", "The sample was small. Nevertheless, the pattern was consistent.", "样本量很小。尽管如此，这一规律仍然一致。"),
            "nonetheless": item("conjunctive adverb", "尽管如此；仍然", "indicate that something is true in spite of what was just said", "功能接近 nevertheless，强调前述因素未改变后项。", ["Nonetheless, + clause", "remain valid nonetheless"], "正式；比 however 使用频率低。", "不要把 nevertheless 和 nonetheless 连用来叠加强度。", "The policy has limitations but is nonetheless a useful first step.", "该政策存在局限，但仍是有用的第一步。"),
        },
    ),
    comparison(
        "ielts-although-despite-in-spite-of", ("although", "despite", "in spite of"),
        "都表示让步，但 although 接从句，despite 和 in spite of 接名词性结构。",
        "although 是从属连词；despite 是介词；in spite of 是与 despite 同义但更长的介词短语。",
        "although + 句子，despite/in spite of + 名词或 -ing。",
        (("补语", "although + subject + verb；despite/in spite of + noun, pronoun, or -ing。"),
         ("改写", "although costs rose = despite the rise in costs；不能保留原从句直接替换。"),
         ("语域", "三者均可正式使用；despite 更紧凑，in spite of 略强调阻碍。")),
        {
            "although": item("conjunction", "虽然；尽管", "introduce a clause that contrasts with the main clause", "引出包含主谓结构的让步从句。", ["although + clause", "although it is true that"], "中性、正式。", "标准英语不把 although 和 but 同时作为同一结构的连接词。", "Although the initial cost is high, the system saves energy.", "虽然初始成本很高，但该系统能够节省能源。"),
            "despite": item("preposition", "尽管；不顾", "introduce a fact or condition that does not prevent the result", "后接名词、代词或动名词，紧凑表达阻碍未改变结果。", ["despite the cost", "despite being expensive"], "中性偏正式，写作高频。", "不能写 despite the cost was high；可改为 despite the high cost 或 although...。", "Despite limited funding, the programme reached all districts.", "尽管资金有限，该项目仍覆盖了所有地区。"),
            "in spite of": item("prepositional phrase", "尽管；不顾", "express that a result occurs despite an obstacle", "意义接近 despite，但形式更长，常稍加强调。", ["in spite of the evidence", "in spite of having little time"], "中性；正式和日常写作均可。", "不要写 in despite of；固定形式是 despite 或 in spite of。", "In spite of heavy traffic, average journey times fell.", "尽管交通拥堵，平均出行时间仍有所下降。"),
        },
    ),
    comparison(
        "ielts-while-whereas", ("while", "whereas"),
        "都可对照两个分句，但 while 还有时间义，whereas 只明确表达对比。",
        "while 可表示“当……时”或“而”；whereas 是正式对比连词，不带时间义，因此在可能歧义时更清楚。",
        "while 可时间可对比，whereas 只负责对比。",
        (("歧义", "while 有 simultaneous-time 和 contrast 两义；whereas 只有 contrast。"),
         ("位置", "二者都可置于两个分句之间；whereas 常直接比较平行项目。"),
         ("语域", "while 中性；whereas 正式、分析性更强。")),
        {
            "while": item("conjunction", "而；虽然；当……时", "contrast two facts or show that events occur at the same time", "可表达对比，也可表达同时发生，需由上下文判断。", ["A rose, while B fell", "while this is true"], "中性，图表和议论文常见。", "若读者可能理解为时间关系，改用 whereas 或 although。", "Urban wages rose, while rural wages remained stable.", "城市工资上涨，而农村工资保持稳定。"),
            "whereas": item("conjunction", "然而；而；相比之下", "set two facts or groups in explicit contrast", "专门把两个平行事实或类别进行对照。", ["A ..., whereas B ...", "whereas the former"], "正式，比较分析中自然。", "whereas 不表示两件事同时发生，也不等于 however 的句间标点结构。", "Private transport was preferred by adults, whereas students favoured buses.", "成年人偏好私人交通，而学生更喜欢公交车。"),
        },
    ),
    comparison(
        "ielts-also-moreover-furthermore", ("also", "moreover", "furthermore"),
        "都可增加信息，但普通添加和强化论点的递进功能不同。",
        "also 是中性的“也”；moreover 和 furthermore 通常在句间增加一个进一步支持当前论点的重要理由，语气更正式。",
        "普通再加一项用 also，递进加论据用 moreover/furthermore。",
        (("论证功能", "also 只添加；moreover/furthermore 常暗示新增信息进一步强化结论。"),
         ("句位", "also 常在实义动词前或 be 后；moreover/furthermore 常置于句首并加逗号。"),
         ("克制", "一段中连续使用 moreover/furthermore 会显得机械，逻辑关系应先于词汇变化。")),
        {
            "also": item("adverb", "也；还", "add another fact, item, or action", "中性添加同级信息，不自动提高论证力度。", ["also increases", "is also important"], "中性、高频。", "注意位置：people also need，而不是通常写 people need also basic services。", "The policy also provides grants for small businesses.", "该政策还为小企业提供补助。"),
            "moreover": item("conjunctive adverb", "而且；此外", "add a further point that strengthens an argument", "递进加入一个支持当前立场的较重要理由。", ["Moreover, + clause", "and, moreover,"], "正式、论证性强。", "不能用逗号单独连接两个完整句；也不适合添加与论点无关的细节。", "The reform is affordable. Moreover, it can be implemented quickly.", "这项改革成本可控，而且可以迅速实施。"),
            "furthermore": item("conjunctive adverb", "此外；而且", "introduce an additional supporting reason or fact", "正式地继续添加支持性论据，功能接近 moreover。", ["Furthermore, + clause", "furthermore, the evidence shows"], "正式，学术写作常见。", "与 moreover 差别很小，不要在一句中并列使用两者。", "Furthermore, the evidence comes from three independent studies.", "此外，这些证据来自三项独立研究。"),
        },
    ),
    comparison(
        "ielts-example-instance-illustration", ("example", "instance", "illustration"),
        "都可译为例子，但通用个案、某次具体实例和用来阐明观点的材料不同。",
        "example 最通用；instance 强调某个实际发生的案例；illustration 强调材料如何解释或证明一个抽象观点。",
        "通用例子是 example，具体一次是 instance，阐明观点是 illustration。",
        (("焦点", "example 展示类别成员；instance 指具体发生；illustration 强调解释功能。"),
         ("固定表达", "for example；for instance；an illustration of。"),
         ("可互换", "for example/for instance 多数场合可互换；illustration 不能总作为同样的插入连接语。")),
        {
            "example": item("noun", "例子；范例", "a representative case used to show what something is like", "最广泛地提供一个代表性项目或情况。", ["for example", "an example of"], "中性、通用。", "例子必须真正支持前句，不能只在新句前机械添加 For example。", "For example, flexible hours can help parents remain in work.", "例如，弹性工作时间可以帮助父母继续就业。"),
            "instance": item("noun", "实例；具体情况", "a particular occurrence or case of a general type", "强调某类现象在现实中的一次具体发生。", ["for instance", "an instance of"], "中性偏正式。", "instance 还有“要求、场合”等义项，需靠搭配明确。", "One instance of successful reform occurred in Finland.", "芬兰曾出现过一个改革成功的实例。"),
            "illustration": item("noun", "说明性例子；例证；插图", "a case or image that makes an idea clearer", "突出例子用于解释、展示或证明观点的功能。", ["an illustration of", "provide a clear illustration"], "正式；也可表示插图。", "纯粹列举一个成员时 example 通常更自然。", "The pilot scheme provides a clear illustration of community-led planning.", "该试点方案清楚说明了社区主导规划的作用。"),
        },
    ),
    comparison(
        "ielts-claim-argue-assert-maintain", ("claim", "argue", "assert", "maintain"),
        "都可引出观点，但未经证实的声称、给出理由的论证、强硬断言和持续坚持不同。",
        "claim 常与证据尚待核实有关；argue 表示用理由支持立场；assert 强调坚定陈述；maintain 表示面对质疑仍坚持原观点。",
        "待证是 claim，有理由是 argue，强断言是 assert，持续坚持是 maintain。",
        (("证据", "argue 暗示理由链；claim 对真实性保持距离；assert 不必展示理由；maintain 强调立场持续。"),
         ("立场距离", "写 researchers claim 可能暗示作者不完全接受；argue 较中性地报告论证。"),
         ("句法", "四者均可接 that-clause；claim/assert 也可接名词，argue for/against，maintain a position。")),
        {
            "claim": item("verb/noun", "声称；主张", "state that something is true, often before it is fully proven", "报告一个真实性可能仍需证据支持的说法。", ["claim that", "make a claim"], "中性偏正式，可带审慎或怀疑距离。", "不要把所有可靠研究结论都写成 claim，否则可能无意质疑来源。", "The company claims that the new process cuts emissions by half.", "该公司声称新工艺可将排放量减半。"),
            "argue": item("verb", "论证；主张；争辩", "support a position with reasons or evidence", "强调观点背后存在理由、证据或推理。", ["argue that", "argue for/against"], "正式学术义常见；日常也可表示争吵。", "argue a policy 不自然；通常说 argue for a policy 或 argue that it is needed。", "Several researchers argue that prevention is more cost-effective.", "几位研究人员论证说，预防措施更具成本效益。"),
            "assert": item("verb", "断言；坚称", "state something firmly and confidently", "强调说话者坚定提出某命题，不表示已展示证据。", ["assert that", "assert a right"], "正式，力度强。", "证据弱时频繁使用 assert 会让论证显得武断。", "The report asserts that access to water is a basic right.", "该报告明确主张获得水资源是一项基本权利。"),
            "maintain": item("verb", "坚持认为；维持", "continue to hold or state a position despite challenge", "在受到质疑或出现反对意见后仍保持原立场。", ["maintain that", "maintain a position"], "正式；另有维持、保养义。", "没有持续或争议背景时，say/argue 通常比 maintain 更准确。", "The authors maintain that the benefits outweigh the risks.", "作者们仍坚持认为收益大于风险。"),
        },
    ),
    comparison(
        "ielts-suggest-propose-recommend", ("suggest", "propose", "recommend"),
        "都可译为建议，但提出可能性、正式提交方案和基于判断推荐行动不同。",
        "suggest 可提出想法或暗示结论；propose 正式提出待讨论的计划；recommend 根据判断建议某人采取合适行动。",
        "给想法或暗示用 suggest，提交方案用 propose，判断后推荐用 recommend。",
        (("功能", "evidence suggests 是暗示；propose a policy 是提出方案；recommend action 是给出建议。"),
         ("句法", "suggest/propose/recommend doing or that + base verb；通常不写 suggest someone to do。"),
         ("正式度", "propose 偏制度和方案；recommend 常暗示评估依据；suggest 范围最广。")),
        {
            "suggest": item("verb", "建议；表明；暗示", "offer an idea or indicate a possible conclusion", "既可温和提出做法，也可说明证据指向某结论。", ["suggest doing", "evidence suggests that"], "中性、正式写作高频。", "避免 suggest people to use；写 suggest that people use 或 suggest using。", "The evidence suggests that shorter lessons improve attention.", "证据表明，较短的课程有助于提高注意力。"),
            "propose": item("verb", "提议；提出", "put forward a plan or idea for formal consideration", "把较具体的计划、制度或解释提交讨论。", ["propose a measure", "propose that + base verb"], "正式，政策和研究语境。", "propose 不等于证明方案有效，只表示正式提出。", "The committee proposed that bus fares be reduced for students.", "委员会提议降低学生公交票价。"),
            "recommend": item("verb", "建议；推荐", "advise a course of action based on judgement or evidence", "根据经验、评估或证据指出较合适的行动。", ["recommend doing", "recommend that + base verb"], "中性偏正式。", "标准正式结构通常不用 recommend someone to do；可用 advise someone to do。", "The review recommends investing in early-childhood services.", "该评估建议投资幼儿服务。"),
        },
    ),
    comparison(
        "ielts-believe-think-consider", ("believe", "think", "consider"),
        "都可表达看法，但信念接受、一般判断和审慎考量不同。",
        "believe 表示把命题视为真实或持有信念；think 是最通用的个人判断；consider 表示经过思考后认为，或把某因素纳入考虑。",
        "信为真用 believe，一般看法用 think，审慎权衡用 consider。",
        (("认知力度", "believe 常关乎真实性或信念；think 中性；consider 暗示思考过程或评价。"),
         ("句法", "believe/think that；consider doing；consider something to be。"),
         ("学术立场", "I think 并非错误，但可通过证据和具体判断提升正式度，而不是机械换成 consider。")),
        {
            "believe": item("verb", "相信；认为", "accept something as true or hold it as a conviction", "表达对真实性的接受或较稳定的信念。", ["believe that", "widely believed to be"], "中性；个人信念色彩可强可弱。", "believe 不能代替基于数据的 demonstrate；信念本身不是证据。", "Many residents believe that the area needs a new clinic.", "许多居民认为该地区需要一所新诊所。"),
            "think": item("verb", "认为；思考", "have an opinion, judgement, or idea", "最通用地表达个人判断或进行思考。", ["think that", "think about"], "中性高频；第一人称中略偏日常。", "think about 是考虑某事，think that 是持有判断，介词不能随意省略。", "Some parents think that homework should be limited.", "一些家长认为家庭作业应受到限制。"),
            "consider": item("verb", "认为；考虑", "think carefully about something or judge it in a particular way", "强调审慎思考，或把对象评价为某种状态。", ["consider doing", "consider something to be"], "正式，分析和决策语境自然。", "不写 consider to do；应写 consider doing。", "Governments should consider subsidising rural transport.", "政府应考虑补贴农村交通。"),
        },
    ),
    comparison(
        "ielts-advantage-benefit-merit", ("advantage", "benefit", "merit"),
        "都可表示好处，但比较优势、实际收益和方案本身的优点不同。",
        "advantage 常相对于另一选择形成有利条件；benefit 是带给人或系统的积极结果；merit 是观点、方案或作品值得肯定的内在优点。",
        "比别项更有利用 advantage，实际获益用 benefit，本身值得肯定用 merit。",
        (("参照", "advantage 常有比较对象；benefit 常有受益者；merit 评价对象自身质量。"),
         ("词性", "advantage/merit 主要作名词；benefit 可作名词或动词。"),
         ("搭配", "an advantage over；benefit from；the merits of a proposal。")),
        {
            "advantage": item("noun", "优势；有利条件", "a condition that makes one option more favourable than another", "突出相对于替代方案的有利位置。", ["an advantage over", "the main advantage of"], "中性、正式，议论文高频。", "若没有比较或选择背景，benefit 可能比 advantage 更准确。", "One advantage of rail is its lower energy use per passenger.", "铁路的一项优势是人均能耗较低。"),
            "benefit": item("noun/verb", "益处；使受益", "a positive result received by a person, group, or system", "强调行动带来的实际改善及其受益者。", ["the benefits of", "benefit from"], "中性、正式。", "作动词时 people benefit from a policy 或 a policy benefits people，方向不同。", "Flexible schedules benefit employees with caring responsibilities.", "弹性工作安排使承担照护责任的员工受益。"),
            "merit": item("noun", "优点；价值", "an intrinsic quality that makes an idea or work worthy of approval", "评价论点、计划或作品本身值得认可之处。", ["the merits of", "have considerable merit"], "正式，评估和论证语境。", "merit 不直接表示谁获得实际收益。", "The proposal has merit, although its cost requires further study.", "这项提案有其优点，但其成本仍需进一步研究。"),
        },
    ),
)


IELTS_ARGUMENT_CURATED_COMPARISONS += (
    comparison(
        "ielts-disadvantage-drawback-limitation", ("disadvantage", "drawback", "limitation"),
        "都可表示不足，但相对劣势、具体缺点和能力或研究边界不同。",
        "disadvantage 是使选择处于不利位置的条件；drawback 是方案伴随的具体负面特征；limitation 是能力、范围、方法或结论不能超越的边界。",
        "处于不利用 disadvantage，方案缺点用 drawback，能力边界用 limitation。",
        (("参照", "disadvantage 常隐含与另一选择比较；drawback 针对对象的负面面向；limitation 说明范围或能力受限。"),
         ("搭配", "at a disadvantage；a drawback of；limitations of the study。"),
         ("研究写作", "small sample size is a limitation；它不一定是某方案相对于另一方案的 disadvantage。")),
        {
            "disadvantage": item("noun", "劣势；不利条件", "a condition that puts someone or something in a less favourable position", "突出相对于其他人或选择处于不利地位。", ["at a disadvantage", "a disadvantage of"], "中性、正式。", "没有比较参照时，不要机械使用 disadvantage 代替所有问题。", "Rural firms are at a disadvantage because broadband access is weaker.", "农村企业因宽带接入较弱而处于不利地位。"),
            "drawback": item("noun", "缺点；不利之处", "a specific negative feature of an otherwise useful option", "指出方案、产品或做法附带的具体缺点。", ["the main drawback", "a drawback of the scheme"], "中性，议论文自然。", "drawback 通常是可识别的缺点，不等于研究范围限制。", "The main drawback of the scheme is its high initial cost.", "该方案的主要缺点是初始成本高。"),
            "limitation": item("noun", "局限；限制", "a boundary on ability, scope, method, or interpretation", "说明方法、数据、能力或结论适用范围受到约束。", ["a limitation of the study", "within these limitations"], "正式，研究与评估语境高频。", "limitation 不必表示整个方案不好；它可能只是结论适用边界。", "A key limitation of the survey is its small sample size.", "这项调查的一个主要局限是样本量较小。"),
        },
    ),
    comparison(
        "ielts-solution-measure-remedy", ("solution", "measure", "remedy"),
        "都可与解决问题有关，但完整解法、具体行动和纠正既有弊病的办法不同。",
        "solution 是解决问题的总体答案；measure 是为达成目标采取的具体步骤或政策；remedy 是纠正问题、损害或缺陷的补救办法。",
        "完整解法用 solution，执行步骤用 measure，纠正弊病用 remedy。",
        (("层级", "一套 solution 可包含多项 measures；remedy 常针对已经存在的不良状态。"),
         ("搭配", "a solution to；take measures to；a remedy for。"),
         ("效果", "提出 measure 不等于问题已 solved；应区分行动与验证后的结果。")),
        {
            "solution": item("noun", "解决方案；解答", "an answer or plan that resolves a problem", "从整体上说明问题如何得到解决。", ["a solution to the problem", "find a viable solution"], "中性、正式。", "介词通常是 solution to，不写 solution of the problem。", "Affordable childcare is part of the solution to labour shortages.", "可负担的儿童照护服务是解决劳动力短缺问题的一部分。"),
            "measure": item("noun/verb", "措施；衡量", "a specific action taken to achieve an aim or address a problem", "指政府、组织或个人采取的具体行动步骤。", ["take measures to", "a policy measure"], "正式，政策写作高频。", "measure 还可表示测量；政策语境需用 action/take 等搭配明确。", "The city introduced measures to reduce household waste.", "该市采取了减少家庭垃圾的措施。"),
            "remedy": item("noun/verb", "补救办法；纠正", "a way of correcting a problem, harm, or defect", "强调对已出现的问题或不公进行纠正和补救。", ["a remedy for", "remedy the situation"], "正式；法律、健康和政策语境常见。", "remedy 往往针对症状或缺陷，不一定消除根本原因。", "Training alone is not a complete remedy for regional inequality.", "仅靠培训并不是解决地区不平等的完整办法。"),
        },
    ),
    comparison(
        "ielts-support-back-endorse", ("support", "back", "endorse"),
        "都可表示支持，但一般帮助或赞同、公开站队和正式认可不同。",
        "support 范围最广，可给资源、证据或赞同；back 常表示公开或实际站在某方背后；endorse 表示个人或机构正式公开认可。",
        "一般支持用 support，公开站队用 back，正式认可用 endorse。",
        (("支持方式", "support 可是论据、资金或态度；back 偏承诺力量；endorse 偏正式批准或公开赞同。"),
         ("语域", "support 中性；back 较直接；endorse 正式、制度性更强。"),
         ("证据", "data support a conclusion，但数据不会 back/endorse 一项政策。")),
        {
            "support": item("verb/noun", "支持；支撑；援助", "provide help, resources, agreement, or evidence", "可描述人、制度或证据提供帮助和支撑。", ["support a proposal", "evidence supports the conclusion"], "中性、正式，范围最广。", "证据通常 supports 而不是 proves 一个结论；注意不要夸大因果。", "The survey results support the case for later opening hours.", "调查结果支持延长开放时间的主张。"),
            "back": item("verb/noun", "支持；为……撑腰", "give active or public support to a person, plan, or side", "强调公开站在某一方，或投入实际力量。", ["back a campaign", "be backed by funding"], "中性偏新闻和日常，正式写作可用。", "学术证据关系优先用 support，不把 figures back a theory 当作默认表达。", "Several local businesses backed the recycling campaign.", "几家当地企业公开支持这项回收活动。"),
            "endorse": item("verb", "正式认可；公开赞同", "declare formal or public approval of something", "个人、专业团体或机构明确给予正式认可。", ["endorse a policy", "officially endorsed by"], "正式，机构和公共立场语境。", "个人私下同意不一定构成 endorse；它通常具有公开或权威意味。", "The proposal was endorsed by the national medical association.", "这项提案获得了全国医学协会的正式认可。"),
        },
    ),
    comparison(
        "ielts-oppose-object-resist", ("oppose", "object", "resist"),
        "都可表示反对，但立场反对、明确提出异议和抵抗压力或改变不同。",
        "oppose 是一般或公开反对；object 通常以 object to 表达具体异议；resist 强调抵抗外力、诱因、政策或变化。",
        "持反对立场用 oppose，提出异议用 object to，抵抗压力用 resist。",
        (("句法", "oppose + noun/-ing；object to + noun/-ing；resist + noun/-ing。"),
         ("行动", "oppose 可是立场；object 是表达异议；resist 常包含不屈从或阻止变化的行动。"),
         ("错误", "to 在 object to 中是介词，因此写 object to paying，不写 object to pay。")),
        {
            "oppose": item("verb", "反对；抵制", "disagree with and seek to prevent a policy, idea, or action", "表明对某项计划、观点或行动持反对立场。", ["oppose a proposal", "oppose doing"], "中性偏正式。", "不写 oppose to the plan；oppose 是及物动词，直接接宾语。", "Some residents oppose building a motorway near the village.", "一些居民反对在村庄附近修建高速公路。"),
            "object": item("verb/noun", "反对；提出异议", "express disagreement or disapproval", "明确说出对某个具体做法的异议。", ["object to something", "raise an objection"], "中性偏正式。", "必须保留介词 to，且其后接名词或 -ing。", "Parents objected to increasing class sizes.", "家长们反对扩大学班规模。"),
            "resist": item("verb", "抵抗；抵制", "withstand pressure, control, temptation, or change", "强调面对外力或变化而不屈从，常包含持续行动。", ["resist pressure", "resist changing"], "中性、正式。", "单纯表达不同意见时 oppose/object 更准确，resist 暗示压力或推动力。", "Small firms may resist adopting costly new equipment.", "小企业可能会抵制采用昂贵的新设备。"),
        },
    ),
    comparison(
        "ielts-responsibility-duty-obligation", ("responsibility", "duty", "obligation"),
        "都可译为责任，但负责范围、角色职责和法律或承诺约束不同。",
        "responsibility 是对任务或结果负责；duty 是职位、道德或公民角色要求履行的职责；obligation 是法律、合同、承诺或强烈道德规范形成的约束。",
        "对结果负责是 responsibility，角色应做是 duty，受规则约束是 obligation。",
        (("来源", "responsibility 来自控制或分工；duty 来自角色或道德；obligation 来自法律、合同、承诺或规范。"),
         ("搭配", "take responsibility for；a duty to；an obligation to/under law。"),
         ("强度", "obligation 通常最具强制性；responsibility 也可指广泛负责领域。")),
        {
            "responsibility": item("noun", "责任；负责的事项", "accountability for a task, person, decision, or outcome", "强调负责范围以及对结果承担责任。", ["take responsibility for", "have responsibility for"], "中性、正式。", "responsibility for 后接名词或 -ing；responsibility to 可指对某人的责任。", "Manufacturers must take responsibility for electronic waste.", "制造商必须对电子废弃物负责。"),
            "duty": item("noun", "职责；义务", "a task or conduct required by a role, morality, or public office", "表示某种身份、职业或道德角色要求做的事情。", ["a duty to protect", "perform a duty"], "正式；职业、公民和道德语境常见。", "日常分配的一项任务未必需要用 duty，task/responsibility 可能更自然。", "Doctors have a duty to protect patient confidentiality.", "医生有责任保护患者隐私。"),
            "obligation": item("noun", "义务；约束", "a binding requirement created by law, contract, promise, or morality", "强调必须履行，常有明确约束来源。", ["a legal obligation", "an obligation to do"], "正式，法律和制度语境。", "个人偏好或一般建议不能自动称为 obligation。", "Employers have a legal obligation to provide a safe workplace.", "雇主有法律义务提供安全的工作场所。"),
        },
    ),
    comparison(
        "ielts-right-entitlement-permission", ("right", "entitlement", "permission"),
        "都可能译为权利或许可，但基本权利、符合条件所得资格和个别授权不同。",
        "right 是法律或道德上可正当主张的权利；entitlement 是依据规则、身份或缴费获得的具体资格或给付；permission 是权威对某次行为的允许。",
        "可正当主张是 right，符合条件可领取是 entitlement，获准去做是 permission。",
        (("来源", "right 来自法律/道德原则；entitlement 来自资格规则；permission 来自有权批准的人或机构。"),
         ("范围", "right 常普遍或原则性；entitlement 具体且有条件；permission 常针对某个行为。"),
         ("句法", "the right to；entitlement to benefits；permission to do。")),
        {
            "right": item("noun/adjective", "权利；正确的", "a justified legal or moral claim to act, receive, or be protected", "表示个人或群体可依法或道德原则正当主张。", ["the right to education", "human rights"], "正式，法律和公共政策高频。", "别人允许一次行为不等于形成永久权利。", "Every child has the right to basic education.", "每个儿童都有接受基础教育的权利。"),
            "entitlement": item("noun", "应享资格；应得权益", "a specific benefit or claim granted when stated conditions are met", "依据身份、缴费、年龄或制度规则获得具体给付资格。", ["entitlement to benefits", "a statutory entitlement"], "正式，社会保障和劳动制度语境。", "entitlement 不是所有人的抽象 human right，通常需要资格条件。", "Full-time workers have an entitlement to paid annual leave.", "全职员工享有带薪年假的法定资格。"),
            "permission": item("noun", "许可；准许", "approval from an authority to do a particular thing", "由有权者批准某人进行特定行为。", ["permission to do", "obtain permission from"], "中性、正式。", "permission 通常不可数，不写 a permission；可写 a permit 表示许可证。", "Researchers obtained permission to interview the participants.", "研究人员获得了采访参与者的许可。"),
        },
    ),
    comparison(
        "ielts-freedom-liberty-independence", ("freedom", "liberty", "independence"),
        "都与自由有关，但不受限制的能力、法律政治自由和不依赖他者的自主不同。",
        "freedom 是免受限制并自主行动的广义能力；liberty 更正式，常指受法律保护的公民或政治自由；independence 是不受另一方控制或不依赖他者。",
        "广义不受限是 freedom，法律政治自由是 liberty，不受控制依赖是 independence。",
        (("关系", "freedom/liberty 关注可做什么；independence 关注是否由自己控制和承担。"),
         ("语域", "freedom 最通用；liberty 正式且法律政治色彩强；independence 适用于国家、机构和个人。"),
         ("搭配", "freedom of speech；civil liberties；gain independence from。")),
        {
            "freedom": item("noun", "自由；自主空间", "the ability to act, speak, or choose without undue restriction", "广义表示行动、表达或选择不受不当限制。", ["freedom of speech", "freedom to choose"], "中性、正式和日常都常见。", "freedom 不表示完全没有责任或规则，论证时需说明限制是否合理。", "Remote work gives employees greater freedom to organise their time.", "远程工作使员工能更自由地安排时间。"),
            "liberty": item("noun", "自由；公民自由", "freedom protected by law, especially from arbitrary control", "偏法律和政治，强调免受任意干预的受保护自由。", ["civil liberties", "individual liberty"], "正式，法律、政治和哲学语境。", "日常时间安排通常用 freedom，不必用 liberty 显得高级。", "Emergency laws must not permanently weaken civil liberties.", "紧急法律不应永久削弱公民自由。"),
            "independence": item("noun", "独立；自主", "freedom from another party's control, support, or influence", "强调个人、机构或国家不受他者控制或不依赖其支持。", ["gain independence from", "financial independence"], "中性、正式。", "有选择自由不一定意味着经济或政治 independence。", "Reliable public transport can increase independence among older people.", "可靠的公共交通可以提高老年人的独立生活能力。"),
        },
    ),
    comparison(
        "ielts-choice-option-alternative", ("choice", "option", "alternative"),
        "都可表示选择，但选择行为或范围、可选项目和替代现有方案的另一办法不同。",
        "choice 可指选择行为、选择权或最终选中项；option 是可供挑选的一个项目；alternative 是替代当前或已提方案的另一条路径。",
        "选择权和结果用 choice，菜单项目用 option，替代方案用 alternative。",
        (("层级", "a choice between options；an alternative to the current policy。"),
         ("数量", "options 可有多个；alternative 传统上常指两者之一，现代也可指多种替代。"),
         ("搭配", "make a choice；available options；an alternative to。")),
        {
            "choice": item("noun", "选择；选择权；选中项", "the act, freedom, range, or result of choosing", "既可指做决定，也可指选择空间和最终结果。", ["make a choice", "have no choice but to"], "中性、高频。", "choice of 表示所选或选择范围；choice between 强调在项目间决定。", "Consumers should have a genuine choice between providers.", "消费者应能在服务提供者之间作出真正的选择。"),
            "option": item("noun", "选项；可选择的办法", "one item or course of action available for selection", "表示选择集合中的一个具体可选项。", ["an available option", "have the option to do"], "中性、正式和日常都自然。", "已经被选中的最终决定不一定叫 option，可能是 choice/decision。", "Cycling is not a practical option for every commuter.", "骑行并不是每位通勤者都可行的选项。"),
            "alternative": item("noun/adjective", "替代方案；可替代的", "another possibility that can replace the current or proposed one", "突出可以替换现有做法的另一条路径。", ["an alternative to", "an alternative approach"], "中性偏正式。", "介词是 alternative to，不写 alternative of；alternative 不只是任意列表项。", "Solar power offers an alternative to imported fuel.", "太阳能为进口燃料提供了一种替代方案。"),
        },
    ),
    comparison(
        "ielts-true-correct-valid", ("true", "correct", "valid"),
        "都可译为正确，但符合事实、答案无误和推理或测量成立不同。",
        "true 判断命题是否符合现实；correct 判断答案、计算、行为或形式是否无误；valid 判断论证、方法、票证或测量是否在规则和逻辑上成立。",
        "符合事实是 true，没有做错是 correct，逻辑方法成立是 valid。",
        (("对象", "a true statement；a correct answer；a valid argument/measure。"),
         ("逻辑", "论证可以 logically valid 但前提不 true；结论也可能碰巧 true。"),
         ("研究", "validity 关乎工具是否测到目标概念，不只是结果算得 correct。")),
        {
            "true": item("adjective", "真实的；符合事实的", "consistent with reality or the facts", "判断陈述、报道或信念是否与事实相符。", ["it is true that", "a true statement"], "中性、高频。", "true 不评价计算步骤或论证结构是否有效。", "It is true that average life expectancy has increased.", "平均预期寿命确实有所提高。"),
            "correct": item("adjective/verb", "正确的；纠正", "free from error according to facts, rules, or calculation", "表示答案、数字、语法或做法没有错误。", ["the correct answer", "factually correct"], "中性、高频。", "correct argument 不如 valid argument 精确；需说明是事实无误还是逻辑有效。", "The calculation is correct, but the data source is outdated.", "计算没有错误，但数据来源已经过时。"),
            "valid": item("adjective", "有效的；成立的", "logically sound in form or acceptable under relevant rules and purpose", "判断论证形式、方法、测量或许可是否成立和适用。", ["a valid argument", "valid evidence"], "正式，逻辑、研究和法律语境。", "valid 不保证前提真实，也不表示研究结论必然正确。", "The criticism is valid because the survey did not include rural households.", "这项批评是成立的，因为调查没有覆盖农村家庭。"),
        },
    ),
    comparison(
        "ielts-false-incorrect-invalid", ("false", "incorrect", "invalid"),
        "都可译为错误，但与事实不符、答案或细节出错和逻辑、方法或资格无效不同。",
        "false 指命题不符合事实；incorrect 指答案、数据或做法有错误；invalid 指论证、方法、票证或推断不符合成立条件。",
        "事实不真是 false，具体做错是 incorrect，逻辑方法不成立是 invalid。",
        (("对象", "a false claim；an incorrect figure；an invalid inference/method。"),
         ("程度", "incorrect 可局部修正；invalid 常意味着不能据此得出预期结论或使用该资格。"),
         ("语气", "描述他人观点时 false 较直接；学术写作可具体说明 unsupported/incorrect/invalid 的原因。")),
        {
            "false": item("adjective", "虚假的；不符合事实的", "not consistent with reality or the facts", "直接判断陈述或信念与事实不符。", ["a false claim", "prove false"], "中性但判断力度强。", "证据不足不等于已经证明 false；可写 unsupported。", "The claim that no residents use buses is false.", "所谓没有居民乘坐公交车的说法并不属实。"),
            "incorrect": item("adjective", "不正确的；有错误的", "containing an error in fact, calculation, form, or action", "指出答案、数字、用法或操作存在具体错误。", ["an incorrect figure", "factually incorrect"], "中性、高频。", "方法整体无法测量目标时应考虑 invalid，而不只是 incorrect。", "The report gives an incorrect total for the final year.", "该报告给出的最后一年总数有误。"),
            "invalid": item("adjective", "无效的；不成立的", "not logically, methodologically, or legally acceptable", "表示推理、方法、测量或资格未满足成立规则。", ["an invalid conclusion", "statistically invalid"], "正式，逻辑、研究和法律语境。", "一个事实数字写错通常是 incorrect，不必称整份数据 invalid。", "The comparison is invalid because the groups were measured differently.", "由于两组采用了不同的测量方法，这一比较并不成立。"),
        },
    ),
)
