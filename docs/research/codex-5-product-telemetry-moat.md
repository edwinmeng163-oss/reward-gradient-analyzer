# Agent 5 报告：产品形态、Telemetry 双通道与防守壁垒

## 核心立场

Reward Gradient Analyzer 的第一性产品不是“自动识别奖励事件的模型”，而是一个让设计师快速把录像变成可争论证据的 calibration/review 工作台。模型只负责把 30 分钟录像压缩成 80-200 个候选事件和 5-10 个可疑区间；真正让产品可用、可复用、可防守的是项目级模板、证据绑定、权重语义和跨版本比较。

我不建议早期把 Unity/Unreal SDK 做成主线。SDK 的价值很大，但早做会把产品从“任何录像可用”拖回“需要接入工程排期”。正确策略是：Phase 0/1 坚持 video-first，但从第一天定义 dual-channel schema 和 timestamp alignment contract；Phase 2 在设计伙伴愿意每周使用后，做一个极薄的 telemetry importer，而不是完整引擎插件；Phase 3 再做 SDK。

## 1. Human-in-the-loop calibration UX：真正的产品表面

### 1.1 MVP 工作流

MVP 应该围绕“第一次校准可接受，第二次分析显著便宜”设计，而不是围绕漂亮 dashboard。

推荐的首次分析流程：

1. Project setup：选择 genre template，例如 `roguelite_run`, `card_battler_run`, `ARPG_quest`；填写 session 目标，例如“新手前 12 分钟每 45-75 秒至少一次明确反馈”。
2. Region-select：在 3-5 个代表帧上框选固定 UI 区域，包括 currency/xp/level、reward popup、combat result、quest objective、ignore overlay。每个 region 保存 `bbox`, `expected_text_type`, `sampling_rate`, `parser_hint`。
3. Candidate event review：系统按置信度和影响排序展示候选事件。每张 event card 必须有短 clip、前后截图、evidence chips，例如 `OCR +120 gold`, `audio: victory_jingle`, `visual: reward_panel`, `confidence=0.82`。
4. Accept/reject/type correction：设计师用快捷键批量确认、拒绝、改类型、合并/拆分事件。目标是每个候选事件平均 2-4 秒处理完。30 分钟 roguelite 录像通常可能产生 80-150 个候选 reward/effort 事件 [ASSUMPTION — verify]，因此 review budget 应控制在 6-10 分钟。
5. Weight tuning：按 reward ontology 调整权重，而不是逐事件打分。例：`small_currency=1`, `new_card_choice=7`, `elite_reward=11`, `boss_clear=25`, `new_system_unlock=30`。支持 8-12 个 pairwise preference 问题：“A 片段和 B 片段哪个更像强奖励？”用 Bradley-Terry 或简单 Elo 更新类型权重。
6. Target curve：用 3 种目标模板替代复杂图表编辑：`steady drip`, `sawtooth challenge-reward`, `crescendo-to-boss`。设计师只需设置窗口长度、目标 gap、最大可接受空窗。例如 `window=60s`, `target_reward_density=0.10-0.25`, `max_gap=90s`, `post_failure_feedback<=20s`。

第二次分析便宜的关键不是“模型自动变聪明”，而是 project template 复用：

```json
{
  "project_id": "p_rogue_001",
  "genre_template": "roguelite_run",
  "ui_regions": [
    {"name": "gold", "bbox": [1540, 42, 1820, 88], "parser": "numeric_delta"},
    {"name": "reward_popup", "bbox": [520, 160, 1400, 620], "parser": "item_card"}
  ],
  "reward_weights": {
    "small_currency": 1.0,
    "card_choice": 7.0,
    "relic_acquired": 10.0,
    "boss_clear": 25.0
  },
  "target_curve": {
    "mode": "sawtooth_challenge_reward",
    "window_sec": 60,
    "max_gap_sec": 90,
    "post_failure_feedback_sec": 20
  },
  "ignored_regions": ["streamer_facecam", "sponsor_overlay"]
}
```

量化目标应更激进：第一次 30 分钟录像从上传到可用报告 <= 45 分钟，其中人工 <= 20 分钟；第二次同项目录像人工 <= 6 分钟，整体 <= 12 分钟。Framework 的“-70% calibration time”方向正确，但如果第一次要花 60 分钟以上，设计师会把它当成研究服务，不会当成周常工具。

### 1.2 可信度机制

每条 finding 都必须是 evidence-bound，不允许生成“感觉像奖励不足”这种抽象评论。诊断卡片最小结构：

