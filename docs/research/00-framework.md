# 游戏奖励梯度分析器框架规划

版本：v0.1  
日期：2026-06-15  
定位：面向游戏设计师、数值策划、UX Research、Producer 的游玩录像分析工具  
工作名：Reward Gradient Analyzer / Reward Pacing Analyzer

## 1. 一句话定义

通过分析游戏游玩录像，自动识别奖励事件、玩家付出成本、阶段节奏和反馈强度，生成可解释的奖励梯度曲线，帮助团队判断“玩家是否在正确的时间获得了足够、合适、可信的回报”。

## 2. 核心判断

这个项目不应承诺“从录像还原游戏内部奖励公式”。录像只能看到玩家实际经历到的可见/可听反馈，无法完整知道掉落表、隐藏概率、服务器逻辑和未触发分支。

更准确的目标是：

> 从玩家体验侧分析奖励机制的可感知梯度。

也就是回答：

- 玩家多久获得一次有效奖励？
- 奖励是否随难度、时间、风险、操作成本同步增长？
- 哪些阶段奖励断档、过密、过弱、过强？
- 玩家失败、重复、等待、探索后有没有得到合理反馈？
- 同一关卡/构筑/任务的奖励节奏是否符合设计意图？
- 不同版本、不同玩家、不同竞品之间的奖励曲线有什么差异？

## 3. 使用场景

### 3.1 内部 playtest 录像分析

团队上传 10 到 30 分钟 playtest 录像，工具输出奖励事件时间轴、奖励密度曲线、挫败点和关键片段。

### 3.2 版本对比

比较 Build A 和 Build B：

- 新手前 10 分钟奖励是否更平滑？
- Boss 战后奖励是否更强？
- 改动后的掉落节奏是否造成奖励稀释？
- 经济系统改动是否让玩家更早进入 grind 感？

### 3.3 竞品拆解

上传公开游戏录像或主播片段，分析竞品在新手引导、战斗结算、抽卡、关卡推进、装备成长上的奖励节奏。

### 3.4 设计评审

为策划会提供证据：

- 时间轴截图
- 自动片段索引
- 奖励间隔分布
- 奖励强度曲线
- 风险-收益匹配度

### 3.5 Telemetry 补强

在后续版本中接入埋点、日志、存档或引擎插件，把录像感知层和内部事件层对齐。

## 4. 目标用户

### 4.1 主要用户

- 系统策划：关心奖励、经济、成长、掉落、循环。
- 关卡设计师：关心关卡推进中的反馈密度。
- UX Research：关心玩家理解、挫败、惊喜、困惑。
- Producer：关心版本改动是否改善体验。

### 4.2 次要用户

- 数据分析师：需要将定性录像变成结构化数据。
- QA：发现 reward trigger、结算、掉落、UI 反馈异常。
- 发行/市场团队：拆解竞品首小时体验和留存钩子。

## 5. 非目标

第一阶段暂不做：

- 自动修改游戏数值。
- 直接预测商业收入。
- 完整替代 telemetry。
- 完整替代人工 UX research。
- 通吃所有游戏类型。
- 判断游戏“好不好玩”的总分。

工具应定位为“设计判断辅助系统”，不是最终裁判。

## 6. 核心概念

### 6.1 奖励事件 Reward Event

玩家感知到回报的离散事件。

常见类型：

- 货币增长：金币、钻石、材料、积分。
- 经验增长：XP、等级、熟练度、通行证进度。
- 掉落获得：装备、卡牌、技能、道具、皮肤。
- 解锁：地图、角色、系统、功能、剧情、难度。
- 结算：胜利、评分、宝箱、章节完成、Boss 击败。
- 社交/成就：排行榜、称号、任务完成、成就弹窗。
- 感官反馈：稀有音效、闪光、震动、镜头、慢动作、庆祝动画。

### 6.2 玩家成本 Effort / Cost

玩家为获得奖励付出的代价。

可从录像估计：

- 时间成本：距离上次奖励经过多久。
- 战斗成本：战斗时长、敌人数量、受伤次数、死亡次数。
- 操作成本：输入频率、瞄准/闪避/连招密度。
- 认知成本：菜单停留、犹豫、反复查看、路线回退。
- 风险成本：低血量、资源耗尽、失败重试。
- 探索成本：移动距离、分岔探索、无奖励空路。

