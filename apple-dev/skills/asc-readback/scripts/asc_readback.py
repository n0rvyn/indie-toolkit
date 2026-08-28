#!/usr/bin/env python3
"""
asc_readback.py — read what App Store Connect ACTUALLY holds, for any app.

Authenticated ASC API reads. Answers questions the public iTunes endpoints cannot:
what is in the keyword field, did my edit save, is this version actually submitted.

Read-only by design: every request is a GET. This tool cannot change your listing.

Credentials, in priority order:
  1. env ASC_KEY_PATH / ASC_KEY_ID / ASC_ISSUER_ID
  2. env ASC_KEY_PATH alone + a sibling `key.info` holding "Key ID:" and "Issuer ID:"
  3. the first AuthKey_*.p8 found under ~/private_keys, ~/.appstoreconnect/private_keys,
     or any dir listed in env ASC_KEY_DIRS (colon-separated), + sibling key.info

Commands:
  apps                          list apps (id, bundleId, name, primaryLocale)
  show   <app> [--limit N]      every version x locale: name/subtitle/keywords/description/
                                promo/whatsNew + URLs + screenshot checksums + review notes
  state  <app>                  submission state — is it actually queued with Apple?
  scan   <app> --forbid a,b,c   search every locale/field for tokens (compliance check)
  diff   <app> <verA> <verB>    field-by-field: what changed between two versions
  assert <app> --locale L --field F --equals STR | --absent STR | --present STR
                                read-back assertion; exit 1 on mismatch. For CI / post-edit.

<app> is a bundle id, an app id, or a case-insensitive name substring.
"""
from __future__ import annotations
import argparse, base64, json, os, re, sys, time, urllib.error, urllib.request
from pathlib import Path

API = "https://api.appstoreconnect.apple.com"

TEXT_FIELDS = ("keywords", "description", "promotionalText", "whatsNew",
               "supportUrl", "marketingUrl")
INFO_FIELDS = ("name", "subtitle", "privacyPolicyUrl")


# ---------------------------------------------------------------- credentials

def _parse_key_info(p: Path) -> tuple[str | None, str | None]:
    """key.info holds 'Key ID: X' and 'Issuer ID: Y'. Apple's UI also says 'Issue ID'."""
    if not p.is_file():
        return None, None
    txt = p.read_text(errors="replace")
    kid = re.search(r"Key\s*ID\s*[:=]\s*(\S+)", txt, re.I)
    iss = re.search(r"Issue(?:r)?\s*ID\s*[:=]\s*(\S+)", txt, re.I)
    return (kid.group(1) if kid else None), (iss.group(1) if iss else None)


def _find_key() -> tuple[Path, str, str]:
    key_path = os.environ.get("ASC_KEY_PATH")
    candidates: list[Path] = [Path(key_path)] if key_path else []
    if not candidates:
        dirs = [Path.home() / "private_keys",
                Path.home() / ".appstoreconnect" / "private_keys"]
        dirs += [Path(d) for d in os.environ.get("ASC_KEY_DIRS", "").split(":") if d]
        for d in dirs:
            if d.is_dir():
                candidates += sorted(d.glob("AuthKey_*.p8"))
    for c in candidates:
        if not c.is_file():
            continue
        kid = os.environ.get("ASC_KEY_ID")
        iss = os.environ.get("ASC_ISSUER_ID")
        fkid, fiss = _parse_key_info(c.parent / "key.info")
        kid, iss = kid or fkid, iss or fiss
        # Apple names the file AuthKey_<KEYID>.p8
        if not kid:
            m = re.match(r"AuthKey_(.+)\.p8$", c.name)
            kid = m.group(1) if m else None
        if kid and iss:
            return c, kid, iss
    sys.exit(
        "No usable ASC credentials.\n"
        "  Set ASC_KEY_PATH (to AuthKey_XXX.p8) plus ASC_KEY_ID and ASC_ISSUER_ID,\n"
        "  or put the .p8 next to a key.info containing 'Key ID:' and 'Issuer ID:',\n"
        "  or set ASC_KEY_DIRS=/path/to/keys.\n"
        f"  Looked at: {[str(c) for c in candidates] or 'nothing'}"
    )


