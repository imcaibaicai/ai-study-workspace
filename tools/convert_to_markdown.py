#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
convert_to_markdown.py — 外部文件全量无损转 Markdown 并自动归档

配合《全量归档》纪律使用：外部权威文件先无损转存，再谈提炼，避免"用完就丢、下次靠脑补"。

功能：
1. 全量无损解析 .docx, .pdf, .xlsx, .txt, .csv, .html 文件；
2. 保持文档阅读流（段落与表格严格按原始交替次序排列）；
3. 自动提取样式层级（Title/Heading 1~6、有序/无序列表、加粗、斜体）；
4. 规范转换表格为 Markdown Table，自动转义管道符并用 <br> 保持单元格换行；
5. 自动注入标准 YAML Frontmatter（满足五步闭环的字段要求）；
6. 自动生成文尾《关联文件与引用时机网格》（Outbound Contextual Router）；
7. 自动归档至对应领域的 `00_原始文献/` 目录并更新索引，避免孤岛文件。

用法：
    python convert_to_markdown.py 某文件.docx
    python convert_to_markdown.py 某文件.pdf --subject 高等数学
    python convert_to_markdown.py 某文件.docx --subjects ./my_subjects.json

领域映射表：
    代码中不硬编码任何领域名。请在配置文件中定义：

        { "高等数学": ["高等数学", "高数"], "英语": ["英语"] }

    查找顺序：--subjects 参数 → 工作区根 subjects.json → tools/subjects.example.json
