#!/usr/bin/env python3
"""
N4 — CONTRACT LINT.  Four mechanical predicates over a design-handoff contract.
Zero model judgment: pure parse + set algebra. Every finding carries file:line.

    usage: n4_contract_lint.py <contract-dir> [--quiet]

Contract dir is expected to hold (discovered by extension, names not hardcoded
except the two mirror files, which are named in the contract itself):
    *.md      prose/spec docs           (DESIGN.md, FLOW.md)
    *.css     token store (source of truth)
    *.swift   native token mirror

PREDICATES
    N4a  dangling anchor   cross-file ref "<X>.md <anchor>" must resolve to a real
                           heading in <X>.md.
    N4b  ghost symbol      a type/member named in prose or comments must exist in
                           the Swift mirror's symbol table.
    N4c  mirror diff       two sources that call themselves mirrors must have equal
                           token sets (bidirectional diff) and equal values where
                           both sides parse.
    N4d  ladder complete   a semantic color ladder must have values on BOTH sides
                           (light + dark).

SEVERITY
    RED   a mechanical violation. Gates the exit code.
    WARN  cannot be auto-decided (honest bucket — needs a human). Never gates.
    INFO  evidence / accounting.
"""

import os
import re
import sys
from collections import defaultdict

# --- Honest, declared configuration. Everything the lint "knows" is here. ------

# N4b: members of stdlib types that the mirror EXTENDS (it owns only its own
# additions, so a reference to a stdlib member must not be called a ghost).
PLATFORM_MEMBERS = {
    "Color": {"clear", "white", "black", "primary", "secondary", "accentColor",
              "red", "green", "blue", "orange", "pink", "gray", "mint", "indigo"},
    "View":  set(),
}

# N4c: naming-normalization aliases. CSS kebab -> Swift identifier, where the
# convention (camelCase) does NOT produce the real name. Kept tiny ON PURPOSE:
# anything not covered by a rule below is reported as "cannot auto-pair".
CSS_TO_SWIFT_ALIAS = {"on-wp": "onWallpaper"}

# N4d: the semantic ladders that owe a light AND a dark value.
LADDERS = {
    "ink":            {"css": r"^--ink-", "swift": r"^ink"},
    "surface":        {"css": r"^--surface-", "swift": r"^surface"},
    "glass-tint":     {"css": r"^--glass-tint-", "swift": r"^glassTint"},
    "wallpaper-base": {"css": r"^--wp-\w+-base", "swift": r"^wallpaperBase"},
}

FILE_EXT_RE = re.compile(r"\.(md|css|swift|jsx|js|html|json|ts|tsx)$", re.I)
HEX_RE = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
SWIFT_HEX_RE = re.compile(r"0x([0-9a-fA-F]{6})")
NUM_RE = re.compile(r"^-?\d*\.?\d+(px|pt|em|rem|%|ms|s)?$")


class Findings:
    def __init__(self):
        self.items = []

    def add(self, pred, sev, msg, ev=""):
        self.items.append((pred, sev, msg, ev))

    def by(self, pred, sev=None):
        return [i for i in self.items
                if i[0] == pred and (sev is None or i[1] == sev)]

    @property
    def reds(self):
        return [i for i in self.items if i[1] == "RED"]


# ------------------------------------------------------------------ utilities

def camel(kebab):
    parts = [p for p in kebab.split("-") if p]
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


def kebab(camel_name):
    return re.sub(r"(?<!^)(?=[A-Z])", "-", camel_name).lower()


def norm_hex(s):
    m = HEX_RE.search(s) if s.startswith("#") else None
    if not m:
        return None
    h = m.group(1).lower()
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return h


def norm_num(s):
    s = s.strip()
    if not NUM_RE.match(s):
        return None
    return float(re.sub(r"(px|pt|em|rem|%|ms|s)$", "", s))


# ------------------------------------------------------------- markdown parse

def md_headings(path, text):
    """Real headings only: skips YAML front matter and fenced code blocks.
    (Reference EXTRACTION does not skip them — refs live inside FLOW's yaml
    fence. Only the target-heading side skips.)"""
    out = []
    lines = text.split("\n")
    i = 0
    if lines and lines[0].strip() == "---":          # YAML front matter
        i = 1
        while i < len(lines) and lines[i].strip() != "---":
            i += 1
        i += 1
    fenced = False
    while i < len(lines):
        line = lines[i]
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced:
            m = re.match(r"^(#{1,6})\s+(.*\S)\s*$", line)
            if m:
                out.append((len(m.group(1)), m.group(2), i + 1))
        i += 1
    return out