### 6.3 奖励梯度 Reward Gradient

奖励强度随时间、阶段、成本、风险变化的趋势。

可以有多种视角：

- 时间梯度：奖励随时间的密度变化。
- 成本梯度：单位付出得到多少奖励。
- 难度梯度：更高难度是否对应更高奖励。
- 进度梯度：越接近目标是否反馈越强。
- 情绪梯度：挫败后是否有恢复性反馈。

### 6.4 奖励密度 Reward Density

在某个时间窗口内的奖励总强度。

```text
reward_density(t) = sum(reward_score in window) / window_duration
```

### 6.5 奖励间隔 Reward Gap

两次有效奖励之间的时间或成本间隔。

```text
reward_gap_i = reward_event_time_i - reward_event_time_(i-1)
```

### 6.6 成本调整奖励 Effort-Adjusted Reward

单位成本得到的奖励强度。

```text
effort_adjusted_reward = reward_score / effort_score
```

### 6.7 奖励波动 Reward Volatility

奖励节奏是否忽高忽低。

```text
reward_volatility = std(reward_density over rolling windows)
```

### 6.8 奖励断崖 Reward Cliff

长期高密度奖励后突然进入低密度区域，或高成本挑战后奖励不足。

### 6.9 奖励稀释 Reward Dilution

奖励频率很高，但单次奖励感知价值过低，导致反馈疲劳。

## 7. 输入数据

### 7.1 必需输入

- 游玩录像：mp4/mov/webm。
- 视频元数据：帧率、分辨率、时长。

### 7.2 推荐输入

- 游戏类型。
- 设计目标：例如“前 10 分钟每 30 到 60 秒有一次反馈”。
- 关卡/章节名。
- 版本号。
- 玩家类型：新手、熟练、硬核、回流。

### 7.3 可选输入

- 语音 think-aloud 转录。
- 问卷。
- Telemetry 日志。
- GDD 或数值表。
- UI 字体/图标素材。
- 预标注奖励样例。

## 8. 输出结果

### 8.1 结构化结果

- 奖励事件列表。
- 玩家成本估计。
- 阶段切分。
- 奖励强度分数。
- 奖励密度曲线。
- 奖励间隔分布。
- 风险-收益匹配度。
- 异常片段索引。

### 8.2 报告结果

报告应避免泛泛总结，必须绑定证据。

每个发现包含：

- 结论。
- 证据片段时间戳。
- 相关截图/短 clip。
- 指标值。
- 置信度。
- 可能原因。
- 建议验证方式。

示例：

```text
发现：第 06:20 到 09:10 出现奖励断档。
证据：该区间 reward_density 下降到全局均值的 28%，同时玩家经历 2 次死亡和 1 次路线回退。
影响：可能造成探索阶段的挫败累积。
建议：在第 07:00 附近加入低价值但明确的探索奖励，或缩短失败回到奖励点的距离。
置信度：0.74
```

## 9. 总体系统架构

```text
Video Upload
  -> Ingestion & Metadata
  -> Frame Sampling
  -> Audio Extraction
  -> OCR / UI Parsing
  -> Visual Event Detection
  -> Audio Reward Cue Detection
  -> Player State & Phase Segmentation
  -> Reward Event Fusion
  -> Reward Scoring
  -> Effort Estimation
  -> Gradient & Change Point Analysis
  -> Report Generation
  -> Human Review / Calibration
```

## 10. 模块设计

### 10.1 录像导入模块

职责：

- 上传视频。
- 提取帧率、时长、分辨率。
- 生成低分辨率分析代理文件。
- 抽取音频轨。
- 生成关键帧。

扩展：

- 支持 YouTube/Twitch 链接。
- 支持 OBS 录制文件。
- 支持游戏内回放文件。
- 支持批量 playtest session。

### 10.2 帧采样模块

第一阶段策略：

- 每秒 1 帧用于全局分析。
- UI 数字变化区域每秒 2 到 5 帧。
- 检测到爆闪、弹窗、音效峰值时局部加密。

后续策略：

- 基于镜头变化动态采样。
- 基于 UI 变化动态采样。
- 基于音频 cue 动态采样。

### 10.3 OCR/UI 解析模块

识别内容：

- 金币、经验、分数、血量、等级。
- 任务文本。
- 结算面板。
- 奖励弹窗。
- 道具名称。
- 稀有度标签。