def _token() -> str:
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.asymmetric import utils as au
    except ImportError:
        sys.exit("Needs `cryptography`:  python3 -m pip install cryptography")
    path, kid, iss = _find_key()
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    b = lambda x: base64.urlsafe_b64encode(x).rstrip(b"=")
    now = int(time.time())
    head = {"alg": "ES256", "kid": kid, "typ": "JWT"}
    body = {"iss": iss, "iat": now, "exp": now + 1200, "aud": "appstoreconnect-v1"}
    si = (b(json.dumps(head, separators=(",", ":")).encode()) + b"."
          + b(json.dumps(body, separators=(",", ":")).encode()))
    r, s = au.decode_dss_signature(key.sign(si, ec.ECDSA(hashes.SHA256())))
    return (si + b"." + b(r.to_bytes(32, "big") + s.to_bytes(32, "big"))).decode()


_TOK: str | None = None


def get(path: str, allow_missing: bool = False) -> dict | None:
    """allow_missing tolerates a 404 (optional sub-resource) and ONLY a 404.
    Auth and rate-limit failures must stay fatal — swallowing them would turn a
    dead read into a confident-looking empty result, which is what this whole
    tool exists to prevent."""
    global _TOK
    if _TOK is None:
        _TOK = _token()
    req = urllib.request.Request(API + path, headers={"Authorization": "Bearer " + _TOK})
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:600]
        if e.code == 404 and allow_missing:
            return None
        if e.code == 401:
            sys.exit(f"401 from ASC — key/issuer rejected.\n{detail}")
        raise SystemExit(f"HTTP {e.code} on {path}\n{detail}")


# ---------------------------------------------------------------- resolution

def resolve_app(token: str) -> dict:
    apps = get("/v1/apps?fields[apps]=name,bundleId,primaryLocale&limit=200")["data"]
    t = token.lower()
    for a in apps:                                   # exact id / bundle id first
        if a["id"] == token or a["attributes"]["bundleId"].lower() == t:
            return a
    hits = [a for a in apps
            if t in (a["attributes"].get("name") or "").lower()
            or t in a["attributes"]["bundleId"].lower()]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        print(f"No app matched {token!r}. Available:", file=sys.stderr)
        for a in apps:
            print(f"  {a['id']}  {a['attributes']['bundleId']}  {a['attributes']['name']}",
                  file=sys.stderr)
        sys.exit(1)
    print(f"{token!r} is ambiguous:", file=sys.stderr)
    for a in hits:
        print(f"  {a['id']}  {a['attributes']['bundleId']}  {a['attributes']['name']}",
              file=sys.stderr)
    sys.exit(1)


def ver_state(at: dict) -> str:
    """Apple's docs on AppStoreVersion.appStoreState: "This attribute is
    deprecated. Use appVersionState instead." Read the successor first — once
    Apple drops the old key, `.get()` would return None and we would print
    "None" as if it were a status."""
    return at.get("appVersionState") or at.get("appStoreState") or "?"


def versions(app_id: str, limit: int = 5) -> list[dict]:
    """ASC documents no `sort` parameter and no default ordering for
    appStoreVersions, so `?limit=3` is NOT "the newest 3" — it is whatever the
    API felt like returning first. Pull a wide page and order it here, or a
    read-back could quietly describe an ancient version."""
    data = get(f"/v1/apps/{app_id}/appStoreVersions?limit=50")["data"]
    data.sort(key=lambda v: v["attributes"].get("createdDate") or "", reverse=True)
    return data[:limit]


def version_locs(vid: str) -> list[dict]:
    return get(f"/v1/appStoreVersions/{vid}/appStoreVersionLocalizations")["data"]


def info_locs(app_id: str) -> list[tuple[str, dict]]:
    """(appInfo state, localization attrs) — name/subtitle live here, not on the version."""
    out = []
    for i in get(f"/v1/apps/{app_id}/appInfos")["data"]:
        st = i["attributes"].get("appStoreState") or i["attributes"].get("state")
        for l in get(f"/v1/appInfos/{i['id']}/appInfoLocalizations")["data"]:
            out.append((st, l["attributes"]))
    return out


def shots(loc_id: str) -> list[tuple[str, str, str]]:
    out = []
    for s in get(f"/v1/appStoreVersionLocalizations/{loc_id}/appScreenshotSets")["data"]:
        dt = s["attributes"].get("screenshotDisplayType") or "?"
        for sh in get(f"/v1/appScreenshotSets/{s['id']}/appScreenshots")["data"]:
            a = sh["attributes"]
            out.append((dt, a.get("fileName") or "?", a.get("sourceFileChecksum") or "?"))
    return out


# ---------------------------------------------------------------- commands

