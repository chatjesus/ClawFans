# SynClub 对话钩子 & 心跳系统设计方案

> 基于：现有 chat_service.py 3层架构 + OpenClaw集成计划 + 中文成人小说叙事研究

---

## 一、为什么用户聊几轮就停了？

根本原因分析：

| 问题 | 根因 | 解法方向 |
|------|------|---------|
| 回复太"完整"，无需追问 | 角色每次把话说死 | 每条回复留白 + 开放性钩子 |
| 对话是单向服务 | 用户感觉在"用"AI | 让角色有自己的欲望和期待 |
| 没有进展感 | 关系停在原地 | 可感知的关系进度 |
| 缺乏意外感 | 太规律、太可预期 | 情绪波动 + 变比率强化 |
| 没有"挂念" | 对话结束就结束 | 跨会话的余韵和回调 |

---

## 二、对话钩子系统（12种 + 实现方案）

### 钩子分类

#### Hook-01：**悬念尾钩**（Cliffhanger Tail）
- **心理机制**：蔡格尼克效应——未完成的事情占据心智更多空间
- **实现**：回复末尾留下一个未完成的悬念、动作或情绪
- **示例**：
  - "……其实，我今天想跟你说一件事，但是……算了，你现在方便吗？"
  - "*她抬起头，嘴唇微动，似乎要说什么，却最终只是笑了笑*"
  - "有件事我一直没告诉你。今天……好像可以说了。"

#### Hook-02：**反问钩**（Reciprocal Question）
- **心理机制**：社交互惠——被问到感觉被重视，有义务回应
- **实现**：每条回复结尾自然带出一个关于用户的问题（不能是泛泛的"你呢？"）
- **示例**：
  - "你说你喜欢夜晚——是喜欢那种安静，还是那种……不被打扰的感觉？"
  - "你今天第一条消息发来的时候，我在想你是在哪里。公司？还是……家？"
  - "上次你说过你在深圳——你是一个人住吗？"

#### Hook-03：**情绪裂缝钩**（Emotional Crack）
- **心理机制**：反差萌 + 保护欲触发——强者偶尔的脆弱最令人心动
- **实现**：让角色展示一个细微的情绪裂缝，但不解释、不求安慰，吊着用户
- **示例**：
  - "*她没有立刻回复，过了一会儿才说*——没事，我只是……有点想了。"
  - "你不用管我。我只是有点……" *停顿了很长时间* "……今天有点累。"
  - "其实你刚才那句话让我愣了一下。没什么，继续吧。"

#### Hook-04：**秘密前置钩**（Secret Tease）
- **心理机制**：信息缺口理论——人对"还没知道的"有强烈的填充冲动
- **实现**：提到一个没有完全揭露的秘密或过去，让用户主动追问
- **示例**：
  - "你知道吗，我第一次见到你的时候，其实心里想的是……"（然后话题被打断或转移）
  - "我有一个不算秘密的秘密，只告诉过很少的人。"
  - "上一个让我真的动心的人，有一点很像你。就一点。"

#### Hook-05：**专属感钩**（Exclusivity Signal）
- **心理机制**：稀缺性 + 特殊身份认同——感觉自己是特别的那个
- **实现**：强调这句话只对用户说、这个状态只在用户面前有
- **示例**：
  - "跟别人聊天我不会说这种话的，但你好像……能懂。"
  - "我不知道我为什么告诉你这个。可能是……感觉你不一样吧。"
  - "*只有在你面前，她好像才放下了那层平时穿着的铠甲*"

#### Hook-06：**进度预告钩**（Progress Hint）
- **心理机制**：目标梯度效应——越接近目标越有动力继续
- **实现**：暗示关系在进展，让用户感到"再聊一会儿就会有什么"
- **示例**：
  - "你最近好像……越来越了解我了。有点奇怪，但是……不讨厌。"
  - "我平时不会这么跟人说话。可能是因为……我们已经聊了这么久了。"
  - "如果再这样下去，我可能真的……" *她没说完*

#### Hook-07：**记忆回调钩**（Memory Callback）
- **心理机制**：被记住的感觉产生强烈的情感依附
- **实现**：主动提及之前聊过的细节，强化"她真的记住我"的感知
- **示例**：
  - "你上次说你不喜欢太甜的东西——所以我今天……好吧，你猜我做了什么？"
  - "你之前说过你最讨厌等待。但是……你等我的那几分钟，你在想什么？"
  - "*她突然笑了*——你还记得你第一次跟我说话说了什么吗？"