技术选择：

- PaddleOCR / PP-OCRv5：轻量、适合多语言 UI。
- VLM：用于复杂 UI 语义解释。
- 自定义 UI 区域模板：对固定游戏或固定品类更稳定。

输出示例：

```json
{
  "timestamp": 382.4,
  "region": "top_right_currency",
  "text": "Gold 1250",
  "value": 1250,
  "confidence": 0.91
}
```

### 10.4 视觉奖励事件检测模块

检测目标：

- 宝箱打开。
- 掉落光柱。
- 卡牌翻开。
- 结算面板。
- 升级特效。
- 新道具弹窗。
- 胜利/失败画面。
- 稀有度颜色。

技术选择：

- YOLO 系列做目标检测。
- SAM 2 做目标跟踪和 UI 区域分割。
- VLM 做少样本事件解释。

事件输出：

```json
{
  "timestamp": 612.8,
  "event_type": "item_acquired",
  "object": "Rare Sword",
  "rarity": "rare",
  "visual_intensity": 0.72,
  "confidence": 0.86
}
```

### 10.5 音频奖励 cue 检测模块

识别：

- 金币音效。
- 胜利音乐。
- 升级音效。
- 稀有掉落音效。
- 失败音效。
- 玩家语音情绪。

技术选择：

- 音频峰值 + 频谱模板：快速 baseline。
- YAMNet：通用音频事件分类。
- CLAP：用文本提示匹配“victory jingle”“coin pickup sound”等。
- Whisper：转录玩家评论或旁白。

输出：

```json
{
  "timestamp": 245.2,
  "audio_event": "victory_jingle",
  "intensity": 0.83,
  "confidence": 0.78
}
```

### 10.6 玩家状态识别模块

状态类别：

- exploration
- combat
- boss_fight
- puzzle
- menu
- inventory
- shop
- reward_screen
- death
- retry
- victory
- idle

第一阶段可用规则：

- 敌人/血条/伤害数字出现 -> combat。
- 地图移动且无敌人 -> exploration。
- 大型血条/特殊音乐 -> boss_fight。
- UI 面板停留 -> menu/inventory/shop。
- 死亡文本/灰屏 -> death。

后续可训练模型：

- VideoMAE / SlowFast / TimeSformer。
- 针对游戏类型微调的阶段分类器。

### 10.7 奖励事件融合模块

同一个奖励可能同时触发：

- OCR 数字增加。
- UI 弹窗。
- 音效。
- 特效。
- 玩家评论。

融合逻辑：

```text
if events are within time window T and spatial/semantic relation matches:
    merge into one reward_event
```

融合后的事件包含：

- event_type
- timestamp_start
- timestamp_end
- visual_evidence
- audio_evidence
- ocr_evidence
- reward_channels
- confidence

### 10.8 奖励评分模块

奖励分数由多维度组成：

```text
reward_score =
  base_value
  * rarity_multiplier
  * progression_multiplier
  * novelty_multiplier
  * sensory_multiplier
  * context_multiplier
```

建议初始规则：

| 奖励类型 | 基础分 |
|---|---:|
| 小货币/小分数增长 | 1 |
| 普通掉落 | 3 |
| 任务小阶段完成 | 5 |
| 稀有道具 | 8 |
| 升级 | 10 |
| 新系统解锁 | 15 |
| 章节完成 | 18 |
| Boss 胜利 | 25 |
| 关键剧情/新玩法解锁 | 30 |

调节因子：

| 因子 | 说明 |
|---|---|
| rarity_multiplier | 稀有度越高分数越高 |
| novelty_multiplier | 第一次出现比分重复出现更高 |
| effort_multiplier | 高成本后的奖励应被标记为更重要 |
| sensory_multiplier | 视觉/音频/震动反馈越强，感知奖励越强 |
| goal_relevance | 和当前目标越相关，奖励越高 |

### 10.9 玩家成本估计模块

成本由多个信号组成：

```text
effort_score =
  time_cost
  + combat_cost
  + failure_cost
  + navigation_cost
  + cognitive_cost
  + resource_cost
```

第一阶段可估计：

- time_cost：距离上次奖励的秒数。
- combat_cost：战斗持续时间、受伤/低血量信号。
- failure_cost：死亡/重试次数。
- navigation_cost：移动但无奖励的持续时间。
- cognitive_cost：菜单停留、重复查看、停顿。