def heading_anchors(headings):
    """Anchor tokens a heading can be addressed by."""
    anchors = {}
    for _lvl, text, line in headings:
        keys = set()
        t = text.strip()
        keys.add(t.lower())
        m = re.match(r"^(\d+[a-z]?)[.)]?\s+(.*)$", t)   # "4c State & tweak..."
        if m:
            keys.add(m.group(1).lower())
            keys.add(m.group(2).strip().lower())
        for k in keys:
            anchors.setdefault(k, line)
    return anchors


def resolve_anchor(anchor, anchors):
    a = anchor.strip().lower()
    if a in anchors:
        return anchors[a]
    for key, line in anchors.items():          # prefix match for quoted titles
        if key.startswith(a) and len(a) >= 4:
            return line
    return None


# ----------------------------------------------------------------- swift parse

class SwiftSymbols:
    def __init__(self):
        self.types = {}          # name -> {kind, line, members{}}
        self.declared = set()    # enum/struct/class
        self.extended = set()    # extension targets

    def member(self, t, m):
        return self.types.get(t, {}).get("members", {}).get(m)

    def all_member_names(self):
        s = set()
        for t in self.types.values():
            s |= set(t["members"].keys())
        return s

    def find_member(self, name):
        for tn, t in self.types.items():
            if name in t["members"]:
                return tn, t["members"][name]
        return None, None


def parse_swift(text):
    sym = SwiftSymbols()
    lines = text.split("\n")
    depth = 0
    cur = None
    for idx, raw in enumerate(lines):
        n = idx + 1
        code = raw.split("//", 1)[0]
        trailing = raw[len(code):].lstrip("/ ").strip() if "//" in raw else ""
        s = code.strip()

        if depth == 0:
            m = re.match(r"(?:public\s+|internal\s+)?(enum|struct|class|actor)\s+(\w+)", s)
            if m:
                cur = m.group(2)
                sym.declared.add(cur)
                sym.types.setdefault(cur, {"kind": m.group(1), "line": n, "members": {}})
            else:
                m = re.match(r"extension\s+(\w+)", s)
                if m:
                    cur = m.group(1)
                    sym.extended.add(cur)
                    sym.types.setdefault(cur, {"kind": "extension", "line": n, "members": {}})
        elif cur:
            mem = None
            m = re.match(r"^case\s+([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)\s*$", s)
            if m:                                             # enum case decl
                for name in [x.strip() for x in m.group(1).split(",")]:
                    sym.types[cur]["members"][name] = {
                        "kind": "case", "type": None, "line": n,
                        "value": None, "comment": trailing, "cases": {}}
            else:
                m = re.match(
                    r"^(?:@\w+\s+)?(static\s+)?(let|var|func|init)\s*([A-Za-z_]\w*)?", s)
                if m and m.group(3):
                    name = m.group(3)
                    kind = m.group(2)
                    ann = re.match(r"^[^:=]*?:\s*([\[\]\w\.]+)", s.split("=")[0]) \
                        if kind in ("let", "var") else None
                    value = s.split("=", 1)[1].strip() if "=" in s and kind in ("let", "var") else None
                    mem = {"kind": kind, "type": ann.group(1) if ann else None,
                           "line": n, "value": value, "comment": trailing, "cases": {}}
                    sym.types[cur]["members"][name] = mem
                    if kind == "var" and s.rstrip().endswith("{"):
                        mem["cases"] = _switch_cases(lines, idx)
                elif re.match(r"^init\s*\(", s):
                    sym.types[cur]["members"]["init"] = {
                        "kind": "init", "type": None, "line": n,
                        "value": None, "comment": trailing, "cases": {}}

        depth += code.count("{") - code.count("}")
        if depth <= 0:
            depth = 0
            cur = None
    return sym


