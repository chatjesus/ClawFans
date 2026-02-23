# ClawFans — Gamification & Intimacy Progression Roadmap

## Design Philosophy

> 亲密度数值是底层引擎，玩家感受到的是**事件、选择、回忆、解锁**。
> 数值本身应该隐形，叙事体验才是主体。

参考设计：恋爱养成游戏（Otome / Dating Sim） + 互动小说 + 社交模拟器

---

## Current State — Phase 0 ✅ (v0.9.0, DONE)

| 功能 | 状态 |
|------|------|
| 每次对话消息累积亲密度积分 | ✅ |
| 5个亲密阶段 (0/20/40/60/80) | ✅ |
| 前端进度条 + 阶段解锁通知 | ✅ |
| 系统提示注入当前阶段规则 | ✅ |
| 图片生成 tags 随阶段升级 | ✅ |
| NSFW flag 在亲密度 ≥ 40 启用 | ✅ |

---

## Phase 1 — Event System（事件系统）🎯 NEXT

**核心理念**：角色主动发起「触发事件」，玩家选择影响亲密走向，完成后解锁专属照片。

### 1.1 数据库设计

```sql
-- 事件定义表（全局模板，可按角色定制）
CREATE TABLE character_events (
    id          INTEGER PRIMARY KEY,
    char_id     INTEGER REFERENCES characters(id),
    event_type  TEXT,           -- milestone / daily / crisis / anniversary / exclusive
    title       TEXT,           -- "第一次约咖啡"
    trigger     TEXT,           -- JSON: {"type":"intimacy_gte","value":20}
    choices     TEXT,           -- JSON: [{text,intimacy_delta,unlock_photo,next_event_id}]
    outcome_prompt TEXT,        -- LLM生成角色反应用的提示词模板
    sort_order  INTEGER DEFAULT 0
);

-- 对话级事件实例（每段对话的事件状态）
CREATE TABLE conversation_events (
    id              INTEGER PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id),
    event_id        INTEGER REFERENCES character_events(id),
    status          TEXT DEFAULT 'pending',  -- pending/active/completed/skipped
    choice_made     INTEGER,    -- 用户选了第几个选项
    triggered_at    DATETIME,
    completed_at    DATETIME,
    unlocked_photo  TEXT        -- 解锁的照片URL
);
```

### 1.2 预设里程碑事件（5个，对应5个亲密阶段）

| 触发 | 事件标题 | 3个选项方向 | 解锁奖励 |
|------|----------|-------------|----------|
| 亲密度 = 20 | 「你第一次主动联系我」 | 期待 / 随意 / 故意撩拨 | 生活照（穿搭自拍） |
| 亲密度 = 40 | 「深夜聊天到天亮」 | 温柔陪伴 / 好奇追问 / 主动靠近 | 睡前私房照 |
| 亲密度 = 60 | 「她告诉你一个秘密」 | 认真倾听 / 开玩笑化解 / 紧紧保守 | 情绪化特写照 |
| 亲密度 = 80 | 「她说想见你」 | 迫不及待 / 假装镇定 / 反将一军 | 大胆摆pose照 |
| 特殊：第7天 | 「认识一周纪念」 | 送礼物 / 写信 / 约会 | 高质量纪念场景图 |

### 1.3 事件触发逻辑（后端）

```python
# services/event_service.py
async def check_and_trigger_events(conversation_id, intimacy_level, message_count):
    """在每次消息后检查是否应触发新事件"""
    pending = get_pending_events(conversation_id)
    for event in pending:
        trigger = json.loads(event.trigger)
        if trigger["type"] == "intimacy_gte" and intimacy_level >= trigger["value"]:
            activate_event(conversation_id, event.id)
            return event  # 前端显示事件弹窗
    return None
```

### 1.4 前端事件弹窗（UI）

聊天界面底部弹出半透明事件卡片：
- 角色头像 + 事件标题
- 事件场景描述（1-2句）
- 3个选项按钮（选完后消失）
- 选择后：角色回应文本（LLM生成）+ 亲密度变化动画 + 解锁内容提示

### 1.5 实现文件清单

