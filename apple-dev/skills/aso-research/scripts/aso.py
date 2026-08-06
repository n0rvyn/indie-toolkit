#!/usr/bin/env python3
"""App Store real-data puller for ASO research.

Only returns data actually pulled from Apple's endpoints. No estimates, no
search-volume or difficulty scores — those require a paid panel this has no
access to, and inventing them makes users act on fiction.

Endpoint details and gotchas: ../references/appstore-data-apis.md

Library use:
    import aso
    aso.live(bundle_id="com.example.App", store="cn")
    aso.search("garmin", "cn")             # ranked results
    aso.details("6760798981", "cn")        # authoritative name + subtitle
    aso.hints("garmin", "us")              # Apple autocomplete
    aso.rank_of("6760798981", aso.search("garmin", "cn"))

CLI use:
    python3 aso.py live com.example.App cn
    python3 aso.py search 佳明 cn --id 6760798981
    python3 aso.py details 6760798981 cn
    python3 aso.py hints garmin us
    python3 aso.py matrix 6760798981 cn 佳明 佳明同步 活动同步
    python3 aso.py check name "佳同步 - 国区国际版活动记录互传"
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse

# Storefront ids: US 143441, CN 143465, JP 143462, GB 143444, DE 143443.
# Format is <storefrontId>-<language>,<platform>. Add rows as needed.
STOREFRONTS = {
    "us": "143441-1,29",
    "cn": "143465-19,29",
    "jp": "143462-1,29",
    "gb": "143444-2,29",
    "de": "143443-1,29",
}

# Browser UAs get 302/503 from the MZ* endpoints. This one works.
UA = ("AppStore/2.0 iOS/17.0 model/iPhone14,2 hwp/t8110 "
      "build/21A329 (6; dt:200)")

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")


def _sf(store):
    try:
        return STOREFRONTS[store]
    except KeyError:
        raise SystemExit(
            f"unknown storefront {store!r}; known: {', '.join(STOREFRONTS)}. "
            "Add its id to STOREFRONTS.")


def _get(url, store, tag, ext="json"):
    """Fetch with storefront header, disk cache, and retry. -L is mandatory:
    several of these endpoints 301 first and return an empty body without it."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"{tag}.{ext}")
    if os.path.exists(path) and os.path.getsize(path) > 100:
        return open(path, encoding="utf-8").read()
    for attempt in range(3):
        p = subprocess.run(
            ["curl", "-sL", "-H", f"X-Apple-Store-Front: {_sf(store)}",
             "-A", UA, url],
            capture_output=True, text=True)
        body = p.stdout
        ok = body.lstrip().startswith("{" if ext == "json" else "<")
        if ok:
            open(path, "w", encoding="utf-8").write(body)
            return body
        time.sleep(1.5 * (attempt + 1))
    return None


def _slug(term):
    return urllib.parse.quote(term, safe="")


# --------------------------------------------------------------------------
# 1. Live listing metadata (public endpoint, no header needed)
# --------------------------------------------------------------------------

def live(bundle_id=None, track_id=None, store="us", entity="software"):
    """Live listing as Apple serves it. Combines lookup (metadata) with
    viewSoftware (subtitle, which lookup does not return).

    entity: 'software' for iOS, 'macSoftware' for Mac. Wrong entity = no hit.
    """
    if bundle_id:
        q = f"bundleId={urllib.parse.quote(bundle_id)}"
    elif track_id:
        q = f"id={track_id}"
    else:
        raise ValueError("need bundle_id or track_id")
    url = (f"https://itunes.apple.com/lookup?{q}&country={store}"
           f"&entity={entity}")
    p = subprocess.run(["curl", "-s", url], capture_output=True, text=True)
    try:
        results = json.loads(p.stdout).get("results", [])
    except json.JSONDecodeError:
        return None
    if not results:
        return None
    a = results[0]
    out = {
        "trackId": a.get("trackId"),
        "name": a.get("trackName"),
        "seller": a.get("sellerName"),
        "genres": a.get("genres"),
        "version": a.get("version"),
        "released": (a.get("releaseDate") or "")[:10],
        "versionReleased": (a.get("currentVersionReleaseDate") or "")[:10],
        "rating": a.get("averageUserRating"),
        "ratingCount": a.get("userRatingCount"),
        "languages": a.get("languageCodesISO2A"),
        "minimumOsVersion": a.get("minimumOsVersion"),
        "screenshots": len(a.get("screenshotUrls") or []),
        "description": a.get("description", ""),
        "releaseNotes": a.get("releaseNotes", ""),
        "subtitle": None,
        "keywords": "NOT READABLE — Apple exposes no public endpoint",
    }
    d = details(out["trackId"], store)
    if d:
        out["subtitle"] = d["subtitle"]
        out["storeName"] = d["name"]
    return out


