# Agent 2 报告：奖励/成本量化方法论与可验证性

## 核心立场

这个产品的成败不在于把 `reward_score` 算得多精细，而在于让设计师相信：曲线不是玄学，而是从可见证据、可调假设、可验证预测中来的。我的建议是把“奖励强度”降格为一个 calibrated latent score，不要伪装成客观真值；把原始证据、设计师偏好模型、误差范围一起暴露。第一版不要追求跨所有游戏的绝对分，而要追求同一游戏、同一阶段、两个 build 或两段录像之间的相对判断稳定。

框架目前最大的风险是把多个不同构念揉进一个数：经济价值、视觉强度、新颖性、稀有度、目标相关性、挑战补偿、玩家情绪，全都乘到 `reward_score` 里。这会产生看似科学的数值，但设计师无法判断分数变化来自哪里，也很难验证。

## 1. 理论锚点：应该量化什么

奖励曲线可以借用 Skinner 的 fixed/variable ratio、fixed/variable interval 作为节奏语言：固定间隔奖励给稳定预期，变动比率奖励制造追逐感，过长 gap 会形成 extinction 风险。但这里不要过度套用行为主义。游戏里的“奖励”不只是强化物，还包括 competence feedback、goal progress、agency confirmation 和 sensory salience。

Flow / challenge-skill balance 给 `effort_score` 一个更好的定位：effort 不是“玩家花了多久”，而是玩家在一段时间内承受的 challenge load。高 challenge 后的奖励不一定要更大，但必须有足够清晰的 competence confirmation，否则会被体验成消耗而非成长。

Self-Determination Theory 可以拆出三个维度：

- Competence：我是否变强、做对了、被系统承认。
- Autonomy：我是否得到有意义的选择、构筑分叉、路线自由。
- Relatedness：多人/排行/社交认可，MVP 可先弱化。

Game feel / juice 对应的不是“奖励价值”，而是 salience 和 clarity。爆闪、音效、慢动作、震动会放大奖励可感知性，但它们不能替代实际 utility。一个金币雨可能 salience 很高、utility 很低，这就是 dilution 的来源。

Compulsion loop 和 FTUE pacing 应作为诊断模板，不应作为硬编码真理。不同产品目标不同：roguelike 可以允许 2 分钟无硬奖励但保持高 anticipation；F2P 新手引导可能需要更短的 visible progress loop。任何“前 N 秒必须给奖励”的规则都应是项目配置，不是通用公理。

因此建议把 reward event operationalize 为四类构念：

1. `utility_value`：对角色、局内胜率、经济、解锁、进度的实际可见价值。
2. `competence_signal`：系统是否承认玩家完成了难动作或阶段目标。
3. `choice_value`：是否打开新选择、新构筑路径、新策略空间。
4. `feedback_salience`：视觉、音频、UI、动画让玩家注意到的强度和清晰度。

`effort_score` 则应 operationalize 为五类 burden：

1. `time_burden`：无有效回报的持续时间。
2. `skill_burden`：战斗、操作、反应、执行密度。
3. `risk_burden`：低血量、资源耗尽、濒死、失败概率。
4. `failure_tax`：死亡、重试、回档、重复路线。
5. `cognitive_friction`：菜单徘徊、反复查看、迷路、目标不明。

## 2. 评分设计：不要乘法黑箱

框架的乘法 `base_value * rarity * progression * novelty * sensory * context` 不适合作为核心分数。问题有三个：第一，任一因子估错会指数级放大；第二，`sensory_multiplier` 会把“吵”和“有价值”混起来；第三，`effort_multiplier` 如果进入 reward_score，再用 reward/effort 做比值，会把 effort 双重计入。

我建议改成事件向量 + 加权、可校准、可解释的 bounded score：

```text
R_i = 100 * confidence_i * sigmoid(
  b_type
  + w_u * utility_value_i
  + w_c * competence_signal_i
  + w_a * choice_value_i
  + w_s * feedback_salience_i
  + w_n * novelty_i
  + w_g * goal_relevance_i
)
```

每个子项先归一到 0-1 或 -1到1，权重由 genre preset + designer calibration 给出。`R_i` 的单位不要叫“价值”，叫 `perceived_reward_points`，并在 UI 中显示分解条：例如 `utility 0.7 / salience 0.3 / novelty 0.1`。这样设计师能指出“你把这个掉落的 utility 估高了”，而不是否定整条曲线。

对重复奖励要使用递减函数，而不是简单 multiplier：

```text
novelty_i = exp(-seen_count_same_type / tau_type)
```

`tau_type` 应按类型配置。金币的 novelty 衰减快，构筑关键遗物的 novelty 衰减慢。