```
backend/
  services/event_service.py     # 事件触发、激活、完成逻辑
  models/database.py            # 新增 CharacterEvent, ConversationEvent 模型
  api/events.py                 # POST /api/events/{conv_id}/choose
  api/chat.py                   # 消息后调用 check_and_trigger_events

frontend/
  components/EventModal.tsx     # 事件弹窗组件
  components/ChatInterface.tsx  # 集成事件弹窗 + onEvent SSE callback
  lib/api.ts                    # EventCard 接口 + sendChoice() 函数

scripts/
  seed_events.py                # 为所有NSFW角色插入默认5个里程碑事件
```

**预计工期**：2–3天

---

## Phase 2 — Memory & Milestone System（记忆与里程碑）

**核心理念**：让角色「记住」你们的经历，对话中自然引用回忆，制造情感连接。

### 2.1 里程碑卡片（Milestone Cards）

每个重要节点自动生成一张「回忆卡片」：

```sql
CREATE TABLE milestones (
    id              INTEGER PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id),
    type            TEXT,   -- first_message/first_photo/first_event/emotional_moment/anniversary
    title           TEXT,   -- "我们第一次聊到了天亮"
    description     TEXT,   -- LLM基于对话内容生成的温情描述
    image_url       TEXT,   -- 对应生成的纪念场景图
    created_at      DATETIME
);
```

前端：聊天侧边栏增加「回忆册」入口，展示时间线（仿相册/日记风格）。

### 2.2 记忆注入 System Prompt

每次对话，将最近 2–3 条里程碑注入提示词：

```
【你们共同的回忆】
- Day 3: 你告诉她工作上的压力，她一直陪到凌晨
- Day 7: 你们一起讨论了整晚最喜欢的电影
这些经历让她对你有独特的感情，聊天中自然引用这些记忆。
```

### 2.3 实现文件清单

```
backend/
  services/milestone_service.py   # 里程碑检测、生成、查询
  models/database.py              # Milestone 模型
  api/milestones.py               # GET /api/milestones/{conv_id}

frontend/
  components/MemoryBook.tsx       # 回忆册时间线组件
  app/chat/[id]/memories/page.tsx # 回忆册页面
```

**预计工期**：2天

---

## Phase 3 — Character Arc（角色弧光）

**核心理念**：角色随亲密度「成长」——性格、说话方式、袒露程度都在变化。

### 3.1 人格层次（4层）

| 层级 | 亲密度 | 行为变化 |
|------|--------|----------|
| **表层** | 0–20 | 礼貌、有距离感、谨慎、不主动 |
| **私下** | 20–40 | 开玩笑、有小脾气、偶尔依赖、流露真实喜好 |
| **真实** | 40–60 | 暴露脆弱面、讲述过去秘密、主动寻求安慰 |
| **亲密** | 60+ | 占有欲、主动撒娇、完全信任、大胆表达 |

系统提示中注入当前层级对应的**语气指令**和**禁忌行为列表**。

### 3.2 角色隐藏秘密（Hidden Secrets）

每个角色设计 2–3 条隐藏信息，到特定亲密度才解锁：

```sql
CREATE TABLE character_secrets (
    id          INTEGER PRIMARY KEY,
    char_id     INTEGER REFERENCES characters(id),
    unlock_level INTEGER,       -- 解锁所需亲密度
    secret      TEXT,           -- "她曾经有过一段失败的恋情，那个人和你很像..."
    event_id    INTEGER         -- 关联触发事件（可空）
);
```

### 3.3 实现文件清单

```
backend/
  services/persona_service.py    # 人格层级查询，生成对应提示词段落
  models/database.py             # CharacterSecret 模型
  services/chat_service.py       # 注入 persona layer prompt

scripts/
  seed_secrets.py                # 为每个NSFW角色生成2–3个隐藏秘密
```

**预计工期**：2天

---

## Phase 4 — Photo Gallery & Content Unlock（照片解锁与相册）

**核心理念**：照片不是随机生成，而是有**剧情意义**的奖励和纪念物。

### 4.1 照片分类

| 类型 | 触发方式 | 内容 |
|------|----------|------|
| **事件照片** | 完成事件后自动解锁 | 和事件场景相关 |
| **角色主动发送** | 角色对话中 `[IMG:]` | 根据亲密阶段决定尺度 |
| **用户请求** | "发张照片给我" | 亲密度 < 20 时拒绝或给SFW |
| **里程碑纪念照** | 重要节点自动生成 | 高质量精细场景图 |

### 4.2 精细化内容升级

