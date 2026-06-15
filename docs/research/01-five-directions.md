# 奖励梯度分析器 — 5 个项目启动方向（合并研究版）

版本：v0.2 · 日期：2026-06-15
输入：本框架 v0.1 + 5 个本地 Codex(gpt-5.5/xhigh) 深度推理报告 + 4 维度 Claude 联网研究(含对抗式复核，附真实 2026 来源)
定位：把"深度推理"和"事实核查"两路研究合并，给出可以**立刻动手**的 5 个启动方向。

---

## 0. 这份文档怎么来的

- **Codex 侧(深度推理，无联网)**：5 个 agent 各深挖一个轴 —— 感知可行性 / 量化方法论 / 竞品与 GTM / 垂类与数据法务 / 产品与壁垒。报告在 `work/codex-1…5-*.md`。
- **Claude 侧(联网 grounding + 对抗复核)**：4 维度 —— 技术 SOTA / 设计科学 / 法务与 GTM / 竞品现状。每条关键结论都做了独立 web 复核(confirmed / refuted / uncertain)，附 URL。
- 两路**高度收敛**，且联网层把 Codex 的多个 `[ASSUMPTION]` 钉成了事实或纠正了方向。下面先列最重要的事实修正，再裁决两个战略张力，最后给 5 个方向。

---

## 1. 必须先接受的 3 条事实修正（都已联网核证）

**① 不要赌"VLM 直接看视频读出奖励"。这是全项目最大技术误区。**
- VideoGameQA-Bench(NeurIPS 2025)：最强 VLM 在"读游戏 UI/HUD"上只有 **~40%**，在视频里定位特定事件 **35–36%**。(arxiv.org/abs/2505.15952)
- 更狠的一篇：*Do VLMs Understand Human Engagement in Games?*(arXiv 2603.18480, 2026-03)——VLM 零样本预测玩家"投入度"只有 **~57%，低于 67.2% 的多数类基线**；有"视觉强度偏置"(画面越炫越判定为高投入，但人类标注无此相关)、时序翻转率是人类的 **18 倍**、且"高置信度反而更不准(38.5%)"。
- **含义**：感知层必须是 **specialist 管线(OCR-on-ROI + 屏幕状态/模板检测 + 音频 cue)+ VLM 仅复核候选帧**；"感知奖励"需要**自有标注数据微调的多模态模型**，没有现成模型。这既是技术风险，也正是"别人难以一键 bolt-on"的护城河来源。

**② 竞品白地真实存在，但窗口约 12–24 个月，且"读视频"的管线别人已经有了。**
- 没有任何在售产品从**游戏视频**里抽"玩家感知奖励节奏曲线"——白地确认(razer.com GDC 2026 blog；lysto.gg)。
- 但：**Razer QA Companion-AI 已在 GDC 2026 上线"零接入、视觉读录像"能力(AWS Marketplace)**，只是限定在 QA/bug；**Antidote** 已同时拿到 视频+面部+发声+**游戏内事件**(最危险的 fast-follower)；**Lysto**(~$15M，2022，web3 转型)做"录像+解说情绪"，离我们最近但走的是评论/情绪不是奖励结构。
- **含义**：护城河**不是**"第一个读视频"，而是**自有奖励事件/成本标注数据集 + 设计师信任/工作流锁定 + designed-vs-perceived 对齐**。

**③ 商业切口要换：first-party 优先，竞品拆解是法务高危区。**
- 爬 Twitch/YouTube VOD 训练或交付，**无论是否构成 fair use，都先违反两家平台 ToS**(YouTube/Twitch 条款已核)。
- 训练侧：Bartz v. Anthropic(2025-06)认为训练"极具转换性"可 fair use，**但前提是来源干净**(Anthropic 仍为盗版来源赔付至多 $1.5B)。
- **竞品拆解报告 = 最高风险**：最像 ROSS v. Thomson Reuters(2025-02)败诉形态(用他人内容造出替代品)，再叠加游戏 EULA 的"仅限个人非商业"。
- 最安全姿态：**客户上传自己游戏的 playtest 录像(自有+已获同意)**——标准可融资 SaaS 数据模型；需要 DPA、GDPR/未成年人同意、"默认不拿客户素材训练"。
- GTM 事实：买家是 **$1M+(尤其 $10M+ AAA) 工作室里的 GUR/UX lead 或 producer**；>50% 工作室没有 playtest 预算、~45% 花 $0；单次 study 预算约 **$400–$5K**(年度研究预算才到 $2.5K–$50K)。行业原话痛点：**"We need more people to analyze the videos."**

---

## 2. 两个战略张力的裁决

