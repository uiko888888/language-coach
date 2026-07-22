from __future__ import annotations

try:
    from .lexical_compare_data import comparison, item
except ImportError:
    from lexical_compare_data import comparison, item


def lookalike(slug, terms, overlap, summary, memory_rule, grammar, items):
    return comparison(
        slug,
        terms,
        overlap,
        summary,
        memory_rule,
        (
            ("拼写锚点", memory_rule),
            ("词性与句位", grammar),
            ("核对方法", "先看句中需要的词性和搭配，再核对易错字母；不要只凭中文译义或字形猜词。"),
        ),
        items,
        confusion_type="lookalike",
    )


LOOKALIKE_CURATED_COMPARISONS = (
    lookalike(
        "compliment-complement", ("compliment", "complement"),
        "两词拼写和读音接近，也都可涉及正面关系，但一个是赞美，一个是补足。",
        "compliment 表示称赞；complement 表示使整体更完整或相配。",
        "夸人用带 i 的 compliment；补全整体用带 e 的 complement。",
        "两词都可作名词或动词，但宾语角色不同：pay a compliment；complement a design。",
        {
            "compliment": item("noun/verb", "赞美；称赞", "an expression of praise or the act of praising", "对人的表现、外貌或选择表达赞许。", ["pay someone a compliment", "compliment someone on", "a sincere compliment"], "中性；人际交流常见。", "不能用来表示颜色、能力或部件彼此补足。", "She complimented him on the clarity of his presentation.", "她称赞他的演示表达清晰。"),
            "complement": item("noun/verb", "补充；补足；相配之物", "something that completes or goes well with another thing", "强调两部分结合后更完整或更协调。", ["complement each other", "a perfect complement to", "complement the design"], "中性及正式写作常见。", "不能表示直接向某人说好话。", "The visual examples complement the written explanation.", "这些视觉示例补充了文字说明。"),
        },
    ),
    lookalike(
        "principal-principle", ("principal", "principle"),
        "两词读音相近，中文都可能出现在学校、规则或重要性语境中。",
        "principal 是主要的或负责人；principle 是原则、原理。",
        "principal 结尾 pal，可联想负责人；principle 结尾 ple，指规则或原理。",
        "principal 可作形容词或可数名词；principle 只作名词。",
        {
            "principal": item("adjective/noun", "主要的；负责人；本金", "most important, or the person in charge", "修饰核心因素，或指学校负责人、委托关系中的本人及本金。", ["the principal reason", "a school principal", "principal and interest"], "正式和教育、金融语境常见。", "表示道德原则或科学原理时不能用 principal。", "The principal reason for the delay was a lack of data.", "延误的主要原因是缺少数据。"),
            "principle": item("noun", "原则；原理；准则", "a basic rule, belief, or explanation", "指指导行为的准则或解释现象的基础规律。", ["a guiding principle", "in principle", "the principle of"], "正式、学术和日常评价均常见。", "不能作形容词修饰 reason，也不指学校负责人。", "The policy is based on the principle of equal access.", "该政策以平等获取原则为基础。"),
        },
    ),
    lookalike(
        "stationary-stationery", ("stationary", "stationery"),
        "两词只差一个元音，读音相同，但意义完全不同。",
        "stationary 表示静止不动；stationery 表示文具。",
        "stationary 的 a 联想 at rest；stationery 的 e 联想 envelope。",
        "stationary 是形容词；stationery 是不可数名词。",
        {
            "stationary": item("adjective", "静止的；不动的", "not moving or not changing", "描述物体、位置或数值保持不动。", ["remain stationary", "a stationary vehicle", "stationary equipment"], "中性及技术语境常见。", "不能表示纸张、信封等办公用品。", "The vehicle was stationary when the collision occurred.", "碰撞发生时车辆处于静止状态。"),
            "stationery": item("noun", "文具；信纸信封", "materials used for writing and office work", "集合表示纸、信封、笔等书写办公用品。", ["office stationery", "a stationery supplier", "buy stationery"], "中性；通常不可数。", "不要写 a stationery 表示一件文具，可说 an item of stationery。", "The department ordered recycled stationery for the office.", "该部门为办公室订购了再生文具。"),
        },
    ),
    lookalike(
        "personal-personnel", ("personal", "personnel"),
        "两词词根相近，中文都与人有关，但一个描述个人，一个指人员。",
        "personal 是个人的；personnel 是组织中的人员或人事部门。",
        "personal 只有一个 n，修饰个人事物；personnel 有双 n，表示一群人员。",
        "personal 是形容词；personnel 是集合名词。",
        {
            "personal": item("adjective", "个人的；私人的；亲自的", "belonging to or concerning one particular person", "修饰个人信息、意见、经历或私人物品。", ["personal information", "a personal opinion", "personal experience"], "中性高频。", "不能直接表示公司员工总数。", "Do not include personal information in the public file.", "不要在公开文件中包含个人信息。"),
            "personnel": item("noun", "全体人员；人事部门", "people employed by an organization", "把机构中的员工视为一个群体，也可指人事管理职能。", ["medical personnel", "military personnel", "personnel records"], "正式、组织和行政语境常见。", "不能放在 opinion 前表示个人意见。", "Only authorised personnel may enter the laboratory.", "只有获授权人员可以进入实验室。"),
        },
    ),
    lookalike(
        "desert-dessert", ("desert", "dessert"),
        "两词只差一个 s，但读音重音和含义不同。",
        "desert 可指沙漠或遗弃；dessert 是餐后甜点。",
        "dessert 多一个 s，可联想 sweet；desert 只有一个 s。",
        "desert 可作名词或动词；dessert 只作名词。",
        {
            "desert": item("noun/verb", "沙漠；遗弃；擅离", "a dry region, or to abandon someone or something", "名词指干旱地貌；动词指离弃职责、地点或需要帮助的人。", ["the Sahara Desert", "desert a post", "be deserted"], "地理义中性；动词义较正式。", "表示餐后食物时必须写 dessert。", "Many residents deserted the town after the mine closed.", "矿场关闭后，许多居民离开了这座小镇。"),
            "dessert": item("noun", "甜点；餐后甜食", "sweet food eaten at the end of a meal", "专指主餐后的甜食。", ["have dessert", "a dessert menu", "fruit for dessert"], "日常高频。", "不能表示沙漠或遗弃。", "We shared a fruit tart for dessert.", "我们餐后一起吃了一份水果挞。"),
        },
    ),
    lookalike(
        "advice-advise", ("advice", "advise"),
        "两词意义相关、拼写相近，但词性和尾音不同。",
        "advice 是建议这个名词；advise 是提出建议这个动词。",
        "advice 的 c 对应名词；advise 的 s 对应动词。",
        "advice 是不可数名词；advise 后可接人、doing 或 that 从句。",
        {
            "advice": item("noun", "建议；忠告", "an opinion about what someone should do", "把建议作为信息或内容来表达。", ["give advice", "a piece of advice", "seek legal advice"], "中性高频；不可数。", "不能说 an advice；使用 a piece of advice。", "The tutor gave me useful advice on structuring the essay.", "导师就论文结构给了我有用的建议。"),
            "advise": item("verb", "建议；劝告；通知", "recommend an action or give professional guidance", "表示向某人提出建议或正式告知。", ["advise someone to do", "advise doing", "advise that"], "中性及专业语境常见。", "需要名词作 give 的宾语时用 advice。", "The doctor advised her to reduce her workload.", "医生建议她减少工作量。"),
        },
    ),
    lookalike(
        "device-devise", ("device", "devise"),
        "两词拼写和读音接近，但一个是物件名词，一个是设计动作。",
        "device 是装置或手段；devise 是构想、设计。",
        "device 的 c 是名词；devise 的 s 是动词。",
        "device 是可数名词；devise 是及物动词。",
        {
            "device": item("noun", "设备；装置；手段", "a piece of equipment or a method used for a purpose", "指具体器材，也可指写作手法或策略。", ["a mobile device", "a medical device", "a literary device"], "技术及日常语境高频。", "不能放在 plan 前表示构想计划的动作。", "The device records temperature every minute.", "该设备每分钟记录一次温度。"),
            "devise": item("verb", "设计；构想；想出", "create a plan, method, or system through thought", "强调经过思考形成方案、方法或系统。", ["devise a plan", "devise a method", "carefully devised"], "较正式，学术和工作语境常见。", "表示一台实体设备时使用 device。", "The team devised a simpler method for collecting responses.", "团队设计了一种更简单的答复收集方法。"),
        },
    ),
    lookalike(
        "loose-lose", ("loose", "lose"),
        "两词只相差一个 o，发音和词性也不同。",
        "loose 表示松的；lose 表示失去或输掉。",
        "loose 有两个 o，像留出了松动空间；lose 只有一个 o。",
        "loose 通常是形容词；lose 是动词，过去式 lost。",
        {
            "loose": item("adjective", "松的；宽松的；未固定的", "not tight, fixed, or firmly controlled", "描述衣物、部件、连接或控制不紧。", ["a loose connection", "loose clothing", "come loose"], "中性高频。", "不能表示丢失物品或输掉比赛。", "A loose cable caused the monitor to flicker.", "一根松动的电缆导致显示器闪烁。"),
            "lose": item("verb", "失去；遗失；输掉", "stop having something or fail to win", "表示不再拥有、找不到、错过或在竞争中失败。", ["lose a key", "lose interest", "lose a game"], "中性高频。", "形容衣服宽松时使用 loose。", "We may lose access if the licence expires.", "如果许可证到期，我们可能会失去访问权限。"),
        },
    ),
    lookalike(
        "quiet-quite", ("quiet", "quite"),
        "两词字母相同但次序不同，读音、词性和意义都不同。",
        "quiet 表示安静；quite 是程度副词，表示相当或完全。",
        "quiet 中 e 在 t 前；quite 中 t 在 e 前。先看句中是否需要程度副词。",
        "quiet 多作形容词；quite 只能作副词修饰形容词、副词或限定表达。",
        {
            "quiet": item("adjective/noun", "安静的；寂静", "making little noise or involving little activity", "描述声音小、环境平静或人不多话。", ["a quiet room", "keep quiet", "a quiet period"], "中性高频。", "不能用来加强 good、different 等形容词。", "The library is usually quiet in the early morning.", "图书馆清晨通常很安静。"),
            "quite": item("adverb", "相当；完全；很", "to a noticeable degree, or completely in some contexts", "修饰程度；具体强度受英美用法和被修饰词影响。", ["quite difficult", "quite a few", "quite certain"], "中性高频。", "不能作表语表示没有声音。", "The two proposals are quite different in scope.", "这两个方案在范围上相当不同。"),
        },
    ),
    lookalike(
        "conscience-conscious", ("conscience", "conscious"),
        "两词共享词根且拼写接近，但一个是道德判断名词，一个是意识状态形容词。",
        "conscience 是良知；conscious 是清醒的、意识到的。",
        "conscience 结尾 -ence，是名词；conscious 结尾 -ous，是形容词。",
        "conscience 常与 moral/guilty 搭配；conscious 常接 of 或 that。",
        {
            "conscience": item("noun", "良心；良知；道德意识", "the inner sense of what is morally right or wrong", "表示对行为是否合乎道德的内在判断。", ["a guilty conscience", "a clear conscience", "a matter of conscience"], "中性及正式语境常见。", "不能表示人在事故后是否清醒。", "He refused the request as a matter of conscience.", "他出于良知拒绝了这一请求。"),
            "conscious": item("adjective", "清醒的；意识到的；有意识的", "awake, aware, or deliberately noticing something", "表示具有知觉，或察觉到事实、影响和选择。", ["be conscious of", "remain conscious", "a conscious decision"], "中性及医学语境高频。", "作为名词表示良知时必须使用 conscience。", "Researchers were conscious of the limits of the sample.", "研究人员意识到了样本的局限。"),
        },
    ),
    lookalike(
        "precede-proceed", ("precede", "proceed"),
        "两词拼写和读音接近，但一个表示在前，一个表示继续。",
        "precede 是先于；proceed 是继续进行或前往。",
        "precede 中 pre- 表示 before；proceed 中 pro- 表示 forward。",
        "precede 是及物动词；proceed 常不及物，并接 with/to。",
        {
            "precede": item("verb", "先于；在……之前发生", "come before something in time, order, or position", "说明某事件、部分或对象位于另一对象之前。", ["precede the meeting", "be preceded by", "the years preceding"], "正式和学术语境常见。", "表示继续下一步时不能用 precede。", "A short briefing will precede the interview.", "面试前会先进行简短说明。"),
            "proceed": item("verb", "继续进行；前往；着手", "continue an action or move forward", "表示在确认条件后继续，或前往某处。", ["proceed with", "proceed to do", "proceed to the exit"], "较正式；说明和程序语境常见。", "通常不直接接事件作宾语来表示先于它。", "Once consent is recorded, the researcher may proceed with the interview.", "记录同意后，研究人员可以继续访谈。"),
        },
    ),
    lookalike(
        "cite-site-sight", ("cite", "site", "sight"),
        "三词同音或近同音，拼写不同，分别涉及引用、地点和视觉。",
        "cite 引用；site 地点或网站；sight 视力、景象或看见。",
        "cite 对应 citation；site 对应 location；sight 对应 see。",
        "cite 主要作动词；site 主要作名词；sight 主要作名词，也可作动词。",
        {
            "cite": item("verb", "引用；引证；列举", "refer to a source or example as evidence", "在写作中注明来源，或列举事例支持判断。", ["cite a source", "cite evidence", "frequently cited"], "学术、法律和正式写作高频。", "表示网页或地理位置时使用 site。", "The report cites three independent studies.", "该报告引用了三项独立研究。"),
            "site": item("noun/verb", "地点；场所；网站；选址", "a place where something exists or happens", "指物理地点，也可缩写指 website。", ["a research site", "a construction site", "a news site"], "中性和技术语境高频。", "不能表示参考文献引用或视觉景象。", "The team visited each field site twice.", "团队两次走访了每个实地研究点。"),
            "sight": item("noun/verb", "视力；景象；看见", "the ability to see or something that is seen", "描述视觉能力、进入视野的景物或观察到目标。", ["at first sight", "lose sight of", "a familiar sight"], "中性高频。", "表示论文引证时使用 cite。", "The northern lights were an unforgettable sight.", "北极光是一幅令人难忘的景象。"),
        },
    ),
    lookalike(
        "later-latter", ("later", "latter"),
        "两词只差一个 t，但一个涉及时间，一个指前述两者中的后者。",
        "later 表示更晚；latter 表示两者中的后者。",
        "later 与 late 同根；latter 有双 t，用于 two 中的第二项。",
        "later 可作副词或形容词；latter 作形容词或代词化名词。",
        {
            "later": item("adverb/adjective", "后来；稍后；较晚的", "at a time after the present or after another time", "比较或指示时间先后。", ["later that day", "see you later", "a later version"], "中性高频。", "不能指前面列出的两个选项中的第二个。", "A later version corrected the calculation error.", "后来的版本修正了计算错误。"),
            "latter": item("adjective/noun", "后者；后一段的", "the second of two people or things just mentioned", "回指明确列出的两个对象中的第二个。", ["the latter option", "in the latter case", "the former and the latter"], "书面和正式语境常见。", "列出三个以上对象时不要含糊地用 latter。", "We considered interviews and surveys, but chose the latter.", "我们考虑了访谈和问卷，但选择了后者。"),
        },
    ),
    lookalike(
        "emigrate-immigrate", ("emigrate", "immigrate"),
        "两词都表示跨国迁居，但参照方向相反。",
        "emigrate 从原国家迁出；immigrate 迁入目标国家。",
        "e- 联想 exit，i- 联想 into。",
        "两词都是不及物动词：emigrate from；immigrate to。",
        {
            "emigrate": item("verb", "移居国外；移出", "leave one's country to live permanently elsewhere", "从出发国视角描述离开并定居海外。", ["emigrate from", "emigrate to", "families who emigrated"], "中性及历史、人口研究语境常见。", "从接收国视角强调迁入时使用 immigrate。", "Her grandparents emigrated from Ireland in the 1950s.", "她的祖父母在二十世纪五十年代从爱尔兰移居国外。"),
            "immigrate": item("verb", "移民入境；迁入", "come to another country to live permanently", "从目的国视角描述进入并定居。", ["immigrate to", "immigrate legally", "people who immigrated"], "中性及政策、人口研究语境常见。", "说明离开原国家时使用 emigrate from。", "They immigrated to Canada after completing university.", "他们大学毕业后移民到了加拿大。"),
        },
    ),
)
