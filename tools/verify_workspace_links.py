#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_workspace_links.py — Markdown 知识库体检器

配合《文尾网格 + 五步闭环》方法论使用：把「索引维护」变成可机检的 CI 步骤。

检查五项：
1. 所有 Markdown 的 YAML Frontmatter 规范性（必填字段可配置）；
2. 每个文档文尾是否包含《关联文件与引用时机网格》；
3. 文档中所有相对路径链接是否有效（无死链）；
4. 是否存在「孤岛文件」（未被任何文档引用）；
5. 状态中枢 JSON 中登记的路径是否真实存在。

用法：
    python verify_workspace_links.py                     # 检查当前目录
    python verify_workspace_links.py --root /path/to/ws  # 检查指定工作区
    python verify_workspace_links.py --config my.json    # 用自定义配置
    python verify_workspace_links.py --no-root-guard     # 关闭根目录防污染检查

退出码：0 = 无阻断项；1 = 存在错误。
"""

import argparse
import json
import re
import sys
import urllib.parse
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ============================================================
# 默认配置：所有项目相关的值都集中在这里，可用 --config 覆盖
# ============================================================
DEFAULT_CONFIG = {
    # Frontmatter 必填字段
    "required_frontmatter_keys": ["id", "title", "type", "triggers", "related_files"],

    # 文尾网格可接受的标题关键词（命中任意一个即算通过）
    "grid_section_keywords": [
        "文尾关联文件与引用时机",
        "文尾关联与时机路由",
        "Outbound Contextual Router",
        "关联文件与引用时机",
    ],

    # 入口文件：豁免「孤岛文件」检查（它们本就该被主动读取）
    "entry_files": ["AGENTS.md", "ROUTER.md", "README.md"],

    # 状态中枢 JSON 的相对路径（相对工作区根）；留空则不检查。
    # 默认指向示例目录；实际使用时请改成你自己的路径，如 "01_状态中枢/状态.json"。
    "state_hub_path": "examples/calculus/状态.json",

    # 是否启用根目录防污染检查
    "enable_root_guard": False,

    # 根目录允许出现的条目白名单（仅在 enable_root_guard=true 时生效）
    "allowed_root_entries": [
        ".git", ".github", ".vscode", "node_modules",
        "AGENTS.md", "ROUTER.md", "README.md", "LICENSE",
        "00_协作协议.md", "01_状态中枢", "02_运行规则", "03_资料库",
        "docs", "templates", "tools", "examples",
    ],

    # 扫描时跳过的目录名（任意层级）
    "skip_dirs": [".git", ".github", "node_modules", "__pycache__", ".venv", "venv"],

    # 跳过「死链检查」的路径前缀。
    # 用途：模板目录里的链接指向的是「使用者未来的工作区」，
    # 在本仓库内必然不存在，属预期行为，不该报错。
    "skip_link_check_prefixes": ["templates/"],
}


def load_config(root: Path, config_path: str | None) -> dict:
    """加载配置：内置默认值 ← 工作区 .verifyrc.json ← 显式 --config。"""
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # 深拷贝

    local_rc = root / ".verifyrc.json"
    for candidate in (local_rc, Path(config_path) if config_path else None):
        if candidate and candidate.exists():
            try:
                cfg.update(json.loads(candidate.read_text(encoding="utf-8-sig")))
                print(f"已加载配置: {candidate}")
            except Exception as e:
                print(f"配置读取失败 {candidate}: {e}")
    return cfg


def check_frontmatter(content: str, required_keys: list[str]) -> tuple[bool, str]:
    """检查 YAML Frontmatter 是否存在且包含必填字段。"""
    match = re.search(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not match:
        return False, "缺少 YAML Frontmatter 头标记（---）"
    fm_text = match.group(1)
    missing = [k for k in required_keys if f"{k}:" not in fm_text]
    if missing:
        return False, f"Frontmatter 缺少核心字段: {', '.join(missing)}"
    return True, "OK"


def check_grid_section(content: str, keywords: list[str]) -> bool:
    """检查文尾是否包含《关联文件与引用时机网格》且确实是一张表。"""
    has_section = any(kw in content for kw in keywords)
    has_table = "|" in content and "---" in content
    return has_section and has_table


def extract_links(content: str) -> list[tuple[str, str]]:
    """提取 Markdown 中的相对文件链接，忽略代码块内的示例。

    注意：链接目标若用 [^)]+，会在文件名首个 ')' 处截断，
    导致 `报告（2024）(1).md` 这类真实文件被误报为死链。
    故改用「允许成对圆括号」或「尖括号包裹」两种目标写法。
    """
    cleaned = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
    cleaned = re.sub(r"`\[[^\]]+\]\([^)]+\)`", "", cleaned)

    link_pattern = r"\[([^\]]+)\]\(\s*(<[^>]*>|(?:[^()]|\([^()]*\))+?)\s*\)"
    links = []
    for text, link in re.findall(link_pattern, cleaned):
        clean_link = link.strip()
        if clean_link.startswith("<") and clean_link.endswith(">"):
            clean_link = clean_link[1:-1]
        # 先移除锚点，再做百分号解码（%20 → 空格），否则带空格路径永远对不上
        clean_link = urllib.parse.unquote(clean_link.split("#")[0]).strip()
        if clean_link and not clean_link.startswith(("http://", "https://", "mailto:", "tel:")):
            links.append((text, clean_link))
    return links


def iter_markdown(root: Path, skip_dirs: list[str]):
    """遍历 Markdown 文件，跳过隐藏目录与被排除的目录。"""
    for path in root.rglob("*.md"):
        rel_parts = path.relative_to(root).parts
        if any(part in skip_dirs or part.startswith(".") for part in rel_parts):
            continue
        yield path


def main() -> int:
    parser = argparse.ArgumentParser(description="Markdown 知识库体检器")
    parser.add_argument("--root", default=None, help="工作区根目录（默认为脚本所在目录）")
    parser.add_argument("--config", default=None, help="自定义配置文件路径（JSON）")
    parser.add_argument("--no-root-guard", action="store_true", help="关闭根目录防污染检查")
    parser.add_argument("--quiet", action="store_true", help="只输出问题，不输出统计")
    args = parser.parse_args()

    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parent
    if not root.exists():
        print(f"❌ 工作区根目录不存在: {root}")
        return 1

    cfg = load_config(root, args.config)
    if args.no_root_guard:
        cfg["enable_root_guard"] = False

    if not args.quiet:
        print(f"=== 开始扫描工作区: {root} ===")

    md_files = sorted(iter_markdown(root, cfg["skip_dirs"]))
    if not args.quiet:
        print(f"发现 Markdown 文档: {len(md_files)} 个\n")

    errors: list[str] = []
    warnings: list[str] = []
    referenced_targets: set[str] = set()

    for f in md_files:
        rel_path = f.relative_to(root).as_posix()
        try:
            content = f.read_text(encoding="utf-8")
        except Exception as e:
            errors.append(f"[{rel_path}] 无法读取文件: {e}")
            continue

        # 1. Frontmatter
        ok, msg = check_frontmatter(content, cfg["required_frontmatter_keys"])
        if not ok:
            warnings.append(f"[{rel_path}] Frontmatter 警告: {msg}")

        # 2. 文尾网格
        if not check_grid_section(content, cfg["grid_section_keywords"]):
            warnings.append(f"[{rel_path}] 文尾缺少《关联文件与引用时机网格》")

        # 3. 死链检查
        skip_prefixes = tuple(cfg.get("skip_link_check_prefixes") or ())
        if skip_prefixes and rel_path.startswith(skip_prefixes):
            continue  # 模板文件：链接指向使用者未来的工作区，跳过

        for text, link in extract_links(content):
            target_path = (f.parent / link).resolve()
            if not target_path.exists():
                errors.append(f"[{rel_path}] 失效链接 -> [{text}]({link})")
            else:
                try:
                    referenced_targets.add(target_path.relative_to(root).as_posix())
                except ValueError:
                    pass  # 指向工作区外部，不算孤岛依据

    # 4. 状态中枢指针检查
    state_path = cfg.get("state_hub_path")
    if state_path:
        hub = root / state_path
        if hub.exists():
            try:
                hub_str = hub.read_text(encoding="utf-8")
                data = json.loads(hub_str)
                # 登记引用：JSON 中出现的 md 文件名也算被引用
                for f in md_files:
                    f_rel = f.relative_to(root).as_posix()
                    if f_rel in hub_str:
                        referenced_targets.add(f_rel)
                # 检查 paths 段登记的路径是否真实存在。
                # 基准是「状态中枢 JSON 自身所在目录」，而非工作区根——
                # 这样状态文件可以放在任意层级，内部路径永远相对自己，便于整体搬迁。
                hub_dir = hub.parent
                for key, value in (data.get("paths") or {}).items():
                    if key.startswith("_") or not isinstance(value, str):
                        continue
                    if not (hub_dir / value).exists():
                        errors.append(f"[{state_path}] 登记的路径不存在: paths.{key} -> {value}")
            except json.JSONDecodeError as e:
                errors.append(f"[{state_path}] JSON 解析失败: {e}")
        elif not args.quiet:
            warnings.append(f"[{state_path}] 状态中枢文件不存在（若暂不需要可忽略）")

    # 5. 孤岛文件
    entry_files = set(cfg["entry_files"])
    for f in md_files:
        rel_path = f.relative_to(root).as_posix()
        if rel_path in entry_files or rel_path in referenced_targets:
            continue
        warnings.append(f"[{rel_path}] 可能是孤岛文件：未被任何文档引用")

    # 6. 根目录防污染
    if cfg["enable_root_guard"]:
        allowed = set(cfg["allowed_root_entries"])
        for item in root.iterdir():
            if item.name.startswith((".agent-teams", ".tmp", ".git")):
                continue
            if item.name not in allowed:
                errors.append(
                    f"[根目录防污染] 非白名单散落条目: {item.name}"
                    "（请就地归档到对应子目录，或加入 allowed_root_entries）"
                )

    # ===== 输出 =====
    if errors:
        print(f"\n❌ 发现 {len(errors)} 个错误（阻断项）：")
        for err in errors:
            print(f"  - {err}")
    elif not args.quiet:
        print("\n✅ 无死链，状态中枢指针有效。")

    if warnings:
        print(f"\n⚠️ 发现 {len(warnings)} 个待补充/规范警告项：")
        for w in warnings:
            print(f"  - {w}")
    elif not args.quiet:
        print("✅ 所有文档均具备标准 Frontmatter 与文尾时机网格，无孤岛文件。")

    if not args.quiet:
        print("\n===============================")
        print(f"统计：文档 {len(md_files)} 篇 | 错误 {len(errors)} | 警告 {len(warnings)}")

    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