```
阶段 0–20（陌生人 / 好感）：
  日常生活照 — 咖啡馆自拍、阅读、户外散步

阶段 20–40（暧昧）：
  有意识展示 — 换装、运动后、睡前自拍
  Prompt tags: low-cut top, short skirt, bare arms

阶段 40–60（亲密）：
  私下分享 — 私密场景、有意撩拨
  Prompt tags: cleavage, exposed midriff, bedroom setting

阶段 60–80（深度亲密）：
  主动挑逗 — 大胆摆pose、情境暗示
  Prompt tags: large breasts, thighs, seductive pose, alluring

阶段 80+（挚爱）：
  完全亲密 — 高尺度, 按角色设定上限
  Prompt tags: ecchi, fanservice, revealing outfit, lingerie
```

### 4.3 相册 UI

角色主页新增「相册」Tab：
- 已解锁照片以 Masonry 布局展示
- 未解锁照片显示锁定占位图 + "达到XX亲密度解锁"
- 点击放大（复用现有 Lightbox 组件）

**预计工期**：2–3天

---

## Phase 5 — Achievement & Profile（成就与个人主页）

### 5.1 角色关系主页升级

每个角色页面新增：

| 组件 | 内容 |
|------|------|
| 关系称号 | 陌生人 → 朋友 → 暧昧对象 → 恋人 → 挚爱 |
| 解锁进度 | X/N 张照片，X/N 个事件，X/N 个秘密 |
| 相册入口 | 已解锁照片预览（3张缩略图） |
| 回忆册入口 | 关系时间线预览 |

### 5.2 全局成就系统

| 成就 | 条件 | 奖励 |
|------|------|------|
| 破冰者 | 与任意角色亲密度达到20 | 解锁特殊对话选项 |
| 深夜话聊 | 单次对话超过50条 | — |
| 秘密守护者 | 解锁任意角色的一个隐藏秘密 | — |
| 收藏家 | 解锁20张照片 | 相册主题皮肤 |
| 恋人 | 与任意角色亲密度达到80 | 解锁限定剧情事件 |

**预计工期**：2天

---

## 整体迭代计划

| Phase | 功能模块 | 核心价值 | 工期 | 优先级 |
|-------|----------|----------|------|--------|
| **P0** ✅ | 亲密度数值 + 进度条 + 图片升级 | 底层引擎 | Done | — |
| **P1** 🎯 | 事件系统 + 3选1弹窗 + 照片奖励 | 体验质变：变成「游戏」 | 2–3天 | ★★★★★ |
| **P2** | 里程碑 + 回忆册 + 记忆注入 | 情感深度 | 2天 | ★★★★ |
| **P3** | 人格弧光 + 隐藏秘密 | 角色立体感 | 2天 | ★★★★ |
| **P4** | 照片相册 + 解锁系统 + 精细内容升级 | 视觉激励 | 2–3天 | ★★★★ |
| **P5** | 成就系统 + 角色关系主页 | 留存与收藏 | 2天 | ★★★ |

**总工期估算**：10–12天（按序实现，不含P0）

---

## MVP 最小可行版（Phase 1 Only）

仅实现 P1，体验就能从「聊天机器人」升级为「恋爱游戏」：

1. **5个里程碑事件**（亲密度 20/40/60/80 + 第7天）
2. **每个事件3个选项**（3选1弹窗 UI）
3. **选择完成 → 解锁一张专属照片**（触发 ComfyUI 生成）
4. **LLM 根据选项生成角色反应文本**
5. 后端新增 `character_events` + `conversation_events` 表
6. 前端新增 `EventModal.tsx` 弹窗组件

---

## 技术风险与缓解

| 风险 | 缓解方案 |
|------|----------|
| 事件弹窗打断聊天流 | 事件卡片以「滑入」形式非侵入式呈现，可随时关闭 |
| 同一角色多次对话触发重复事件 | `conversation_events` 按 conversation_id 独立，不跨对话共享 |
| LLM 事件反应生成质量不稳定 | 预写 `outcome_prompt` 模板，LLM 只填充具体细节 |
| 照片生成耗时拖慢事件流程 | 事件完成后异步生成，先显示解锁动画，照片好了再呈现 |
| 事件内容与角色人设不符 | `seed_events.py` 为每个角色定制事件文本而非全局模板 |