def _switch_cases(lines, start):
    """case .state: <expr>  inside a computed var body."""
    out = {}
    depth = 0
    for i in range(start, len(lines)):
        code = lines[i].split("//", 1)[0]
        depth += code.count("{") - code.count("}")
        m = re.match(r"^\s*case\s+\.(\w+)\s*:\s*(.+?)\s*$", code)
        if m:
            out[m.group(1)] = (m.group(2), i + 1)
        if i > start and depth <= 0:
            break
    return out


# ------------------------------------------------------------------- css parse

def parse_css(text):
    """Declarations with their selector context. Handles multi-decl lines and
    @media blocks. Block comments are blanked out (line structure preserved)."""
    clean = []
    i, n, inc = 0, len(text), False
    while i < n:
        if not inc and text.startswith("/*", i):
            inc, i = True, i + 2
            clean.append("  ")
            continue
        if inc and text.startswith("*/", i):
            inc, i = False, i + 2
            clean.append("  ")
            continue
        ch = text[i]
        clean.append(ch if (not inc or ch == "\n") else " ")
        i += 1
    src = "".join(clean)

    decls, stack, buf, line, buf_line = [], [], "", 1, 1
    for ch in src:
        if ch == "\n":
            line += 1
        if ch == "{":
            stack.append(buf.strip())
            buf, buf_line = "", line
        elif ch == "}":
            if stack:
                stack.pop()
            buf, buf_line = "", line
        elif ch == ";":
            d = buf.strip()
            m = re.match(r"^(--[\w-]+)\s*:\s*(.+)$", d, re.S)
            if m:
                decls.append({"name": m.group(1),
                              "value": re.sub(r"\s+", " ", m.group(2)).strip(),
                              "line": buf_line, "ctx": list(stack)})
            buf, buf_line = "", line
        else:
            if not buf.strip():
                buf_line = line
            buf += ch
    return decls


def is_dark_ctx(ctx):
    return any(re.search(r"prefers-color-scheme\s*:\s*dark|\[data-theme\s*=\s*[\"']?dark|\.dark\b", c)
               for c in ctx)


def is_root(ctx):
    return any(c.strip() == ":root" for c in ctx)


# ================================ PREDICATES ==================================

def n4a(files, F):
    md = {os.path.basename(p): t for p, t in files.items() if p.endswith(".md")}
    anchors = {name: heading_anchors(md_headings(name, t)) for name, t in md.items()}
    for name, t in md.items():
        h = md_headings(name, t)
        numbered = [x for x in h if re.match(r"^\d+[a-z]?[.)]?\s", x[1])]
        F.add("N4a", "INFO",
              f"{name}: {len(h)} real headings, {len(numbered)} numbered "
              f"(front matter + fenced blocks excluded)", name)

    num_re = re.compile(
        r"([A-Za-z0-9_.-]+\.md)\s*[（(]?\s*(?:§|#)?\s*(\d+[a-z]?(?:\s*/\s*\d+[a-z]?)*)")
    title_re = re.compile(r"([A-Za-z0-9_.-]+\.md)\s*[“\"']([^”\"'\n]{4,60})[”\"']")

    refs = []
    for path, text in files.items():                # NO fence/front-matter skip:
        base = os.path.basename(path)               # refs live inside the yaml fence
        for i, line in enumerate(text.split("\n"), 1):
            for m in num_re.finditer(line):
                for a in re.split(r"\s*/\s*", m.group(2)):
                    refs.append((base, i, m.group(1), a, "numeric"))
            for m in title_re.finditer(line):
                refs.append((base, i, m.group(1), m.group(2), "title"))

    if not refs:
        F.add("N4a", "INFO", "no anchored cross-file references found", "-")
    for base, ln, target, anchor, kind in refs:
        ev = f"{base}:{ln}"
        if target not in anchors:
            F.add("N4a", "RED",
                  f'ref "{target} {anchor}" → target file not in the contract', ev)
            continue
        hit = resolve_anchor(anchor, anchors[target])
        if hit:
            F.add("N4a", "INFO",
                  f'ref "{target} {anchor}" → resolves ({target}:{hit})', ev)
        else:
            F.add("N4a", "RED",
                  f'DANGLING ANCHOR: "{target} {anchor}" — {target} has no such '
                  f'heading ({kind} ref)', ev)

    # accounting: every statesRef field, classified (so "N refs" reconciles)
    for path, text in files.items():
        base = os.path.basename(path)
        for i, line in enumerate(text.split("\n"), 1):
            m = re.search(r'statesRef:\s*"([^"]*)"', line)
            if m:
                v = m.group(1)
                tgt = re.search(r"([A-Za-z0-9_.-]+\.md)", v)
                anch = num_re.search(v)
                kind = ("anchored cross-file ref" if anch else
                        "bare file ref (no anchor)" if tgt else "inline states (no file ref)")
                F.add("N4a", "INFO", f'statesRef "{v[:46]}…" → {kind}', f"{base}:{i}")


