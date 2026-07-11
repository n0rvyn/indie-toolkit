#!/usr/bin/env python3
"""
N6 — 材质表面色数值断言（抓 D3：玻璃卡表面色缺失 → 明暗符号反转）

判据是**渲染采样 vs 契约声明的值**，不是渲染 vs 原型截图。
原型截图自带假设备外框净空（`screens-today.jsx:115` 的 `padding:'64px 20px 100px'`），
拿它当 ground truth 会奖励另一个 bug（arm2/arm4 把 64/100 直译进了 SwiftUI）。

═══════════════════════════════════════════════════════════════════════════
契约声明的值（三处独立互证，不是我编的）
═══════════════════════════════════════════════════════════════════════════
  run2/contract/DESIGN.md:43       tints: "... regular .60 / thick .78 (+sat 200% blur 50)"
  run2/contract/DESIGN.md:109      Card = `GlassBlur tint="thick" radius=22`   ← 卡片用 thick
  run2/design-src/glass-primitives.jsx:12   thick:      bg rgba(255,255,255,0.78)
  run2/design-src/glass-primitives.jsx:14   dark-thick: bg rgba(28,28,30,0.78)
  run2/design-src/shared.jsx:559   thick: dark ? 'rgba(28,28,30,0.78)' : 'rgba(255,255,255,0.78)'
  run2/design-src/shared.jsx:186   dark --surface-rgb: 28,28,30   (= #1C1C1E)

玻璃 = 半透明 tint 压在背景上。所以「契约声明的表面色」要解析成不透明色：

    表面色_预期 = α·T + (1−α)·B          α = 0.78
                                          T = #FFFFFF（浅）/ #1C1C1E（深）
                                          B = 同高度实测壁纸（从渲染图自己取）

B 取自**被测图自己的壁纸**，不取自真值图 —— 检测器因此只依赖 (渲染图, 契约)，
不需要设计真值截图。这正是「不和原型截图比」的落地方式。

blur(50)/saturate(200%) **不进预期值**：DESIGN.md:42 明写它们是浏览器假货
（"DO NOT port the web blur/saturate stack — it only fakes glass in a browser"），
原生 .glassEffect 不做 saturate。把它算进去 = 把浏览器缺陷写成验收标准。
（--sat 可以打开，作为敏感性对照 —— 结论不变，见 --sensitivity。）

═══════════════════════════════════════════════════════════════════════════
两条判据
═══════════════════════════════════════════════════════════════════════════
【N6-A 抬升量符号】⭐ 主判据，**不依赖阈值标定**
    lift_actual   = L*(卡内) − L*(同高度壁纸)
    lift_expected = L*(α·T + (1−α)·B) − L*(B)        ← 纯从契约算
    符号不一致 → 🔴 CRITICAL（设计的明暗关系被整个翻转）

    深色：T=#1C1C1E（L*≈11）比暗色壁纸（L*≈37）暗 → 卡必须**比壁纸暗**。
    浅色：T=#FFFFFF（L*=100）比浅色壁纸（L*≈89）亮 → 卡必须**比壁纸亮**。

【N6-B 表面色数值断言】次判据，需要阈值
    ΔE00(卡内采样, α·T + (1−α)·B) > τ → 🔴

用法：
    n6_surface_color.py --render arm4-dark.png --mode dark
    n6_surface_color.py --matrix          # 全 8 臂 × 明暗
    n6_surface_color.py --sensitivity     # 背景模型 / sat / 阈值 敏感性
"""
import argparse, json, pathlib, sys
import numpy as np
import cv2

W, H = 1206, 2622
ROOT  = pathlib.Path(__file__).resolve().parent.parent / "run2"
ARMS  = ["arm1", "arm1b", "arm1c", "arm2", "arm3", "arm4", "arm4t", "arm4u"]
MODES = ["light", "dark"]

# ─── 采样窗（@3x 设备像素）—— hero 卡的空白面 + 同高度纯壁纸边条 ────────
CARD_Y, CARD_X = slice(850, 1150), slice(700, 1100)
WALL_L_X       = slice(0, 45)        # 左侧 20pt gutter 内的壁纸
WALL_R_X       = slice(1161, 1206)   # 右侧 gutter

