---
id: DOC_STATE_HUB
title: 状态中枢：把「现在在哪」从对话里剥离
type: design_doc
status: ACTIVE
last_updated: 2026-01-01
triggers:
  - 跨会话总是忘记进度时
  - 准备设计状态文件 schema 时
reads_before:
  - 00-architecture.md
related_files:
  - path: 00-architecture.md
    desc: 见该文件标题
    timing: 需要该主题时
  - path: 02-router.md
    desc: 见该文件标题
    timing: 需要该主题时
---
# 状态中枢：把"现在在哪"从对话里剥离

> 跨会话失忆的根源不是模型记性差，而是**状态存在对话历史里**。对话一结束，状态就没了。

---

## 一、问题

每次开新会话，Agent 都得先问"我们上次做到哪了？"。这有三个代价：

1. 用户要重复描述进度
2. Agent 可能记错或脑补
3. 浪费首轮上下文

**根因**：状态是对话的副产品，不是一等公民。

---

## 二、做法

把状态抽出来，落成一个**结构化 JSON**，Agent 启动时第一步读它。

```json
{
  "meta": {
    "project": "你的项目名",
    "current_phase": "第 3 阶段",
    "last_sync": "2026-01-01",
    "_privacy": "不写姓名、机构、账号等任何可定位信息"
  },
  "active_items": [
    {
      "id": "item_01",
      "title": "当前在推进的事",
      "status": "IN_PROGRESS",
      "deadline": "2026-01-15",
      "notes": "卡在哪、下一步是什么"
    }
  ],
  "matrix": {
    "模块A": "MASTERED",
    "模块B": "WEAK",
    "模块C": "PENDING"
  }
}
```

### 三个字段设计要点

| 字段 | 为什么需要 |
| :--- | :--- |
| `current_phase` / `current_week` | 让 Agent 知道"现在是什么时候"，不用问 |
| `matrix` 三态 | **MASTERED / WEAK / PENDING** 比"完成度 60%"更好用——它直接告诉 Agent 该往哪使劲 |
| `_privacy` | 显式声明隐私边界，防止后续会话往里写不该写的东西 |

---

## 三、关键纪律

### 1. 状态中枢是唯一事实源

同一个状态**只存在一处**。不能既有 JSON 又有 README 里的进度表——两份必然漂移。

### 2. 静默更新

Agent 在对话中得知进度变化时，**直接改 JSON，不要汇报**"我已更新状态中枢"。状态更新是内务，不是产品功能。

### 3. 与路由表分离

- 状态中枢回答：**现在在哪**
- 路由矩阵回答：**该读什么**

两者职责不同，不要合并。

---

## 四、最小可用版本

如果觉得 JSON 太重，从三个字段起步也够：

```json
{
  "current_phase": "第 3 阶段",
  "active_items": ["正在做的事"],
  "matrix": {"模块A": "WEAK"}
}
```

先跑起来，再逐步加字段。**不要一开始就设计完美 schema**——那通常意味着你还没开始用。

---

## 五、常见错误

| 错误 | 后果 | 修正 |
| :--- | :--- | :--- |
| 状态写进 Markdown 正文 | 无法机读，Agent 要解析自然语言 | 用 JSON |
| 一个状态存多处 | 必然漂移，不知信哪个 | 单一事实源 |
| 每次更新都汇报 | 噪音，稀释信息密度 | 静默更新 |
| schema 过度设计 | 迟迟不能开始用 | 三字段起步 |

---

## 文尾关联文件与引用时机网格

| 目标文件相对路径 | 核心内容 | 引用时机与触发条件 | 关联类型 |
| :--- | :--- | :--- | :--- |
| [00-architecture.md](00-architecture.md) | 四级架构总纲 | 需要理解状态中枢在整体中的位置时 | 上游总纲 |
| [02-router.md](02-router.md) | 意图路由矩阵 | 状态有了，接下来解决"该读什么"时 | 平行机制 |
| [../templates/state-hub.json](../templates/state-hub.json) | 状态中枢可填写模板 | 准备建自己的状态文件时 | 落地模板 |
| [../tools/verify_workspace_links.py](../tools/verify_workspace_links.py) | 校验器会检查状态中枢指针 | 想知道状态中枢如何被自动校验时 | 配套工具 |
