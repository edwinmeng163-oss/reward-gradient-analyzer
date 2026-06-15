# Agent 3 报告：竞品、市场切口与 GTM

## 结论先行

这是一个可以成立的产品方向，但**不能以“AI playtest summary 的又一个 dashboard”启动**。如果只做 reward timeline、reward density 曲线、自动高亮片段，Lysto / PlaytestCloud / Antidote 很容易把它做成现有 playtest 报告里的一个 tab。真正可防守的切口是：

> 面向设计/发行团队的“首小时/FTUE 奖励节奏审计”，从录像中提取玩家实际感知到的奖励、成本和反馈强度，并和同品类竞品或历史 build 做对照。

我会把它先做成**服务化 + 半自动工具**，而不是一上来做纯 SaaS。理由很简单：早期客户买的不是模型准确率，而是“这份报告能不能让设计会少争 2 小时，并指出一个可验证改动”。自动化是 margin，报告质量是 wedge。

## 竞品 2x4 地图：数据源 × 任务

以下基于框架和常识推断；未核验的产品能力标记为 `[ASSUMPTION — verify]`。

| 工具 | 主要数据源 | QA | UX summary | Economy / design | Coaching |
|---|---|---:|---:|---:|---:|
| Lysto AI | playtest 录像、玩家评论、问卷 `[ASSUMPTION — verify]` | 低 | 高 | 低-中 | 无 |
| PlaytestCloud | 录像、think-aloud、transcript、问卷 | 低 | 高 | 低 | 无 |
| Antidote | playtest 录像、问卷、访谈/AI insights `[ASSUMPTION — verify]` | 低 | 高 | 低 | 无 |
| modl.ai | 游戏运行画面、agent 行为、OCR/视觉 `[ASSUMPTION — verify]` | 高 | 低 | 中，偏覆盖/平衡测试 | 无 |
| Razer QA Companion-AI | 画面/录像、bug 复现上下文 `[ASSUMPTION — verify]` | 高 | 低 | 低 | 无 |
| GameDriver | engine/SDK/API 自动化、测试脚本 | 高 | 无 | 中，偏回归验证 | 无 |
| GameAnalytics / Unity Analytics / PlayFab | SDK telemetry、事件、漏斗、留存 | 低 | 中 | 高，依赖埋点 | 无 |
| Machinations | 手工经济模型、模拟参数 | 无 | 无 | 高，设计前/设计中 | 无 |
| Balancy | liveops 配置、经济参数、A/B/remote config `[ASSUMPTION — verify]` | 低 | 无 | 高，偏运营调参 | 无 |
| Omnic.AI / trophi.ai | 玩家录像、比赛/对局数据 `[ASSUMPTION — verify]` | 无 | 低 | 低 | 高 |

把坐标压成更直观的白区：

- **Telemetry/SDK × economy-design**：GameAnalytics、Unity、PlayFab、Machinations、Balancy 已经强。这里不要正面竞争。它们回答“内部系统发生了什么”和“数值模型是否成立”。
- **Video/recording × UX-summary**：Lysto、PlaytestCloud、Antidote 已经强。它们回答“玩家说了什么、哪里困惑、哪里喜欢”。
- **Video/recording × QA**：modl.ai、Razer QA、GameDriver 相关能力更强。它们回答“bug、卡关、复现、覆盖率”。
- **Video/recording × coaching**：Omnic/trophi 已经在玩家改进方向。它们回答“玩家如何打得更好”。
- **真正白区**：**Video/recording × economy/design 的感知层**。不是模拟经济，也不是埋点漏斗，而是“玩家看见、听见、感受到的奖励节奏是否足够支撑成本”。这是系统策划、UX research、发行竞品研究之间的缝隙。

问题是：这个白区很窄。它不是“所有 playtest insight”，也不是“所有 economy analytics”。必须把语言收窄到 reward pacing、FTUE、first-hour、build comparison、competitor teardown。

## Feature 还是 Product？

**Feature 的诚实论证：**