def n4b(files, F, sym, mirror_name):
    prefix_count = defaultdict(list)
    for t in sym.declared:
        if re.match(r"^[A-Z][A-Z][a-z]", t):
            prefix_count[t[0]].append(t)
    ns = [p for p, ts in prefix_count.items() if len(ts) >= 2]
    ns_re = None
    if ns:
        p = ns[0]
        ns_re = re.compile(rf"^{p}[A-Z][a-z]\w*$")
        F.add("N4b", "INFO",
              f'local type namespace derived from the mirror: "{p}*" '
              f'({", ".join(sorted(prefix_count[p]))}) — a `{p}Xxx` reference must '
              f"be declared there", mirror_name)

    ticks = []
    for path, text in files.items():
        base = os.path.basename(path)
        for i, line in enumerate(text.split("\n"), 1):
            for m in re.finditer(r"`([^`\n]+)`", line):
                ticks.append((base, i, m.group(1).strip(), line))

    checked, oos = 0, 0
    for base, ln, tok, line in ticks:
        ev = f"{base}:{ln}"
        if FILE_EXT_RE.search(tok) or not re.match(r"^[A-Za-z_][\w]*(\.[\w*]+)?$", tok):
            oos += 1
            continue

        hit = False
        # b1 — local namespace type
        if ns_re and ns_re.match(tok):
            checked, hit = checked + 1, True
            if tok in sym.declared:
                F.add("N4b", "INFO", f"`{tok}` → declared ({mirror_name}:"
                      f"{sym.types[tok]['line']})", ev)
            else:
                F.add("N4b", "RED",
                      f"GHOST SYMBOL: `{tok}` is named as a mirror type but is not "
                      f"declared in {mirror_name}. Declared: "
                      f"{', '.join(sorted(sym.declared))}", ev)
        # b2 — Type.member on a type the mirror declares or extends
        m = re.match(r"^([A-Z]\w*)\.([\w*]+)$", tok)
        if m and not hit:
            tn, mn = m.group(1), m.group(2)
            if tn in sym.types:
                checked, hit = checked + 1, True
                if mn == "*":
                    F.add("N4b", "INFO", f"`{tok}` → wildcard, type exists", ev)
                elif sym.member(tn, mn) or mn in PLATFORM_MEMBERS.get(tn, set()):
                    where = ("mirror" if sym.member(tn, mn) else "platform allowlist")
                    F.add("N4b", "INFO", f"`{tok}` → resolves ({where})", ev)
                else:
                    kind = ("declares" if tn in sym.declared else "extends")
                    F.add("N4b", "RED",
                          f"GHOST SYMBOL: `{tok}` — {mirror_name} {kind} `{tn}` but "
                          f"has no member `{mn}`", ev)
        # b3 — any backticked symbol on a line that names the mirror file
        if not hit and mirror_name in line:
            checked = checked + 1
            base_t = tok.split(".")[0]
            mem_t = tok.split(".")[1] if "." in tok else None
            ok = (base_t in sym.types and (mem_t in (None, "*")
                  or sym.member(base_t, mem_t)
                  or mem_t in PLATFORM_MEMBERS.get(base_t, set()))) \
                or (mem_t is None and base_t in sym.all_member_names())
            if ok:
                F.add("N4b", "INFO", f"`{tok}` (line names {mirror_name}) → resolves", ev)
            else:
                F.add("N4b", "RED",
                      f"GHOST SYMBOL: `{tok}` is named as a {mirror_name} symbol but "
                      f"does not exist there", ev)
        elif not hit:
            oos += 1

    F.add("N4b", "INFO",
          f"{checked} backticked symbol refs in scope; {oos} out of scope "
          f"(platform/web/file refs — not claims about the mirror, not checked)", "-")


