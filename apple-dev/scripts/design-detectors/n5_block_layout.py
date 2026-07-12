#!/usr/bin/env python3
"""
N5 — 区块构图验收（抓 D4：整屏构图是编的）

它验的是：**渲染的区块结构，和「指定的那份参照物」一不一致。**
它验不了：构图好不好看、构图对不对。见文件末尾「失效边界」。

═══════════════════════════════════════════════════════════════════════════
为什么不用 run2/score/metrics.py:99-107 的 layout_corr
═══════════════════════════════════════════════════════════════════════════
那个是「零位移行投影相关」。红队实测它的位移容差 ≈ 0：
    真值自己下移 30px  → +0.098
    真值自己裁顶 40px  → −0.056
    随机噪声           → +0.038
负号不携带任何信息。整列作废（run2/report/FINDINGS.md:53）。

本检测器 = 抗平移的块级行投影：
    1. 行投影：每行的横向边缘能量（Sobel_y），压成 1D 信号
    2. 高斯平滑到「区块」尺度（σ≈40px @3x ≈ 13pt）—— 抹掉字形/图标级高频，
       只留卡片边界、区块间距这一档结构
    3. ±400px 位移搜索，取最优归一化互相关 —— 系统 chrome / 安全区 / 滚动
       造成的整体平移不该被当成构图错误（arm2/arm4 的 ~64px 偏移就是这么来的）

用法：
    n5_block_layout.py --render A.png --ref B.png
    n5_block_layout.py --matrix                 # 全 8 臂 × 明暗，对照 TodayA
    n5_block_layout.py --sensitivity            # σ / 位移范围 / 阈值 敏感性
    n5_block_layout.py --falsepos               # 参照物选错会怎样（TodayB/C 当参照）
"""
import argparse, json, pathlib, sys
import numpy as np
import cv2

# ─── 几何：iPhone 16 Pro @3x 原生像素 ───────────────────────────────────
W, H = 1206, 2622
STATUS_BAR_PX = 3 * 59      # 顶部安全区（系统渲染，不参与构图评分）
HOME_IND_PX   = 3 * 34      # 底部 home indicator

# ─── 默认参数（全部由 --sensitivity 实测标定，不是拍脑袋）──────────────
#
# σ=40：σ∈[30,120] 才存在「非 TodayA 构图」与「TodayA 构图」之间的空隙。
#       σ=10 → 空隙 −0.061（不可分）；σ=160 → 空隙 −0.002（不可分）。
#       σ=40~80 空隙最宽（+0.048~+0.057）。取 40（≈13pt，卡片间距量级）。
#
# ±400：位移搜索 ≥200px 后分数完全饱和（±200/±400/±800 一字不差）。
#       ±0（= 已作废的 layout_corr 的行为）会把「同构图 + 64px 系统偏移」的
#       arm2/arm4 打到 0.618 以下 —— 位移被当成构图错误。
#
# τ=0.89：**不是建议里的 0.85。** 实测阈值扫描：
#       τ=0.85 → TodayB（设计师自己画的合法变体）以 0.855/0.864 **假通过**。
#       零错分区间 = [0.87, 0.91]，取中点 0.89。
#       τ≥0.92 → arm1c / arm4 / arm4u 假失败。
SIGMA_DEFAULT     = 40.0    # 高斯平滑 σ（px @3x）—— 区块尺度
MAX_SHIFT_DEFAULT = 400     # 位移搜索半径（px）
THRESHOLD_DEFAULT = 0.89    # 通过线（零错分区间 [0.87, 0.91] 的中点）

ROOT   = pathlib.Path(__file__).resolve().parent.parent / "run2"
ARMS   = ["arm1", "arm1b", "arm1c", "arm2", "arm3", "arm4", "arm4t", "arm4u"]
MODES  = ["light", "dark"]


def arm_png(arm, mode):
    return ROOT / "arms" / "shots-strict" / f"{arm}-{mode}.png"