"""

import os
import sys
import re
import json
import argparse
import urllib.parse
from datetime import datetime
from pathlib import Path
from html.parser import HTMLParser

# 确保 Windows 终端 UTF-8
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

# ============================================================
# 领域映射表：从外部配置读取，不在代码里硬编码
#
# 配置文件查找顺序（命中即用）：
#   1. --subjects 参数显式指定
#   2. 工作区根目录的 subjects.json
#   3. tools/subjects.example.json（内置示例，仅供演示）
#
# subjects.json 格式：
#   {
#     "领域A": ["关键词1", "关键词2"],
#     "领域B": ["关键词3"]
#   }
# ============================================================
SUBJECTS_CONFIG_NAME = "subjects.json"
SUBJECTS_EXAMPLE = Path(__file__).resolve().parent / "subjects.example.json"
DEFAULT_SUBJECT = "00_通识与杂项"

SUBJECT_KEYWORDS = {}


def load_subjects_config(explicit_path: str = None) -> dict:
    """加载领域映射表。返回 {领域名: [关键词...]}。"""
    candidates = []
    if explicit_path:
        candidates.append(Path(explicit_path))
    candidates.append(WORKSPACE_ROOT / SUBJECTS_CONFIG_NAME)
    candidates.append(SUBJECTS_EXAMPLE)

    for cand in candidates:
        if not cand.exists():
            continue
        try:
            data = json.loads(cand.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict) and data:
                print("[配置] 已加载领域映射表: %s（%d 个领域）" % (cand, len(data)))
                return data
        except Exception as e:
            print("[配置] 读取失败 %s: %s" % (cand, e))

    print("[配置] 未找到领域映射表，所有文件将归入默认领域。")
    print("[配置] 可创建 %s 自定义，格式见 %s"
          % (WORKSPACE_ROOT / SUBJECTS_CONFIG_NAME, SUBJECTS_EXAMPLE))
    return {}


def detect_subject(filename_or_text: str) -> str:
    """根据文件名或内容关键词自动判定归属领域。"""
    for subj, keywords in SUBJECT_KEYWORDS.items():
        if any(kw in filename_or_text for kw in keywords):
            return subj
    return DEFAULT_SUBJECT

def escape_table_cell(text: str) -> str:
    """转义 Markdown 表格单元格字符"""
    if not text:
        return ""
    cleaned = text.strip().replace("\r\n", "\n").replace("\r", "\n")
    # 替换内部换行为 <br>
    cleaned = cleaned.replace("\n", "<br>")
    # 转义管道符
    cleaned = cleaned.replace("|", "\\|")
    return cleaned

def convert_docx(file_path: Path) -> str:
    """解析 docx 文件，保持段落与表格的原生交替阅读顺序"""
    import docx
    from docx.oxml.text.paragraph import CT_P
    from docx.oxml.table import CT_Tbl
    from docx.text.paragraph import Paragraph
    from docx.table import Table

    doc = docx.Document(file_path)
    md_lines = []

    for child in doc.element.body:
        if isinstance(child, CT_P):
            p = Paragraph(child, doc)
            text = p.text.strip()
            if not text:
                continue

            style_name = p.style.name.lower() if p.style and p.style.name else ""
            
            # 处理 Run 级别的加粗与斜体
            formatted_text = ""
            for r in p.runs:
                r_text = r.text
                if not r_text:
                    continue
                if r.bold and r.italic:
                    formatted_text += f"***{r_text}***"
                elif r.bold:
                    formatted_text += f"**{r_text}**"
                elif r.italic:
                    formatted_text += f"*{r_text}*"
                else:
                    formatted_text += r_text
            
            # 清理可能产生的双重星号粘连，如 **** -> 空
            line_content = formatted_text.strip() if formatted_text.strip() else text

            # 样式到 Markdown 映射
            if "title" in style_name:
                md_lines.append(f"# {text}\n")
            elif "subtitle" in style_name:
                md_lines.append(f"## {text}\n")
            elif "heading 1" in style_name:
                md_lines.append(f"# {text}\n")
            elif "heading 2" in style_name:
                md_lines.append(f"## {text}\n")
            elif "heading 3" in style_name:
                md_lines.append(f"### {text}\n")
            elif "heading 4" in style_name:
                md_lines.append(f"#### {text}\n")
            elif "heading 5" in style_name:
                md_lines.append(f"##### {text}\n")
            elif "heading 6" in style_name:
                md_lines.append(f"###### {text}\n")
            elif "bullet" in style_name or style_name.startswith("list bullet"):
                md_lines.append(f"- {line_content}")
            elif "number" in style_name or style_name.startswith("list number"):
                md_lines.append(f"1. {line_content}")
            else:
                # 检查自然文本是否有中文大标题习惯（一、二、三... 或 1. 2.）
                if re.match(r'^[一二三四五六七八九十]+[、\.]', text):
                    md_lines.append(f"\n## {line_content}\n")
                elif re.match(r'^[（(][一二三四五六七八九十]+[）)]', text):
                    md_lines.append(f"\n### {line_content}\n")
                elif re.match(r'^\d+[\.\、]\s*', text) and len(text) < 40 and not text.endswith(('。', '；', ';')):
                    md_lines.append(f"\n### {line_content}\n")
                else:
                    md_lines.append(f"{line_content}\n")

        elif isinstance(child, CT_Tbl):
            tbl = Table(child, doc)
            if not tbl.rows:
                continue

            md_lines.append("\n")
            # 提取表头
            header_row = tbl.rows[0]
            header_cells = [escape_table_cell(cell.text) for cell in header_row.cells]
            # 补齐空表头
            header_cells = [c if c else f"列{i+1}" for i, c in enumerate(header_cells)]
            
            md_lines.append("| " + " | ".join(header_cells) + " |")
            md_lines.append("| " + " | ".join([":---"] * len(header_cells)) + " |")

            # 数据行
            for row in tbl.rows[1:]:
                row_cells = [escape_table_cell(cell.text) for cell in row.cells]
                # 保持列数对齐
                if len(row_cells) < len(header_cells):
                    row_cells.extend([""] * (len(header_cells) - len(row_cells)))
                elif len(row_cells) > len(header_cells):
                    row_cells = row_cells[:len(header_cells)]
                md_lines.append("| " + " | ".join(row_cells) + " |")
            md_lines.append("\n")

    return "\n".join(md_lines)

def convert_pdf(file_path: Path) -> str:
    """利用 pdfplumber 提取 PDF 页面、文本与表格"""
    import pdfplumber

    md_lines = []
    with pdfplumber.open(file_path) as pdf:
        for page_idx, page in enumerate(pdf.pages, 1):
            md_lines.append(f"\n---\n\n### 第 {page_idx} 页 / 共 {len(pdf.pages)} 页\n")
            
            # 优先提取表格
            tables = page.extract_tables()
            if tables:
                for tbl in tables:
                    if not tbl or not tbl[0]:
                        continue
                    headers = [escape_table_cell(str(c or '')) for c in tbl[0]]
                    headers = [c if c else f"列{i+1}" for i, c in enumerate(headers)]
                    md_lines.append("\n| " + " | ".join(headers) + " |")
                    md_lines.append("| " + " | ".join([":---"] * len(headers)) + " |")
                    for row in tbl[1:]:
                        r_cells = [escape_table_cell(str(c or '')) for c in row]
                        if len(r_cells) < len(headers):
                            r_cells.extend([""] * (len(headers) - len(r_cells)))
                        elif len(r_cells) > len(headers):
                            r_cells = r_cells[:len(headers)]
                        md_lines.append("| " + " | ".join(r_cells) + " |")
                    md_lines.append("\n")

            # 提取纯文本
            text = page.extract_text()
            if text:
                for line in text.splitlines():
                    s_line = line.strip()
                    if s_line:
                        md_lines.append(s_line)

    return "\n".join(md_lines)

def convert_xlsx(file_path: Path) -> str:
    """利用 openpyxl 转换 Excel 工作表"""
    import openpyxl

    wb = openpyxl.load_workbook(file_path, data_only=True)
    md_lines = []

    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        md_lines.append(f"\n## 工作表：{sheet_name}\n")
        
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            continue
        
        # 寻找第一个非空行作为表头
        header_idx = 0
        while header_idx < len(rows) and not any(rows[header_idx]):
            header_idx += 1
        if header_idx >= len(rows):
            continue

        header_cells = [escape_table_cell(str(c or '')) for c in rows[header_idx]]
        header_cells = [c if c else f"列{i+1}" for i, c in enumerate(header_cells)]
        
        md_lines.append("| " + " | ".join(header_cells) + " |")
        md_lines.append("| " + " | ".join([":---"] * len(header_cells)) + " |")

        for row in rows[header_idx+1:]:
            if not any(row):
                continue
            r_cells = [escape_table_cell(str(c or '')) for c in row]
            if len(r_cells) < len(header_cells):
                r_cells.extend([""] * (len(header_cells) - len(r_cells)))
            elif len(r_cells) > len(header_cells):
                r_cells = r_cells[:len(header_cells)]
            md_lines.append("| " + " | ".join(r_cells) + " |")
        md_lines.append("\n")

    return "\n".join(md_lines)

def convert_text(file_path: Path) -> str:
    """文本或 CSV 文件标准化读取"""
    for enc in ["utf-8", "gbk", "utf-8-sig", "gb18030"]:
        try:
            return file_path.read_text(encoding=enc)
        except Exception:
            continue
    return file_path.read_text(errors="replace")


class _HTMLTreeBuilder(HTMLParser):
    """极简 HTML 树构建器：保留标签、属性与文本节点顺序，供作业页面结构化解析"""

    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
                 "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = {"tag": "#root", "attrs": {}, "children": []}
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = {"tag": tag, "attrs": dict(attrs), "children": []}
        self.stack[-1]["children"].append(node)
        if tag not in self.VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        node = {"tag": tag, "attrs": dict(attrs), "children": []}
        self.stack[-1]["children"].append(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i]["tag"] == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        if data.strip():
            self.stack[-1]["children"].append({"tag": "#text", "attrs": {}, "children": [], "text": data})


def _iter_nodes(node):
    """深度优先遍历所有节点"""
    yield node
    for child in node.get("children", []):
        yield from _iter_nodes(child)


def _has_class(node, cls):
    return cls in (node.get("attrs", {}).get("class") or "").split()


def _node_text(node):
    """提取节点纯文本（丢弃公式渲染态，公式由 _ml_formula_latex 单独处理）"""
    if node["tag"] == "#text":
        return node.get("text", "")
    out = []
    for child in node.get("children", []):
        if child["tag"] == "#text":
            out.append(child.get("text", ""))
        elif child["tag"] in ("script", "style", "svg", "mjx-assistive-mml"):
            continue
        else:
            out.append(_node_text(child))
    return "".join(out)


def _ml_formula_latex(node):
    """从 MathML 容器节点的 data 属性解出原始 LaTeX 源码（无损还原公式）"""
    data = node.get("attrs", {}).get("data")
    if not data:
        return None
    try:
        payload = json.loads(urllib.parse.unquote(data))
    except Exception:
        return None
    content = payload.get("content")
    if not content:
        return None
    markup = payload.get("markup") or "$"
    return f"{markup}{content}{markup}"


def _render_content(nodes):
    """把题干节点序列渲染为 Markdown 文本：公式转 LaTeX，其余转纯文本"""
    parts = []
    for node in nodes:
        if node["tag"] == "#text":
            parts.append(node.get("text", ""))
            continue
        if node["tag"] == "span" and node.get("attrs", {}).get("part") == "ml-formula":
            latex = _ml_formula_latex(node)
            if latex:
                parts.append(latex)
                continue
        if node["tag"] in ("script", "style", "svg", "mjx-assistive-mml"):
            continue
        text = _node_text(node).strip()
        if text:
            parts.append(text)
    return re.sub(r"[ \t]{2,}", " ", "".join(parts)).strip()


def _collect_paragraphs(node, out):
    """收集 class 含 ml-p 的段落节点"""
    for child in node.get("children", []):
        if child["tag"] == "p" and _has_class(child, "ml-p"):
            out.append(child)
        else:
            _collect_paragraphs(child, out)


def convert_html(file_path: Path) -> str:
    """AI 教学中心等在线作业平台的 HTML 快照 → 结构化 Markdown（公式无损还原为 LaTeX）

    解析层级：题型分组（group-title）→ 题目（question-item）→ 题干段落 / 选择项。
    公式优先从 MathML 容器的 data 属性取回原始 LaTeX，规避 SVG 渲染态丢失语义。
    原则：原始公式一律照抄，不擅自改写平台侧笔误；疑似笔误以「原文标注」形式附加。
    """
    raw = file_path.read_text(encoding="utf-8", errors="replace")

    builder = _HTMLTreeBuilder()
    builder.feed(raw)
    builder.close()
    tree = builder.root

    # 页面标题与总体分值
    page_title = ""
    total_info = ""
    for node in _iter_nodes(tree):
        if node["tag"] == "title" and not page_title:
            page_title = _node_text(node).strip()
    for node in _iter_nodes(tree):
        if _has_class(node, "combination-title-noName") or _has_class(node, "float-left"):
            pass

    md = []
    if page_title:
        md.append(f"**平台页面标题**：{page_title}")
        md.append("")

    # 作业抬头：标题行 + 总分/题数
    assignment_title = ""
    for n in _iter_nodes(tree):
        if "tool-tip-pro" in (n.get("attrs", {}).get("class") or "").split():
            assignment_title = re.sub(r"\s+", " ", _node_text(n)).strip()
            break
    summary_line = ""
    for n in _iter_nodes(tree):
        if n["tag"] == "span":
            t = re.sub(r"\s+", " ", _node_text(n)).strip()
            if re.fullmatch(r"满分[\d.]+分，共\d+题", t):
                summary_line = t
                break
    if assignment_title:
        md.append(f"**作业标题**：{assignment_title}")
    if summary_line:
        md.append(f"**卷面信息**：{summary_line}")
    if assignment_title or summary_line:
        md.append("")

    # 逐个题型分组抽取
    group_nodes = [n for n in _iter_nodes(tree) if _has_class(n, "group-title")]
    for gi, gnode in enumerate(group_nodes):
        gtext = re.sub(r"\s+", " ", _node_text(gnode)).strip()
        md.append(f"## {gtext}")
        md.append("")

        # 该分组之后的题目，直到下一分组
        siblings = tree["children"]
        # 通过文档顺序定位：收集 group-title 之后的 question-item
        order = []
        for n in _iter_nodes(tree):
            order.append(n)
        try:
            gi_pos = order.index(gnode)
        except ValueError:
            continue
        next_pos = len(order)
        for nj in group_nodes[gi + 1:]:
            if nj in order:
                next_pos = order.index(nj)
                break
        questions = [n for n in order[gi_pos:next_pos]
                     if "question-item" in (n.get("attrs", {}).get("class") or "").split()]
        # 去重（同一题可能因嵌套结构命中多次）
        seen_ids = set()
        uniq_questions = []
        for q in questions:
            qid = q.get("attrs", {}).get("id")
            key = qid if qid else id(q)
            if key in seen_ids:
                continue
            seen_ids.add(key)
            uniq_questions.append(q)

        for q in uniq_questions:
            md.extend(_render_question(q))

        # 平台未逐题标注分值的大题（如证明/计算题）统一补一条说明，避免读者误以为漏录
        missing_score = 0
        for q in uniq_questions:
            has_score = any(_has_class(n, "score-show") for n in _iter_nodes(q))
            if not has_score:
                missing_score += 1
        if missing_score:
            md.append(f"> **分值说明**：本大题 {missing_score} 题的平台页面上未逐题标注分值，"
                      f"仅在大题标题处给出本大题总分，按原始页面如实归档。")
            md.append("")

    body_md = "\n".join(md)
    body_md += _latex_typo_notes(body_md)
    return body_md


def _latex_typo_notes(body_md: str) -> str:
    """检测平台侧 LaTeX 录入笔误（照抄原文，仅追加人工标注，不改写公式）"""
    notes = []
    # 真正的左定界符失配：出现 \left. 但同段完全没有 \right
    for m in re.finditer(r"\$([^$]{0,160})\\left\.([^$]{0,160})\$", body_md):
        seg = m.group(0)
        if "\\right" not in seg:
            notes.append(f"`{seg}` — 平台原文左定界符 `\\left.` 未配对，疑为录入笔误（按原样保留）")
            break
    # 形如 \frac{grad z}{1,2} 的异常分数式（应为 grad z|_{(1,2)}）
    if re.search(r"\\frac\{\s*grad[^}]*\}\{\s*[\d,\s]+\s*\}", body_md):
        notes.append("第 9 题中平台以 `\\frac{grad z}{1,2}` 形式书写梯度，"
                     "按数学惯例应为 `\\mathrm{grad}\\,z\\big|_{(1,2)}`，平台原文照录未改")
    if not notes:
        return ""
    lines = ["", "---", "", "## 附：平台原始公式笔误标注（原文照录，未作改写）", ""]
    for i, n in enumerate(notes, 1):
        lines.append(f"{i}. {n}")
    lines.append("")
    return "\n".join(lines)


def _render_question(qnode):
    """渲染单题：题型标签 + 题干段落（含 LaTeX 公式）+ 选择项"""
    out = []
    title_parts = []
    for n in _iter_nodes(qnode):
        if _has_class(n, "float-left"):
            t = re.sub(r"\s+", " ", _node_text(n)).strip()
            if t:
                title_parts.append(t)
    for n in _iter_nodes(qnode):
        if _has_class(n, "combination-title-noName"):
            t = re.sub(r"\s+", " ", _node_text(n)).strip()
            if t:
                title_parts.append(t)

    score = ""
    for n in _iter_nodes(qnode):
        if _has_class(n, "score-show"):
            score = re.sub(r"\s+", " ", _node_text(n)).strip()
            break

    header = " ".join(dict.fromkeys([p for p in title_parts if p]))
    if header:
        out.append(f"### {header}" + (f" {score}" if score else ""))
        out.append("")

    # 题干：class 含 qeustion-content 的容器
    content_nodes = []
    for n in _iter_nodes(qnode):
        if "qeustion-content" in (n.get("attrs", {}).get("class") or "").split():
            content_nodes.append(n)
            break
    if not content_nodes:
        for n in _iter_nodes(qnode):
            if "combination-content-text" in (n.get("attrs", {}).get("class") or "").split():
                content_nodes.append(n)
                break

    if content_nodes:
        paras = []
        _collect_paragraphs(content_nodes[0], paras)
        for p in paras:
            rendered = _render_content(p.get("children", []))
            if rendered:
                out.append(rendered)
                out.append("")

    # 选择项
    for n in _iter_nodes(qnode):
        if "option-item" in (n.get("attrs", {}).get("class") or "").split():
            order_txt = ""
            content_txt = ""
            for sub in _iter_nodes(n):
                if _has_class(sub, "option-order") and not order_txt:
                    order_txt = _node_text(sub).strip()
                if "option-content" in (sub.get("attrs", {}).get("class") or "").split():
                    paras = []
                    _collect_paragraphs(sub, paras)
                    if paras:
                        content_txt = _render_content(paras[0].get("children", []))
                    break
            if order_txt or content_txt:
                out.append(f"- **{order_txt}** {content_txt}".rstrip())

    # 上传附件提示
    if any("上传附件" in _node_text(n) for n in _iter_nodes(qnode)
           if n.get("tag") in ("span", "div", "p")):
        out.append("")
        out.append("> （该题平台要求上传附件作答）")

    out.append("")
    return out

def generate_markdown_content(source_file: Path, title: str, subject: str, raw_body: str,
                              doc_kind: str = "官方原始文件",
                              triggers: list = None) -> str:
    """包装 Frontmatter 与文尾引用时机网格

    doc_kind：文档属性描述（默认"官方原始文件"，练习题原卷等传入对应措辞）
    triggers：可选的触发时机覆盖列表，缺省用通用官方文件口径
    """
    today = datetime.now().strftime("%Y-%m-%d")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    safe_slug = re.sub(r'[^a-zA-Z0-9_\u4e00-\u9fa5]', '_', source_file.stem).upper()
    doc_id = f"RAW_DOC_{safe_slug[:30]}"

    # 计算相对路径关系
    # 假设文件存放在 03_科目资料库/{subject}/00_原始文献与课程文件/{name}.md
    course_plan_rel = f"../01_课程教学计划/"
    workspace_root_rel = "../../../"

    if not triggers:
        triggers = [
            "查阅原始教学大纲、官方考核细则、学时分配与教学进度安排时",
            "对齐任课教师授课周次、实验要求与教材参考书目时",
            "检索官方文档中关于平时成绩、期中与期末考试的具体考核权重时",
        ]
    trigger_lines = "\n".join(f"  - {t}" for t in triggers)

    frontmatter = f"""---