### 10.10 梯度分析模块

核心输出：

```text
reward_density[t]
reward_gap[t]
effort_adjusted_reward[t]
reward_volatility[t]
reward_cliff_score[t]
reward_dilution_score[t]
```

推荐算法：

- Rolling window aggregation。
- Exponential moving average。
- Change point detection。
- Quantile threshold。
- Session phase normalization。
- Cross-session alignment。

示例：

```text
window = 60 seconds
reward_density = sum(reward_score in window) / 60
effort_density = sum(effort_score in window) / 60
reward_effort_ratio = reward_density / max(effort_density, epsilon)
```

### 10.11 诊断规则模块

初始诊断规则：

1. 奖励断档  
   reward_gap 超过同阶段 P90，且 effort_score 持续上升。

2. 高成本低回报  
   boss/combat/retry 后 reward_score 低于同类事件均值。

3. 奖励稀释  
   reward_event 很密集，但单次 reward_score 低，且没有新颖性变化。

4. 奖励前置过强  
   新手期过早给出高稀有度或高价值奖励，后续曲线下降。

5. 失败恢复不足  
   death/retry 后缺少进度保留、提示、安慰奖励或快速再挑战路径。

6. 探索空洞  
   长时间移动、绕路、回退后没有发现、资源或信息奖励。

7. 结算反馈弱  
   完成高强度挑战后仅出现低视觉强度/低价值结算。

8. 目标进度不可感知  
   玩家完成多个动作但主线目标、通行证、等级、任务进度没有明显变化。

## 11. 数据结构草案

### 11.1 Session

```json
{
  "session_id": "s_001",
  "game": "Example Game",
  "build": "0.3.2",
  "player_profile": "new_player",
  "video_path": "upload/s_001.mp4",
  "duration_sec": 1800,
  "fps": 60,
  "created_at": "2026-06-15T00:00:00Z"
}
```

### 11.2 RewardEvent

```json
{
  "event_id": "r_024",
  "session_id": "s_001",
  "timestamp_start": 412.6,
  "timestamp_end": 416.9,
  "event_type": "level_up",
  "reward_channels": ["visual", "audio", "ocr"],
  "reward_score": 12.5,
  "confidence": 0.89,
  "evidence": [
    {"type": "ocr", "text": "LEVEL UP", "confidence": 0.94},
    {"type": "audio", "label": "level_up_sound", "confidence": 0.81}
  ]
}
```

### 11.3 EffortSegment

```json
{
  "segment_id": "e_010",
  "session_id": "s_001",
  "timestamp_start": 360.0,
  "timestamp_end": 420.0,
  "phase": "combat",
  "time_cost": 60,
  "combat_cost": 0.72,
  "failure_cost": 0,
  "cognitive_cost": 0.18,
  "effort_score": 8.4,
  "confidence": 0.76
}
```

### 11.4 GradientWindow

```json
{
  "session_id": "s_001",
  "window_start": 360.0,
  "window_end": 420.0,
  "reward_sum": 12.5,
  "effort_sum": 8.4,
  "reward_density": 0.208,
  "effort_adjusted_reward": 1.49,
  "reward_gap_sec": 96.2,
  "flags": ["post_combat_reward_ok"]
}
```

## 12. MVP 范围

### 12.1 推荐先选游戏类型

建议先选一个垂直类型，不做通用游戏。

优先级：

1. Roguelike / Roguelite  
   奖励事件明显：房间、宝箱、道具、升级、Boss。

2. 动作 RPG  
   奖励事件丰富：战斗、装备、经验、任务。

3. 卡牌构筑  
   奖励事件结构化：选牌、遗物、金币、战斗结算。

4. 放置/养成  
   奖励密度和经济曲线明显，但 UI OCR 压力更高。

首个 MVP 推荐：Roguelike 或卡牌构筑。原因是奖励节点清楚，视频识别难度低，报告价值直接。

### 12.2 MVP 输入

- 1 个游戏类型。
- 10 到 30 分钟单局录像。
- 开发者手动标注 5 到 20 个奖励样例。
- 可选：游戏名称和阶段目标。

### 12.3 MVP 输出

- 奖励事件时间轴。
- reward_density 曲线。
- reward_gap 分布。
- effort_adjusted_reward 曲线。
- 3 到 8 条诊断结论。
- 每条结论绑定截图或时间戳。