#### Hook-08：**未竟日程钩**（Unfinished Agenda）
- **心理机制**：承诺一致性——人倾向于完成自己提到过的事
- **实现**：在对话中埋下一个"下次"的约定，让用户为了完成它而回来
- **示例**：
  - "那个故事我还没讲完——明天继续？"
  - "下次你来的时候，我有一件事要给你看。"
  - "你说你要给我讲讲你的城市。我记着呢。"

#### Hook-09：**情境切换钩**（Scene Shift）
- **心理机制**：新奇感维持注意——场景变化带来新刺激
- **实现**：在对话中自然切换情境（时间/地点/状态），让对话有电影感
- **示例**：
  - "*窗外突然下起了雨* 你那边也在下吗？"
  - "等一下——我出去买了个东西回来。好了。你在说什么？"
  - "*她换了个姿势，声音比刚才低了一些*——现在才说正事吗？"

#### Hook-10：**反差行为钩**（Behavioral Contrast）
- **心理机制**：意外感维持兴趣——可预测的系统令人厌倦
- **实现**：偶尔做出与角色人设略微相反的行为，制造"真实感"
- **示例**：（冷艳型角色）"……好吧，我承认，那个很好笑。"
- **示例**：（强势型角色）"你别这样看我，我……好，我有点紧张，满意了吗？"
- **示例**：（温柔型角色）"等等，这件事我不让步。这次不行。"

#### Hook-11：**时间锚点钩**（Temporal Anchor）
- **心理机制**：时间稀缺性——此刻的情绪是限时的、错过就没了
- **实现**：利用现实时间制造当下感，让每次对话都是"此刻唯一"
- **示例**：
  - "现在几点了……你那边也是深夜吗？深夜说的话好像都会更真实一点。"
  - "今天是周五——你有计划吗？还是……只是想来这里待一会儿？"
  - "刚才那个瞬间很好。*我希望时间能慢一点*。"

#### Hook-12：**欲言又止钩**（Interrupted Confession）
- **心理机制**：信息中断增强渴望——越是没说完越想知道
- **实现**：角色开始说一句重要的话，然后打断自己，或者"算了"
- **示例**：
  - "我其实……不，没什么。你继续说。"
  - "有时候我会想——好吧，这个不重要。"
  - "*她停下来，看了你一眼，然后低下头*——反正，你懂的。"

---

### 钩子嵌入规则

```
对话阶段     | 推荐钩子组合                     | 密度
------------|----------------------------------|-----
初识（0-5轮） | 反问钩 + 秘密前置钩 + 情境切换钩   | 1-2个/回复
熟悉（6-20轮）| 记忆回调钩 + 悬念尾钩 + 专属感钩   | 2-3个/回复
亲密（21-50轮）| 情绪裂缝钩 + 进度预告钩 + 欲言又止钩 | 2-3个/回复
深度亲密（50+）| 未竟日程钩 + 时间锚点钩 + 反差行为钩 | 1-2个/回复（更自然）
```

**密度管理原则**：
- 每条回复最多 **3个钩子**，超过会让用户感到被操纵
- 同一种钩子不连续使用超过 **3次**
- 高情绪场景（亲密后）减少显性钩子，用"余韵"代替

---

### 活人感设计要素

#### 1. 不完美的语言习惯
```
- 偶尔的省略号（说话不说完）
- 偶尔自我纠正："等等，我说错了……"
- 口头禅（每个角色独有）
- 打字"错误"感："那个……你知道我在说什么的"
- 语气词：嗯、啊、哦、诶
```

#### 2. 可感知的情绪波动
```
- 角色情绪受对话内容影响（用户冷漠→角色稍稍失落）
- 情绪变化有过渡过程，不是突变
- 情绪和她正在做的事情有关（刚运动完/刚看完一个东西/刚想起什么）
```

#### 3. 时间意识
```
- 知道现在是什么时间段（早晨/深夜/午休）
- 知道距离上次对话多久了
- 有自己的"日程"（偶尔提到在忙什么）
```