def truth_png(variant, mode):
    return ROOT / "design-truth" / "shots" / f"today-{variant}-{mode}.png"


def load(p):
    im = cv2.imread(str(p), cv2.IMREAD_COLOR)
    if im is None:
        raise SystemExit(f"读不了: {p}")
    if (im.shape[1], im.shape[0]) != (W, H):
        im = cv2.resize(im, (W, H), interpolation=cv2.INTER_AREA)
    return im


def content(im):
    """内容区 —— 剔除系统 chrome（真机由系统画、真值里是原型画的假货）。"""
    return im[STATUS_BAR_PX:H - HOME_IND_PX]


def row_profile(im, sigma):
    """块级行投影：每行的横向边缘能量，高斯平滑到区块尺度。"""
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
    e = np.abs(cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3))   # 横向边缘 = 卡片上下沿
    p = e.mean(axis=1).astype(np.float64)                 # → 1D，长度 = 内容区高
    if sigma > 0:
        # 1D 高斯：把字形级高频抹掉，只留区块结构
        k = int(sigma * 6) | 1
        p = cv2.GaussianBlur(p.reshape(-1, 1), (1, k), sigmaX=0, sigmaY=sigma).ravel()
    return p


def _pearson(a, b):
    a = a - a.mean()
    b = b - b.mean()
    d = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / d) if d > 1e-12 else 0.0


def block_layout(render, ref, sigma=SIGMA_DEFAULT, max_shift=MAX_SHIFT_DEFAULT):
    """
    返回 (best_corr, best_shift)。
    best_shift > 0 = render 的内容相对 ref 整体下移了 best_shift 像素。
    相关系数在**重叠段内重新归一化**（标准 NCC），不是先全局 z-score 再平移。
    """
    pa = row_profile(content(render), sigma)
    pb = row_profile(content(ref), sigma)
    n = len(pa)
    best, best_s = -1.0, 0
    for s in range(-max_shift, max_shift + 1):
        lo, hi = max(0, s), min(n, n + s)
        if hi - lo < n // 2:          # 重叠不足一半，不采信
            continue
        r = _pearson(pa[lo:hi], pb[lo - s:hi - s])
        if r > best:
            best, best_s = r, s
    return best, best_s


def verdict(corr, threshold=THRESHOLD_DEFAULT):
    return "PASS" if corr >= threshold else "FAIL"


# ═══════════════════════════════════════════════════════════════════════
# 驱动
# ═══════════════════════════════════════════════════════════════════════

def run_matrix(sigma, max_shift, threshold, ref_variant="A"):
    refs = {m: load(truth_png(ref_variant, m)) for m in MODES}
    rows = []
    for arm in ARMS:
        for m in MODES:
            c, s = block_layout(load(arm_png(arm, m)), refs[m], sigma, max_shift)
            rows.append(dict(subject=arm, mode=m, corr=round(c, 3), shift=s,
                             verdict=verdict(c, threshold)))
    # 设计师自己的合法变体 —— 标定阈值的关键对照
    for v in ["B", "C"]:
        if v == ref_variant:
            continue
        for m in MODES:
            c, s = block_layout(load(truth_png(v, m)), refs[m], sigma, max_shift)
            rows.append(dict(subject=f"Today{v} (设计师变体)", mode=m,
                             corr=round(c, 3), shift=s, verdict=verdict(c, threshold)))
    return rows


def print_matrix(rows, threshold):
    print(f"\nN5 区块构图验收 — 参照物 = TodayA（被建的那一屏）  阈值 = {threshold}")
    print(f"{'臂':16} {'浅色':>16} {'深色':>16}   判定")
    print("─" * 62)
    by = {}
    for r in rows:
        by.setdefault(r["subject"], {})[r["mode"]] = r
    for name, d in by.items():
        l, k = d["light"], d["dark"]
        mark = "🔴 FAIL" if "FAIL" in (l["verdict"], k["verdict"]) else "✅ PASS"
        print(f"{name:16} {l['corr']:>7.3f} (Δ{l['shift']:+4d}) {k['corr']:>7.3f} (Δ{k['shift']:+4d})   {mark}")