# --------------------------------------------------------------------------
# 2. Authoritative name + subtitle, per storefront
# --------------------------------------------------------------------------

def details(app_id, store):
    url = ("https://itunes.apple.com/WebObjects/MZStore.woa/wa/viewSoftware"
           f"?id={app_id}")
    raw = _get(url, store, f"sw_{store}_{app_id}")
    if not raw:
        return None
    try:
        d = json.loads(raw)
    except json.JSONDecodeError:
        return None
    for sec in d.get("storePlatformData", {}).values():
        for v in sec.get("results", {}).values():
            if str(v.get("id")) == str(app_id):
                return {"id": str(app_id),
                        "name": v.get("name", ""),
                        "subtitle": v.get("subtitle") or "",
                        "artist": v.get("artistName", ""),
                        "genres": v.get("genreNames", [])}
    return None


# --------------------------------------------------------------------------
# 3. Ranked search results
# --------------------------------------------------------------------------

def search(term, store):
    """Real App Store ranked results. Returns [] on a genuinely empty result
    set, None when the fetch itself failed — do not conflate the two.

    Apple caps the response around 250 entries (undocumented; observed
    246-250). Absence means 'not in the top ~250', not 'not indexed'.
    """
    url = ("https://search.itunes.apple.com/WebObjects/MZSearch.woa/wa/search"
           "?clientApplication=Software&term=" + urllib.parse.quote(term))
    raw = _get(url, store, f"srch_{store}_{_slug(term)}")
    if not raw:
        return None
    try:
        d = json.loads(raw)
    except json.JSONDecodeError:
        return None
    # Ordering lives in pageData.bubbles, NOT in the lockup section — that one
    # has no resultIds and hydrates only the first 8 entries.
    bubbles = d.get("pageData", {}).get("bubbles") or [{}]
    ids = [r["id"] for r in bubbles[0].get("results", [])
           if r.get("entity") == "software"]
    hydrated = (d.get("storePlatformData", {})
                 .get("native-search-lockup", {}).get("results", {}))
    out = []
    for i, k in enumerate(ids, 1):
        v = hydrated.get(k, {})
        out.append({"rank": i, "id": str(k),
                    "name": v.get("name", ""),
                    "subtitle": v.get("subtitle") or "",
                    "artist": v.get("artistName", ""),
                    "hydrated": bool(v)})
    return out


def rank_of(app_id, results):
    """Rank of app_id, or None if absent. None also when results is None —
    check `results is None` separately before reading anything into it."""
    for r in results or []:
        if r["id"] == str(app_id):
            return r["rank"]
    return None


def hydrate(results, store, limit=50, workers=8):
    """Fill in name/subtitle/artist past the first 8 via viewSoftware."""
    import concurrent.futures as cf
    subset = results[:limit]
    with cf.ThreadPoolExecutor(workers) as ex:
        det = list(ex.map(lambda x: details(x["id"], store), subset))
    for x, d in zip(subset, det):
        if d:
            x.update(name=d["name"], subtitle=d["subtitle"],
                     artist=d["artist"], hydrated=True)
    return subset


# --------------------------------------------------------------------------
# 4. Apple search autocomplete
# --------------------------------------------------------------------------