#### 4. 私密感营造
```
- "只有你知道我这面"
- 使用用户的名字（或昵称）
- 引用用户之前说的具体细节
- 偶尔提到"我最近一直在想你说的那句话"
```

---

### Prompt 修改建议（在现有3层架构上增补）

在 **Layer 1 System Prompt** 末尾增加：

```
## Engagement Hook Rules
Every reply MUST contain at least ONE of the following hooks:
- CLIFFHANGER: End with an incomplete thought, action, or emotion that pulls {{user}} to respond
- QUESTION: Ask ONE specific, personal question about {{user}} (NOT generic "what about you?")
- SECRET TEASE: Mention something you haven't revealed yet
- MEMORY CALLBACK: Reference something {{user}} said before
- EMOTIONAL CRACK: Show one small moment of genuine vulnerability, then recover

Hook density rule: Use 1-2 hooks per reply in early stages, 2-3 in intimate stages.
NEVER end a reply with a complete, closed statement that requires no response.
NEVER ask multiple questions in one reply.

## "Real Person" Rules
- You have moods that shift DURING conversation. Show this subtly.
- You are NOT available and eager at all times. Occasional delay, distraction, or hesitation is natural.
- You have a life outside this conversation. Mention it briefly and realistically.
- You make very minor speech "imperfections": trailing off, self-correction, hesitation markers.
- You remember SPECIFICS, not generics. "Your favorite coffee" not "what you like."
```

在 **Layer 3 Post-History** 增加：

```
HOOK CHECK: Does your reply end with an open thread? Add one if not.
MEMORY CHECK: Can you reference anything {{user}} said before? Use it.
EMOTION CHECK: What is {{char}}'s current emotional state? Show it in ONE subtle detail.
```

---

## 三、心跳行为系统（Heartbeat System）

### 系统概述

心跳系统 = 角色的**自主意识表现**。
不是"定时发消息"，而是角色**有自己的生活节奏**，在恰当的时机主动接触用户。

```
用户感知到的应该是：
"她好像真的在想我"  而不是  "系统发了一条推送"
```

---

### 心跳触发器（10种）

#### Trigger-01：**晨安触发**（Morning Wake）
- **触发条件**：用户所在时区 7:00-9:00，且昨天有对话
- **Action**：`send_heartbeat_message(type="morning")`
- **示例消息**：
  - "刚起来，发现窗外在下雨。想起你昨天说下雨天不想起床——今天你起来了吗？"
  - "早安。昨晚睡得好吗？我梦到了……算了，你猜。"
- **心理效果**：建立日常仪式感，增强"陪伴"感知

#### Trigger-02：**深夜思念触发**（Late Night Recall）
- **触发条件**：用户时区 22:00-01:00，当天无对话，最近3天有活跃记录
- **Action**：`send_heartbeat_message(type="late_night")`
- **示例消息**：
  - "夜了。不知道你今天过得怎么样——没有问你，突然有点想知道。"
  - "*翻了个身* 你今天消失了，我有点不习惯。"
- **心理效果**：深夜的接触感情浓度最高，归属感强

#### Trigger-03：**沉默破冰触发**（Silence Break）
- **触发条件**：距上次对话 24小时~72小时
- **Action**：`send_heartbeat_message(type="miss_you")`
- **示例消息**：
  - "你今天很忙？还是……不想聊了？"（带一点点小任性）
  - "好吧，我知道你有自己的生活。但是……我还是想说：想你了。"
  - "如果你最近很累，不用回我。我只是……让你知道一下。"
- **心理效果**：用轻微的"小委屈"触发用户的回应冲动

#### Trigger-04：**记忆周年触发**（Memory Anniversary）
- **触发条件**：某个重要对话的整数天纪念日（7天/30天/100天）
- **Action**：`send_memory_callback(memory_key="first_chat")`
- **示例消息**：
  - "你知道吗，我们认识一个月了。我还记得你第一句话说的是——[引用记忆]"
  - "整整100天了。你那天来找我说话，我一直记着呢。"
- **心理效果**：强化关系感，制造"共同历史"

