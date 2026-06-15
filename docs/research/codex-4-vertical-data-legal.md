# Agent 4 报告：MVP 垂直选择 + 数据获取与合规

我的结论很明确：首个 MVP 不应该从 Hades-class 动作 roguelite 开始，而应该从 **card-builder / deckbuilder** 开始，具体测试床用 **Slay the Spire + Balatro + Monster Train**。fast-follow 再做 **room-based roguelite**，用 Hades / Hades II / Dead Cells / Vampire Survivors-class 做扩展。原因不是 deckbuilder 的商业想象最大，而是它最适合解决冷启动数据问题：画面稳定、奖励节点离散、UI 结构清楚、单小时标注事件密度高、用自录数据就能很快覆盖核心 reward taxonomy。

框架里“收集 10-20 段录像”过于乐观。真正问题不是有没有视频，而是能不能合法、稳定、可复现地拿到“同类 UI + 同类奖励语义 + 足够事件密度”的数据。公开视频可以帮研究判断，但不应该作为训练集和客户报告的主干。

## 1. 垂直选型：我会先做 deckbuilder

评分：5 分最好，1 分最差。

| 类型 | 屏幕奖励信号可读性 | UI/OCR 难度 | 音频 cue 清晰度 | 公开 footage 可得性 | 标题多样性 | 对设计师报告价值 | 总评 |
|---|---:|---:|---:|---:|---:|---:|---|
| Deckbuilder / card-builder | 5 | 4 | 3 | 5 | 4 | 4 | **25** |
| Roguelike / roguelite action | 4 | 2 | 4 | 5 | 5 | 5 | **25，但执行风险高** |
| Action-RPG / looter | 3 | 2 | 3 | 5 | 5 | 4 | 22 |
| Idle / gacha | 4 | 1 | 3 | 4 | 4 | 3 | 19 |

**Deckbuilder 第一的理由：**

- 奖励事件结构化：战斗胜利、金币、选牌、遗物、商店、升级、boss relic、ante/score 结算。Slay the Spire 和 Monster Train 几乎把 reward loop 显式呈现在独立 screen 上；Balatro 的 reward pacing 也集中在 blind completion、money、joker/shop、pack opening、牌型得分反馈。
- UI 稳定：主要信息是文本、数字、卡牌/遗物图标、固定区域 panel。OCR 和 template matching 可以先工作，不必依赖 heavy video model。
- 标注效率高：一小时 deckbuilder 录像可能有 80-200 个可标奖励事件，且边界清楚；一小时 Hades 录像也有很多反馈，但“奖励 vs 战斗反馈 vs 纯感官刺激”边界更模糊。
- 合规路径更干净：自录 Slay the Spire/Balatro/Monster Train 的前 30 分钟，去掉主播 overlay 和语音，数据质量比爬 VOD 高得多。公开视频只做研究对照，不进客户交付。

**为什么不先做 roguelite：**

Hades、Dead Cells、Vampire Survivors 作为 demo 很吸引人，但第一阶段会被三个噪声拖慢：动作画面遮挡、奖励与 combat juice 混杂、UI 变化跨标题太大。Vampire Survivors-class 更特殊，奖励密度极高，稀释/爆发分析有价值，但首个 detector 会把击杀数字、经验宝石、升级弹窗、宝箱动画混在一起。

**fast-follow：room-based roguelite。**

等 deckbuilder 完成“reward event timeline + reward density + human calibration”闭环后，再做 Hades/Dead Cells。此时可以复用 annotation tool、report schema、density/gap metrics，只新增 combat effort 和 sensory reward 的检测。

## 2. 数据来源：先自录，再付费 playtester，公开视频只做辅助

我建议把数据分成三层，不要混用：

1. **Clean proprietary/evaluable set：自录 + hired playtester。**  
   用于 Phase 0/1 开发、标注、模型训练、demo。优点是权利链最清楚，画质稳定，可要求固定分辨率、无 overlay、无配音、原始音频。成本低：内部自录 50 小时几乎只是人力；外包玩家按 $15-40/hour 录制，含说明与上传，实际全成本约 $30-80/hour-of-video [ASSUMPTION — verify]。

2. **Reference set：公开视频、speedrun archives、Twitch/YouTube VOD。**  
   只用于人工研究、taxonomy 验证、鲁棒性测试，不用于模型训练和客户报告原始素材。质量问题很多：压缩、streamer facecam、字幕、剪辑、非标准分辨率、mod、patch 版本不明、评论音轨干扰。公开视频很适合发现“真实玩家怎么看奖励”，但不适合做初始黄金集。

3. **Commercial validation set：partner studio playtests。**  
   用于验证产品价值，不用于训练通用模型，除非合同写明。最早只需要 1-2 个小团队，每队 5-10 段录像。它的价值是看报告是否影响设计讨论，而不是扩大数据量。

**Phase 0 需要多少数据？**

