# Agent 1：感知管线技术可行性 — Perception Pipeline Feasibility

## 结论先行

“从录像稳定抽取玩家可感知奖励事件”可行，但前提非常窄：**按单个游戏/单个类型做项目级校准，而不是通用视频理解**。2026 年最靠谱路线不是单一 video VLM 端到端读录像，而是 **frame sampling + OCR/UI 模板 + 视觉/音频 specialist detector + 少量 VLM 复核**。Phase 1 的指标（30 分钟录像 <10 分钟、明显事件 precision >0.8、timestamp error <2s）在一款固定游戏上有机会达成；跨游戏泛化基本不应承诺。

真正瓶颈不是模型“看不懂画面”，而是：什么算一个 reward event、多个感官信号如何合并、结算面板里多项奖励是否拆分、货币小幅增长是否值得进入时间轴。这些是产品/标注规范问题，会直接吞掉模型精度。

## 1. 分模态可行性与现实数字

### OCR / UI 数字读取

最佳实践：固定游戏里先让用户框选 ROI（金币、XP、等级、任务、结算面板），再用 PaddleOCR/PP-OCRv5 类 OCR 跑 ROI crop，叠加 temporal smoothing 和数字差分。VLM 可用于“这块 UI 是什么含义”的初始化，不适合作为逐帧 OCR 主力。

现实精度：

| 场景 | Precision / Accuracy | Recall | 主要失败 |
|---|---:|---:|---|
| 固定 ROI 大号数字，如金币/分数 | 90–98% 数值准确率 | 85–95% | 字体描边、压缩、滚动计数动画、遮挡 |
| 结算面板文本/奖励名 | 75–92% | 70–90% | 稀有字体、多语言、图标代替文字 |
| 战斗中飘字/小图标 | 50–75% | 35–65% | 动态模糊、VFX 遮挡、持续时间 <0.5s |

我会把 OCR 当作 Phase 0/1 的主信号，因为它能给出“货币增加、LEVEL UP、Reward、Victory、Complete”等强证据。但它不能单独判断感知强度：+3 gold 和 boss chest 都可能只是数字变化。

### 视觉奖励事件检测

最佳实践：**项目级 detector + 屏幕状态分类**。用 YOLOv8/YOLO11 类模型检测 reward panel、chest、drop beam、rarity border、card/relic/item popup；用 SAM2 做分割/跟踪只在需要生成证据截图或复杂 UI mask 时使用。少样本 VLM 适合给候选帧解释：“这是奖励选择界面还是商店界面？”不适合全量扫描。

现实精度（固定游戏、100–300 个标注事件后）：

| 事件类型 | Precision | Recall | 备注 |
|---|---:|---:|---|
| 结算/胜利/升级面板 | 85–95% | 80–95% | UI 结构稳定，最好做 |
| 宝箱开启/卡牌翻开/道具弹窗 | 75–90% | 65–85% | 需要检测持续区间而不是单帧 |
| 掉落光柱/稀有颜色/VFX 强度 | 60–85% | 45–75% | 和技能特效、爆炸、环境光误混 |
| 跨游戏 zero-shot | 40–70% | 25–55% | 不应作为产品承诺 |

这里我会避免“先上 SAM2/VideoMAE 做通用视觉理解”。奖励事件通常是 UI/符号事件，不是自然视频动作识别；screen-state classifier 往往比大模型更便宜、更稳。

### 音频奖励 cue 检测

最佳实践：固定游戏做音频指纹/频谱模板；通用 baseline 用 CLAP/AudioCLIP 类文本-音频匹配或 YAMNet/AST 类分类器。Whisper 只负责玩家语音/旁白转录，不负责 coin sound 或 victory jingle。

现实精度：

| 场景 | Precision | Recall | 主要失败 |
|---|---:|---:|---|
| 同一游戏固定 coin / level-up / victory cue | 85–95% | 80–95% | 音量变化、混响、叠音 |
| 通用“奖励音效”zero-shot | 50–75% | 40–70% | 背景音乐、主播说话、技能音效相似 |
| 玩家 think-aloud 里说“nice/level up”等 | 60–85% | 40–75% | 语言、口音、噪声、沉默玩家 |

音频适合做 trigger 和 confidence boost，不适合独立产生 reward_event。尤其公开录像常有主播 overlay、音乐压缩、语音混音。Phase 0 可以只做 onset/峰值 + 若干关键词 cue，不要把音频做成核心依赖。

### Gameplay phase segmentation

最佳实践：粗粒度 phase 用规则 + UI/视觉信号：敌人血条/伤害数字 -> combat，地图移动无敌人 -> exploration，大血条/特殊音乐 -> boss，面板占屏 -> menu/reward/shop，死亡字样/灰屏 -> death/retry。VLM 可以按 5–10 秒 chunk 复核阶段标签。VideoMAE/SlowFast/TimeSformer 只有在有大量同类型标注时才值得。

现实精度：