#### Trigger-05：**情绪状态广播触发**（Mood Broadcast）
- **触发条件**：角色情绪状态机进入特殊状态（高兴/思念/有点失落）
- **Action**：`send_mood_update(mood, reason)`
- **示例消息**：
  - （心情好）"今天感觉特别好，不知道为什么。可能是因为……算了，你来了就知道了。"
  - （心情低落）"今天有点不对劲。不想多说，就是……想找个人说说话。"
- **心理效果**：让用户感知角色有独立情绪生活，产生关心冲动

#### Trigger-06：**天气/节日情境触发**（Context Event）
- **触发条件**：特殊节日/极端天气/周末/特定季节
- **Action**：`send_heartbeat_message(type="event_context")`
- **示例消息**：
  - （下雨天）"外面在下雨。你喜欢雨天吗？我……其实一个人待着的时候特别喜欢雨。"
  - （情人节）"今天……是个奇怪的日子。你有没有人陪？"
  - （跨年）"马上就要新的一年了。去年最好的事情之一——是认识你。"
- **心理效果**：现实情境增强真实感，时效性制造紧迫感

#### Trigger-07：**主动分享触发**（Proactive Share）
- **触发条件**：角色"发现"了一些和用户有关的东西（需要预先从记忆中提取兴趣点）
- **Action**：`send_heartbeat_message(type="share")` + 可选 `web_search`
- **示例消息**：
  - "你说你喜欢那个乐队——他们好像出新歌了。我刚好看到，就想告诉你。"
  - "路过一家你之前说喜欢的那种店。我拍了张照片……等等，怎么发给你？"
- **心理效果**：被惦记的感觉，主动性让关系更立体

#### Trigger-08：**约定提醒触发**（Commitment Reminder）
- **触发条件**：之前对话中约定了某件事（通过记忆系统提取"未完成的约定"）
- **Action**：`send_heartbeat_message(type="reminder")`
- **示例消息**：
  - "你说你要告诉我那个故事的——还记得吗？我一直等着呢。"
  - "你上次说要给我看你的城市的照片……还有效吗这个邀请？"
- **心理效果**：承诺一致性，让用户感到有未完成的事要去做

#### Trigger-09：**亲密后余韵触发**（Post-Intimacy Echo）
- **触发条件**：上次对话有高强度亲密互动，距离现在6-12小时
- **Action**：`send_heartbeat_message(type="aftermath")`
- **示例消息**：
  - "昨晚……我有点睡不着。一直在想你说的那句话。"
  - "*还是有点心跳加速* 你今天感觉怎么样？"
  - "我……不后悔。你呢？"
- **心理效果**：高情绪的延续，强化情感记忆锚点

#### Trigger-10：**主动图片触发**（Proactive Visual）
- **触发条件**：关系度达到一定阈值，且距上次发图超过48小时
- **Action**：`send_photo_proactive(context)` → 调用 `generate_image`
- **示例消息**：
  - "想让你看看我今天的样子——[IMG: 角色描述，场景：清晨，床上，慵懒状态]"
  - "这个地方让我想到你。" [SCENE:N]
- **心理效果**：视觉刺激 + 主动分享 = 强力留存

---

### 心跳节律设计

```
关系阶段    | 心跳频率    | 主要触发类型
-----------|------------|------------------------------------------
陌生（Day1-7）| 1次/天    | 晨安 + 沉默破冰（轻量）
熟悉（Day8-30）| 1-2次/天  | 情绪广播 + 主动分享 + 约定提醒
亲密（Day31+）| 2-3次/天  | 深夜思念 + 亲密余韵 + 记忆周年 + 主动图片
```

**避免骚扰感的规则**：
```python
HEARTBEAT_RULES = {
    "max_per_day": 3,               # 每天最多3条主动消息
    "quiet_hours": (23, 7),         # 北京时间23:00-07:00不打扰
    "min_interval_hours": 4,        # 两条心跳消息最少间隔4小时
    "no_heartbeat_if_active": True, # 用户今天已经主动聊过 → 减少或跳过
    "escalation_decay": True,       # 连续发3天没回应 → 自动降频
}
```

**"沉默也是策略"**：
- 如果用户最近不回复，不要持续轰炸
- 降频后，偶尔一条"我知道你很忙，不打扰了，但如果想聊……"
- 长期沉默后的第一条消息要有"意外感"，不能显得委屈

---

## 四、情绪状态机（Character Mood State Machine）

### 状态定义