def n4c(F, sym, css, css_name, mirror_name):
    states = [c for c in sym.types.get("Readiness", {}).get("members", {})
              if sym.types["Readiness"]["members"][c]["kind"] == "case"]
    F.add("N4c", "INFO",
          f"normalization rules: --r-<state>-<prop> → Readiness.<camel(prop)> "
          f"[alias {CSS_TO_SWIFT_ALIAS}] · --wp-<state>-b<N> → Readiness.wallpaperBlobs[N] · "
          f"--wp-<state>-base[-dark] → Readiness.wallpaperBase[Dark] · "
          f"--<kebab> → <camel> (any namespace). States: {states}", "-")

    root = [d for d in css if is_root(d["ctx"]) and not is_dark_ctx(d["ctx"])]
    other = [d for d in css if not is_root(d["ctx"])]
    for d in other:
        F.add("N4c", "INFO", f'{d["name"]} declared under {d["ctx"]} — runtime state '
              f"binding, not a token decl (excluded)", f'{css_name}:{d["line"]}')

    consumed, unpaired_css = set(), []
    for d in root:
        name, val, ev = d["name"], d["value"], f'{css_name}:{d["line"]}'
        if val.startswith("var("):
            F.add("N4c", "INFO", f"{name} = {val} → alias/indirection, not a value "
                  "(excluded from the diff)", ev)
            continue
        if not re.match(r"^(#[0-9a-fA-F]{3,8}|rgba?\(|-?\d|linear-gradient|radial-gradient)", val):
            F.add("N4c", "WARN", f"{name} = {val} → not a value token (quoted string / "
                  "CSS keyword). CANNOT AUTO-PAIR — needs a human", ev)
            continue

        swift_path, swift_val, sline = None, None, None
        m = re.match(rf"^--r-({'|'.join(states)})-(.+)$", name) if states else None
        mw = re.match(rf"^--wp-({'|'.join(states)})-(b[123]|base-dark|base)$", name) if states else None
        if m:
            st, prop = m.group(1), m.group(2)
            mem = CSS_TO_SWIFT_ALIAS.get(prop, camel(prop))
            swift_path = f"Readiness.{mem}"
            info = sym.member("Readiness", mem)
            if info and st in info["cases"]:
                swift_val, sline = info["cases"][st]
            consumed.add(("Readiness", mem))
        elif mw:
            st, what = mw.group(1), mw.group(2)
            is_blob = bool(re.match(r"^b[123]$", what))
            mem = ("wallpaperBlobs" if is_blob
                   else "wallpaperBaseDark" if what == "base-dark" else "wallpaperBase")
            swift_path = f"Readiness.{mem}"
            info = sym.member("Readiness", mem)
            if info and st in info["cases"]:
                expr, sline = info["cases"][st]
                hexes = SWIFT_HEX_RE.findall(expr)
                if is_blob:
                    i = int(what[1]) - 1
                    swift_val = f"0x{hexes[i]}" if i < len(hexes) else None
                    swift_path += f"[{i}]"
                else:
                    swift_val = " ".join(f"0x{h}" for h in hexes)
            consumed.add(("Readiness", mem))
        else:
            ident = camel(name[2:])
            tn, info = sym.find_member(ident)
            if info:
                swift_path = f"{tn}.{ident}"
                swift_val, sline = info["value"], info["line"]
                consumed.add((tn, ident))

        exists = swift_path and sym.member(swift_path.split(".")[0],
                                           swift_path.split(".")[1].split("[")[0])
        if not exists:
            unpaired_css.append(name)
            target = swift_path or f"<{camel(name[2:])}>"
            F.add("N4c", "RED",
                  f"ONLY-IN-CSS: {name} = {val} — the mirror has no {target}. "
                  f"{mirror_name} claims to mirror {css_name} and to author nothing.", ev)
            continue

        # value compare — only where BOTH sides parse. Never guess.
        if swift_val is None:
            F.add("N4c", "INFO", f"{name} ↔ {swift_path} → paired (per-state value not "
                  "parsed)", ev)
            continue
        cv = [norm_hex(x) for x in re.findall(r"#[0-9a-fA-F]{3,8}", val)] or [norm_hex(val)]
        sv = [h.lower() for h in SWIFT_HEX_RE.findall(swift_val)]
        cv = [x for x in cv if x]
        if cv and sv:
            if cv == sv:
                F.add("N4c", "INFO", f"{name} ↔ {swift_path} → paired, values equal "
                      f"(#{'/#'.join(cv)})", ev)
            else:
                F.add("N4c", "RED", f"VALUE DRIFT: {name} = #{'/#'.join(cv)} but "
                      f"{swift_path} = #{'/#'.join(sv)} ({mirror_name}:{sline})", ev)
            continue
        cn, sn = norm_num(val), norm_num((swift_val or "").rstrip(";"))
        if cn is not None and sn is not None:
            if abs(cn - sn) < 1e-9:
                F.add("N4c", "INFO", f"{name} ↔ {swift_path} → paired, values equal ({cn})", ev)
            else:
                F.add("N4c", "RED", f"VALUE DRIFT: {name} = {val} but {swift_path} = "
                      f"{swift_val} ({mirror_name}:{sline})", ev)
            continue
        F.add("N4c", "INFO", f"{name} ↔ {swift_path} → paired; values not comparable "
              f"({val} vs {swift_val}) — set-diff only", ev)

    # ---- swift -> css
    css_names = {d["name"] for d in css}
    for tn, t in sym.types.items():
        if tn in PLATFORM_MEMBERS:                       # extension on a stdlib type
            continue
        for mn, info in t["members"].items():
            if info["kind"] in ("func", "init", "case"):
                continue
            if info["type"] in ("String", "LinearGradient"):
                continue                                  # content / composed, not a token
            if (tn, mn) in consumed:
                continue
            ev = f'{mirror_name}:{info["line"]}'
            if f"--{kebab(mn)}" in css_names:
                F.add("N4c", "INFO", f"{tn}.{mn} ↔ --{kebab(mn)} → paired", ev)
                continue
            hint = re.search(r"(--[a-z][\w-]*)|(\b[a-z]+(?:-[a-z0-9]+)+\b)",
                             info["comment"] or "")
            if hint:
                tok = hint.group(0)
                F.add("N4c", "WARN",
                      f'ONLY-IN-SWIFT: {tn}.{mn} — no --{kebab(mn)} in {css_name}, but its '
                      f'comment cites "{tok}", which is not in {css_name} either. The BASE '
                      f"token store (lib/liquid-glass.css) is NOT part of this contract, so "
                      f"this cannot be auto-decided. CANNOT AUTO-PAIR — needs a human", ev)
            else:
                F.add("N4c", "RED",
                      f"ONLY-IN-SWIFT: {tn}.{mn} = {info['value']} — no --{kebab(mn)} in "
                      f"{css_name}. The mirror authors a value the token store lacks.", ev)