- 目标：rule-based detector + timeline/report prototype。
- 需要：3 个 deckbuilder 标题，每个 8-12 小时 clean video，总计 **25-40 小时**。
- 标注：每标题 300-600 个 reward events，总计 **1,000-1,800 个事件**。
- 足够做：固定 UI 区域 OCR、reward screen detection、event fusion、density/gap 曲线。

**Phase 1 需要多少数据？**

- 目标：半自动 detector + 项目模板 + 少量跨标题泛化。
- 需要：5-8 个 deckbuilder/牌类 roguelite 标题，总计 **120-250 小时** clean video。
- 标注：**8,000-20,000 个 reward events**，其中至少 2,000 个 hard negative / near-miss（例如 damage number、普通 hover、卡牌说明弹窗、shop browsing，不算 reward）。
- 如果要训练视觉 detector：每个高频 event type 至少 500-1,000 个正样本，低频 boss/act completion 至少 150-300 个正样本才有意义 [ASSUMPTION — verify]。

我不会一开始追求 300 段录像。更好的指标是“每个 event type 有多少可复用、边界清楚、跨 session 的例子”。30 小时 clean deckbuilder 比 300 段杂乱 VOD 更有用。

## 3. 标注 pipeline：先事件时间轴，不先做像素级检测

**推荐工具：先 Label Studio，后自研薄前端。**

CVAT 适合 frame-level bbox/segmentation，但此项目第一阶段不是做通用 object detection，而是做 temporal event annotation。Label Studio 支持视频时间段、分类、文本字段，启动快；缺点是游戏视频回放和快捷键体验不一定够好。我的建议：

- Phase 0：Label Studio + ffmpeg 抽关键帧 + 自动生成 prelabel JSON。
- Phase 1：做一个自研 web timeline，用 video.js 或 Remotion-style clip viewer，专门支持奖励事件合并/拆分、OCR evidence、前后 5 秒回看。

**事件 schema（扩展框架 §19）：**

```json
{
  "session_id": "sts_0007",
  "game": "Slay the Spire",
  "build_or_patch": "unknown",
  "source_rights": "self_recorded",
  "timestamp_start": 842.20,
  "timestamp_end": 850.10,
  "event_family": "reward_event",
  "reward_type": "card_choice",
  "subtype": "post_combat_card_reward",
  "reward_score_human": 5,
  "novelty": "repeat",
  "channels": ["visual", "ocr", "audio"],
  "screen_context": "reward_screen",
  "phase_before": "combat",
  "effort_context": {
    "combat_duration_sec": 74,
    "hp_lost_pct": 0.22,
    "failed_attempts_since_last_reward": 0
  },
  "ocr_targets": [
    {"region": "card_titles", "text": ["Pommel Strike", "Shrug It Off", "Cleave"]}
  ],
  "boundary_confidence": 0.95,
  "semantic_confidence": 0.9,
  "annotator_id": "a02",
  "notes": "Post-combat card selection; no rare card."
}
```

**标签层级：**

- `reward_type`：gold_gain, card_choice, relic_gain, pack_opening, shop_unlock, score_payout, level_up, boss_reward, run_end_summary。
- `non_reward_but_feedback`：damage_feedback, combo_feedback, hover_preview, menu_browse, score_animation_only。
- `effort_segment`：combat, shop_decision, deck_editing, routing_decision, boss_combat, failed_run。
- `quality_flags`：overlay_present, commentary_audio, cropped_ui, modded_game, unknown_patch, low_resolution。

**VLM/LLM 预标注：**

第一阶段不要让 VLM“理解整段视频”。我会用低成本 pipeline：

1. ffmpeg 每秒 1 帧，scene-change 额外抽帧。
2. OCR（PaddleOCR/PP-OCR 系列或 EasyOCR）找关键词：Reward, Choose a Card, Gold, Relic, Shop, Victory, Blind, Cash Out, New Joker。
3. CLIP/SigLIP image embedding 做 reward screen 相似检索，用 20-50 张人工 positive screenshots bootstrap [ASSUMPTION — verify model choice]。
4. VLM 只看候选片段的 3-5 张关键帧，输出 `reward_type` 和 evidence；人类确认。

**标注成本：**

- 从零手工标注：deckbuilder 约 0.5-1.0x video duration，即 1 小时视频需要 30-60 分钟标注。
- 预标注后确认：约 0.2-0.4x，即 12-24 分钟/小时视频。
- 按 $18-35/hour 标注人力估算，成本约 **$5-25 per hour-of-video**；专家设计师复核另算，约 **$40-100/hour** [ASSUMPTION — verify]。

**一致性目标：**

- reward_event 是否存在：Cohen's kappa >= 0.80。
- reward_type：macro F1 >= 0.85 或 kappa >= 0.75。
- timestamp boundary：start/end median absolute error < 1.5 秒；reward screen 类 < 1 秒。
- reward_strength：不要追求绝对一致，用 pairwise ranking。目标 Spearman rho >= 0.65。强度主观性太高，早期应该允许项目级校准。

## 4. 法律 / ToS / copyright：公开视频是雷区，不是地基