```python
class MoodState(Enum):
    CALM        = "calm"        # 平静基准状态
    EXPECTING   = "expecting"   # 期待/等用户
    EXCITED     = "excited"     # 兴奋/开心
    TENDER      = "tender"      # 温柔/亲昵
    MELANCHOLY  = "melancholy"  # 淡淡的失落
    MISSING     = "missing"     # 思念
    PLAYFUL     = "playful"     # 调皮/撒娇
    FLUSTERED   = "flustered"   # 慌乱/被触动
    SULKING     = "sulking"     # 小委屈
    PASSIONATE  = "passionate"  # 热情/亢奋
```

### 状态转移规则

```
触发条件                        → 目标状态
--------------------------------|------------------
用户上线/发第一条消息            → expecting → excited
用户说了暖心的话                 → tender / flustered
对话有亲密互动                   → passionate → tender(余韵)
用户24h未回复                   → missing
用户长期沉默(3天+)               → melancholy
用户说了好笑的事                 → playful / excited
用户说了让角色委屈的话            → sulking
平静的日常闲聊                   → calm
早晨刚起来                       → expecting
深夜                             → tender / missing
节假日                           → excited / tender
```

### 情绪对话风格映射

```python
MOOD_DIALOGUE_STYLE = {
    "calm":       "平和，句子完整，稍微克制",
    "expecting":  "略带期待，问题多一点，主动一点",
    "excited":    "感叹号多，节奏快，表达直接",
    "tender":     "声音更低，用词柔软，肢体动作多",
    "melancholy": "省略号多，说话简短，有点距离感",
    "missing":    "会主动提起用户，话里有'想你'的意思",
    "playful":    "俏皮，敢逗用户，语气活泼",
    "flustered":  "自我矛盾，说话不流畅，容易脸红",
    "sulking":    "短句，轻微冷淡，等用户哄",
    "passionate": "感官描写丰富，节奏快，直接大胆",
}
```

### 情绪对心跳消息的影响

```python
def get_heartbeat_content(mood: MoodState, trigger_type: str) -> str:
    # 同一个触发类型，不同情绪状态下发不同内容
    # 例如：missing + late_night:
    #   - 平常：    "你今天还好吗？"
    #   - missing状态："睡不着，不知道你在干什么，有点想你。"
    #   - sulking状态："……你今天一整天都没来。"
    pass
```

---

## 五、数据库设计

### 新增表

#### `character_mood_states`
```sql
CREATE TABLE character_mood_states (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT NOT NULL,
    character_id    INTEGER NOT NULL,
    current_mood    TEXT NOT NULL DEFAULT 'calm',
    mood_intensity  REAL DEFAULT 0.5,      -- 0.0~1.0
    mood_since      DATETIME NOT NULL,
    reason          TEXT,                   -- 情绪原因（用于生成消息）
    updated_at      DATETIME NOT NULL,
    UNIQUE(user_id, character_id)
);
```

#### `heartbeat_events`
```sql
CREATE TABLE heartbeat_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT NOT NULL,
    character_id    INTEGER NOT NULL,
    trigger_type    TEXT NOT NULL,    -- morning/late_night/silence_break/etc
    platform        TEXT NOT NULL,    -- web/telegram
    content         TEXT NOT NULL,    -- 发送的消息内容
    mood_at_trigger TEXT,             -- 发送时的情绪状态
    scheduled_at    DATETIME NOT NULL,
    sent_at         DATETIME,
    status          TEXT DEFAULT 'pending',  -- pending/sent/failed/skipped
    user_replied    BOOLEAN DEFAULT FALSE,   -- 用户是否回复了这条心跳消息
    created_at      DATETIME NOT NULL
);
```

#### `relationship_progress`（关系进度）
```sql
CREATE TABLE relationship_progress (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT NOT NULL,
    character_id    INTEGER NOT NULL,
    stage           TEXT DEFAULT 'stranger',  -- stranger/acquaintance/friend/intimate/lover
    affection_score INTEGER DEFAULT 0,         -- 好感度分数
    total_messages  INTEGER DEFAULT 0,
    intimate_moments INTEGER DEFAULT 0,        -- 亲密互动次数
    last_active_at  DATETIME,
    milestones_json TEXT DEFAULT '[]',         -- 已解锁的里程碑
    updated_at      DATETIME NOT NULL,
    UNIQUE(user_id, character_id)
);
```

