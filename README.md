---
id: README
title: 学习工作区架构
type: repo_readme
status: ACTIVE
last_updated: 2026-01-01
triggers:
  - 第一次接触本仓库时
  - 想快速判断这套方法是否适合自己时
reads_before: []
related_files:
  - path: docs/00-architecture.md
    desc: 四级渐进披露总纲
    timing: 看完总览决定深入时
  - path: examples/calculus/README.md
    desc: 高等数学脱敏示范
    timing: 想直接看落地形态时
  - path: tools/verify_workspace_links.py
    desc: 知识库体检器
    timing: 准备跑第一次体检时
---

# 学习工作区架构

> 一套给 AI Agent 用的**长期项目知识库组织方法**。核心不是"教 AI 怎么学习"，而是**教 AI 在跨会话、跨文件的长期项目里，什么时候该读哪几个文件、什么时候不该读**。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 这套东西解决什么

把一堆资料丢给 AI，短期能跑，长期必崩。三个崩溃点：

| 崩溃点 | 现象 | 后果 |
| :--- | :--- | :--- |
| **上下文膨胀** | 每次会话都全量读资料 | token 成本线性增长，首字延迟上升 |
| **注意力稀释** | 关键约束淹没在无关内容里 | 模型"读了规则但不执行" |
| **跨会话失忆** | 新会话不知道上次做到哪 | 反复确认进度，重复劳动 |

这套方法的应对是：**把"读什么"从模型自由裁量，变成按层级查表**。

---

## 目录结构

```text
.
├── docs/                    # 方法论正文（五篇）
│   ├── 00-architecture.md   # 四级渐进披露总纲
│   ├── 01-state-hub.md      # 状态中枢：跨会话不失忆
│   ├── 02-router.md         # 意图路由矩阵：该读什么
│   ├── 03-file-protocol.md  # 文尾网格 + 五步闭环 + 校验器
│   └── 04-failure-ledger.md # 避坑账本与防膨胀四闸门
├── templates/               # 可直接填写使用的模板
│   ├── AGENTS.md            # L0 入口
│   ├── ROUTER.md            # 路由表
│   ├── state-hub.json       # 状态中枢
│   ├── failure-ledger.md    # 避坑账本
│   └── file-with-grid.md    # 带 Frontmatter 与文尾网格的通用文件
├── tools/
│   └── verify_workspace_links.py   # 知识库体检器（本仓库唯一可执行部分）
└── examples/
    └── calculus/            # 高度脱敏的完整示例
```

---

## 三个核心机制

### 1. 四级渐进披露

```text
L0 入口层    AGENTS.md（≤90 行，首屏预算）
      ↓
L1 状态与调度  状态中枢 JSON + ROUTER.md
      ↓
L2 规则与底座  协作协议 + 避坑账本
      ↓
L3 领域层     资料库/{领域}/ → 计划 → 考点 → 模板
```

详见 [docs/00-architecture.md](docs/00-architecture.md)。

### 2. 双向互联：树 + 网

- **中枢路由表（Top-Down）**：`ROUTER.md` 维护「意图 → 触发时机 → 文件」映射
- **文尾网状辐射（Bottom-Up）**：每个文件文尾挂《关联文件与引用时机网格》，任意文件都能继续走

结果是**图而非树**，没有死胡同。

### 3. 唯一自带验收的机制

绝大多数"Agent 工作流方法论"都是纯提示词约定，模型一飘就失效。这套有校验器：

```bash
python tools/verify_workspace_links.py --root /path/to/your/workspace
```

它检查五项：Frontmatter 规范、文尾网格存在性、死链、孤岛文件、状态中枢指针有效性。

**这是整套架构里唯一可证伪的部分**——clone 下来跑一遍，立刻知道它是否真在工作。

---

## 快速开始

```bash
git clone <this-repo> my-workspace
cd my-workspace

# 1. 复制模板到根目录
cp templates/AGENTS.md ./AGENTS.md
cp templates/ROUTER.md ./ROUTER.md
mkdir -p 01_状态中枢 02_运行规则 03_资料库
cp templates/state-hub.json 01_状态中枢/状态.json
cp templates/failure-ledger.md 02_运行规则/避坑账本.md

# 2. 按你的领域改写 AGENTS.md 的环境基线、ROUTER.md 的路由表
# 3. 跑一次体检
python tools/verify_workspace_links.py
```

建议第一次跑体检时会有不少警告，那是正常的——它把"还没搭完的结构"标出来了。

---

## 完整示例

[`examples/calculus/`](examples/calculus/README.md) 是一个**高度脱敏**的完整示例：用一门公共基础课（高等数学）演示 L0→L3 四层如何落地、文尾网格如何串起来。

它**只保留结构与方法**：没有具体教材页码、没有真实题目、没有个人进度、没有任何可定位到具体个人或机构的信息。

---

## 这套方法不做什么

诚实地划清边界：

- **不提供领域知识**。它只管"知识怎么组织、什么时候加载"，不管"这道题怎么算"。
- **不保证模型遵守规则**。硬约束是提示词，模型仍可能违反。真正可靠的是校验器。
- **不适合一次性任务**。开销在"建立和维护结构"，短任务用不上。
- **层级数不是教条**。四层是经验值；领域多就加层，项目小就砍到两层。

---

## 已知局限

校验器能查**结构**，查不了**语义**：

| 查得到 | 查不到 |
| :--- | :--- |
| Frontmatter 缺字段 | 字段内容写得对不对 |
| 链接目标不存在 | 链接该不该指过去 |
| 文件无人引用 | 引用是否有意义 |

还有一个盲区：**正文里的数字会漂移**（文档 A 说"四层"，文档 B 说"五层"）。对策是尽量不写死数字，或把计数集中到一个常量文件。

---

## 设计来源

这套方法是在一个真实长期使用的工作区里迭代出来的：从一个具体学科的备考工作区起步，经过数月实际使用，把与学科耦合的部分剥离，留下与领域无关的骨架。

**留下的**：文档拓扑治理、渐进披露、路由、校验、经验沉淀。
**剥离的**：具体学科内容、考核细节、任何个人与机构信息。

---

## 许可

[MIT](LICENSE)