**张力 A — 首发垂类：deckbuilder vs Hades/roguelite。**
Codex-4 主张 deckbuilder(数据最干净、UI 稳定、OCR 能用)；Codex-1 主张 Hades(才能证明是"gameplay video"而非"OCR dashboard")。
→ **裁决：deckbuilder 先行(Slay the Spire / Balatro / Monster Train)，Hades/roguelite 作 fast-follow。** 理由：事实①说明"读 HUD/读视频"是头号风险，deckbuilder 把这个风险压到最低，能最快产出"录像→奖励曲线→设计师认可"的闭环；Hades 留到管线跑通后再证明"动作视频也行"。

**张力 B — beachhead：竞品首小时拆解 vs first-party FTUE 审计。**
Codex-3 主张竞品拆解(最快拿钱、无 SDK/隐私之争)；但法务维度证明竞品拆解是**最高法律风险**。
→ **裁决：以 first-party FTUE/playtest 奖励审计为核心销售品；竞品拆解降级为"律师把关、只输出抽象指标/不再分发原始素材"的内容营销与内部 benchmark 用途，不作为核心交付，且绝不用于训练。** 这同时命中真实买家痛点("没人手分析视频")并避开 ROSS 式风险。

---

## 3. 五个启动方向

> 顺序即推荐优先级。方向 1+2 立刻并行启动；3 紧随；4 在 1–3 出信号后建；5 与 1–4 并行做客户验证。

### 方向 1 — 技术 Spike：单 deckbuilder 的 specialist 感知管线 + `reward_moment` 抽取
**一句话**：2 周内在一款 deckbuilder 上，用 specialist-heavy 管线证明"录像能稳定抽出可感知奖励时刻"。
**为什么(证据)**：这是全项目可证伪性最高的假设；事实①说明不能靠 VLM 读 HUD。Codex-1/4 一致主张 specialist 管线 + VLM 仅复核 + 项目级模板；联网层确认 specialist/音频路 **<10 分钟/30 分钟** 现实、VLM-per-frame 不现实。
**首步动作**：
- 选 Slay the Spire(主)；ffmpeg 1fps 全局 + 触发时局部升 4–8fps；音频 16kHz。
- PaddleOCR PP-OCRv5 **只读固定 ROI**(金币/能量/分数/结算关键词)；颜色/模板检测 reward/shop/victory 屏；CLAP/onset 做音频 cue(最便宜最稳的主信号之一)。
- VLM 只对低置信候选帧问"获得/预览/商店/非奖励?"。
- 输出两级：先 `reward_moment`(感知时刻)，后再拆 `reward_items`。
**验收/验证**：明显奖励 **recall ≥0.6、precision ≥0.8(精确优先)**、timestamp 中位误差 <2s；产出可读 timeline + reward density 曲线。
**关键不确定性**：单垂类 precision 能否 >0.8？若连 deckbuilder 都不行，整条 video-only 路线降级为"人工辅助标注工具"。
**工作量**：1 eng + 0.3 标注，~2 周。

### 方向 2 — 数据与标注资产：黄金集 + 标注规范 + 奖励本体（真正的护城河）
**一句话**：把"事件定义 + 自录干净数据 + 标注流水线"做成可复用资产——这是最能抵御 bolt-on 的护城河。
**为什么(证据)**：事实①说明需要自有标注数据微调；事实②说明 Razer/Antidote 已有读视频的"管线",护城河只能是数据+信任。Codex-2/5 强调"gold-label 规范决定管线成败""数据集长期最强但启动慢"。
**首步动作**：
- **自录** Slay the Spire/Balatro/Monster Train 干净录像(固定分辨率、无 overlay、无解说)25–40 小时；**公开 VOD 仅作 reference，不进训练、不进交付**(法务硬约束)。
- Label Studio 做**时间段事件标注**(不先做像素 bbox)；schema 见框架 §19 扩展(加 `source_rights`、`success_contingent`、`screen_context`、`boundary/semantic confidence`)。
- 定 **core 奖励本体 + genre 模板**(resource/power/progression/unlock/completion/choice_expansion/mastery_feedback/sensory_celebration)。
- LLM/VLM 预标注 → 人工确认，把成本压到 ~0.3× 视频时长。
**验收/验证**：每标题 **300–600 事件**；事件存在 **Cohen's κ ≥0.80**、类型 macro-F1 ≥0.85、边界误差 <1.5s；强度**不打 1–10 分**，用序数 + pairwise。
**关键不确定性**：商业游戏自录用于内部训练 + 付费 SaaS 分析的权利边界(需 counsel)。若逐游戏授权，转向 partner studio / 授权或开源游戏素材。
**工作量**：1–2 team-weeks 起,持续滚动。