- Claim：例如 `06:20-09:10 exploration reward gap exceeds project target`。
- Metric：`gap=170s`, `target_max=90s`, `effort_density=1.6x session median`。
- Evidence：3 个可跳转 clip：gap start、最高 effort、下一次 reward。
- Confidence breakdown：`phase_conf=0.76`, `reward_detection_conf=0.89`, `effort_conf=0.62`。
- Actionability：只能输出验证建议，例如“在 07:10 附近插入低价值探索发现，并对比 gap P90”，不要直接宣判“应该加宝箱”。

最值得做的 UX 细节是 clip jump-to 和 diffable evidence。设计评审场景里，报告本身不是终点，团队会争论。工具要让设计师在 5 秒内跳到证据、在 30 秒内导出 15 秒 clip、在 compare view 中并排看 Build A/B 的同类片段。

## 2. Perceived-vs-actual reward 双通道

视频通道回答“玩家可能感知到了什么”；telemetry 通道回答“游戏内部实际发生了什么”。双通道的 killer insight 不是更高 precision，而是发现二者错位：

1. Internal reward fired, player did not perceive：后台给了 XP、quest progress 或 pity counter，但 UI 没有反馈，导致玩家体验上是空窗。
2. Player perceived reward, internal value is tiny：华丽特效包装了低价值奖励，短期爽感高但可能形成 reward dilution。
3. Event timing mismatch：奖励在战斗结束后 12 秒才结算，视频显示玩家已经转入菜单/移动，反馈错过情绪峰值。
4. Hidden economy inflation：telemetry 显示货币增长频繁，视频显示玩家只注意到少数弹窗；这会解释“数值上不缺奖励，体验上仍然干”。

Telemetry schema 应非常薄，先 importer 后 SDK：

```json
{
  "session_id": "s_001",
  "client_time_ms": 381240,
  "monotonic_time_ms": 10294420,
  "event_name": "reward_granted",
  "reward_type": "xp",
  "amount": 120,
  "source": "quest_step",
  "presentation": {
    "ui_surface": "toast",
    "audio_cue": "none",
    "animation_id": "xp_tick_small"
  },
  "player_state": {
    "level": 3,
    "quest_id": "q_014",
    "phase": "exploration"
  }
}
```

Alignment contract：

- 录制开始时显示/记录 `sync_marker`，例如画面左上角 2 秒显示 session code，同时 telemetry 发送 `video_sync_marker_displayed`。
- SDK/日志使用 monotonic clock，不信任 wall clock。
- 对齐后允许 drift correction：每 5 分钟插入 heartbeat，估计 `video_time = a * telemetry_time + b`。
- 验收指标：明显 UI reward 的 telemetry-video timestamp median error < 500ms，P95 < 2s [ASSUMPTION — verify]；对设计诊断来说 2 秒已足够。

是否早做 SDK？我的答案：不要早做“SDK 产品”，但要早做“telemetry 文件导入”。原因很现实：早期设计伙伴未必愿意排工程接入；他们愿意上传录像和一份 CSV/JSON log 的概率更高。Unity/Unreal 插件会引入隐私、版本兼容、性能、构建流程、console 平台限制等工程成本，容易吞掉 4-8 team-weeks [ASSUMPTION — verify]。一个 CSV/JSON importer + sync marker 可能 1-2 team-weeks 做到可用。

## 3. Moat / defensibility 排名

我对候选壁垒的排名如下：

1. Project-level UI/weight templates：最早产生、最贴近工作流、最能带来 switching cost。一个项目积累了 10 个 UI region、30 个 reward type 权重、目标曲线和误检规则后，第二次分析才真正便宜。这是短期最强壁垒。
2. Annotated event dataset：长期最强，但早期不要自欺。100-300 个事件样例只够做 demo；要形成跨游戏泛化，可能需要每个垂类 5k-20k 高质量事件 [ASSUMPTION — verify]，且版权/公开视频来源会限制训练用途。它会 compound，但启动慢。
3. Designer-trust/workflow lock-in：如果每条 insight 都能跳 clip、导出、进入评审结论，这会形成组织记忆。它比模型准确率更防守，因为竞品即使识别事件，也未必嵌入设计评审流程。
4. Video+telemetry alignment：中长期高价值，尤其面向 internal studio。它能产生独特洞察，但只有在客户愿意接入后才成立；早期不是 go-to-market 壁垒。
5. Per-genre reward ontologies：必要但不够防守。taxonomy 很容易被复制；真正有价值的是 taxonomy + weights + examples + diagnostics 的组合。
6. Competitor-teardown corpus：营销价值高，防守性中等偏低。公开视频版权、平台条款和版本漂移都会限制复用。它适合作为内容获客和 benchmark，不应当作为核心 moat。