如果输出只是“自动识别奖励事件 + 时间轴 + 若干洞察卡片”，它非常像 playtest 平台的增强功能。Lysto / PlaytestCloud 已经有录像、transcript、问卷、玩家招募和客户信任；它们加一个 `reward_event` taxonomy、让 LLM 总结“奖励断档”，商业上比新工具更顺滑。Unity/PlayFab 也可以从 telemetry 侧加 reward pacing dashboard，并且数据更准。对于多数 studio，“又传一次视频到另一个工具”是摩擦。

**Product 的诚实论证：**

现有工具的弱点是：它们通常把录像变成“用户研究摘要”，而不是可复用的设计度量。Reward Gradient Analyzer 如果积累了类型专用 reward ontology、竞品 benchmark、项目级 UI 模板、pairwise reward strength calibration，就能成为“奖励体验审计系统”。尤其是竞品录像和公开首小时体验，不需要 SDK，telemetry 工具做不了。它能把 senior designer 人工拆片的工作结构化：每 30 分钟视频输出 20-80 个 reward events、3-8 个 pacing findings、对应 clip 和改动假设。

**我的判断：是产品，但必须服务化启动。**

最小可防守 wedge 不是“reward timeline view”，而是：

> 同一品类下，首小时/FTUE 的 perceived reward pacing benchmark：自家 build vs 2-3 个竞品 vs 设计目标曲线。

这比单个视频报告难复制，因为价值来自三层复合资产：类型本体、竞品样本库、设计解释框架。Lysto 可以加 reward timeline，但不一定愿意维护“Roguelite 首局奖励间隔 P50/P90”“mobile hero collector 第 0-10 分钟解锁节奏”“post-failure recovery reward pattern”这种设计 benchmark。

我不会先做：通用游戏识别、全自动 SaaS、实时分析、泛 UX insight、纯 telemetry 插件。那些要么太宽，要么撞巨头，要么还没证明有人为这个具体问题付费。

## ICP 与付费意愿排序

评分按痛感 × 预算 × 可触达性，1-5 分粗估。

| ICP | 痛感 | 预算 | 可触达 | 排名 | 建议价格 |
|---|---:|---:|---:|---:|---|
| 发行商/投资方/竞品研究团队 | 4 | 4 | 4 | 1 | $3k-$12k / title teardown |
| 中型 F2P/mobile studio | 5 | 4 | 3 | 2 | $2k-$8k/月 design partner，或 $100-$300/视频小时 |
| AA/AAA UX research team | 4 | 5 | 2 | 3 | $30k-$100k/年 enterprise + 私有部署 |
| Indie / small PC studio | 3 | 1 | 5 | 4 | $199-$499/report 或免费样例获客 |

**第一 ICP 应该是发行/竞品研究或中型 F2P 团队，而不是 indie。** Indie 好触达但付费弱，容易把产品拖成低价 self-serve。AAA 有钱但采购慢、数据安全要求高、已有 UX lab。中型 F2P/mobile 的痛最贴近：FTUE、D1 留存、奖励循环、liveops 调参都是真钱问题；但他们会问“为什么不用我们的 telemetry？”所以切入点最好是 telemetry 无法覆盖的竞品和感知反馈。

一个可卖的早期包装：

- `Competitor First-Hour Reward Teardown`：3-5 个工作日，分析 1 个竞品首小时或 3 段公开/录制视频，输出 15-25 页报告 + clip index，$5k 起。
- `FTUE Reward Audit`：自家 build 的 5-10 段新手录像，与 2 个竞品 benchmark 对比，$8k-$20k。
- `Design Partner`：每月 20-40 小时视频、2 次 report review、项目级模板沉淀，$4k-$10k/月。

等重复交付 10-15 个项目后，再抽象 SaaS：基础席位 $499-$1,500/月 + $25-$100/视频小时；enterprise 才谈私有部署和 telemetry fusion。

## Wedge Sequence

**Beachhead：竞品首小时 reward pacing teardown。**

这是最快拿钱的用例，因为它绕开 SDK、隐私、集成和“你们比我 telemetry 准吗”的争论。客户给一个竞品、一组目标问题，比如“为什么它的 D1 感觉更爽”“它什么时候开始给抽卡/装备/系统解锁”。我们交付：