def cmd_apps(_a):
    for a in get("/v1/apps?fields[apps]=name,bundleId,primaryLocale&limit=200")["data"]:
        at = a["attributes"]
        print(f"{a['id']:<12} {at['bundleId']:<40} {at.get('primaryLocale','?'):<8} {at['name']}")


def cmd_show(args):
    app = resolve_app(args.app)
    print(f"APP {app['id']}  {app['attributes']['bundleId']}  {app['attributes']['name']}")

    print("\n=== App Info (name / subtitle live here) ===")
    for st, at in info_locs(app["id"]):
        print(f"  [{st}] {at['locale']:<8} name={at.get('name')!r} subtitle={at.get('subtitle')!r}")
        if at.get("privacyPolicyUrl"):
            print(f"           privacyPolicyUrl={at['privacyPolicyUrl']}")

    for v in versions(app["id"], args.limit):
        at = v["attributes"]
        print(f"\n=== Version {at.get('versionString')}  [{ver_state(at)}]  {v['id']}"
              f"  created={at.get('createdDate')}")
        for l in version_locs(v["id"]):
            a = l["attributes"]
            kw = a.get("keywords") or ""
            print(f"  --- {a['locale']}  (locId {l['id']})")
            print(f"      keywords ({len(kw)}/100): {kw!r}")
            for f in ("promotionalText", "whatsNew", "description", "supportUrl", "marketingUrl"):
                val = a.get(f)
                if val is None:
                    continue
                show = val if (args.full or len(val) <= 120) else val[:120] + f"… (+{len(val)-120})"
                print(f"      {f} ({len(val)}): {show!r}")
            if args.screenshots:
                for dt, fn, ck in shots(l["id"]):
                    print(f"      shot[{dt}] {fn:<24} {ck}")
        detail = get(f"/v1/appStoreVersions/{v['id']}/appStoreReviewDetail",
                     allow_missing=True)
        if detail is None:
            print("  --- Review Notes: none set for this version (404)")
        else:
            notes = (detail.get("data") or {}).get("attributes", {}).get("notes") or ""
            print(f"  --- Review Notes ({len(notes)} chars)")
            for line in notes.splitlines():
                print("      " + line)


def cmd_state(args):
    app = resolve_app(args.app)
    print(f"APP {app['id']}  {app['attributes']['name']}")
    print("\n=== Versions (sorted here by createdDate, newest first) ===")
    for v in versions(app["id"], 5):
        at = v["attributes"]
        print(f"  {at.get('versionString'):<8} {ver_state(at):<24} created={at.get('createdDate')}")

    # No `sort` parameter exists on this endpoint and Apple documents no default
    # ordering, so order it here rather than printing an unearned "newest first".
    print("\n=== Review submissions (sorted here by submittedDate, newest first) ===")
    subs = get(f"/v1/apps/{app['id']}/reviewSubmissions?limit=10")["data"]
    subs.sort(key=lambda s: s["attributes"].get("submittedDate") or "", reverse=True)
    if not subs:
        print("  (none — this app has never had a review submission)")
    states = []
    for s in subs:
        a = s["attributes"]
        items = get(f"/v1/reviewSubmissions/{s['id']}/items")["data"]
        istates = ", ".join(i["attributes"].get("state", "?") for i in items) or "-"
        print(f"  {s['id']}")
        print(f"    state={a.get('state')}  submitted={a.get('submittedDate')}  items=[{istates}]")
        states.append(a.get("state"))

    print("\n=== Verdict ===")
    # The criterion is the SUBMISSION state. The item state is a verdict field
    # (READY_FOR_REVIEW -> APPROVED/REJECTED); it never passes through
    # WAITING_FOR_REVIEW, so it cannot tell you whether you submitted.
    #
    # Decided by membership, not by list position: ASC guarantees no ordering
    # here, so "the first one that looks in-flight" would be a coin flip.
    queued = next((s for s in states if s in ("WAITING_FOR_REVIEW", "IN_REVIEW")), None)
    if queued:
        print(f"  ✅ QUEUED WITH APPLE (submission state = {queued})")
    elif "UNRESOLVED_ISSUES" in states:
        print("  ⛔ NOT SUBMITTED — a submission is sitting in UNRESOLVED_ISSUES.")
        print("     Rejected items must be edited and then RESUBMITTED. Editing the fields")
        print("     and saving does NOT queue it. Open the submission in ASC and click")
        print("     'Resubmit to App Review'.")
        sys.exit(1)
    elif "READY_FOR_REVIEW" in states:
        print("  ⛔ NOT SUBMITTED — submission state is READY_FOR_REVIEW, which Apple")
        print("     defines as 'added to a submission, but hasn't been submitted yet'.")
        sys.exit(1)
    elif not states:
        print("  ⛔ NOTHING AWAITING REVIEW — this app has no review submission at all.")
        sys.exit(1)
    else:
        print(f"  ⛔ NOTHING AWAITING REVIEW — every submission is finished ({', '.join(sorted(set(states)))}).")
        print("     Correct if the current version is already live. If you were expecting a")
        print("     version to be in review, it was never submitted.")
        sys.exit(1)