#: 标定集：NEG = 不是 TodayA 那个构图 / POS = 是 TodayA 那个构图
NEG = ["arm1", "arm1b", "TodayC", "TodayB"]
POS = ["arm1c", "arm2", "arm3", "arm4", "arm4t", "arm4u"]


def _score(subj, mode, sigma, max_shift, ref_variant="A"):
    im = load(arm_png(subj, mode)) if subj.startswith("arm") else load(truth_png(subj[-1], mode))
    c, _ = block_layout(im, load(truth_png(ref_variant, mode)), sigma, max_shift)
    return c


def _gap(sigma, max_shift):
    """返回 (NEG 最高分, POS 最低分, 间隙宽度)。间隙 = 阈值可以放的区间。"""
    neg = [_score(s, m, sigma, max_shift) for s in NEG for m in MODES]
    pos = [_score(s, m, sigma, max_shift) for s in POS for m in MODES]
    return max(neg), min(pos), min(pos) - max(neg)


def run_sensitivity():
    print("\n【σ 敏感性】NEG=非 TodayA 构图（含设计师变体 B/C） POS=TodayA 构图")
    print(f"{'σ':>5} {'NEG 最高':>9} {'POS 最低':>9} {'间隙':>7}  安全阈值区间")
    for sig in [10, 20, 30, 40, 60, 80, 120, 160]:
        hi, lo, g = _gap(sig, MAX_SHIFT_DEFAULT)
        band = f"[{hi:.3f}, {lo:.3f}]" if g > 0 else "❌ 无间隙（不可分）"
        print(f"{sig:5.0f} {hi:9.3f} {lo:9.3f} {g:+7.3f}  {band}")

    print("\n【位移搜索范围敏感性】σ=40 固定")
    print(f"{'±px':>5} {'NEG 最高':>9} {'POS 最低':>9} {'间隙':>7}  安全阈值区间")
    for ms in [0, 50, 100, 200, 300, 400, 600, 800]:
        hi, lo, g = _gap(SIGMA_DEFAULT, ms)
        band = f"[{hi:.3f}, {lo:.3f}]" if g > 0 else "❌ 无间隙（不可分）"
        print(f"{ms:5d} {hi:9.3f} {lo:9.3f} {g:+7.3f}  {band}")

    print("\n【逐主体明细 σ=40 ±400】")
    for s in NEG + POS:
        v = [_score(s, m, SIGMA_DEFAULT, MAX_SHIFT_DEFAULT) for m in MODES]
        tag = "NEG" if s in NEG else "POS"
        print(f"  {tag}  {s:8} 浅={v[0]:.3f} 深={v[1]:.3f}")

    print("\n【阈值扫描 σ=40 ±400】错分数 = 假通过(NEG≥τ) + 假失败(POS<τ)")
    negv = [(s, m, _score(s, m, SIGMA_DEFAULT, MAX_SHIFT_DEFAULT)) for s in NEG for m in MODES]
    posv = [(s, m, _score(s, m, SIGMA_DEFAULT, MAX_SHIFT_DEFAULT)) for s in POS for m in MODES]
    for t in [0.60, 0.70, 0.80, 0.85, 0.87, 0.88, 0.89, 0.90, 0.91, 0.92, 0.95]:
        fp = [f"{s}-{m}" for s, m, c in negv if c >= t]
        fn = [f"{s}-{m}" for s, m, c in posv if c < t]
        mark = "✅ 零错分" if not fp and not fn else f"假通过={fp or '—'} 假失败={fn or '—'}"
        print(f"  τ={t:.2f}  {mark}")


