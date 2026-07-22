from __future__ import annotations


def item(pos, meaning_zh, focus_en, focus, patterns, register, avoid, example, example_zh):
    return {
        "pos": pos,
        "meaning_zh": meaning_zh,
        "focus_en": focus_en,
        "focus": focus,
        "patterns": patterns,
        "register": register,
        "avoid": avoid,
        "example": example,
        "example_zh": example_zh,
    }


def comparison(slug, terms, shared_translation, summary, memory_rule, dimensions, items):
    return {
        "slug": slug,
        "terms": terms,
        "title": " / ".join(terms),
        "shared_translation": shared_translation,
        "summary": summary,
        "memory_rule": memory_rule,
        "dimensions": [
            {"label": label, "value": value}
            for label, value in dimensions
        ],
        "items": items,
    }


COMMON_CURATED_COMPARISONS = (
    comparison(
        "say-tell-speak-talk",
        ("say", "tell", "speak", "talk"),
        "中文都可能译成“说”，但宾语结构、交流方向和语境不同。",
        "say 关注说出的内容；tell 关注把信息告诉某人；speak 偏语言能力或正式发言；talk 强调交谈过程。",
        "say 内容，tell 对象，speak 发言或语言，talk 双向交谈。",
        (
            ("句法", "say something；tell someone something；speak to someone / speak English；talk to/with someone about something。"),
            ("交流方向", "say 可只报告话语；tell 通常有信息接收者；speak 可单向；talk 常暗示互动。"),
            ("可互换性", "say 和 tell 不能只替换动词而保留原宾语；speak/talk 在正式程度和固定搭配上也不同。"),
        ),
        {
            "say": item("verb", "说；说出", "express words or state particular content", "重点是话语内容，而不是听者。", ["say something", "say that ...", "say hello to someone"], "中性，口语和书面语都常见。", "不能说 say me the answer；应说 tell me the answer。", "She said that the deadline had changed.", "她说截止日期已经变了。"),
            "tell": item("verb", "告诉；讲述", "give information, instructions, or a story to someone", "通常突出信息接收者，常直接接人作宾语。", ["tell someone something", "tell someone to do", "tell the truth"], "中性；叙事和指令中常见。", "不能说 tell that the deadline changed 而省略接收者；可改为 say that。", "Please tell me why the meeting was cancelled.", "请告诉我会议为什么取消。"),
            "speak": item("verb", "说话；发言；会说某种语言", "use the voice, address an audience, or use a language", "偏说话能力、正式发言或单向表达。", ["speak English", "speak to someone", "speak at a conference"], "比 talk 稍正式；语言能力搭配固定用 speak。", "日常长时间聊天通常用 talk，不说 speak about it for hours。", "She will speak at the climate conference.", "她将在气候会议上发言。"),
            "talk": item("verb/noun", "交谈；讨论", "exchange ideas in conversation", "强调双方或多人持续交流。", ["talk to/with someone", "talk about something", "have a talk"], "日常、互动性强；也可用于非正式演讲。", "表示会某种语言时通常不用 talk English。", "We talked about the proposal over lunch.", "我们午餐时讨论了这项提案。"),
        },
    ),
    comparison(
        "look-see-watch",
        ("look", "see", "watch"),
        "中文都可能译成“看”，区别在主动性、持续时间和注意方式。",
        "look 是主动把视线转向；see 是视觉上注意到或看见；watch 是持续关注变化中的对象。",
        "转眼去看用 look，进入视野用 see，持续盯着变化用 watch。",
        (
            ("主动性", "look 和 watch 是主动行为；see 常表示视觉结果或自然注意到。"),
            ("持续性", "look 可以很短；watch 通常持续一段时间；see 不强调持续观察。"),
            ("典型对象", "look at a picture；see a person/problem；watch a film/game/child。"),
        ),
        {
            "look": item("verb/noun", "看；瞧；看起来", "direct your eyes or attention toward something", "主动转移视线或注意力，通常与 at 连用。", ["look at something", "look for something", "look like"], "中性高频；不同介词形成不同短语动词。", "有具体宾语时不能漏掉 at：look at the screen。", "Look at the chart before answering the question.", "回答问题前先看图表。"),
            "see": item("verb", "看见；看到；理解", "notice with the eyes or become aware of something", "强调视觉结果，也可引申为理解、会面或经历。", ["see something", "see that ...", "see a doctor"], "中性高频，义项很多。", "持续观看比赛通常用 watch，不说 see the match for two hours。", "I could see smoke above the building.", "我能看到楼顶上方的烟。"),
            "watch": item("verb/noun", "观看；注视；留意", "look at something carefully for a period as it changes", "持续观察动态对象或留意可能发生的变化。", ["watch a film", "watch someone do/doing", "watch out for"], "中性；影视、比赛、儿童和风险监测中常见。", "静态图片通常用 look at，而不是 watch a photograph。", "Researchers watched how the animals reacted.", "研究人员观察了这些动物如何反应。"),
        },
    ),
    comparison(
        "learn-study",
        ("learn", "study"),
        "中文都可能译成“学习”，但一个强调获得结果，一个强调投入过程。",
        "learn 表示学会、得知或逐渐掌握；study 表示系统阅读、练习或研究。",
        "投入过程用 study，获得知识或技能用 learn。",
        (
            ("结果与过程", "learn 常带有获得知识或能力的结果；study 本身不保证已经学会。"),
            ("宾语", "learn a skill/fact；study a subject/text/problem。"),
            ("其他义项", "learn 还可表示“得知”；study 还可表示“仔细观察、研究”。"),
        ),
        {
            "learn": item("verb", "学习；学会；得知", "gain knowledge, skill, or information", "关注知识、技能或信息进入认知。", ["learn to do", "learn about something", "learn that ..."], "中性高频。", "只表示坐下来复习两小时，通常说 study for two hours。", "She learned to analyse survey data in R.", "她学会了用 R 分析调查数据。"),
            "study": item("verb/noun", "学习；研究；仔细观察", "spend time examining or practising a subject", "关注有计划的学习、阅读、练习或研究过程。", ["study English", "study for an exam", "a study of"], "教育和学术语境高频。", "表示从消息中得知结果时不用 study，应使用 learn。", "He studied the report before the interview.", "他在采访前仔细研究了报告。"),
        },
    ),
    comparison(
        "borrow-lend",
        ("borrow", "lend"),
        "中文分别常译为“借入”和“借出”，参照方向相反。",
        "borrow 从别人处暂时拿来；lend 把自己的东西暂时给别人。",
        "东西朝我来是 borrow，东西从我出去是 lend。",
        (
            ("方向", "borrower 接收物品；lender 提供物品。"),
            ("介词", "borrow something from someone；lend something to someone / lend someone something。"),
            ("主语", "同一事件中，接收者 borrow，提供者 lend。"),
        ),
        {
            "borrow": item("verb", "借入；借用", "take and use something temporarily with permission", "主语是暂时取得物品的人。", ["borrow something", "borrow from someone", "borrow money"], "中性高频。", "不能说 borrow me your book；应说 lend me your book。", "Can I borrow your charger for an hour?", "我能借用你的充电器一小时吗？"),
            "lend": item("verb", "借出；出借", "allow someone to use something temporarily", "主语是提供物品的人。", ["lend someone something", "lend something to someone", "lend support"], "中性；lend support/credibility 有抽象用法。", "不能说 lend a book from the library；应说 borrow a book。", "The library lends laptops to students.", "图书馆把笔记本电脑借给学生。"),
        },
    ),
    comparison(
        "bring-take-fetch",
        ("bring", "take", "fetch"),
        "中文都可能译成“拿、带”，区别在移动方向和是否往返。",
        "bring 朝说话者或目标地点带来；take 从当前位置带走；fetch 去取并带回来。",
        "带来 bring，带走 take，去取回来 fetch。",
        (
            ("方向", "bring 指向参照点；take 离开参照点；fetch 包含去和回两个阶段。"),
            ("视角", "选择 bring/take 取决于说话者把哪个地点当作中心。"),
            ("动作结构", "fetch 通常是 go and get，不等于简单携带。"),
        ),
        {
            "bring": item("verb", "带来；拿来", "carry or cause something to come toward a place or person", "移动方向朝向说话者、听者或讨论中的目的地。", ["bring something to", "bring someone something", "bring about change"], "中性高频。", "从这里把垃圾带走通常用 take，不用 bring。", "Please bring your student ID to the exam.", "考试时请带上学生证。"),
            "take": item("verb", "带走；拿走；带到", "carry something away from the current reference point", "移动方向离开当前参照点。", ["take something to", "take someone home", "take away"], "中性高频，义项很多。", "请别人来你所在位置时通常说 bring it here，不说 take it here。", "Could you take these files to the office?", "你能把这些文件带到办公室吗？"),
            "fetch": item("verb", "去取来；接来", "go to get someone or something and return with it", "明确包含离开、取得、带回。", ["fetch something", "fetch someone from", "go and fetch"], "英式英语和日常指令中常见；美式英语也使用。", "已经拿在手里并带走时不用 fetch。", "I will fetch the documents from the printer.", "我去打印机那里把文件取来。"),
        },
    ),
    comparison(
        "job-work-career",
        ("job", "work", "career"),
        "中文都可能与“工作”有关，但分别指职位、劳动活动和长期职业路径。",
        "job 是具体职位或任务；work 是劳动活动或工作内容；career 是长期发展的职业生涯。",
        "一个职位是 job，做的事情是 work，长期路线是 career。",
        (
            ("可数性", "job 可数；work 作“工作”时通常不可数；career 可数。"),
            ("时间尺度", "job 可短期；work 描写活动；career 跨越多年发展。"),
            ("搭配", "get a job；do work / go to work；pursue a career。"),
        ),
        {
            "job": item("noun", "工作；职位；任务", "a particular paid position or specific task", "指一个可识别的职位或需要完成的任务。", ["get a job", "apply for a job", "do a good job"], "中性高频，可数。", "不能说 I have many works 表示多份工作；应说 jobs。", "She applied for a job at the university library.", "她申请了大学图书馆的一份工作。"),
            "work": item("noun/verb", "工作；劳动；工作内容", "effort or activity done to achieve a result", "强调付出的活动、任务内容或成果。", ["go to work", "work on something", "a piece of work"], "中性高频；作劳动活动时不可数。", "谈具体职位时通常用 job，不说 apply for a work。", "The research involves a great deal of fieldwork.", "这项研究包含大量实地工作。"),
            "career": item("noun", "职业；职业生涯", "a long-term course of professional development", "把多年职位、经验和发展看作一条持续路径。", ["pursue a career", "career development", "a career in medicine"], "职业规划和正式语境常见。", "临时兼职通常是 job，不一定构成 career。", "He hopes to build a career in public health.", "他希望在公共卫生领域发展职业生涯。"),
        },
    ),
    comparison(
        "affect-effect-influence",
        ("affect", "effect", "influence"),
        "中文都可能涉及“影响”，但词性、因果强度和表达角度不同。",
        "affect 通常是动词，表示产生影响；effect 通常是名词，表示结果；influence 强调改变倾向、判断或发展方向。",
        "动词影响 affect，结果名词 effect，潜移默化或左右方向 influence。",
        (
            ("词性", "affect 通常作动词；effect 通常作名词；influence 可作名词或动词。"),
            ("因果角度", "affect 指作用发生；effect 指产生的结果；influence 常较间接、渐进。"),
            ("固定结构", "affect something；have an effect on；influence someone/something。"),
        ),
        {
            "affect": item("verb", "影响；使发生变化", "produce a change in someone or something", "直接说明某因素对对象产生作用。", ["affect performance", "be affected by", "adversely affect"], "学术和日常语境都高频。", "需要名词时通常用 effect：have an effect on。", "Sleep deprivation can affect concentration.", "睡眠不足会影响注意力。"),
            "effect": item("noun", "影响；效果；结果", "a change or result caused by something", "把注意力放在已经产生或可观察的结果上。", ["have an effect on", "side effects", "take effect"], "中性和学术语境高频。", "effect 偶尔可作动词表示“促成”，但初学阶段不要与 affect 混用。", "The policy had little effect on housing costs.", "该政策对住房成本影响很小。"),
            "influence": item("noun/verb", "影响；影响力", "shape attitudes, decisions, or development, often indirectly", "常强调对选择、观点或长期发展方向的左右。", ["influence a decision", "have an influence on", "under the influence of"], "中性；社会科学和人物关系中常见。", "明确的即时物理作用不一定适合用 influence。", "Family expectations influenced her choice of major.", "家庭期望影响了她对专业的选择。"),
        },
    ),
    comparison(
        "effective-efficient",
        ("effective", "efficient"),
        "中文都可能译成“有效、高效”，但一个看是否达成目标，一个看资源使用。",
        "effective 表示方法确实产生预期结果；efficient 表示以较少时间、精力或成本完成任务。",
        "做得到是 effective，做得省是 efficient。",
        (
            ("评价标准", "effective 看结果；efficient 看投入产出比。"),
            ("可能组合", "一个方案可以有效但低效，也可以高效执行却没有解决真正问题。"),
            ("典型搭配", "effective treatment/strategy；efficient system/process/worker。"),
        ),
        {
            "effective": item("adjective", "有效的；能产生预期结果的", "successful in producing the intended result", "核心是目标是否真正实现。", ["an effective method", "highly effective", "effective against"], "中性、学术和专业语境高频。", "不要仅因速度快就称 effective；必须确认结果。", "The new treatment is effective against the infection.", "这种新疗法对该感染有效。"),
            "efficient": item("adjective", "高效的；效率高的", "achieving results with little wasted time, effort, or cost", "核心是减少浪费并优化过程。", ["an efficient system", "energy-efficient", "work efficiently"], "商业、工程和流程管理中高频。", "efficient 不自动表示目标选择正确或结果质量足够。", "The revised process is faster and more efficient.", "修改后的流程更快、更高效。"),
        },
    ),
    comparison(
        "economic-economical",
        ("economic", "economical"),
        "中文都可能与“经济”相关，但一个属于经济体系，一个表示节省。",
        "economic 描写经济、产业和财富体系；economical 描写使用成本低、不浪费。",
        "经济领域 economic，省钱省资源 economical。",
        (
            ("语义领域", "economic 对应 economy；economical 对应节约和性价比。"),
            ("典型名词", "economic growth/policy/crisis；economical car/use/method。"),
            ("可互换性", "economic solution 是经济层面的方案；economical solution 是成本较低的方案。"),
        ),
        {
            "economic": item("adjective", "经济的；经济学的", "related to the economy, trade, industry, or wealth", "描述宏观经济、政策、产业或财务条件。", ["economic growth", "economic policy", "economic inequality"], "正式、新闻和学术语境高频。", "表示某物省钱时通常不用 economic。", "The region has experienced rapid economic growth.", "该地区经历了快速的经济增长。"),
            "economical": item("adjective", "节约的；实惠的；经济省用的", "using money, fuel, time, or materials without waste", "强调成本低、消耗少或使用资源节制。", ["an economical car", "economical to run", "an economical use of space"], "消费、工程和日常评价中常见。", "不能用 economical growth 表示经济增长。", "The smaller printer is more economical to run.", "这台较小的打印机使用成本更低。"),
        },
    ),
    comparison(
        "remember-remind",
        ("remember", "remind"),
        "中文都与“记得、提醒”有关，但记忆发生者和触发者不同。",
        "remember 表示某人自己记得或想起；remind 表示某人或某物促使另一个人想起。",
        "自己想起 remember，让别人想起 remind。",
        (
            ("论元结构", "remember something/to do；remind someone of/about something / to do。"),
            ("角色", "remember 的主语是记忆者；remind 的主语是提醒来源。"),
            ("时间差异", "remember doing 回忆已做；remember to do 记得要做。"),
        ),
        {
            "remember": item("verb", "记得；想起", "retain or bring information back to mind", "记忆在主语本人脑中保持或重新出现。", ["remember something", "remember doing", "remember to do"], "中性高频。", "不能说 remember me to submit；应说 remind me to submit。", "Remember to attach the consent form.", "记得附上同意书。"),
            "remind": item("verb", "提醒；使想起", "cause someone to remember something", "外部的人、事件或线索触发另一个人的记忆。", ["remind someone to do", "remind someone of", "remind someone that"], "中性高频。", "remind 后通常需要被提醒的人，不能简单替换 remember。", "Please remind me to email the supervisor.", "请提醒我给导师发邮件。"),
        },
    ),
)
