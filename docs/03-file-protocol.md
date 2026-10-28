---
id: DOC_FILE_PROTOCOL
title: 文尾网格 + 五步闭环 + 校验器
type: design_doc
status: ACTIVE
last_updated: 2026-01-01
triggers:
  - 知识库开始出现死链或孤岛文件时
  - 准备新建文件规范时
reads_before:
  - 00-architecture.md
related_files:
  - path: 00-architecture.md
    desc: 见该文件标题
    timing: 需要该主题时
  - path: 02-router.md
    desc: 见该文件标题
    timing: 需要该主题时
  - path: 04-failure-ledger.md
    desc: 见该文件标题
    timing: 需要该主题时
---
# 文尾网格 + 五步闭环 + 校验器：唯一自带验收的机制

> 绝大多数"Agent 工作流方法论"都是纯提示词约定，模型一飘就失效。这套不一样：**它有 172 行 Python 做 CI 式验收。**

---

## 一、要解决的问题

知识库有一个宿命：**越写越多，最后没人（包括 Agent）知道哪份文件还有效、谁引用谁。**

手工维护索引必死——人懒、Agent 也会忘。所以必须让索引维护**变成创建动作的一部分**。

---

## 二、文尾引用网格

每个 Markdown 文件**文尾**必须挂一张四列表：

```markdown
## 文尾关联文件与引用时机网格

| 目标文件相对路径 | 核心内容 | 引用时机与触发条件 | 关联类型 |
| :--- | :--- | :--- | :--- |
| [../ROUTER.md](../ROUTER.md) | 全局路由 | 需要定位其他文件时 | 上游总纲 |
| [02-考点卡.md](02-考点卡.md) | 本章核心机理 | 准备做作业前 | 下游模板 |
| [../状态中枢.json](../状态中枢.json) | 当前进度 | 需要更新掌握度时 | 状态中枢 |
```

### 硬性门槛

- **至少 3 项**关联文档
- **触发时机列必填**（不能写"需要时"这种废话，要写具体条件）
- 相对路径，不用绝对路径

### 为什么有效

打开任意一个文件，都能沿网格继续走。**形成图，而非树**。没有死胡同。

---

## 三、五步闭环

新建任何文件，必须在**同一轮交互内**完成五步：

```text
① 写 YAML Frontmatter
   ↓  id / title / type / triggers / reads_before / related_files
② 文尾加引用网格（≥3 项）
   ↓
③ 父级 README 登记
   ↓
④ 上游文件反向回填（让父级指向新文件）
   ↓
⑤ 跑校验器
   tools/verify_workspace_links.py
```

**关键在第 ⑤ 步。** 前四步是约定，第 ⑤ 步是验收。没有验收的约定等于没有。

### Frontmatter 必填五字段

```yaml
---
id: RULE_NEW_FILE          # 唯一标识
title: 新文件创建规范        # 标题
type: workspace_protocol    # 类型
triggers:                   # 什么时候该读这个文件
  - 准备新建任何文件时
reads_before: []            # 读它之前必须先读什么
related_files:              # 与文尾网格呼应
  - path: ../ROUTER.md
    desc: 全局路由
    timing: 需要定位其他文件时
---
```

---

## 四、校验器

`tools/verify_workspace_links.py` 做五项检查：

| 检查 | 发现什么 |
| :--- | :--- |
| ① Frontmatter 规范性 | 缺必填字段 |
| ② 文尾网格存在性 | 没挂网格的裸文件 |
| ③ 相对链接死链 | 指向不存在文件的链接 |
| ④ 孤岛文件统计 | 没有任何文件引用它 |
| ⑤ 状态中枢指针映射 | JSON 里写的路径是否存在 |

### 用法

```bash
python tools/verify_workspace_links.py --root /path/to/your/workspace
```

输出示例：

```text
=== 开始扫描工作区: /your/workspace ===
[Frontmatter 缺失] docs/新文件.md -> 缺少: triggers
[死链] docs/a.md -> ../b.md (不存在)
[孤岛文件] docs/孤儿.md -> 无任何文件引用
=== 扫描完成：3 项问题 ===
```

### 为什么这是整套架构里最值钱的部分

1. **可证伪**。别人 clone 下来跑一遍，立刻知道这套东西是否真在工作。
2. **可 CI**。挂进 GitHub Actions，每次 push 自动检查。
3. **与学科无关**。任何 Markdown 知识库都能用。

---

## 五、局限（必须承认）

校验器能查**结构**，查不了**语义**：

| 查得到 | 查不到 |
| :--- | :--- |
| Frontmatter 缺字段 | 字段内容写得对不对 |
| 链接目标不存在 | 链接该不该指过去 |
| 文件无人引用 | 引用是否有意义 |
| 状态指针失效 | 状态是否真实 |

还有一个已知盲区：**正文里的数字会漂移**。比如总纲说"四层"，实际写了五层；文档 A 说"7 个模块"，文档 B 说"8 个"。

这类问题校验器目前查不了。实践中的对策是**尽量不写死数字**，或者把计数写进一个常量文件，正文引用它。

---

## 六、常见错误

| 错误 | 后果 | 修正 |
| :--- | :--- | :--- |
| 只写约定不跑校验 | 三周后全是死链 | 建库当天就把校验挂上 |
| 网格里写"需要时查看" | 触发时机失效 | 写具体条件 |
| 建完文件忘了回填父级 | 新文件成孤岛 | 五步在同一轮做完 |
| 校验报错就先注释掉 | 腐烂加速 | 要么修，要么删文件 |

---

## 文尾关联文件与引用时机网格

| 目标文件相对路径 | 核心内容 | 引用时机与触发条件 | 关联类型 |
| :--- | :--- | :--- | :--- |
| [00-architecture.md](00-architecture.md) | 四级架构总纲 | 需要理解网格在整体中的位置时 | 上游总纲 |
| [02-router.md](02-router.md) | 路由矩阵（Top-Down 那一半） | 想补齐自上而下的路由时 | 平行机制 |
| [../tools/verify_workspace_links.py](../tools/verify_workspace_links.py) | 校验器本体 | 准备跑体检时 | 配套工具 |
| [../templates/file-with-grid.md](../templates/file-with-grid.md) | 带完整 Frontmatter 与网格的模板 | 准备新建文件时 | 落地模板 |