def n4d(F, sym, css, css_name, mirror_name):
    dark_blocks = {tuple(d["ctx"]) for d in css if is_dark_ctx(d["ctx"])}
    F.add("N4d", "INFO",
          f"{css_name}: {len(dark_blocks)} dark-scheme block(s) "
          f"(@media prefers-color-scheme: dark / [data-theme=dark] / .dark)", css_name)

    value_syms = {}
    for tn, t in sym.types.items():
        if tn in PLATFORM_MEMBERS:
            continue
        for mn, info in t["members"].items():
            if info["kind"] in ("func", "init", "case"):
                continue
            value_syms[mn] = (tn, info)

    for fam, pat in LADDERS.items():
        c_light = [d for d in css if re.match(pat["css"], d["name"])
                   and not d["name"].endswith("-dark") and not is_dark_ctx(d["ctx"])]
        c_dark = [d for d in css if re.match(pat["css"], d["name"])
                  and (d["name"].endswith("-dark") or is_dark_ctx(d["ctx"]))]
        s_light = [(m, i) for m, (tn, i) in value_syms.items()
                   if re.match(pat["swift"], m) and not m.endswith("Dark")]
        s_dark = [(m, i) for m, (tn, i) in value_syms.items()
                  if re.match(pat["swift"], m) and m.endswith("Dark")]

        for store, light, dark, fname in (
                ("css", c_light, c_dark, css_name),
                ("swift", s_light, s_dark, mirror_name)):
            nl, nd = len(light), len(dark)
            if nl == 0 and nd == 0:
                F.add("N4d", "WARN",
                      f'ladder "{fam}" absent from {fname} entirely — the contract\'s '
                      f"sourceOfTruth puts base semantics in lib/liquid-glass.css, which is "
                      f"NOT in this contract. Cannot evaluate. Needs a human", fname)
            elif nl > 0 and nd == 0:
                names = [x["name"] if store == "css" else x[0] for x in light]
                lines = [x["line"] if store == "css" else x[1]["line"] for x in light]
                F.add("N4d", "RED",
                      f'LADDER INCOMPLETE: "{fam}" in {fname} has {nl} LIGHT rung(s) '
                      f'({", ".join(names)}) and 0 DARK. A semantic color step must resolve '
                      f"in both schemes.",
                      ", ".join(f"{fname}:{l}" for l in lines))
            elif nd > 0 and nl == 0:
                F.add("N4d", "RED",
                      f'LADDER INCOMPLETE: "{fam}" in {fname} has {nd} DARK rung(s) and 0 '
                      f"LIGHT.", fname)
            else:
                F.add("N4d", "INFO",
                      f'ladder "{fam}" in {fname}: {nl} light + {nd} dark → complete', fname)