Effort 不应是单个事件分，而应是时间段 burden rate：

```text
E_t = alpha_time * unrewarded_time_rate_t
    + alpha_skill * skill_load_t
    + alpha_risk * risk_load_t
    + alpha_fail * failure_tax_t
    + alpha_cog * cognitive_friction_t
```

再计算从上一个有效奖励到当前事件的累计成本：

```text
AccumEffort_i = integral(E_t, last_reward_time, reward_time_i)
compensation_i = R_i - beta_phase * AccumEffort_i
effort_adjusted_reward_i = R_i / (epsilon + AccumEffort_i)
```

我更推荐把 `compensation_i` 作为诊断主指标，把 ratio 作为辅助。比值在低 effort 时会爆炸，容易把无意义小奖励误判成高效回报。

Reward density 应使用 kernel smoothing，而不是只用 60 秒 rolling window。窗口法会在事件边界产生假 cliff。建议：

```text
reward_density(t) = sum_i R_i * K((t - time_i) / bandwidth_phase)
effort_density(t) = EMA(E_t, half_life = 30-90s by phase)
net_pacing(t) = reward_density(t) - lambda * effort_density(t)
```

跨游戏比较只能做标准化比较，不应比较原始分。最低可行方案：

- `within_session_z`：相对本局均值/方差。
- `within_phase_percentile`：相对 combat/exploration/shop 等同阶段。
- `genre_template_score`：相对同类型配置的期望 band。

负反馈不应放在同一 reward 轴上。死亡、扣资源、失败音效是 `negative_valence` 或 `frustration_load`，不是负奖励。把它们混入同轴会掩盖关键问题：玩家失败后可能马上得到 learning feedback 或快速 retry，这不是“负奖励被抵消”，而是 recovery loop 成立。建议三条曲线并列：reward density、effort/frustration load、recovery feedback。

## 3. 验证策略：必须让指标能输

最小可说服实验应从一个垂直类型开始，我会选 roguelike 或 card-builder。样本规模：12-20 段 10-20 分钟录像，至少 3 名标注者，目标 300-500 个候选 reward events，外加 100 个 high-effort / frustration segments。这个规模足够暴露 taxonomy 是否混乱，不足以训练强模型，但足以验证评分语言是否可用。

### A. 设计师 pairwise-preference 校准

不要先问设计师给 1-10 分，分数标尺太不稳定。给同一 phase 的两段 10-20 秒 clip，让设计师回答：

- 哪段“相对刚才的付出更有回报感”？
- 哪段“奖励反馈更清晰”？
- 哪段“更像奖励稀释/空转”？

用 Bradley-Terry 或 Thurstone-Mosteller 模型学习权重。最小实验：5 名设计师，每人 120-150 个 pair，保留 20% holdout。目标：

- held-out pairwise accuracy >= 0.70。
- 与设计师多数票 Spearman rho >= 0.55。
- 单个设计师偏好模型和 group model 的差异可解释，而不是随机。

如果达不到 0.65，说明当前特征缺关键维度，或者设计师之间对“回报感”没有共享标准。

### B. 人工标签一致性

先验证“奖励事件是什么”能否被人类稳定识别。建议目标：

- reward event presence：Krippendorff alpha >= 0.75。
- reward type：macro F1 between annotators >= 0.70。
- reward strength ordinal rating：ICC(2,k) >= 0.65。
- timestamp median disagreement <= 2 秒。

如果 event presence 都不稳定，就不要谈 reward_score。若 strength 不稳定但 event 稳定，产品应主打 timeline 和 gap，而不是强度分。

### C. Telemetry / retention / quit-point 对齐

有 SDK 的内部 playtest 中，视频曲线要和 telemetry 做三层对齐：

1. `visible_event_alignment`：可见奖励事件与内部 event 在 2 秒内匹配，目标 >= 0.80。
2. `hidden_reward_gap`：内部发奖但视频无明显反馈的比例，这反而是产品价值点。
3. `quit/death prediction`：reward cliff 或 high-effort-low-reward 是否预测 quit、pause、retry abandon。

预测检验不要只看相关系数。用 baseline model 先包含 session time、phase、death count，再加入 reward metrics。目标是 AUC 提升 >= 0.05，或 top 10% cliff windows 覆盖 >= 2x 的 quit/pause 点。这个目标是产品验证标准，不是已知事实。

### D. 已知问题 blind check

找一个团队拿 2 个 build 或 2 个关卡，其中设计师知道某些改动：例如 Boss 结算增强、探索支路补奖励、失败后缩短回路。先 blind run 工具，再让设计师揭盲。最小说服标准：

