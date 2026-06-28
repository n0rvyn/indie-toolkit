// flow-export.js — deterministic FLOW.md extractor.
//
// Run this from the design tool's run_script (the readFile/ls/log/saveFile
// helpers are in scope). It does the mechanical 90% so nobody re-greps a
// prototype by hand each project: it walks the router + every nav.go() call
// site and emits a FLOW.md SKELETON + a dead-edge report. You then annotate
// the 10% a script can't know (node descriptions, which stubs are intentional).
//
// CONVENTION this assumes (the useNav/go prototype shape):
//   • a router file with `route === 'x' && <Comp .../>` or `route.startsWith('x:')`
//   • navigation via `nav.go('x')` / `nav?.go('x')` / `nav.go(`x:${id}`)`
//   • a route-picker option list (value/label) is a bonus source of node ids
// If a project doesn't match, fall back to the manual procedure in SKILL.md
// (the skeleton just comes out thin — the dead-edge check still runs).
//
// ── CONFIG: point these at the project ───────────────────────────────────
const ROUTER_FILE = 'src/prototype-app.jsx';
const SRC_GLOB    = 'src/';        // folder to scan for go() call sites
const OUT         = 'FLOW.md';     // skeleton output path
const TABS        = ['today', 'plan', 'insights', 'me'];  // tab-bar root ids (reached via tab bar, not go()) — set to YOUR project's tabs
// ─────────────────────────────────────────────────────────────────────────

const files = (await ls(SRC_GLOB)).filter(f => /\.(jsx?|tsx?)$/.test(f));

// 1. NODES — ONLY the route literals the router actually branches on. The
//    router switch is the authoritative node source; do NOT scrape option/value
//    lists (a tweaks/settings picker enumerates state values like 'light' /
//    'recovery' / 'ready', not screens — scraping them pollutes the node set).
const router = await readFile(ROUTER_FILE);
const nodeIds = new Set();
//   route === 'x'
for (const m of router.matchAll(/route\s*===\s*['"]([a-zA-Z][\w]*)['"]/g)) nodeIds.add(m[1]);
//   route.startsWith('x:')  → parametrized family, store base id
for (const m of router.matchAll(/route\.startsWith\(['"]([a-zA-Z][\w]*):['"]\)/g)) nodeIds.add(m[1]);

// 2. EDGES — every go() call site across src.
const edges = [];
const goRe = /(?<![\w.$])(?:nav\??\.)?go\(\s*[`'"]([a-zA-Z][\w]*)(?::([^`'"]*))?[`'"]/g;
for (const f of files) {
  const txt = await readFile(SRC_GLOB.replace(/\/?$/, '/') + f);
  const lines = txt.split('\n');
  lines.forEach((ln, i) => {
    for (const m of ln.matchAll(goRe)) {
      edges.push({ to: m[1], param: m[2] || null, src: `${f}:${i + 1}` });
    }
  });
}

// 3. DEAD-EDGE SELF-CHECK — any go() target with no node.
const targets = new Set(edges.map(e => e.to));
const dead = [...targets].filter(t => !nodeIds.has(t));
const unreached = [...nodeIds].filter(n =>
  !targets.has(n) && !TABS.includes(n)); // tabs reached via tab bar, not go()

// 4. EMIT skeleton.
const nodeLines = [...nodeIds].sort().map(id =>
  `  - { id: ${id}, type: screen, a11y: ${id}_root, present: TODO, status: not-started }  # TODO: describe + states; set status stub|implemented per node (default not-started fails CLOSED — a forgotten node stays counted as not-done)`).join('\n');
const edgeLines = edges.map(e =>
  `  - { from: TODO, via: TODO, to: ${e.to}${e.param ? ', param: ' + JSON.stringify(e.param) : ''}, trigger: tap, src: "${e.src}" }`).join('\n');

const md = `# FLOW.md (SKELETON — emitted by flow-export.js, then annotate)
\`\`\`yaml
nodes:        # ${nodeIds.size} screen nodes — fill present/status/statesRef per node
${nodeLines}
edges:        # ${edges.length} go() call sites — fill from/via; 'to'+src are extracted
${edgeLines}
selfCheck:
  deadEdges: ${dead.length}        # ${dead.length ? 'FIX: ' + dead.join(', ') : 'clean'}
  unreachedNodes: ${unreached.length}   # ${unreached.length ? unreached.join(', ') + ' — reached only via tab bar? or orphan?' : 'none'}
\`\`\`
`;
await saveFile(OUT, md);

log(`nodes: ${nodeIds.size}  edges: ${edges.length}`);
log(`DEAD EDGES (go() with no node): ${dead.length ? dead.join(', ') : 'none ✓'}`);
log(`UNREACHED nodes (no inbound go(), non-tab): ${unreached.length ? unreached.join(', ') : 'none ✓'}`);
log(`→ wrote ${OUT} skeleton. Annotate node descriptions + mark intentional stubs.`);