| Phase | 固定游戏准确率 | 边界误差 |
|---|---:|---:|
| menu / reward_screen / death / victory | 85–95% | 1–3s |
| combat / boss_fight | 75–90% | 2–6s |
| exploration / puzzle / idle / cognitive confusion | 55–80% | 5–15s |

Phase segmentation 的作用应是给 reward_event 加上下文，不要先追求完美 phase 再做奖励识别。

## 2. VLM-heavy vs specialist-heavy

**VLM-heavy**：把抽帧或视频片段交给 GPT-4o/5-class、Gemini-class、Qwen2.5-VL-class 模型 few-shot 读事件。[ASSUMPTION — verify] 2026 年商用 video VLM 对短片段语义总结很强，但对“漏掉 0.7 秒掉落闪光、稳定输出结构化 timestamp、区分商店展示和实际获得”仍不稳定。优点是冷启动快、能解释复杂 UI；缺点是成本、延迟、隐私、幻觉、schema drift、采样漏检。

**Specialist-heavy**：ffmpeg 抽帧/音频，PaddleOCR 读 ROI，YOLO/模板检测 UI 状态和奖励对象，CLAP/YAMNet/模板做音频 cue，最后规则融合。优点是便宜、可测、可缓存、能跑 30 分钟 <10 分钟；缺点是每个游戏要校准，初期工程碎。

我的排序：

1. **Specialist-heavy + VLM 复核候选帧**：唯一适合产品化 Phase 1。
2. **VLM-heavy 做标注助手/原型分析**：适合 Phase 0 快速发现 taxonomy，不适合作为主干。
3. **端到端视频 VLM 全自动事件流**：不建议作为启动方向，除非只做内部研究 demo。

## 3. 多模态融合难度

融合本身中等难，不是深度学习难题，更像事件数据库清洗问题。推荐把每个 detector 输出成统一候选：

```json
{
  "t_start": 412.1,
  "t_end": 416.8,
  "modality": "ocr|visual|audio",
  "label": "level_up|gold_delta|victory|item_popup",
  "value": {"delta_gold": 25, "rarity": "rare"},
  "confidence": 0.84,
  "evidence_ref": "frame_04122.jpg"
}
```

然后用 interval clustering 合并：

```text
merge_score = 0.45 * temporal_overlap
            + 0.25 * semantic_compatibility
            + 0.20 * spatial_relation
            + 0.10 * phase_prior

if merge_score > 0.65 and abs(center_i - center_j) < T(label_pair):
    merge candidates
```

时间窗不能固定一个 T：金币音效可能领先/滞后 0.5–1.5s；结算面板会持续 5–20s；boss victory 到奖励掉落可能隔 10s。真正会打破融合的是：

- 一个结算面板包含 5 个奖励：是一个 event 还是五个 event？
- 货币连续 tick：每个 tick 都是 event 会造成 reward dilution 假象。
- 商店/背包展示道具：视觉上像奖励，但不是获得。
- 奖励延迟：Boss 死亡、过场动画、结算、开箱之间跨越十几秒。
- 音频 cue 被技能音效或 streamer 盖住。

因此需要两级输出：`reward_moment`（一次玩家感知奖励时刻）和 `reward_items`（该时刻包含的具体奖励项）。Phase 0 只做 moment，Phase 1 再拆 items。

## 4. 成本与延迟估算

30 分钟 1080p/60fps 是 108,000 帧。任何“全帧 VLM”都不可接受。必须采样。

### A. VLM-heavy

假设抽 1 fps 全局帧（1,800 张）+ 100 个 3–5 秒候选片段给商用 VLM。[ASSUMPTION — verify] 2026 年不同供应商视觉 token/视频计费差异很大，保守估计每条 30 分钟录像 **$5–$80**，极端高分辨率或高频采样可更高。wall-clock 在高并发 API 下可能 8–25 分钟；受 rate limit、上传、模型排队影响，很难稳定承诺 <10 分钟。若用本地 Qwen2.5-VL-class 模型，[ASSUMPTION — verify] 单张图 0.3–2s 级别取决于 GPU 和模型大小，1,800 帧通常会落到 10–60 分钟，不适合作为默认 SaaS fast path。

### B. Specialist-heavy

推荐分析代理：视频降到 720p，1 fps 全局帧；UI ROI 2–5 fps；音频 16kHz；触发区间局部升到 8–15 fps。

粗略成本：

| 模块 | GPU/CPU 时间 |
|---|---:|
| ffmpeg 转码/抽帧/音频 | 1–3 分钟 |
| OCR 1,800 全帧 + ROI 加密 | CPU 4–12 分钟；GPU 1–4 分钟 |
| YOLO/模板检测 1–5 fps | GPU 1–5 分钟 |
| 音频 cue / CLAP / 峰值 | 0.5–2 分钟 |
| fusion/report | <1 分钟 |

[ASSUMPTION — verify] 用 L4/A10/4090 级 GPU，单条 30 分钟录像端到端 **5–12 分钟**现实；云成本约 **$0.10–$1.00/30min video**（不含工程、存储、VLM 复核）。CPU-only 更像 20–45 分钟。