def _walk_fields(app_id: str, limit: int):
    """Yield (where, field, text) over every localized metadata string."""
    for st, at in info_locs(app_id):
        for f in INFO_FIELDS:
            if at.get(f):
                yield f"appInfo[{st}]/{at['locale']}", f, at[f]
    for v in versions(app_id, limit):
        vs = v["attributes"].get("versionString")
        for l in version_locs(v["id"]):
            a = l["attributes"]
            for f in TEXT_FIELDS:
                if a.get(f):
                    yield f"v{vs}/{a['locale']}", f, a[f]


def cmd_scan(args):
    app = resolve_app(args.app)
    tokens = [t.strip().lower() for t in args.forbid.split(",") if t.strip()]
    print(f"APP {app['id']}  {app['attributes']['name']}")
    print(f"Scanning for: {tokens}\n")
    # One pass. Walking twice doubled every ASC round trip and let the scan and
    # its own control read two different snapshots.
    fields = list(_walk_fields(app["id"], args.limit))
    hits = 0
    for where, field, text in fields:
        low = text.lower()
        for t in tokens:
            if t in low:
                hits += 1
                i = low.index(t)
                ctx = text[max(0, i - 45): i + len(t) + 45].replace("\n", " ")
                print(f"  ⛔ {where:<24} {field:<18} {t!r}  …{ctx}…")

    # A scan that finds nothing is only meaningful if the scanner read anything.
    # The control counts what the walk actually produced — NOT whether some
    # sentinel letter appears in it. A Chinese-only listing contains no "a", and
    # the previous control failed such a listing as "read no fields".
    chars = sum(len(t) for _, _, t in fields)
    print(f"\n  [positive control] read {len(fields)} non-empty field(s), {chars} chars "
          f"across {len({w for w, _, _ in fields})} locale/version slot(s).")
    if not fields:
        sys.exit("  !! The walk produced no fields at all. This scan read nothing; "
                 "its 'no hits' means nothing.")
    if hits:
        print(f"\n{hits} forbidden-token hit(s).")
        sys.exit(1)
    print("\n✅ No forbidden tokens found.")
    print("  NOTE: screenshots are images. This scans text fields only — a brand name")
    print("  burned into screenshot artwork will NOT be caught here. Check those by eye.")


def _first_diff(a: str, b: str) -> int:
    """Index of the first differing character. Long fields often differ only at the
    end, so a head-truncated diff would print two identical-looking lines."""
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i
    return n