### 12.4 MVP 不做

- 全自动理解所有 UI。
- 自动训练游戏代理。
- 自动修数值。
- 多语言完整本地化。
- 实时分析。

## 13. 算法流程草案

### 13.1 基础流程

```text
1. Load video
2. Extract frames and audio
3. Detect UI text and visual reward events
4. Detect audio reward cues
5. Infer gameplay phase per time window
6. Merge visual/OCR/audio detections into reward events
7. Estimate reward score
8. Estimate effort score
9. Compute reward gradient metrics
10. Detect abnormal pacing patterns
11. Generate timestamped report
```

### 13.2 伪代码

```python
def analyze_session(video):
    frames = sample_frames(video)
    audio = extract_audio(video)

    ocr_events = run_ocr(frames)
    visual_events = detect_visual_rewards(frames)
    audio_events = detect_audio_cues(audio)
    phases = infer_gameplay_phases(frames, audio)

    reward_events = fuse_reward_events(
        ocr_events=ocr_events,
        visual_events=visual_events,
        audio_events=audio_events,
    )

    effort_segments = estimate_effort(
        frames=frames,
        phases=phases,
        reward_events=reward_events,
    )

    scored_rewards = score_rewards(reward_events, phases)
    gradient = compute_reward_gradient(scored_rewards, effort_segments)
    findings = diagnose_reward_pacing(gradient, scored_rewards, effort_segments)

    return build_report(scored_rewards, effort_segments, gradient, findings)
```

## 14. 人工校准机制

必须保留 human-in-the-loop，否则不同游戏的 UI 和奖励语义差异太大。

### 14.1 校准入口

开发者可以：

- 框选金币/经验/等级 UI 区域。
- 标记某个事件为“奖励”或“不是奖励”。
- 修改奖励强度权重。
- 定义设计目标曲线。
- 合并/拆分检测事件。

### 14.2 学习方式

第一阶段：

- 基于模板和规则保存每个游戏项目的配置。

第二阶段：

- 使用主动学习微调奖励事件检测器。

第三阶段：

- 训练项目级 reward scorer。

## 15. 评估指标

### 15.1 事件识别指标

- reward_event precision。
- reward_event recall。
- timestamp error。
- OCR numeric accuracy。
- event_type accuracy。

### 15.2 梯度分析指标

- 奖励断档检测准确率。
- 高成本低回报片段命中率。
- 设计师认可率。
- 与 telemetry 事件对齐率。
- 报告节省人工看片时间。

### 15.3 产品价值指标

- 分析 30 分钟录像所需时间。
- 设计师从报告跳转到关键片段的次数。
- 被采纳的设计建议数量。
- Build 对比报告使用频率。

## 16. 竞品与差异化

### 16.1 现有相邻工具

- Lysto AI：分析 playtest 录像、玩家评论、问卷，输出结构化 insight。
- PlaytestCloud：招募玩家、录制游玩、基于 transcript 和问卷做 AI 分析。
- Antidote：playtest 平台，提供 AI insights。
- modl.ai：黑盒 AI agent 测试游戏，视觉/OCR 理解画面，重点是 QA。
- Razer QA Companion-AI：视觉检测 bug、生成复现步骤和 Jira 报告。
- GameDriver：自动化 QA 服务，覆盖 combat、economy、progression 等回归验证。
- GameAnalytics / Unity Analytics / PlayFab：基于 SDK/telemetry 的行为分析。
- Machinations：设计和模拟经济系统。
- Balancy：liveops 和虚拟经济配置检查。
- Omnic.AI / trophi.ai：面向玩家的 AI coaching 和录像分析。

### 16.2 差异化切口

现有工具大多在以下方向：

- 主观 playtest 总结。
- QA 自动化。
- 事件埋点分析。
- 经济模拟。
- 玩家 coaching。

本项目的切口：

> 从录像中抽取玩家实际感受到的奖励事件，并量化奖励节奏、奖励间隔、奖励强度和成本匹配度。

### 16.3 可防守优势

- 游戏类型专用奖励本体。
- 奖励事件标注数据集。
- 设计师可解释指标体系。
- 录像 + telemetry 双通道对齐。
- 竞品拆解能力。
- 可复用的项目级 UI 模板和奖励权重。