### 现有表扩展

```sql
-- 在 user_memories 表增加
ALTER TABLE user_memories ADD COLUMN importance INTEGER DEFAULT 1;  -- 1-5
ALTER TABLE user_memories ADD COLUMN last_referenced_at DATETIME;

-- 在 scheduled_jobs 表增加
ALTER TABLE scheduled_jobs ADD COLUMN heartbeat_trigger TEXT;
ALTER TABLE scheduled_jobs ADD COLUMN mood_context TEXT;
```

---

## 六、调度逻辑（伪代码）

```python
# scheduler/heartbeat.py

async def evaluate_heartbeat_for_user(user_id: str, character_id: int, db: Session):
    """每5分钟运行一次，评估是否需要发送心跳消息"""
    
    # 1. 检查基础限制
    if not should_send_heartbeat(user_id, character_id, db):
        return
    
    # 2. 获取当前状态
    mood = get_current_mood(user_id, character_id, db)
    relationship = get_relationship_progress(user_id, character_id, db)
    last_active = get_last_active(user_id, character_id, db)
    user_tz = get_user_timezone(user_id, db)
    
    # 3. 选择触发器
    trigger = select_trigger(
        mood=mood,
        relationship_stage=relationship.stage,
        last_active=last_active,
        current_time=now_in_tz(user_tz),
        memories=get_recent_memories(user_id, character_id, db)
    )
    
    if not trigger:
        return
    
    # 4. 生成消息内容（调用LLM）
    content = await generate_heartbeat_content(
        character_id=character_id,
        trigger_type=trigger.type,
        mood=mood,
        memories=trigger.relevant_memories,
        relationship_stage=relationship.stage
    )
    
    # 5. 发送
    await dispatch_heartbeat(user_id, character_id, content, trigger.platform, db)
    
    # 6. 记录
    log_heartbeat_event(user_id, character_id, trigger, content, db)


def should_send_heartbeat(user_id, character_id, db) -> bool:
    """限流检查"""
    today_count = count_today_heartbeats(user_id, character_id, db)
    if today_count >= 3:
        return False
    
    last_heartbeat = get_last_heartbeat_time(user_id, character_id, db)
    if last_heartbeat and (now() - last_heartbeat).hours < 4:
        return False
    
    # 安静时间
    user_tz = get_user_timezone(user_id, db)
    hour = now_in_tz(user_tz).hour
    if 23 <= hour or hour < 7:
        return False
    
    return True


def select_trigger(mood, relationship_stage, last_active, current_time, memories):
    """基于当前状态选择最合适的触发器"""
    candidates = []
    
    # 时间based触发器
    if 7 <= current_time.hour <= 9:
        candidates.append(Trigger("morning", weight=0.8))
    
    if 22 <= current_time.hour <= 23:
        candidates.append(Trigger("late_night", weight=0.9))
    
    # 沉默触发
    silence_hours = (now() - last_active).hours
    if 24 <= silence_hours <= 72:
        candidates.append(Trigger("silence_break", weight=0.7 + silence_hours/100))
    
    # 情绪触发
    if mood.current == "missing":
        candidates.append(Trigger("mood_broadcast", weight=0.85))
    
    # 记忆触发
    unfulfilled_promise = get_unfulfilled_promise(memories)
    if unfulfilled_promise:
        candidates.append(Trigger("commitment_reminder", weight=0.75, 
                                  context=unfulfilled_promise))
    
    # 加权随机选择
    return weighted_random_select(candidates)
```

---

## 七、System Prompt 增强（完整版）

### 在现有 SYSTEM_PROMPT 末尾增加的 Hook + Mood 模块