- reward event timeline：按货币、升级、装备、解锁、结算、感官反馈分层。
- `reward_gap_p50/p90`、`reward_density_60s`、`effort_adjusted_reward`。
- 3-8 个强观点，例如“06:30-09:20 探索成本上升但无可见进度，竞品在同位置用任务进度和低价值掉落填补”。
- 关键 clip：每条结论前后 10-20 秒。
- “可测试改动”：不是说“加奖励”，而是“在首次失败后 20 秒内给保底进度反馈；目标 gap < 45s”。

**扩展 1：自家 FTUE audit。**  
竞品报告让客户信任后，再拿自家 build 的 playtest 录像做同口径对比。这里开始沉淀项目级 UI 模板和 reward weights。

**扩展 2：build-vs-build comparison。**  
当团队改过 FTUE 或掉落节奏后，比较 Build A/B 的 `reward_gap_p90`、cliff count、post-failure recovery time。这个用例会形成月度复购。

**扩展 3：telemetry fusion。**  
只有在客户连续使用后再做 SDK/插件。此时卖点不是替代录像，而是发现“内部发了奖励，但玩家没感知到”的弱反馈问题。

## 商业上会死在哪里

第一，**准确率预期错配**。框架里 Phase 0 recall > 0.6 是研究原型合理标准，但商业报告如果漏掉关键奖励，会直接损害信任。早期必须承认 human-in-the-loop，把“自动检测”包装成 analyst acceleration，而不是全自动裁判。

第二，**购买者不清晰**。UX research、系统策划、数据分析、producer 都觉得有用，但没人有明确预算。GTM 必须绑定一个预算线：竞品研究、FTUE 优化、发行评估或 liveops 调优。

第三，**现有工具吸收**。Playtest 平台拥有视频供应链；analytics 平台拥有事件数据；经济工具拥有策划心智。这个产品如果没有 benchmark 和报告方法论，只是功能。

第四，**游戏类型碎片化**。不同品类的 reward semantics 差异巨大。用同一套模型分析 Slay the Spire、Genshin Impact、Diablo、Candy Crush、Valorant，结果会很浅。早期必须选 1-2 个商业痛强的类型。

第五，**竞品录像的法律/平台风险**。公开视频、主播录像、商店素材是否可用于商业分析有条款风险 `[ASSUMPTION — verify]`。最好让客户提供他们有权使用的录像，或只输出内部研究报告，不做公开 benchmark 宣传。

最强购买理由是：**现有工具告诉团队哪里掉人、玩家说哪里不爽，但不能把“奖励为什么没有被感受到”用片段和曲线钉在设计会上。** 对一个 F2P/mobile 团队，如果一次 FTUE 改动能提升 D1 留存 0.5-1.0 个百分点 `[ASSUMPTION — verify]`，$10k 的审计非常便宜。即使没有直接留存承诺，节省 senior designer/UX researcher 手工看片和竞品拆解时间也足够：一个 8 小时人工 teardown 变成 90 分钟 review，这个价值容易解释。

## 对启动方向的建议 (Recommendations for project kickoff)

1. **先卖 3 份手工增强的竞品首小时奖励节奏报告**：不要等 SaaS；用半自动标注 + 人工判断验证是否有人为“reward pacing teardown”付 $3k-$8k。预计 2 周。
2. **只选一个首发品类，建议 mobile/F2P RPG 或 roguelite/card battler 二选一**：前者预算更强，后者识别更容易；不要同时做多品类。预计 1 周决策 + 2 周样本库。
3. **建立最小 benchmark schema**：固定输出 `reward_event_type`、`reward_score_1_30`、`reward_gap_sec`、`effort_segment`、`clip_ref`、`finding_type`，让每份报告可横向比较。预计 1 周。
4. **把产品命名包装成 audit/report，而不是 AI analytics platform**：早期客户买决策材料，不买平台承诺；等 10-15 份报告后再产品化 dashboard。预计 1 周。

## 关键不确定性 (Key uncertainties to resolve)

1. **客户是否真的为“perceived reward pacing”单独付费**，还是只把它视为 playtest/analytics 套件里的一个免费维度？
2. **视频侧识别 + 人工校准能否在 30 分钟录像内稳定产出 3 条以上设计师认可的非显然 insight**，否则报告会变成漂亮但不改变决策的材料。
3. **竞品 teardown 的数据来源和版权/条款风险是否可控**，如果不能用公开或客户提供录像做商业交付，最强 beachhead 会受损。