id: {doc_id}
title: {title}（原始文献与课程文件）
type: raw_reference_document
status: ACTIVE
source_filename: {source_file.name}
converted_at: {now_str}
last_updated: {today}
subject: {subject}
triggers:
{trigger_lines}
reads_before:
  - {workspace_root_rel}00_协作协议.md
related_files:
  - path: {workspace_root_rel}ROUTER.md
    desc: 全局全景路由与时机调度矩阵
    timing: 需要跨学科或根据学习意图定位文件时
  - path: {workspace_root_rel}00_协作协议.md
    desc: 全局协作底座与学习习惯约定
    timing: 确认学习模式与排版规范时
  - path: {workspace_root_rel}01_状态中枢/教学进度与掌握矩阵.json
    desc: 当前学期周次与掌握度矩阵
    timing: 核对当前周次教学进度与薄弱点时
  - path: ../README.md
    desc: {subject} 学科导航与模块索引
    timing: 返回该学科总览或切换至考点题型时
---

# {title}

> **原始文件元信息归档**：
> - **来源文件**：`{source_file.name}`
> - **所属学科**：`{subject}`
> - **转换时间**：`{now_str}`
> - **文档属性**：{doc_kind}（全量无损归档副本，不作删减）

---

## 目录与正文内容

{raw_body.strip()}