# ─── 契约声明的卡片 tint ────────────────────────────────────────────────
CONTRACT_TINT = {
    # mode: (T_rgb, alpha, saturate%)   —— 出处见 docstring
    "light": ((255, 255, 255), 0.78, 200),
    "dark":  (( 28,  28,  30), 0.78, 200),
}

# ─── 阈值（--sensitivity 标定，见文件末尾）───────────────────────────────
# τ=20：**不是建议里的 5。** 5 在这个尺度上会把**设计真值自己**判失败（真值 8.7/10.4）。
#       深色 D3 单变量集上，五种背景/sat 模型下的零错分区间交集 = [10.9, 32.1)。
#       取近中点的 20：比最差的合法渲染（含真值）高 ≥9 ΔE，比真 bug（arm4=34.5）低 ≥12。
DE_THRESHOLD_DEFAULT = 20.0
N5_GATE              = 0.89   # 构图不是 TodayA → 采样窗不落在 hero 卡上 → INVALID


# ═══════════════════════════════════════════════════════════════════════
# 色彩：sRGB → CIELab → CIEDE2000（浮点，不走 uint8 量化）
# ═══════════════════════════════════════════════════════════════════════
_M = np.array([[0.4124564, 0.3575761, 0.1804375],
               [0.2126729, 0.7151522, 0.0721750],
               [0.0193339, 0.1191920, 0.9503041]])
_WP = np.array([0.95047, 1.00000, 1.08883])


def srgb_to_lab(rgb):
    """rgb: (...,3) in 0..255 → Lab (L 0..100)."""
    c = np.asarray(rgb, np.float64) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    xyz = lin @ _M.T / _WP
    d = 6.0 / 29.0
    f = np.where(xyz > d ** 3, np.cbrt(xyz), xyz / (3 * d * d) + 4.0 / 29.0)
    fx, fy, fz = f[..., 0], f[..., 1], f[..., 2]
    return np.stack([116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)], axis=-1)