## 17. 产品界面设想

### 17.1 Dashboard

页面结构：

- 顶部：Session 信息、游戏、版本、玩家类型、时长。
- 中部：奖励密度曲线 + 玩家成本曲线。
- 下方：奖励事件时间轴。
- 右侧：关键诊断卡片。

### 17.2 Timeline

显示：

- 奖励事件点。
- 死亡/失败点。
- 战斗/探索/菜单阶段。
- 奖励断档区域。
- 高成本低回报区域。

### 17.3 Clip Evidence

每条诊断能跳到：

- 前 10 秒。
- 事件发生时。
- 后 10 秒。

支持导出 clip 给团队讨论。

### 17.4 Calibration Panel

允许用户：

- 调整某类奖励权重。
- 标记误检。
- 选择 UI 区域。
- 设置目标奖励间隔。
- 选择游戏类型模板。

### 17.5 Compare View

比较：

- 两个版本。
- 两个玩家。
- 新手 vs 熟练玩家。
- 自家游戏 vs 竞品。

输出：

- 曲线差异。
- 事件分布差异。
- 诊断差异。
- 关键 clip 对照。

## 18. 技术路线图

### Phase 0：研究原型

目标：验证录像能否稳定抽取奖励事件。

任务：

- 选 1 个游戏类型。
- 收集 20 段录像。
- 手工标注奖励事件。
- 跑 OCR、抽帧、音频峰值。
- 用规则生成 reward_density 曲线。

验收：

- 能识别 60% 以上明显奖励事件。
- 能输出可读的时间轴。
- 设计师认为 3 条以上发现有讨论价值。

### Phase 1：MVP

目标：半自动分析单局录像。

任务：

- 上传视频。
- 自动抽帧和 OCR。
- 视觉奖励事件检测。
- 音频 cue 检测。
- 手动校准奖励权重。
- 输出 Markdown/PDF 报告。

验收：

- 30 分钟录像分析时间小于 10 分钟。
- 明显奖励事件 precision 大于 0.8。
- 时间戳误差小于 2 秒。
- 设计师能基于报告定位关键片段。

### Phase 2：项目级配置

目标：支持同一个游戏多次分析。

任务：

- 项目模板。
- UI 区域保存。
- 奖励类型词典。
- 权重配置。
- Build 对比。
- 批量 session 分析。

验收：

- 同一游戏第二次分析人工校准时间下降 70%。
- 支持 10 个 session 聚合。
- 输出 group-level reward pacing report。

### Phase 3：Telemetry 融合

目标：把可见奖励和内部事件对齐。

任务：

- 设计通用 telemetry schema。
- 接入 Unity/Unreal 插件。
- 对齐 video timestamp 和 game event timestamp。
- 识别“内部发生但玩家没感知到”的奖励。

验收：

- telemetry reward event 与视频 reward event 对齐率大于 0.85。
- 能发现弱反馈奖励和 UI 不明显奖励。

### Phase 4：设计建议引擎

目标：从诊断走向可执行建议。

任务：

- 类型化问题库。
- 设计 pattern 库。
- 竞品曲线参考。
- 实验建议生成。
- A/B test 假设生成。

验收：

- 建议被设计师采纳或进入讨论的比例大于 30%。
- 每条建议都包含证据和验证方法。

## 19. 数据标注计划

### 19.1 标注对象

- reward_event
- reward_type
- reward_strength
- reward_channel
- gameplay_phase
- failure_event
- high_effort_segment
- confusion_segment
- delight_segment

### 19.2 标注格式

```json
{
  "timestamp_start": 120.5,
  "timestamp_end": 124.0,
  "label": "reward_event",
  "reward_type": "item_acquired",
  "strength": 8,
  "channels": ["visual", "audio", "ocr"],
  "notes": "Rare item popup after elite fight"
}
```

### 19.3 标注策略

- 先标明显事件，不追求全量。
- 每个游戏类型建立 100 到 300 个高质量事件样例。
- 用大模型预标注，人类确认。
- 用误检/漏检样例驱动下一轮训练。

## 20. 风险与解决方案

### 20.1 视频只能看到表层

风险：无法知道隐藏奖励、未显示概率、后台数值。

解决：

- 明确定位为 perceived reward。
- 后续接入 telemetry。
- 报告中区分“可见奖励”和“推断奖励”。