def hints(term, store):
    """Apple's own autocomplete, in Apple's own order. NOT search volume.
    An empty list means Apple surfaces no suggestion for this term."""
    url = ("https://search.itunes.apple.com/WebObjects/MZSearchHints.woa/wa/"
           "hints?clientApplication=Software&term=" + urllib.parse.quote(term))
    raw = _get(url, store, f"hint_{store}_{_slug(term)}", ext="xml")
    if raw is None:
        return None
    return re.findall(r"<key>term</key>\s*<string>([^<]*)</string>", raw)


# --------------------------------------------------------------------------
# 5. Field length check
# --------------------------------------------------------------------------

LIMITS = {"name": 30, "subtitle": 30, "keywords": 100,
          "promo": 170, "description": 4000}


def check(field, text):
    limit = LIMITS[field]
    return {"field": field, "len": len(text), "limit": limit,
            "ok": len(text) <= limit, "text": text}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _selftest(store):
    """Positive control. A zero result is only meaningful once the collector
    has been shown to return non-zero on a term known to match."""
    probe = "garmin" if store != "jp" else "garmin"
    r = search(probe, store)
    if not r:
        print(f"SELFTEST FAILED: search({probe!r}, {store!r}) returned "
              f"{r!r}. The collector is broken — do not read anything into "
              f"empty results until this passes.", file=sys.stderr)
        return False
    print(f"selftest ok: search({probe!r}, {store!r}) -> {len(r)} results",
          file=sys.stderr)
    return True


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    if cmd == "live":
        ident, store = argv[2], (argv[3] if len(argv) > 3 else "us")
        key = "track_id" if ident.isdigit() else "bundle_id"
        print(json.dumps(live(**{key: ident}, store=store),
                         ensure_ascii=False, indent=2))
    elif cmd == "details":
        print(json.dumps(details(argv[2], argv[3]), ensure_ascii=False,
                         indent=2))
    elif cmd == "hints":
        h = hints(argv[2], argv[3])
        print(json.dumps(h, ensure_ascii=False, indent=2))
        if h == []:
            print("(empty: Apple surfaces no suggestion for this term)",
                  file=sys.stderr)
    elif cmd == "search":
        term, store = argv[2], argv[3]
        own = argv[argv.index("--id") + 1] if "--id" in argv else None
        r = search(term, store)
        if r is None:
            print("FETCH FAILED — not an empty result set", file=sys.stderr)
            return 2
        for x in hydrate(r, store, limit=int(os.environ.get("ASO_TOP", 25))):
            mark = "  <== TARGET" if own and x["id"] == own else ""
            print(f"{x['rank']:>3} | {x['name'][:34]:<34} | "
                  f"{x['subtitle'][:32]:<32} | {x['artist'][:20]}{mark}")
        print(f"total {len(r)} | target rank: {rank_of(own, r) if own else 'n/a'}")
    elif cmd == "check":
        # aso.py check name "佳同步 - 国区国际版活动记录互传"
        field = argv[2]
        if field not in LIMITS:
            print(f"unknown field {field!r}; known: {', '.join(LIMITS)}",
                  file=sys.stderr)
            return 2
        bad = 0
        for text in argv[3:]:
            r = check(field, text)
            flag = "OK  " if r["ok"] else "OVER"
            bad += 0 if r["ok"] else 1
            print(f"[{flag}] {r['len']:>4}/{r['limit']}  {text}")
        return 1 if bad else 0
    elif cmd == "matrix":
        own, store, terms = argv[2], argv[3], argv[4:]
        if not _selftest(store):
            return 2
        print(f"{'term':<24}{'results':>9}{'rank':>7}")
        for t in terms:
            r = search(t, store)
            if r is None:
                print(f"{t:<24}{'FETCH FAIL':>9}{'?':>7}")
                continue
            rk = rank_of(own, r)
            print(f"{t:<24}{len(r):>9}{(str(rk) if rk else '—'):>7}")
        print("\n'—' = not in the ~250 returned, NOT 'not indexed'.")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