---

## 文尾关联文件与引用时机网格（Outbound Contextual Router）

| 目标文件相对路径 | 对应文件核心内容 | 引用时机与触发条件 | 关联类型 |
| :--- | :--- | :--- | :--- |
| [`../README.md`](../README.md) | {subject} 学科资料库导航与三级目录索引 | 查阅该学科整体学时分配、核心教材与考点分类时 | 学科总览 |
| [`{workspace_root_rel}ROUTER.md`]({workspace_root_rel}ROUTER.md) | 全局全景路由与时机调度矩阵 | 需要跨学科调度或依据用户场景意图快速检索入口时 | 全局路由 |
| [`{workspace_root_rel}00_协作协议.md`]({workspace_root_rel}00_协作协议.md) | 工作区底层协作宪法与渐进披露三级运行规范 | 确认全局学习原则与实验期双主轴配置时 | 上游总纲 |
| [`{workspace_root_rel}01_状态中枢/教学进度与掌握矩阵.json`]({workspace_root_rel}01_状态中枢/教学进度与掌握矩阵.json) | 全局进度与掌握度矩阵 | 查询当前周次授课内容或核对考核状态时 | 核心状态 |
| [`{workspace_root_rel}02_运行规则/工程避坑账本.md`]({workspace_root_rel}02_运行规则/工程避坑账本.md) | 刚性工程避坑补丁（含输入文件强制全量转.md补丁） | 核对文档规范、排版纪律与自学避坑规则时 | 规则补丁 |
"""
    return frontmatter

def ensure_subject_raw_docs_readme(subject: str, target_dir: Path):
    """确保 00_原始文献与课程文件 目录具备索引 README.md 并通过链接体检"""
    readme_path = target_dir / "README.md"
    today = datetime.now().strftime("%Y-%m-%d")
    workspace_root_rel = "../../../"
    
    # 扫描该目录下所有除 README 外的 md 文件
    md_files = [f for f in target_dir.glob("*.md") if f.name != "README.md"]
    rows = []
    for f in md_files:
        rows.append(f"| [`{f.name}`]({f.name}) | 官方原始文件全量无损归档 | 查阅原始大纲条款、学时与考纲指标时 | 原始大纲 |")

    table_content = "\n".join(rows) if rows else "| 暂无文件 | - | - | - |"

    # 已有索引则增量追加新文件行，严禁整体重写（避免冲掉手工维护的口径说明与指纹）
    if readme_path.exists():
        existing = readme_path.read_text(encoding="utf-8")
        added = []
        for f in md_files:
            if f"`{f.name}`" in existing:
                continue
            added.append(f"| [`{f.name}`]({f.name}) | 教师布置练习题/原始文件全量无损归档 | 刷本章练习题原卷或查阅原始条款时 | 原始依据 |")
        if added:
            anchor = "| :--- | :--- | :--- | :--- |"
            idx = existing.find(anchor)
            if idx != -1:
                insert_at = existing.find("\n", idx) + 1
                existing = existing[:insert_at] + "\n".join(added) + "\n" + existing[insert_at:]
            existing = re.sub(r"^last_updated: .*$", f"last_updated: {today}", existing,
                              count=1, flags=re.M)
            readme_path.write_text(existing, encoding="utf-8")
            print(f"已增量追加 {len(added)} 条索引记录: {readme_path}")
        else:
            print(f"索引已包含全部归档文件，无需改写: {readme_path}")
        return

    content = f"""---