### 20.2 不同游戏 UI 差异大

风险：通用识别准确率不稳定。

解决：

- 垂直类型切入。
- 项目级 UI 模板。
- 人工框选关键区域。
- 主动学习。

### 20.3 奖励强度主观

风险：同一奖励不同游戏价值不同。

解决：

- 默认规则 + 可调权重。
- 设计师 pairwise preference 校准。
- 与 telemetry/问卷/留存数据对齐。

### 20.4 音视频噪声

风险：压缩、遮挡、主播 overlay、不同分辨率影响识别。

解决：

- 支持置信度。
- 支持忽略区域。
- 多模态融合。
- 不把单一模型结论作为最终证据。

### 20.5 建议过于泛化

风险：报告变成空话。

解决：

- 每条结论必须绑定片段、指标、置信度。
- 不给无证据建议。
- 输出验证实验，而不是直接下判断。

## 21. 商业化方向

### 21.1 SaaS

- 按视频时长计费。
- 按项目席位计费。
- 按团队协作和批量分析计费。

### 21.2 专业版

- 私有部署。
- 本地模型。
- 数据不出 studio。
- Unity/Unreal 插件。

### 21.3 服务化

- 帮团队做竞品首小时奖励拆解。
- 帮发行团队做 Demo/Steam Next Fest 录像分析。
- 帮 mobile/F2P 团队做 FTUE reward pacing audit。

## 22. 早期验证实验

### 实验 A：明显奖励识别

问题：仅用录像能否识别大部分明显奖励？

方法：

- 选 20 段 roguelike 录像。
- 人工标注宝箱、道具、升级、Boss 结算。
- 比较 OCR + 视觉 + 音频融合结果。

成功标准：

- precision > 0.8
- recall > 0.6
- timestamp error < 2s

### 实验 B：设计师可用性

问题：奖励密度曲线是否对设计师有用？

方法：

- 给 3 到 5 名设计师看报告。
- 询问哪些发现值得讨论。
- 记录他们是否能快速定位问题片段。

成功标准：

- 每份报告至少 3 条 insight 被认为有价值。
- 人工看片时间节省 50% 以上。

### 实验 C：版本对比

问题：工具能否检测版本改动造成的奖励节奏变化？

方法：

- 同一关卡两个版本录像。
- 比较 reward_gap、reward_density、reward_effort_ratio。

成功标准：

- 能指出设计师已知的主要改动。
- 能发现至少 1 个设计师未注意到的节奏变化。

## 23. 推荐下一步

1. 选定首个游戏类型：建议 roguelike 或卡牌构筑。
2. 收集 10 到 20 段公开视频或自录 playtest。
3. 定义第一版 reward taxonomy。
4. 手工标注 100 个奖励事件。
5. 做一个离线 Python notebook 原型。
6. 输出第一张 reward_density 曲线。
7. 找 2 到 3 名游戏设计师验证报告是否有用。

## 24. 开放问题

- 奖励强度应该更偏“设计价值”还是“玩家感知价值”？
- 是否要把负反馈也纳入同一曲线？
- 不同类型游戏是否需要完全不同的 reward taxonomy？
- 竞品录像分析是否涉及平台条款或版权风险？
- 是否优先做无 SDK 录像方案，还是尽早做 telemetry 插件？
- 报告应该偏 UX research 语言，还是系统策划/数值策划语言？

## 25. 参考线索

- Lysto AI: https://lysto.gg/ai-playtest-analysis
- PlaytestCloud AI Analysis: https://www.playtestcloud.com/ai-powered-analysis
- Antidote AI Insights: https://antidote.gg/platform-features/ai-insights/
- modl.ai: https://modl.ai/
- Razer QA Companion-AI: https://www.razer.ai/qa/
- GameAnalytics: https://www.gameanalytics.com/
- Unity Analytics: https://docs.unity.com/en-us/analytics
- PlayFab Analytics: https://learn.microsoft.com/en-us/gaming/playfab/data-analytics/
- Machinations: https://machinations.io/
- Balancy Virtual Economy: https://en.docs.balancy.dev/liveops/virtual_economy/
- Google Cloud game developer AI workflow survey: https://www.googlecloudpresscorner.com/2025-08-18-90-of-Games-Developers-Already-Using-AI-in-Workflows%2C-According-to-New-Google-Cloud-Research