### 方向 3 — 评分与可信度方法论：interest/reward 曲线 + 分解式 latent score + 验证协议
**一句话**：让曲线不是玄学——用设计师本来就信的"interest curve"框定输出，分数可解释、可校准、可证伪。
**为什么(证据)**：设计科学维度确认 **interest curve(Jesse Schell) 是设计师最认的构念**——直接把输出叫 interest/reward 曲线即继承合法性；**SDT/PENS(胜任/自主)** 比泛"fun"更能预测留存；**CHI 2024(Kao et al., n=1,699)** 证明起作用的是**"可读、与成功挂钩、分级"的反馈 + 不确定成功(好奇)**，而**单纯加大 juice 反而降低动机**——所以**不能只数 reward density**。**避免 Skinner/多巴胺叙事**(folk psychology，对资深设计师反伤信任)。Codex-2 的"分解式 latent score、3 条独立曲线"与此完全一致。
**首步动作**：
- 输出框定为 **interest/reward 曲线**；分数用**分解式 bounded latent score**(utility / competence-signal / choice-value / salience / novelty / goal-relevance 的加权 sigmoid)+ UI 显示分解条；**禁用乘法黑箱**。
- **三轴并列**：reward / effort-frustration / recovery(负反馈不入奖励轴)。
- 检测**"成功挂钩的可读反馈"**而非原始密度;主指标用 `compensation = R − β·累计effort`,ratio 仅辅助。
- 写**验证协议**:设计师 pairwise(Bradley-Terry,held-out ≥0.70)、人工一致性、**blind build 对比命中已知问题 ≥4/5、每 10 分钟误报 ≤1**、(有 telemetry 时)quit/pause 预测增量。
**验收/验证**:把上面协议跑在方向 1 的输出上;3+ 条发现被 lead designer 标"值得进会"。
**关键不确定性**:设计师对"相对付出是否有回报感"的 pairwise 一致性能否 ≥0.70?不行则 reward_score 降级为可视化辅助。
**工作量**:方法设计 3–5 天;标注+pairwise 实验 2–3 team-weeks。

### 方向 4 — 产品形态：HITL 校准/复核工作台 MVP + compare view（first-party SaaS）
**一句话**:产品本体是"让设计师快速把录像变成可争论证据"的校准/复核台,不是模型;第二次分析必须便宜。
**为什么(证据)**:Codex-5 —— 模型只把 30 分钟压成 80–200 个候选 + 5–10 个可疑区间,**项目模板(UI 区域+权重+目标曲线)是最强短期壁垒**。GTM 维度 —— 卖点是 **"analyst capacity in software"**(命中"没人手看视频"的原话痛点)。法务维度 —— first-party 数据姿态(DPA、默认不训练、GDPR)是企业单的入场券(80% 中端 SaaS RFP 要 SOC2 Type II)。
**首步动作**:
- MLP:上传 → 30 分钟内拿到 **可审阅/可修正/可比较** 的 reward timeline。
- **项目模板**:region-select、ignored regions(facecam/overlay)、reward 本体、权重、目标曲线模板(steady drip / sawtooth / crescendo-to-boss)。
- **证据绑定**:每条 finding 带 metric + 可跳转 clip + confidence 分解;只给"验证建议"不给"加宝箱"式判决。
- **compare view(Build A/B)放进 MLP**,不延后(团队复购的核心)。
- 量化目标:首次人工 ≤20 分钟、第二次同项目人工 ≤6 分钟;每次结束显示"manual actions / template updates / next-run est."。
**验收/验证**:设计伙伴**每周**愿意用;第二次同项目人工 <10 分钟(否则没形成工作流价值)。
**关键不确定性**:设计师首次校准愿意投入的时间上限?>10–15 分钟就要大幅收缩 HITL,只 review 高影响候选、权重按类型不按事件调。
**工作量**:3 人 8–10 周出 MLP(同时做 SDK 会膨胀到 14–18 周——别做)。