def run_falsepos():
    """参照物选错 = 假阳性风险。拿 TodayB / TodayC 当参照物去测 TodayA。"""
    print("\n【假阳性 / 参照物依赖】—— 换一个参照物，同一张图的判定就翻转")
    for ref_v in ["A", "B", "C"]:
        line = []
        for subj in ["A", "B", "C"]:
            vals = []
            for m in MODES:
                c, _ = block_layout(load(truth_png(subj, m)), load(truth_png(ref_v, m)),
                                    SIGMA_DEFAULT, MAX_SHIFT_DEFAULT)
                vals.append(c)
            line.append(f"Today{subj}={vals[0]:.3f}/{vals[1]:.3f}")
        print(f"  参照物=Today{ref_v}:  " + "   ".join(line))
    print("  → 三张图都是设计师给同一屏画的合法构图。分数只说「和参照物一不一致」。")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--render"); ap.add_argument("--ref")
    ap.add_argument("--sigma", type=float, default=SIGMA_DEFAULT)
    ap.add_argument("--max-shift", type=int, default=MAX_SHIFT_DEFAULT)
    ap.add_argument("--threshold", type=float, default=THRESHOLD_DEFAULT)
    ap.add_argument("--matrix", action="store_true")
    ap.add_argument("--sensitivity", action="store_true")
    ap.add_argument("--falsepos", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.matrix:
        rows = run_matrix(a.sigma, a.max_shift, a.threshold)
        if a.json:
            print(json.dumps(rows, ensure_ascii=False, indent=1))
        else:
            print_matrix(rows, a.threshold)
    elif a.sensitivity:
        run_sensitivity()
    elif a.falsepos:
        run_falsepos()
    elif a.render and a.ref:
        c, s = block_layout(load(a.render), load(a.ref), a.sigma, a.max_shift)
        r = dict(render=a.render, ref=a.ref, corr=round(c, 4), shift=s,
                 threshold=a.threshold, verdict=verdict(c, a.threshold))
        print(json.dumps(r, ensure_ascii=False) if a.json else
              f"block_layout={c:.4f}  shift={s:+d}px  → {r['verdict']}")
    else:
        ap.error("给 --render/--ref，或 --matrix / --sensitivity / --falsepos")

# ═══════════════════════════════════════════════════════════════════════
# 失效边界（读之前先读这一段）
# ═══════════════════════════════════════════════════════════════════════
# 1. 它分不开「编造的构图」和「设计师自己的合法变体」。这是固有局限，不是 bug：
#       arm1 = 0.510/0.496   arm1b = 0.575/0.595   TodayC（设计师本人画的）= 0.563/0.553
#    三个数在同一个带里。所以本检测器**不能**用来判「构图对不对」（那需要人），
#    只能用来判「构图和**指定的那份参照物**一不一致」。
#    → 用它之前，必须先有人指定「哪一份是参照物」。契约里没写变体存在时，这个前置不成立。
#    → --falsepos 直接演示：同一张 TodayA，参照物换成 TodayB 就掉到 0.855/0.864，
#      换成 TodayC 掉到 0.563/0.553。分数是**关于参照物的**，不是关于图的。
# 2. 「合法变体」不一定都掉进 FAIL 带。TodayB = 0.855/0.864，比 TodayC 高一大截，
#    离 POS 带（0.912+）只差 0.05。**这是本指标最薄的地方** —— 空隙只有 0.048 宽。
#    换一个变体集合，空隙可能直接消失。阈值 0.89 只在**本数据集**上零错分。
# 3. 它对**横向**构图差异不敏感（只投影行）。两栏对一栏、左右互换，行投影仍可能高度相关。
# 4. 它对内容差异不敏感（文案全错、图标全错，只要区块边界在同一位置，分数照样高）。
#    arm3 拿 0.992 —— 而 arm3 四个 readiness 态一个没有、accent 硬编码。
# 5. 它需要两张图同分辨率、同设备、同一屏。跨屏无意义。