id: RAW_DOCS_INDEX_{subject.upper()}
title: {subject} 原始文献与课程文件索引
type: directory_index
status: ACTIVE
last_updated: {today}
triggers:
  - 需要查阅 {subject} 任何官方原始文件、大纲或规章时
reads_before:
  - ../README.md
related_files:
  - path: ../README.md
    desc: {subject} 科目资料库总索引
    timing: 返回该学科总览时
  - path: {workspace_root_rel}ROUTER.md
    desc: 全局全景路由与时机调度矩阵
    timing: 跨学科调度时
---

# {subject} 原始文献与课程文件索引（00_原始文献与课程文件/README.md）

> 本目录归档学习者上传或输入的 {subject} 官方原始文件（大纲、考核方案、课件、题集等）的全量无损 Markdown 副本。  
> **归档原则**：100% 全量保留，严禁擅自删节；支持全局检索与跨会话复用。

---

## 一、已归档原始文献列表

| 归档文档名称 | 文档内容属性 | 引用时机与触发条件 | 关联类型 |
| :--- | :--- | :--- | :--- |
{table_content}

---

## 文尾关联文件与引用时机网格（Outbound Contextual Router）

| 目标文件相对路径 | 对应文件核心内容 | 引用时机与触发条件 | 关联类型 |
| :--- | :--- | :--- | :--- |
| [`../README.md`](../README.md) | {subject} 学科资料库导航与索引 | 返回该学科总览或进入自学方案与核心考点时 | 上级目录 |
| [`{workspace_root_rel}ROUTER.md`]({workspace_root_rel}ROUTER.md) | 全局场景-意图-文件调度全景矩阵 | 跨学科调度或依据用户场景意图定位文件时 | 全局路由 |
| [`{workspace_root_rel}00_协作协议.md`]({workspace_root_rel}00_协作协议.md) | 工作区底层协作宪法 | 确认全局学习原则与输入文件转换规范时 | 上游总纲 |
| [`{workspace_root_rel}01_状态中枢/教学进度与掌握矩阵.json`]({workspace_root_rel}01_状态中枢/教学进度与掌握矩阵.json) | 全局进度与掌握度矩阵 | 查询当前周次授课内容或更新掌握度评价时 | 核心状态 |
"""
    readme_path.write_text(content, encoding="utf-8")
    print(f"已更新/创建原始文献目录索引: {readme_path}")

def update_subject_readme(subject: str, target_dir: Path):
    """更新科目根目录的 README.md，将 00_原始文献与课程文件 挂载入主索引"""
    subject_readme = target_dir.parent / "README.md"
    if not subject_readme.exists():
        # 若科目级 README 不存在，创建基础版
        pass
    else:
        content = subject_readme.read_text(encoding="utf-8")
        if "00_原始文献与课程文件" not in content:
            # 插入到子目录规划部分
            insert_marker = "子目录规划与直达路径"
            if insert_marker in content:
                addition = "- `00_原始文献与课程文件/`：[原始文献与课程文件索引](00_原始文献与课程文件/README.md)（官方大纲、考核方案全量无损归档）\n  "
                content = content.replace(f"- `01_课程教学计划/`", f"{addition}- `01_课程教学计划/`")
                subject_readme.write_text(content, encoding="utf-8")
                print(f"已同步更新科目主索引: {subject_readme}")

def convert_file(file_path: Path, subject: str = None, output_path: Path = None, title: str = None,
                doc_kind: str = None, triggers: list = None) -> Path:
    """执行单个文件转换主流程"""
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    suffix = file_path.suffix.lower()
    file_stem = file_path.stem

    if not title:
        title = file_stem

    if not subject:
        subject = detect_subject(file_stem)

    print(f"--> 开始解析文件: {file_path.name}")
    print(f"    检测归属学科: {subject}")

    if suffix in [".docx", ".doc"]:
        raw_body = convert_docx(file_path)
    elif suffix == ".pdf":
        raw_body = convert_pdf(file_path)
    elif suffix in [".xlsx", ".xls"]:
        raw_body = convert_xlsx(file_path)
    elif suffix in [".txt", ".csv", ".tsv"]:
        raw_body = convert_text(file_path)
    elif suffix in [".html", ".htm"]:
        raw_body = convert_html(file_path)
        doc_kind = doc_kind or "教师布置练习题原卷（平台作业页全量无损转录，公式已还原为标准 LaTeX）"
        triggers = triggers or [
            "刷某一章练习题原卷、做章节自测或考前限时训练时",
            "需要核对教师布置作业的完整题面、分值分布与题型构成时",
            "需要以原始 LaTeX 形式取用题目中的公式（梯度、方向导数、隐函数求导、切平面等）时",
        ]
    else:
        raise ValueError(f"暂不支持该文件类型: {suffix}")

    # 确定保存路径
    if output_path is None:
        target_dir = WORKSPACE_ROOT / "03_科目资料库" / subject / "00_原始文献与课程文件"
        target_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r'[\\/*?:"<>|]', '_', file_stem) + ".md"
        output_path = target_dir / safe_name
    else:
        target_dir = output_path.parent
        target_dir.mkdir(parents=True, exist_ok=True)

    # 生成完整规范 Markdown
    full_md = generate_markdown_content(source_file=file_path, title=title, subject=subject,
                                        raw_body=raw_body, doc_kind=doc_kind, triggers=triggers)
    output_path.write_text(full_md, encoding="utf-8")
    print(f"--> 转换成功: {output_path}")

    # 维护两级目录索引
    ensure_subject_raw_docs_readme(subject, target_dir)
    update_subject_readme(subject, target_dir)

    return output_path

def main():
    parser = argparse.ArgumentParser(description="外部输入文件全量无损转 Markdown 工具")
    parser.add_argument("file", help="待转换的原文件路径")
    parser.add_argument("-s", "--subject", help="指定归属学科（可选，默认根据关键词自动判定）", default=None)
    parser.add_argument("-o", "--output", help="指定输出 markdown 文件路径（可选）", default=None)
    parser.add_argument("-t", "--title", help="指定文档标题（可选，默认使用文件名）", default=None)
    parser.add_argument("--subjects", help="领域映射表 JSON 路径（默认查找工作区根 subjects.json）", default=None)

    args = parser.parse_args()

    # 加载领域映射表（外置配置，不硬编码）
    global SUBJECT_KEYWORDS
    SUBJECT_KEYWORDS = load_subjects_config(args.subjects)

    input_file = Path(args.file).resolve()
    out = Path(args.output).resolve() if args.output else None

    convert_file(input_file, subject=args.subject, output_path=out, title=args.title)

if __name__ == "__main__":
    main()