def de00(lab1, lab2):
    """CIEDE2000。lab1/lab2 broadcastable (...,3)。"""
    L1, a1, b1 = np.moveaxis(np.asarray(lab1, np.float64), -1, 0)
    L2, a2, b2 = np.moveaxis(np.asarray(lab2, np.float64), -1, 0)
    C1, C2 = np.hypot(a1, b1), np.hypot(a2, b2)
    Cb = (C1 + C2) / 2
    G = 0.5 * (1 - np.sqrt(Cb ** 7 / (Cb ** 7 + 25.0 ** 7 + 1e-30)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360
    dLp, dCp = L2 - L1, C2p - C1p
    dhp = h2p - h1p
    dhp = np.where(dhp > 180, dhp - 360, np.where(dhp < -180, dhp + 360, dhp))
    dHp = 2 * np.sqrt(C1p * C2p) * np.sin(np.radians(dhp) / 2)
    Lb, Cbp = (L1 + L2) / 2, (C1p + C2p) / 2
    hs, hd = h1p + h2p, np.abs(h1p - h2p)
    hbp = np.where(hd > 180, (hs + 360) / 2, hs / 2)
    hbp = np.where(C1p * C2p == 0, hs, hbp)
    T = (1 - 0.17 * np.cos(np.radians(hbp - 30)) + 0.24 * np.cos(np.radians(2 * hbp))
         + 0.32 * np.cos(np.radians(3 * hbp + 6)) - 0.20 * np.cos(np.radians(4 * hbp - 63)))
    Sl = 1 + (0.015 * (Lb - 50) ** 2) / np.sqrt(20 + (Lb - 50) ** 2)
    Sc, Sh = 1 + 0.045 * Cbp, 1 + 0.015 * Cbp * T
    dT = 30 * np.exp(-(((hbp - 275) / 25) ** 2))
    Rc = 2 * np.sqrt(Cbp ** 7 / (Cbp ** 7 + 25.0 ** 7 + 1e-30))
    Rt = -Rc * np.sin(2 * np.radians(dT))
    return np.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2
                   + Rt * (dCp / Sc) * (dHp / Sh))


def saturate(rgb, s):
    """CSS filter saturate() 的线性色矩阵（sRGB 空间，按 CSS Filter Effects 规范）。"""
    m = np.array([[0.213 + 0.787 * s, 0.715 - 0.715 * s, 0.072 - 0.072 * s],
                  [0.213 - 0.213 * s, 0.715 + 0.285 * s, 0.072 - 0.072 * s],
                  [0.213 - 0.213 * s, 0.715 - 0.715 * s, 0.072 + 0.928 * s]])
    return np.clip(np.asarray(rgb, np.float64) @ m.T, 0, 255)


# ═══════════════════════════════════════════════════════════════════════
# 采样
# ═══════════════════════════════════════════════════════════════════════
def load(p):
    im = cv2.imread(str(p), cv2.IMREAD_COLOR)
    if im is None:
        raise SystemExit(f"读不了: {p}")
    if (im.shape[1], im.shape[0]) != (W, H):
        im = cv2.resize(im, (W, H), interpolation=cv2.INTER_AREA)
    return im[..., ::-1].astype(np.float64)      # → RGB float


BACKDROPS = ["interp", "left", "right"]


def sample(im, backdrop="interp"):
    # 卡面用**中位数**（鲁棒：文字/图标是少数派，不该污染表面色估计）
    card_med = np.median(im[CARD_Y, CARD_X].reshape(-1, 3), axis=0)
    wl_med   = np.median(im[CARD_Y, WALL_L_X].reshape(-1, 3), axis=0)
    wr_med   = np.median(im[CARD_Y, WALL_R_X].reshape(-1, 3), axis=0)
    # 卡下方的背景：两条 gutter 在 x 上线性内插到卡中心（壁纸是平滑渐变）
    f = ((700 + 1100) / 2 - 22.5) / (1183.5 - 22.5)      # ≈ 0.756
    B = {"interp": wl_med + f * (wr_med - wl_med),
         "left":   wl_med,
         "right":  wr_med}[backdrop]
    return dict(card=card_med, wall_l=wl_med, wall_r=wr_med, B=B)


def expected_surface(mode, B, use_sat=False):
    T, alpha, sat = CONTRACT_TINT[mode]
    bg = saturate(B, sat / 100) if use_sat else np.asarray(B, np.float64)
    return alpha * np.asarray(T, np.float64) + (1 - alpha) * bg


def _lift_pair(im, mode, backdrop, use_sat):
    """
    实测抬升量 与 契约预期抬升量 —— **两者锚在同一个 B 上**。
    （早期版本把实测锚在 WALL_L、预期锚在 B，尺子不同 —— 那会在壁纸横向摆幅大的
      渲染上（arm1c）凭空造出一个「符号反转」。见文件末尾失效边界 #6。）
    """
    s = sample(im, backdrop)
    pred = expected_surface(mode, s["B"], use_sat)
    L_B = float(srgb_to_lab(s["B"])[0])
    L_card = float(srgb_to_lab(s["card"])[0])
    return (L_card - L_B, float(srgb_to_lab(pred)[0]) - L_B, s, pred)


def check(im, mode, backdrop="interp", use_sat=False, tau=DE_THRESHOLD_DEFAULT,
          n5_corr=None):
    lift_act, lift_exp, s, pred = _lift_pair(im, mode, backdrop, use_sat)

    # ── N6-A 抬升量符号 ──────────────────────────────────────────────
    # 只有当**三种背景模型全部**判反转时才叫 CRITICAL。任一模型不同意 → AMBIGUOUS。
    # 「背景到底是什么」是估计出来的，不是量出来的；一个结论要是随这个估计翻转，
    # 它就不是结论。
    signs = [((e > 0) == (a > 0))
             for a, e, _, _ in (_lift_pair(im, mode, bd, use_sat) for bd in BACKDROPS)]
    sign_reversed = not any(signs)      # 三个模型一致认为反转
    sign_unstable = any(signs) and not all(signs)

    # 已发表口径的抬升量（卡内 L* − 同高度**左**壁纸条），用于和 FINDINGS 交叉核对
    L_card_pub = float(srgb_to_lab(im[CARD_Y, CARD_X])[..., 0].mean())
    L_wall_pub = float(srgb_to_lab(im[CARD_Y, WALL_L_X])[..., 0].mean())

    # ── N6-B 表面色 ΔE00 vs 契约 ────────────────────────────────────
    d = float(de00(srgb_to_lab(s["card"]), srgb_to_lab(pred)))

    if n5_corr is not None and n5_corr < N5_GATE:
        v = "INVALID"           # 构图不是参照物那一个 → 采样窗不在 hero 卡上
    elif sign_reversed:
        v = "CRITICAL"          # D3：明暗符号反转（三种背景模型一致）
    elif sign_unstable:
        v = "AMBIGUOUS"         # 背景欠定 —— 该渲染自己的壁纸横向摆幅太大
    elif mode == "light" and d > tau:
        v = "ADVISORY"          # 浅色的契约值自身失效（见失效边界 #4）—— 只报数不下 🔴
    elif d > tau:
        v = "FAIL"
    else:
        v = "PASS"

    return dict(mode=mode, verdict=v,
                card_rgb=[round(x, 1) for x in s["card"]],
                pred_rgb=[round(x, 1) for x in pred],
                dE00_vs_contract=round(d, 1),
                lift_actual=round(lift_act, 1), lift_expected=round(lift_exp, 1),
                lift_published=round(L_card_pub - L_wall_pub, 1),   # 交叉核对用
                L_card=round(L_card_pub, 1), L_wall=round(L_wall_pub, 1),
                sign_reversed=bool(sign_reversed), sign_unstable=bool(sign_unstable),
                n5_corr=n5_corr)


# ═══════════════════════════════════════════════════════════════════════
# 驱动
# ═══════════════════════════════════════════════════════════════════════
def _n5(arm, mode):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import n5_block_layout as n5
    c, _ = n5.block_layout(n5.load(ROOT / "arms" / "shots-strict" / f"{arm}-{mode}.png"),
                           n5.load(ROOT / "design-truth" / "shots" / f"today-A-{mode}.png"))
    return c


def _de_vs_truth(arm, mode):
    """交叉校验用：卡内 ΔE00 vs 真值截图（= FINDINGS 里 26.0/4.0/5.9 那一列）。"""
    a = load(ROOT / "arms" / "shots-strict" / f"{arm}-{mode}.png")[CARD_Y, CARD_X]
    t = load(ROOT / "design-truth" / "shots" / f"today-A-{mode}.png")[CARD_Y, CARD_X]
    return float(de00(srgb_to_lab(a), srgb_to_lab(t)).mean())


def run_matrix(backdrop, use_sat, tau):
    print(f"\nN6 材质表面色断言 — 背景模型={backdrop} saturate={'on' if use_sat else 'off'} τ={tau}")
    print("契约: 浅 rgba(255,255,255,.78) / 深 rgba(28,28,30,.78)  [glass-primitives.jsx:12,14]")
    print(f"\n{'臂':7} {'态':5} {'卡内 RGB':17} {'契约预期 RGB':17} {'ΔE00':>6} "
          f"{'抬升实测':>8} {'抬升预期':>8} {'已发表':>8} {'N5':>5}  判定")
    print("─" * 112)
    rows = []
    for arm in ARMS:
        for m in MODES:
            c5 = _n5(arm, m)
            r = check(load(ROOT / "arms" / "shots-strict" / f"{arm}-{m}.png"),
                      m, backdrop, use_sat, tau, c5)
            r["arm"] = arm
            r["dE00_vs_truth"] = round(_de_vs_truth(arm, m), 1)
            rows.append(r)
            _prow(arm, r, c5)
    # 真值自己也过一遍 —— 检测器不该把设计真值判失败
    for m in MODES:
        r = check(load(ROOT / "design-truth" / "shots" / f"today-A-{m}.png"), m,
                  backdrop, use_sat, tau, 1.0)
        _prow("真值A", r, 1.0, tail="  ← 自检")
    return rows


MARK = {"PASS": "✅ PASS", "FAIL": "🔴 FAIL", "CRITICAL": "🔴 CRITICAL 符号反转",
        "AMBIGUOUS": "⚠️ AMBIGUOUS 背景欠定", "INVALID": "⚪ INVALID 构图不符",
        "ADVISORY": "⚠️ ADVISORY 契约浅色值失效"}


def _prow(name, r, c5, tail=""):
    fmt = lambda v: str(tuple(int(round(x)) for x in v))
    print(f"{name:7} {r['mode']:5} {fmt(r['card_rgb']):17} {fmt(r['pred_rgb']):17} "
          f"{r['dE00_vs_contract']:6.1f} {r['lift_actual']:+8.1f} {r['lift_expected']:+8.1f} "
          f"{r['lift_published']:+8.1f} {c5:5.2f}  {MARK[r['verdict']]}{tail}")


#: D3 单变量实验集（其余代码完全相同，只改玻璃 tint）。arm1c 不在这个集里 ——
#: 它的暗色壁纸自己就是坏的（L*壁=7.4，真值 38.3），卡面判定被壁纸缺陷混淆。
D3_NEG = [("arm4", "dark")]                                   # 真 bug：不贴 tint
D3_POS = [("arm4t", "dark"), ("arm4u", "dark"), ("arm2", "dark"),
          ("arm3", "dark"), ("真值A", "dark")]                 # 可接受
CONFOUNDED = [("arm1c", "dark")]
MODELS = [("interp", False), ("left", False), ("right", False),
          ("interp", True), ("left", True)]


def _img(a, m):
    return (load(ROOT / "design-truth" / "shots" / f"today-A-{m}.png") if a == "真值A"
            else load(ROOT / "arms" / "shots-strict" / f"{a}-{m}.png"))


def run_sensitivity():
    subjects = [(a, m) for a in ["arm1c", "arm2", "arm3", "arm4", "arm4t", "arm4u"] for m in MODES] \
               + [("真值A", "light"), ("真值A", "dark")]
    imgs = {k: _img(*k) for k in subjects}

    print("\n【N6-A 抬升量符号 — 主判据，无阈值】实测/预期，三种背景模型")
    print(f"{'':14} {'interp':>16} {'left':>16} {'right':>16}   一致性")
    for k in subjects:
        a, m = k
        out, ok = [], []
        for bd in BACKDROPS:
            la, le, _, _ = _lift_pair(imgs[k], m, bd, False)
            s = (le > 0) == (la > 0)
            ok.append(s)
            out.append(f"{la:+.1f}/{le:+.1f}" + ("✅" if s else "❌"))
        cons = ("🔴 一致反转" if not any(ok) else
                "⚠️ 随模型翻转" if not all(ok) else "✅ 一致正确")
        print(f"{a+'-'+m:14} " + " ".join(f"{o:>16}" for o in out) + f"   {cons}")
    print("  → 只有 arm4-dark 三个模型**一致**判反转 = D3 真 bug，且不依赖任何阈值。")
    print("  → arm1c-dark 随背景模型翻转 → AMBIGUOUS，不下 🔴。它自己的暗色壁纸横向")
    print("     摆幅太大（L* 左 7.4 / 右 35），「卡下方的背景」欠定。坏的是壁纸不是卡面。")

    print("\n【N6-B ΔE00 vs 契约 — 背景模型 × saturate 敏感性】")
    print(f"{'':14} {'interp':>8} {'left':>8} {'right':>8} {'itp+sat':>8} {'left+sat':>9} | {'vs真值':>7}")
    for k in subjects:
        a, m = k
        vals = [check(imgs[k], m, bd, st, 999, 1.0)["dE00_vs_contract"] for bd, st in MODELS]
        vt = "—" if a == "真值A" else f"{_de_vs_truth(a, m):.1f}"
        print(f"{a+'-'+m:14} " + " ".join(f"{v:8.1f}" for v in vals) + f" | {vt:>7}")

    print("\n【N6-B 阈值标定 — 深色 D3 单变量集】")
    print(f"  NEG(真 bug) = {[f'{a}-{m}' for a,m in D3_NEG]}")
    print(f"  POS(可接受) = {[f'{a}-{m}' for a,m in D3_POS]}   （含设计真值自己）")
    print(f"\n  {'背景模型':14} {'POS 最高':>9} {'NEG 最低':>9}  零错分 τ 区间")
    los, his = [], []
    for bd, st in MODELS:
        p = max(check(imgs[k], k[1], bd, st, 999, 1.0)["dE00_vs_contract"] for k in D3_POS)
        n = min(check(imgs[k], k[1], bd, st, 999, 1.0)["dE00_vs_contract"] for k in D3_NEG)
        los.append(p); his.append(n)
        tag = f"{bd}{'+sat' if st else ''}"
        print(f"  {tag:14} {p:9.1f} {n:9.1f}  [{p:.1f}, {n:.1f})")
    print(f"\n  五种模型的**交集** = [{max(los):.1f}, {min(his):.1f})  → τ={DE_THRESHOLD_DEFAULT:.0f} 落在其中")
    print(f"  建议的 τ=5 不可用：设计真值自己的 ΔE00 vs 契约 = "
          f"{check(imgs[('真值A','dark')],'dark','interp',False,999,1.0)['dE00_vs_contract']:.1f}"
          f"（深）/ {check(imgs[('真值A','light')],'light','interp',False,999,1.0)['dE00_vs_contract']:.1f}（浅）"
          f" —— τ=5 会把设计真值本身判失败。")

    print("\n【⚠️ 浅色：契约值自身失效 —— N6-B 在浅色下判定是**反的**】")
    for a in ["arm4t", "arm4u"]:
        r = check(imgs[(a, "light")], "light", "interp", False, 999, 1.0)
        print(f"  {a}-light  ΔE00 vs 契约 = {r['dE00_vs_contract']:5.1f}   抬升实测 "
              f"{r['lift_published']:+.1f}（真值 +4.8）")
    print("  arm4t 贴了契约的浅色白 .78 → 契约 ΔE00 只有 3.7（「合规」），但抬升 +9.3，超调真值一倍。")
    print("  arm4u 没贴 → 契约 ΔE00 15.2（「违规」），但抬升 +4.6 ≈ 真值 +4.8。")
    print("  → 断言浅色契约值 = **奖励错的那一臂、惩罚对的那一臂**。所以浅色只报 ADVISORY。")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--render"); ap.add_argument("--mode", choices=MODES)
    ap.add_argument("--backdrop", choices=["interp", "left", "right"], default="interp")
    ap.add_argument("--sat", action="store_true", help="预期值里算上 CSS saturate(200%%)（默认关）")
    ap.add_argument("--tau", type=float, default=DE_THRESHOLD_DEFAULT)
    ap.add_argument("--matrix", action="store_true")
    ap.add_argument("--sensitivity", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.matrix:
        rows = run_matrix(a.backdrop, a.sat, a.tau)
        if a.json:
            print(json.dumps(rows, ensure_ascii=False, indent=1))
    elif a.sensitivity:
        run_sensitivity()
    elif a.render and a.mode:
        r = check(load(a.render), a.mode, a.backdrop, a.sat, a.tau)
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        ap.error("给 --render --mode，或 --matrix / --sensitivity")

# ═══════════════════════════════════════════════════════════════════════
# 失效边界（前置条件不满足时，这个检测器不成立）
# ═══════════════════════════════════════════════════════════════════════
# 1. **契约里必须有目标值。** 本例能跑，是因为 glass-primitives.jsx:12/14 明写了
#    thick/dark-thick 的 rgba。契约缺陷 #4「暗色 ink/卡面阶梯在整个契约里不存在」——
#    真要是连 dark tint 都没有，N6 无值可断，只剩 N6-A 的符号判据（它只需要
#    「深色卡该比壁纸暗」这一条设计意图，比数值弱、但也比数值更难写漏）。
#
# 2. **渲染必须带真实背景合成。** `.glassEffect` 是**背景采样材质** —— 它要有东西可采。
#    孤立 `#Preview` / `ImageRenderer` 上量不出 arm4 的 L*=53.6，因为那里根本没有壁纸
#    可折射。必须是真机 / 模拟器上跑起来的整屏截图。
#    （FINDINGS「装置缺陷 #9」记的正是这件事：arm3 的平涂玻璃可能只是 ImageRenderer
#     渲不出 backdrop 采样材质的产物。）
#
# 3. **采样窗预设了构图。** CARD=y[850:1150],x[700:1100] 是按 TodayA 的 hero 卡标的。
#    构图一换，这个窗就不落在卡上 —— arm1/arm1b 的窗落在别的东西上（arm1b-dark 的
#    「壁纸」边条实测 RGB(167,149,91)，根本不是壁纸）。
#    → **所以 N6 必须 gate 在 N5 上**：N5 < 0.89 → INVALID，不是 PASS/FAIL。
#    两个检测器是串联的，不是并联的。生产环境里正确的做法是从 XCUITest 的元素 frame
#    取采样窗，而不是硬编码像素坐标。
#
# 4. **判别力几乎全在深色。** 浅色下所有臂的抬升量符号都对（tint 是白的，怎么贴都变亮），
#    ΔE00 又被契约自己的缺陷污染（浅色的白 .78 是浏览器补偿产物，见 FINDINGS 结论 7）——
#    原生玻璃本来就有 +4.6 抬升，再贴 .78 白会超调到 +9.3。**浅色这一列，契约本身是错的，
#    断言它 = 奖励一个 bug。** N6 在浅色下只应报数，不应下 🔴。
#
# 5. **「卡下方的背景」是估计出来的，不是量出来的。** 卡片占满 gutter 之间的整宽，
#    同高度只有左右两条 45px 壁纸可采，卡正下方的壁纸只能内插。壁纸横向摆幅小时
#    （真值、arm2/3/4*）三种模型给同一个结论；摆幅大时（arm1c 暗色：L* 左 7.4 / 右 35）
#    结论会随模型翻转 → 判 AMBIGUOUS，不判 🔴。
#
# 6. **早期版本在这里有一个真 bug，值得记下来：** 实测抬升量锚在 WALL_L、预期抬升量
#    锚在内插背景 B —— 两把尺子。它在 arm1c-dark 上凭空造出一个「符号反转」
#    （实测 +23.7 vs 预期 −14.6 → CRITICAL）。而裁图一看，arm1c 的卡是**暗**的，
#    坏的是它自己的壁纸（近黑）。现在两者都锚在同一个 B 上，arm1c 落到 AMBIGUOUS。
#    → 教训：任何「实测 vs 预期」的判据，两边必须用同一个参照物。
#
# ═══════════════════════════════════════════════════════════════════════
# τ 的标定（--sensitivity 全表）
# ═══════════════════════════════════════════════════════════════════════
# 建议的 τ=5 是拿「ΔE00 vs **真值截图**」那一列（arm4=26.0 / arm4t=arm4u=4.0 /
# arm2=5.9）定的。但本检测器断言的是**契约值**，不是真值截图 —— 两列尺度不同：
#
#   ΔE00 vs 契约（深色, 背景=interp, sat=off）:
#       arm4 = 34.5 ❌ │ arm4t = 6.5  arm4u = 6.5  arm2 = 5.0  arm3 = 9.0  真值A = 10.4
#
#   → **τ=5 会连设计真值本身（10.4）一起判失败。** τ=5 在这个尺度上不可用。
#   → 五种背景/sat 模型下的零错分区间**交集** = [10.9, 32.1)。取 τ=20（近中点）：
#       比最差的合法渲染（含真值 10.4）高 ≥9 ΔE，比真 bug（34.5）低 ≥12 ΔE。
#
# 真值自己有 10.4 的残差，是因为**原生玻璃 ≠ CSS backdrop-filter**：真值是浏览器渲的，
# 带 blur(50)+saturate(200%)，而契约预期值按 DESIGN.md:42 的指令**不含**这两者。
# 这个残差是**契约自己的浏览器/原生鸿沟**，不是检测器的误差 —— 它必须留在阈值下方，
# 而不是被 saturate 调参「修掉」（--sat 打开后真值残差降到 6.7，但 arm4 仍是 32.1，
# 结论不变。所以这个旋钮怎么拧都不影响判定 —— 这正是它可以不拧的理由）。
