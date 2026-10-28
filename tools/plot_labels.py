# -*- coding: utf-8 -*-
"""
plot_labels.py — 图表标注防压线的语义化工具

解决一个所有手工调图的人都踩过的坑：**标注文字压线、压点、被裁掉。**

传统做法是反复试 `ha=` / `va=` 的组合，或者加白底框（丑）、加箭头（乱）。
本模块把这些经验固化成一个语义化 API：

    place_clean_label(ax, x, y, "A 点", direction="top-left")

它会自动选对齐方式 + 加纯白光晕描边——既清晰，又不遮挡背景、不生成多余箭头。

依赖：
    pip install matplotlib
"""

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt

# 纯白光晕：让文字在任何背景上都清晰，且不需要遮挡性背景框
HALO = [pe.withStroke(linewidth=3.5, foreground="white")]

FONT_FALLBACK = [
    "Microsoft YaHei",
    "PingFang SC",
    "Noto Sans CJK SC",
    "SimHei",
    "DejaVu Sans",
]

# 八个方向的语义 → (ha, va) 映射
ALIGNMENTS = {
    "bottom": ("center", "top"),        # 文字在点下方
    "top": ("center", "bottom"),        # 文字在点上方
    "left": ("right", "center"),        # 文字在点左侧
    "right": ("left", "center"),        # 文字在点右侧
    "top-left": ("right", "bottom"),
    "top-right": ("left", "bottom"),
    "bottom-left": ("right", "top"),
    "bottom-right": ("left", "top"),
    "center": ("center", "center"),
}


def get_base_style(font_size=11, line_width=1.1):
    """最小可用的中文出图样式。若已用 academic_canvas，可跳过本函数。"""
    plt.rcParams["font.sans-serif"] = FONT_FALLBACK
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["mathtext.fontset"] = "stix"
    plt.rcParams["font.size"] = font_size
    plt.rcParams["axes.linewidth"] = line_width
    plt.rcParams["xtick.direction"] = "in"
    plt.rcParams["ytick.direction"] = "in"


def place_clean_label(ax, x, y, text, direction="top", offset=(0, 0), halo=True, **kwargs):
    """语义化放置文字标注。

    参数：
        ax         : matplotlib Axes
        x, y       : 锚点坐标（数据坐标）
        text       : 标注文字
        direction  : 文字相对锚点的方位，取 ALIGNMENTS 的键
        offset     : 额外像素级微调 (dx, dy)，数据坐标单位
        halo       : 是否加白色光晕描边（默认开）
        **kwargs   : 透传给 ax.text

    返回：matplotlib.text.Text 对象，可交给 academic_canvas.auto_adjust_labels 继续避让。
    """
    ha, va = ALIGNMENTS.get(direction, ("center", "center"))
    if halo:
        kwargs.setdefault("path_effects", HALO)
    return ax.text(x + offset[0], y + offset[1], text, ha=ha, va=va, **kwargs)


def annotate_point(ax, x, y, text, direction="top", marker="o", color="black", **kwargs):
    """在点上画标记并加标注，一步到位。"""
    ax.plot([x], [y], marker=marker, color=color, markersize=5, zorder=5)
    return place_clean_label(ax, x, y, text, direction=direction, color=color, **kwargs)