### 方向 5 — GTM 验证：first-party FTUE/playtest 奖励审计设计伙伴（竞品拆解不作核心）
**一句话**:在烧钱建全套 SaaS 前,先用 2–3 份"半自动 + 人工"的 first-party FTUE 奖励审计验证有人付费。
**为什么(证据)**:Codex-3 的"先服务化、后产品化"正确,但其 beachhead(竞品拆解)被法务维度否决(ROSS 风险);GTM 维度把买家、预算、痛点钉死。差异化:vs Lysto/PlaytestCloud(读 transcript/情绪) 与 Unity/PlayFab(要埋点) 的缝隙 = **从视觉流读"感知奖励节奏"**;vs Machinations(设计的曲线) = **designed-vs-perceived 差距**。
**首步动作**:
- 找 1–2 个有 GUR/UX lead 或 producer、dev budget $1M+(理想 $10M+)的工作室做 **design partner**。
- 交付:用客户**自有** FTUE/前 1 小时录像,产出 reward timeline + `reward_gap P50/P90`+ density + 3–8 条带 clip 的发现 + 可测试改动假设(对齐 FTUE 启发式:首个奖励/到核心循环/首胜时间)。
- 价格落在 study 预算区间($400–$5K/study,审计包可往 $5–10K)。
- 竞品拆解:**仅用自录/授权素材做内部 benchmark 与 thought-leadership 内容**,律师把关、只出抽象指标、不再分发帧、不进训练。
**验收/验证**:每份报告 ≥3 条非显然且被采纳进设计讨论的 insight;人工看片时间省 ≥50%;有客户愿意续约/付月费。
**关键不确定性**:客户是否为"perceived reward pacing"**单独付费**,还是只当 playtest 套件里的免费维度?——这是是否成立为独立产品的命门。
**工作量**:2–4 周(与 1–4 并行)。

---

## 4. 推荐 90 天序列

| 周 | 主线 | 里程碑 |
|---|---|---|
| W1–2 | 方向 1(技术 spike)+ 方向 2(自录+标注规范)并行;方向 5 开始约设计伙伴 | deckbuilder reward_moment 管线出第一条 density 曲线;100–150 事件黄金集 |
| W3–5 | 方向 3(评分+验证协议)接到方向 1 输出;方向 2 滚动到 300+ 事件/标题 | 分解式 score + 三轴曲线;pairwise 校准实验跑通 |
| W4–8 | 方向 4(HITL 工作台 MLP)开建;方向 5 交付首份 first-party 审计 | 上传→可修正 timeline + compare view;1 个设计伙伴每周用 |
| W8–12 | 把 Hades/roguelite 作 fast-follow 接入;telemetry **importer**(非 SDK)定 schema + sync marker | 证明"动作视频也行";跑出第一例 designed/perceived/actual 错位洞察 |

**贯穿原则**:precision 优先于 recall(少报胜过乱报);每条结论必须可跳证据;不碰 Skinner/多巴胺话术;公开 VOD 永远只做 reference。

---

## 5. 还需尽快核查的高杠杆问题

1. **法务**:商业游戏自录素材用于(a)内部训练、(b)付费 SaaS 分析 的权利边界 → 必须 counsel review(决定数据战略是否要 partner/授权游戏)。
2. **客户**:perceived reward pacing 是否值得单独付费 → 方向 5 的设计伙伴对话直接回答。
3. **技术**:单 deckbuilder precision 能否 >0.8、跨标题泛化代价 → 方向 1/2 直接回答。
4. **方法**:设计师 pairwise 一致性 ≥0.70 → 方向 3 实验回答。
5. **竞品监控**:Antidote / Lysto 是否在 roadmap 里加 reward/progression pacing;Razer QA 是否从 bug 扩到 design feel(变更日志/销售对话跟踪)。

---

## 附:关键来源（已联网核证）

- VideoGameQA-Bench(VLM 读游戏 UI ~40%):https://arxiv.org/abs/2505.15952 · https://asgaardlab.github.io/videogameqa-bench/
- VLM 难懂玩家投入(57% < 67.2% 基线，2026-03):https://arxiv.org/abs/2603.18480
- CHI 2024 *Juicy Game Feedback*(可读/成功挂钩反馈 > 单纯加 juice):https://dl.acm.org/doi/10.1145/3613904.3642656
- Gemini 长视频(1fps、$1–3/30min):https://ai.google.dev/gemini-api/docs/video-understanding
- PP-OCRv5(艺术字仅 ~0.64,需逐游戏校准):http://www.paddleocr.ai/main/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5.html
- ROSS v. Thomson Reuters(竞品替代品败诉):https://www.jenner.com/en/news-insights/publications/client-alert-court-decides-that-use-of-copyrighted-works-in-ai-training-is-not-fair-use...
- Bartz v. Anthropic(训练可 fair use 但来源要干净):https://www.goodwinlaw.com/en/insights/publications/2025/06/alerts-practices-aiml-district-court-issues-ai-fair-use-decision
- GUR 预算与买家(>50% 无 playtest 预算;痛点"没人手分析视频"):https://gamesuserresearch.com/the-2023-playtest-survey/ · https://gamesuserresearch.com/how-to-budget-for-games-user-research/
- Razer QA Companion-AI(GDC 2026 视觉读录像，限 QA):https://www.razer.com/blog/ai-that-plays-to-test-razer-qa-companion-ai-at-gdc-2026
- 设计科学:interest curve / SDT-PENS / Slay the Spire metrics(GDC 2019)— 见 work 内各 dimension 来源清单。