假的壁垒是“我们有一个 reward score 公式”。公式不防守，且主观性强。可防守的是团队在每个项目中把公式校准成可复用配置，并把每次设计师纠错变成下一次分析的资产。

## 4. Minimum Lovable Product：设计伙伴每周会用什么

最小可爱产品不是全自动报告，而是“上传录像后，30 分钟内拿到一条可审阅、可修正、可比较的 reward timeline”。

我会把 MLP 定义为：

- 支持 1 个垂类，优先 card battler 或 roguelite。原因是 reward node 清楚，region template 稳定，事件解释成本低。
- 支持单项目模板：UI regions、ignored regions、reward ontology、weights、target curve。
- 支持 candidate review queue：accept/reject/type/merge/split，快捷键操作，保存纠错。
- 支持 timeline + curve + evidence clips：reward events、effort segments、phase bands、gap/cliff/dilution flags。
- 支持 Build A/B compare：同一模板下比较 reward_gap P50/P90、reward_density、post-failure feedback delay、boss/elite reward score。
- 输出 Markdown/PDF 报告，但报告必须能回链到 web UI 的时间戳和 clip。

刻意推迟：

- 不做实时分析。
- 不做通用游戏。
- 不做完整 Unity/Unreal SDK。
- 不做自动设计建议引擎。
- 不做复杂主动学习训练 UI。
- 不做“奖励好坏总分”。

3 人小团队粗估：8-10 周可以做出 MLP。拆分为：video ingestion/OCR/frames 2 周，review UI 2-3 周，template/weights/target curve 2 周，metrics/report/compare 2 周，设计伙伴试跑和修补 1 周 [ASSUMPTION — verify]。如果同时做 SDK，范围会膨胀到 14-18 周，且未必提高早期验证质量。

## 5. Adversarial：HITL 什么时候会比人工看片更慢

最危险的失败模式是“工具把设计师变成标注员”。如果 30 分钟录像产生 300 个候选，要求逐个确认、逐个打分、逐个修正类型，这比 1.5 倍速看片还慢。另一个陷阱是 region-select 太细：让用户框 20 个 UI 区域、配置 20 个 parser，产品就变成 CV 标注工具。

避免办法：

1. 只 review 高影响候选。低价值小货币事件可以按聚合曲线处理，不要求逐个确认。UI 应提供 `auto-accept below impact threshold`。
2. 按 uncertainty 和 diagnostic impact 排序，而不是按时间排序。先问会改变结论的事件，例如断档边界、boss reward、失败后反馈。
3. 权重按类型调，不按事件调。逐事件打分会毁掉体验。
4. 第一版宁可少报，不要多报。Precision 比 recall 更重要；漏掉小奖励比塞满误检更可接受。
5. 复用模板必须显性量化。每次分析结束显示：`manual actions: 31`, `template updates: 7`, `next-run estimated review: 5 min`。让用户看到校准是在积累资产。

我的判断：如果第二次同项目分析人工仍超过 10 分钟，产品就没有形成工作流价值；如果每条 insight 不能一键跳到证据，报告就不可信；如果没有 compare view，设计团队不会每周复用，只会偶尔当研究报告。

## 对启动方向的建议 (Recommendations for project kickoff)

1. 先做 project template + review queue，而不是先做更复杂模型。理由：第二次分析是否便宜决定留存；粗估 2-3 team-weeks。
2. 选择一个 reward node 清楚的垂类做 MLP，推荐 roguelite 或 card battler。理由：HITL 成本和识别难度最低，能最快验证设计师是否愿意每周用；粗估 1 team-week 定义 ontology 和样例。
3. 从第一天定义 telemetry schema 和 sync marker，但只做 JSON/CSV importer，不做 SDK。理由：保留 dual-channel 路径，同时避免工程接入拖慢 video-first 验证；粗估 1-2 team-weeks。
4. 把 compare view 放进 MLP，不要延后到高级版。理由：设计团队最常见问题是 Build A/B 是否改善，单次报告不足以形成周常习惯；粗估 2 team-weeks。

## 关键不确定性 (Key uncertainties to resolve)

1. 设计师愿意投入的首次校准时间上限是多少？如果真实上限低于 10-15 分钟，当前 HITL 方案必须大幅收缩。
2. 视频候选事件 precision 能否在单垂类达到 >0.8？如果误检太多，review queue 会退化为标注劳动。
3. 设计伙伴是否有能力提供 telemetry log 或愿意加 sync marker？如果不能，dual-channel 只能作为 enterprise 后续路线，不能影响早期定位。