def _window(txt: str, at: int, span: int = 110) -> str:
    lo = max(0, at - span // 3)
    hi = min(len(txt), lo + span)
    return ("…" if lo else "") + txt[lo:hi] + ("…" if hi < len(txt) else "")


def cmd_diff(args):
    app = resolve_app(args.app)
    want = {args.ver_a, args.ver_b}
    snap: dict[str, dict[tuple[str, str], str]] = {}
    for v in versions(app["id"], 20):
        vs = v["attributes"].get("versionString")
        if vs not in want:
            continue
        d = {}
        for l in version_locs(v["id"]):
            a = l["attributes"]
            for f in TEXT_FIELDS:
                d[(a["locale"], f)] = a.get(f) or ""
            for dt, fn, ck in shots(l["id"]):
                d[(a["locale"], f"shot:{fn}")] = ck
        snap[vs] = d
    missing = want - set(snap)
    if missing:
        sys.exit(f"Version(s) not found: {sorted(missing)}")
    a, b = snap[args.ver_a], snap[args.ver_b]
    print(f"APP {app['attributes']['name']}   {args.ver_a} → {args.ver_b}\n")
    same = 0
    for k in sorted(set(a) | set(b), key=lambda x: (x[0], x[1])):
        va, vb = a.get(k, "<absent>"), b.get(k, "<absent>")
        if va == vb:
            same += 1
            continue
        loc, field = k
        print(f"  ~ {loc}/{field}")
        for tag, txt in ((args.ver_a, va), (args.ver_b, vb)):
            print(f"      {tag}: {_window(txt, _first_diff(va, vb))!r}")
    print(f"\n  {same} field(s) identical across the two versions.")
    print("  Identical = a CONSTANT, not this run's variable. If a review outcome changed,")
    print("  the cause is among the fields listed above, not among the identical ones.")


def cmd_assert(args):
    known = set(TEXT_FIELDS) | set(INFO_FIELDS)
    if args.field not in known:
        sys.exit(f"FAIL: unknown field {args.field!r}. Known: {', '.join(sorted(known))}")

    app = resolve_app(args.app)
    found = source = None

    if args.field in INFO_FIELDS:
        # name / subtitle / privacyPolicyUrl live on appInfo, not on a version.
        for st, at in info_locs(app["id"]):
            if at["locale"] == args.locale:
                found, source = at.get(args.field) or "", f"appInfo[{st}]/{args.locale}"
                break
    else:
        # Resolve inside ONE version and stop there. Falling through to an older
        # version when the field is null answers "did my edit save?" with the
        # PREVIOUS version's value — a confident PASS about the wrong data.
        # Measured 2026-08-28: v1.1 had a null promotionalText and the old code
        # reported PASS on v1.0's 78 characters.
        vs = versions(app["id"], args.limit)
        if args.version:
            vs = [v for v in vs if v["attributes"].get("versionString") == args.version]
            if not vs:
                sys.exit(f"FAIL: version {args.version} not found "
                         f"(searched the newest {args.limit}; raise --limit)")
        if not vs:
            sys.exit("FAIL: this app has no App Store version")
        v = vs[0]
        vstr = v["attributes"].get("versionString")
        for l in version_locs(v["id"]):
            a = l["attributes"]
            if a["locale"] == args.locale:
                found, source = a.get(args.field) or "", f"v{vstr}/{args.locale}"
                break
        if source is None:
            sys.exit(f"FAIL: v{vstr} has no {args.locale} localization")

    if found is None:
        sys.exit(f"FAIL: no value for {args.locale}/{args.field}")

    label = f"{source}/{args.field}"
    size = f"{len(found)} chars"

    # An emptied field satisfies every --absent test. Without this line, a save
    # that silently dropped the field prints a PASS byte-identical to the one an
    # intact field prints — which is failure mode #1 this tool exists to catch.
    if not found:
        print(f"⚠️  {label} is EMPTY (0 chars). Any --absent check on an empty field "
              f"passes vacuously. If you just saved a value here, it did not commit.")

    if args.equals is not None:
        ok = found == args.equals
        print(f"{'PASS' if ok else 'FAIL'} {label} equals expected ({size})")
        if not ok:
            print(f"  expected: {args.equals!r}\n  actual:   {found!r}")
    elif args.absent is not None:
        ok = args.absent.lower() not in found.lower()
        print(f"{'PASS' if ok else 'FAIL'} {label} does not contain {args.absent!r} ({size})")
        if not ok:
            print(f"  actual: {found!r}")
    else:
        ok = args.present.lower() in found.lower()
        print(f"{'PASS' if ok else 'FAIL'} {label} contains {args.present!r} ({size})")
        if not ok:
            print(f"  actual: {found!r}")
    sys.exit(0 if ok else 1)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("apps").set_defaults(fn=cmd_apps)

    s = sub.add_parser("show"); s.add_argument("app")
    s.add_argument("--limit", type=int, default=3)
    s.add_argument("--screenshots", action="store_true")
    s.add_argument("--full", action="store_true", help="do not truncate long fields")
    s.set_defaults(fn=cmd_show)

    s = sub.add_parser("state"); s.add_argument("app"); s.set_defaults(fn=cmd_state)

    s = sub.add_parser("scan"); s.add_argument("app")
    s.add_argument("--forbid", required=True, help="comma-separated tokens")
    s.add_argument("--limit", type=int, default=1, help="how many versions back")
    s.set_defaults(fn=cmd_scan)

    s = sub.add_parser("diff"); s.add_argument("app")
    s.add_argument("ver_a"); s.add_argument("ver_b"); s.set_defaults(fn=cmd_diff)

    s = sub.add_parser("assert"); s.add_argument("app")
    s.add_argument("--locale", required=True); s.add_argument("--field", required=True)
    s.add_argument("--version"); s.add_argument("--limit", type=int, default=3)
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--equals"); g.add_argument("--absent"); g.add_argument("--present")
    s.set_defaults(fn=cmd_assert)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