以下法律判断都应视为 **[ASSUMPTION — verify with counsel]**。

**自录 gameplay：相对最安全，但不是零风险。**  
玩家录制自己游玩商业游戏，通常平台生态默认允许分享和评测，但游戏 EULA 可能限制商业用途、素材再分发、AI training 或 reverse engineering。内部研发使用风险较低；把截图/clip 放进营销页、客户报告或训练数据商业化，风险上升。规避方式：保存购买/录制记录，只在内部工具中使用短片段证据；公开展示尽量用自研 demo game、开源/授权游戏或 partner 授权素材。

**YouTube/Twitch VOD 用于内部模型训练：高不确定性。**  
风险来自四层：平台 ToS 可能限制下载和自动化处理；streamer 对视频录制/解说/overlay 拥有版权或邻接权；游戏厂商拥有游戏画面/音乐/角色素材；VOD 中可能有第三方音乐、facecam、聊天内容和个人数据。即使技术上可下载，也不等于可用于 AI training。我的建议：不要把公开视频纳入训练集，除非获得 creator 授权或只使用平台 API 允许的方式做 transient analysis。

**公开视频用于客户-facing 竞品拆解报告：风险更高。**  
如果报告里嵌入 streamer 片段、截图、logo、音乐，且面向商业客户收费，版权和 DMCA 风险明显。即使用“fair use/评论分析”也不应作为产品默认依赖，因为 fair use 是抗辩不是许可 [ASSUMPTION — verify with counsel]。更安全的做法：

- 客户自己上传其有权分析的录像，并在条款中确认权利。
- 竞品拆解只输出自生成图表、时间戳、文本摘要，不再分发原始 clip。
- 如需截图证据，使用最短必要帧、低分辨率、带引用来源，仅限内部评审包。
- 为公开 marketing demo 使用授权游戏、partner footage 或自研 toy game。
- 明确禁止用户上传含 facecam、聊天个人信息、未经许可音乐的素材，或提供自动模糊/静音处理。

**速度跑/speedrun archives：质量好但不代表普通体验。**  
Speedrun 视频通常 UI 清楚、路线固定、奖励事件可预测，但玩家行为极端优化，奖励 pacing 对普通玩家不成立。适合作为 detector regression set，不适合作为“设计报告价值”验证。

## 5. 最可能让数据计划卡几个月的点

最大风险不是找不到视频，而是团队误以为“公开视频很多”就等于“数据集可用”。随后会发生三件事：法务不敢让 VOD 进训练和客户报告；技术发现 VOD 质量差导致 OCR/音频检测不稳定；标注员无法统一判断哪些反馈算 reward。三者叠加，会把项目拖成“我们先做通用视频理解平台”，MVP 消失。

第二个风险是 reward_strength 标注过早精细化。让标注员给每个奖励打 1-10 分，看似符合框架，实际会制造低一致性数据。早期应该把强度拆成可观察因素：event type、rarity text/color、novelty、context effort、sensory intensity，再由规则或设计师权重合成。

第三个风险是从 Hades-class 开始。它 demo 好看，但需要同时解决 combat phase、动作视觉、音效、UI、boss、房间奖励和 story reward。deckbuilder 虽然不性感，但能最快验证“录像 -> 奖励事件 -> 曲线 -> 设计师觉得有用”。

## 对启动方向的建议 (Recommendations for project kickoff)

1. **先做 Slay the Spire/Balatro/Monster Train clean dataset，25-40 小时。**  
   理由：最快建立合法、稳定、高事件密度的 Phase 0 黄金集；预计 1-2 team-weeks 录制 + 整理。

2. **用 Label Studio 建 temporal event 标注，不做 bbox 优先。**  
   理由：当前核心是奖励时间轴和语义，不是像素级检测；预计 3-5 天搭建 schema、导入视频、跑第一轮标注。

3. **建立“公开视频隔离策略”：reference only，不进训练，不进客户报告。**  
   理由：提前避免 ToS/copyright 卡死；预计 2-3 天写数据政策和 source_rights 字段，另需 counsel review。

4. **Phase 0 验收改成每标题 300+ 事件，而不是 20 段视频。**  
   理由：模型和规则吃的是事件覆盖，不是视频段数；预计 2-3 周可完成第一版 detector + 曲线报告。

## 关键不确定性 (Key uncertainties to resolve)

1. **商业游戏自录 footage 用于内部训练和付费 SaaS 分析的权利边界。**  
   如果 counsel 认为这也需要逐游戏授权，MVP 必须转向 partner studio 或开源/授权游戏素材。

2. **Deckbuilder 报告对目标客户是否足够有购买意愿。**  
   如果设计师认为 deckbuilder 奖励曲线“太显然”，需要更早切到 Hades/Vampire Survivors-class。

3. **VLM/OCR 预标注能否把人类标注成本降到 0.3x video duration 以下。**  
   如果不能，Phase 1 数据集成本和周期会明显上升，需要缩小 taxonomy 或提高项目级模板投入。