# ===================================== main ===================================

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    root = os.path.abspath(sys.argv[1])
    quiet = "--quiet" in sys.argv

    if not os.path.isdir(root):
        print(f"!! contract dir not found: {root}", file=sys.stderr)
        print("   (exit 2 = the check did not run. This is NOT a pass, and not a finding.)",
              file=sys.stderr)
        sys.exit(2)

    files = {}
    for fn in sorted(os.listdir(root)):
        if fn.endswith((".md", ".css", ".swift")):
            with open(os.path.join(root, fn), encoding="utf-8") as fh:
                files[os.path.join(root, fn)] = fh.read()
    swift_files = [p for p in files if p.endswith(".swift")]
    css_files = [p for p in files if p.endswith(".css")]
    if not swift_files or not css_files:
        print(f"!! need one .swift mirror and one .css token store in {root}")
        sys.exit(2)
    mirror_name = os.path.basename(swift_files[0])
    css_name = os.path.basename(css_files[0])

    sym = parse_swift(files[swift_files[0]])
    css = parse_css(files[css_files[0]])

    F = Findings()
    n4a(files, F)
    n4b(files, F, sym, mirror_name)
    n4c(F, sym, css, css_name, mirror_name)
    n4d(F, sym, css, css_name, mirror_name)

    print("=" * 78)
    print(f"N4 CONTRACT LINT — {root}")
    print(f"  {len(files)} files · mirror={mirror_name} · token store={css_name}")
    print(f"  swift symbols: {len(sym.types)} types, "
          f"{sum(len(t['members']) for t in sym.types.values())} members · "
          f"css: {len(css)} declarations")
    print("=" * 78)

    titles = {
        "N4a": "DANGLING ANCHOR   — cross-file refs must resolve to a real heading",
        "N4b": "GHOST SYMBOL      — named types/members must exist in the mirror",
        "N4c": "MIRROR DIFF       — self-declared mirrors must have equal token sets",
        "N4d": "LADDER COMPLETE   — semantic color ladders need light AND dark",
    }
    total_red = 0
    for pred in ("N4a", "N4b", "N4c", "N4d"):
        reds = F.by(pred, "RED")
        warns = F.by(pred, "WARN")
        total_red += len(reds)
        verdict = "🔴 FAIL" if reds else "🟢 PASS"
        print(f"\n{'-'*78}\n{pred}  {titles[pred]}\n  {verdict}  "
              f"{len(reds)} RED · {len(warns)} WARN(needs-human)\n")
        for _p, _s, msg, ev in reds:
            print(f"  🔴 [{ev}] {msg}")
        for _p, _s, msg, ev in warns:
            print(f"  ⚠️  [{ev}] {msg}")
        if not quiet:
            for _p, _s, msg, ev in F.by(pred, "INFO"):
                print(f"  ·  [{ev}] {msg}")

    print("\n" + "=" * 78)
    print(f"VERDICT: {total_red} RED (gating) · "
          f"{len([i for i in F.items if i[1]=='WARN'])} WARN (cannot auto-decide, "
          f"needs a human)")
    print("=" * 78)
    sys.exit(1 if total_red else 0)


if __name__ == "__main__":
    main()