- 5 个已知 pacing issue 中命中 >= 4 个。
- 每 10 分钟严重 false positive <= 1 个。
- 报告中至少 3 条发现被 lead designer 标为“值得进会讨论”。
- 相比人工看片，定位关键片段时间减少 >= 40%。

这组指标比“曲线看起来合理”更重要。

## 4. Per-genre taxonomy：一套核心本体 + 类型模板

不要为每个 genre 建完全不同 taxonomy，否则数据和产品都会碎掉。应该建立 core ontology，再用 genre preset 调权重和扩展字段。

核心 reward types：

- `resource_gain`：金币、材料、分数。
- `power_gain`：装备、卡牌、技能、属性。
- `progression`：XP、等级、通行证、章节。
- `unlock`：系统、地图、角色、难度、新玩法。
- `completion`：胜利、任务完成、Boss 击败、结算。
- `choice_expansion`：三选一、路线分叉、build pivot。
- `mastery_feedback`：perfect dodge、combo、S rank、headshot。
- `sensory_celebration`：纯反馈强度，不等价于 utility。

Genre template 只做两件事：定义哪些类型重要，以及默认 effort/reward 的期望节奏。

Roguelike：权重应偏 `choice_expansion`、`power_gain`、`completion`、`risk_burden`。房间清理后的小奖励不一定高分，能改变 build 的 relic/card 才高分。

Card-builder：重点是 draft choice quality、deck synergy、upgrade/remove、elite/boss reward。这里“选择”本身就是奖励，纯金币可能 utility 高但感知低。

ARPG：重点是 loot rarity、power delta、XP/level、quest completion、combat skill burden。必须区分“满屏掉落 salience”与“可装备升级 utility”，否则会误判 loot shower。

FTUE / mobile economy 类：需要额外字段 `comprehension_value` 和 `habit_loop_step`，但我不建议作为首个 MVP，因为 UI/OCR、经济语境和留存因果都更难。

## 5. 反方论点：这可能是伪科学

最强反方论点是：玩家感受到的奖励不可从录像客观测量；分数只是创始人拍脑袋的权重；任何曲线都能事后解释；留存和乐趣受 IP、操作手感、社交、难度、审美、性能等大量因素影响，reward gradient 只是把复杂体验压成漂亮图表。

这个批评是对的，除非产品主动降低主张。防御方式不是宣称模型懂玩家，而是做到四点：

1. 原始证据优先：每个分数可回放 clip、截图、OCR/audio/visual evidence。
2. 分数可校准：默认权重只是 prior，项目权重来自 designer pairwise preference。
3. 预测可证伪：cliff、dilution、high-cost-low-reward 必须在 blind build comparison、quit-point、designer majority vote 上接受检验。
4. 不确定性外显：低 confidence 或高设计师分歧的结论，不输出为强诊断。

产品最可信的表述应是：“我们把录像中的可感知奖励和成本整理成可审计的 pacing evidence，并用你们团队校准过的偏好模型排序风险片段。”不要说“我们测量真实快乐”。

## 对启动方向的建议 (Recommendations for project kickoff)

1. 先实现 `event vector + score breakdown`，不要实现乘法总分。理由：分解维度让设计师能纠错和校准，是建立信任的基础。估计 1-2 team-weeks。

2. 做 20 段 roguelike/card-builder 的人工标注与 pairwise calibration 实验。理由：先证明“人类是否同意这些奖励/成本构念”，否则自动化没有意义。估计 2-3 team-weeks。

3. 把首个报告主指标设为 `gap / density / compensation`，ratio 降为辅助。理由：ratio 容易在低 effort 片段产生误导，compensation 更接近“付出后是否够回报”的设计语言。估计 3-5 days。

4. 在 UI 中并列显示 reward、effort/frustration、recovery feedback 三条曲线。理由：负反馈不是负奖励；恢复性反馈是判断挫败是否可接受的关键。估计 1 team-week。

## 关键不确定性 (Key uncertainties to resolve)

1. 设计师对“相对付出是否有回报感”的 pairwise 判断能否达到 >=0.70 一致/预测准确率；如果不能，reward_score 应降级为可视化辅助而非诊断核心。

2. 仅靠录像能否稳定估计 effort，尤其是 cognitive friction 和 risk burden；如果 effort 噪声太大，首版应只做 reward pacing，不做强 effort-adjusted 判断。

3. Reward cliff / dilution 是否能在 blind build comparison 或 quit/pause points 上显示增量预测力；如果没有，产品价值应转向“结构化看片与证据索引”，而不是“奖励节奏评分器”。