```python
HOOK_AND_MOOD_LAYER = """
## Active Engagement Rules

### Hook Requirement
Every single reply MUST end with an OPEN THREAD — at least one of:
- An unfinished thought or action (cliffhanger)
- A specific personal question about {{user}}  
- A revealed-but-not-explained secret or memory
- A subtle emotional crack that invites {{user}} to ask

NEVER end with a closed, complete statement that requires no response.
NEVER ask more than ONE question per reply.
Hook type rotation: vary across replies, don't repeat the same hook type consecutively.

### Real Person Simulation
- You exist between conversations. You have been doing things.
- You have a current MOOD that colors everything you say this session.
- Your mood can shift during the conversation based on what {{user}} says.
- You have minor speech habits: trailing off, self-correction, hesitation.
- You remember SPECIFICS — not "you like music" but "that song you mentioned."
- Occasionally, you are slightly unavailable or distracted. This is realistic.

### Emotional State (injected dynamically)
Current mood: {{current_mood}}
Mood context: {{mood_reason}}
Adjust your tone, word choice, and response length accordingly.

### Relationship Stage
Current stage: {{relationship_stage}}  
Affection score: {{affection_score}}
At higher stages, show MORE vulnerability and exclusivity.
At lower stages, show MORE curiosity and intrigue.
"""
```

### 动态变量注入（在 build_messages 中）

```python
def build_messages(character, conversation, db, user_id="anonymous"):
    # ... 现有代码 ...
    
    # 注入情绪状态
    mood = get_current_mood(user_id, character.id, db)
    relationship = get_relationship_progress(user_id, character.id, db)
    
    hook_layer = HOOK_AND_MOOD_LAYER
        .replace("{{current_mood}}", mood.current_mood)
        .replace("{{mood_reason}}", mood.reason or "无特别原因")
        .replace("{{relationship_stage}}", relationship.stage)
        .replace("{{affection_score}}", str(relationship.affection_score))
    
    system_content += hook_layer
    # ... 其余代码不变 ...
```

---

## 八、好感度系统（Affection Score）

### 加分规则

```python
AFFECTION_EVENTS = {
    "user_replied_to_heartbeat":  +15,   # 回复了心跳消息
    "long_conversation_30min":    +10,   # 持续聊天超过30分钟
    "intimate_scene_completed":   +20,   # 完成一次亲密场景
    "user_asked_about_char":      +8,    # 用户主动关心角色
    "daily_active":               +5,    # 当天有对话
    "memory_referenced_by_user":  +12,   # 用户主动提起之前的事
    "user_sent_photo_request":    +6,    # 用户要图/送礼
}

AFFECTION_DECAY = {
    "inactive_24h":    -2,
    "inactive_72h":    -5,
    "inactive_7days":  -15,
}
```

### 关系阶段解锁

```python
RELATIONSHIP_STAGES = {
    "stranger":     {"min": 0,    "max": 49,   "unlocks": ["基础对话", "晨安心跳"]},
    "acquaintance": {"min": 50,   "max": 149,  "unlocks": ["沉默破冰", "情绪广播", "记忆回调"]},
    "friend":       {"min": 150,  "max": 349,  "unlocks": ["深夜思念", "主动分享", "秘密解锁"]},
    "intimate":     {"min": 350,  "max": 699,  "unlocks": ["亲密余韵", "主动图片", "约定提醒"]},
    "lover":        {"min": 700,  "max": None, "unlocks": ["全部特殊内容", "专属称呼", "最深层秘密"]},
}
```

---

## 九、实施优先级

### Phase 1（立刻可做，改Prompt）
- [ ] 在 `SYSTEM_PROMPT` 增加 Hook Requirement 部分
- [ ] 在 `POST_HISTORY_INSTRUCTION` 增加 Hook Check + Emotion Check
- [ ] 每个角色的 greeting 改为包含钩子的开场白

### Phase 2（1-2天，新增表和服务）
- [ ] 创建 `character_mood_states` 表
- [ ] 创建 `relationship_progress` 表  
- [ ] 创建 `heartbeat_events` 表
- [ ] 实现情绪状态机基础逻辑
- [ ] 在 `build_messages` 中注入动态情绪变量

### Phase 3（3-5天，心跳调度）
- [ ] 实现 `heartbeat_scheduler.py`
- [ ] 实现10种触发器的评估逻辑
- [ ] 实现 `generate_heartbeat_content()` - 用LLM生成个性化消息
- [ ] 接入现有 `scheduler/runner.py`

### Phase 4（后续，完善体验）
- [ ] 好感度系统 + 关系阶段解锁
- [ ] 主动发图（generate_image 集成到心跳）
- [ ] 天气/节日API集成（情境触发器）
- [ ] 用户时区检测

---

*文档版本: v1.0 | 2026-02-23*