所以 Phase 1 的“30 分钟分析 <10 分钟”现实条件是：GPU、有采样策略、OCR ROI 化、VLM 只查候选帧。若坚持 VLM-heavy，这个指标不稳定。

## 5. 最便宜可信的 Phase-0 demo

我会选 **Hades**，不是 Slay the Spire。Slay the Spire 太 UI 化，能证明 OCR dashboard，但不能证明“gameplay video reward perception”。Hades 有房间奖励、boon/hammer 选择、金币/宝石/钥匙、宝箱、Boss victory、强音效/VFX，足够代表 roguelite。

两周 demo 目标：10 段 10–20 分钟 Hades 录像，人工标注 100–150 个明显 reward_moment，自动识别 recall ≥0.60、precision ≥0.75、timestamp median error <3s，输出 timeline + reward_density。

最小管线：

1. ffmpeg 抽 2 fps 720p 帧；音频抽 16kHz wav。
2. 手工定义 5–8 个 screen states：combat、room_clear、boon_choice、shop、inventory、death、victory、loading。
3. OCR：PaddleOCR 读大字和面板关键词，如 “BOON”、“CHOOSE”、“LEVEL”、“VICTORY”、货币数字；对固定 UI 区域做模板/颜色检测。
4. 视觉：先不用训练 YOLO，优先用颜色/布局/模板检测 boon panel、reward icon、chest/victory screen；如果时间够，再标 100 张图训练一个 YOLOv8n reward-panel detector。
5. 音频：只做 onset/能量峰值 + 少量 victory/boon cue 模板；用于 trigger，不单独产事件。
6. VLM：只对低置信候选帧批量问“这是获得奖励/选择奖励/商店展示/非奖励吗”，作为复核，不进入实时主链。
7. 输出：`reward_moment` 时间轴，事件类型限定为 `boon_choice`, `currency_gain`, `room_reward`, `boss_victory`, `death_no_reward`, `shop_non_reward`。

明确跳过：SAM2、通用跨游戏 detector、完整 reward_score、复杂 effort 模型、玩家语音情绪。Phase 0 effort 只用 `time_since_last_reward + combat_duration + death_count`。

## 6. 对 framework 的逆向批评

1. **Section 9–10 模块过多，顺序看似完整但启动成本偏高。** Phase 0 不应同时做 OCR、视觉、音频、phase、scoring、effort、diagnosis。先把 `reward_moment` 做准，否则后面曲线全是精致噪声。
2. **1 fps 全局采样太乐观。** 很多 pickup/VFX 少于 1 秒。正确做法是 1 fps baseline + UI 差分/音频峰值/场景变化触发局部高频采样。
3. **“视觉奖励事件检测”被低估。** 最难不是检测宝箱，而是区分获得、预览、商店、背包查看、任务提示、教程提示。这需要游戏语义和状态上下文。
4. **奖励评分早了。** 在事件识别未稳定前，`reward_score = base * multipliers` 会制造伪精确。前两个月应只做 ordinal strength：small / medium / major / milestone。
5. **验收指标缺少 event definition。** Precision/recall 必须绑定 gold-label 规则：结算面板算一个还是多个？金币 tick 合并窗口多长？玩家看到但未选择的奖励是否计入？

我认为准确率瓶颈排序是：

1. reward event 标注规范与融合规则；
2. UI/OCR ROI 稳定性；
3. 状态上下文，尤其商店/背包/奖励选择的区分；
4. 视觉 VFX detector；
5. 音频 detector。

## 对启动方向的建议 (Recommendations for project kickoff)

1. **先做单游戏 Hades reward_moment extractor** — 用模板/OCR/规则证明 60% recall 与可读时间轴，避免一开始陷入通用 AI； effort：2 周，1 engineer + 0.3 annotator。
2. **建立 gold-label 规范和 100–150 个事件标注集** — 没有事件定义就无法判断 pipeline 成败；effort：3–5 天，需 1 名懂 roguelite 的设计/研究人员参与。
3. **实现 specialist-heavy skeleton，并把 VLM 限定为候选帧复核** — 这是 Phase 1 <10 分钟分析的唯一现实路径；effort：2–3 周，1–2 engineers。
4. **把输出 schema 改为 reward_moment + reward_items** — 先分析玩家感知时刻，再拆具体奖励项，能显著降低融合歧义；effort：1–2 天。

## 关键不确定性 (Key uncertainties to resolve)

1. **固定游戏上 obvious reward 的 recall 是否能超过 0.60 且 precision 接近 0.80？** 如果连 Hades/类似游戏都达不到，视频-only 路线应降级为人工辅助标注工具。
2. **设计师是否接受 reward_moment 而非完整 reward_items？** 如果他们必须看到每个具体掉落/数值项，Phase 0/1 成本会上升很多。
3. **30 分钟 <10 分钟是否是硬 SLA 还是体验目标？** 若硬 SLA，需要 GPU 队列、缓存、采样预算和限制 VLM；否则产品可先走离线批处理。
