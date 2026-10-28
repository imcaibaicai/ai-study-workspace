# -*- coding: utf-8 -*-
"""
academic_canvas.py — matplotlib 出版级出图脚手架

把「让图表看起来像论文插图」这件事固化成可复用配置：
1. 中文字体回退链 + 负号正常显示 + STIX 数学字体
2. 约束布局（constrained_layout）与内向刻度线
3. 标签自动避让（依赖 adjustText，缺失时优雅降级）

用法：
    from academic_canvas import create_figure, auto_adjust_labels

    fig, ax = create_figure()
    ax.plot(x, y)
    ax.set_xlabel("时间 / s")
    plt.savefig("out.png", dpi=300)

依赖：
    pip install matplotlib
    pip install adjusttext   # 可选，缺了只影响 auto_adjust_labels
"""

import sys

import matplotlib.pyplot as plt

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    from adjustText import adjust_text

    _HAS_ADJUST_TEXT = True
except ImportError:  # 优雅降级：没装 adjustText 也能用其余功能
    adjust_text = None
    _HAS_ADJUST_TEXT = False


# 中文字体回退链：按顺序尝试，覆盖 Windows / macOS / Linux
FONT_FALLBACK = [
    "Microsoft YaHei",  # Windows
    "PingFang SC",      # macOS
    "Noto Sans CJK SC", # Linux
    "SimHei",
    "DejaVu Sans",
]


def apply_academic_style(font_size=11, line_width=1.2, tick_size=5):
    """应用全局排版约束。幂等，可重复调用。"""
    plt.rcParams["font.sans-serif"] = FONT_FALLBACK
    plt.rcParams["axes.unicode_minus"] = False   # 修复负号显示为方块
    plt.rcParams["mathtext.fontset"] = "stix"    # 数学公式用 STIX，接近 Times
    plt.rcParams["font.size"] = font_size
    plt.rcParams["axes.linewidth"] = line_width
    plt.rcParams["xtick.direction"] = "in"       # 刻度朝内，出版规范
    plt.rcParams["ytick.direction"] = "in"
    plt.rcParams["xtick.major.size"] = tick_size
    plt.rcParams["ytick.major.size"] = tick_size
    plt.rcParams["figure.autolayout"] = False    # 交给 constrained_layout 管


def create_figure(nrows=1, ncols=1, figsize=(8, 5.5), dpi=300, **kwargs):
    """创建已应用排版约束的画布。返回 (fig, axes)。"""
    apply_academic_style()
    fig, axes = plt.subplots(
        nrows, ncols, figsize=figsize, dpi=dpi, constrained_layout=True, **kwargs
    )
    return fig, axes


def auto_adjust_labels(ax, texts, arrows=True, **kwargs):
    """自动推开重叠标签（力导向）。

    texts 是 ax.text(...) 返回的对象列表。未安装 adjustText 时静默跳过，
    调用方无需改动代码。
    """
    if not texts:
        return
    if not _HAS_ADJUST_TEXT:
        return
    arrowprops = (
        dict(arrowstyle="->", color="#555555", lw=0.8, alpha=0.75) if arrows else None
    )
    adjust_text(
        texts,
        ax=ax,
        arrowprops=arrowprops,
        expand=(1.2, 1.4),
        force_text=(0.8, 1.0),
        force_points=(0.5, 0.5),
        **kwargs,
    )


def save(fig, path, dpi=300):
    """统一保存入口，确保白底、紧凑、无多余留白。"""
    fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
    return path
