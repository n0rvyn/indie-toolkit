# FLOW.md — Runetic Navigation & Completeness Contract

> Emitted from the prototype router (`src/prototype-app.jsx` render switch + every `nav.go(...)` call site across `src/`). **Do not hand-edit** — re-emit from the prototype when routes change. This is the *structure* axis; appearance is owned by `DESIGN.md`. Per-screen state-completeness (readiness × empty/zero-data branches) stays in DESIGN.md (4c/4e) — FLOW only guarantees each screen *exists* and every entry *reaches a non-stub one*.

```yaml
targetTabs: [today, plan, insights, me]
targetOS: iOS 26

# ── NODES — every screen the router can land on. `status` is what the coverage script counts.
nodes:
  - { id: today.root,      type: screen, tab: today,    a11y: today_root,      present: tab,        status: implemented, statesRef: "DESIGN.md 4c/4e — readiness×4, phase pre/done, planState, loadData, yesterday, watchSync" }
  - { id: today.processing,type: screen, a11y: today_processing,               present: fullscreen, status: implemented, note: "T4 post-run interstitial — appears because data arrived, not on tap" }
  - { id: plan.root,       type: screen, tab: plan,     a11y: plan_root,       present: tab,        status: implemented, statesRef: "DESIGN.md — planState empty/generating/ready" }
  - { id: insights.root,   type: screen, tab: insights, a11y: insights_root,   present: tab,        status: implemented, statesRef: "DESIGN.md 4e — dataState full/partial/empty" }
  - { id: me.root,         type: screen, tab: me,        a11y: me_root,         present: tab,        status: implemented, statesRef: "DESIGN.md 4e — meData full/new" }
  - { id: prescription,    type: screen, a11y: prescription_detail,            present: push,       status: implemented }
  - { id: coach,           type: screen, a11y: coach_chat,                      present: push,       status: implemented }
  - { id: watchsent,       type: screen, a11y: watch_sent,                      present: fullscreen, status: implemented, note: "T8 handoff; onRecall = acknowledged reverse-flow (~1200ms) → today" }
  - { id: workout,         type: screen, a11y: workout_detail,                  present: push,       status: implemented, param: "runId", note: "3 tabs 总览/细节/分析" }
  - { id: phase,           type: screen, a11y: phase_detail,                    present: push,       status: implemented, param: "phaseId base/build/peak/taper" }
  - { id: day,             type: screen, a11y: day_detail,                      present: push,       status: implemented, param: "dayNum", statesRef: "today/past/future/rest" }
  - { id: week,            type: screen, a11y: week_detail,                     present: push,       status: implemented, param: "weekNum", statesRef: "P2 normal / P5 locked framework-only" }
  - { id: adaptations,     type: screen, a11y: adaptations_six,                 present: push,       status: implemented, note: "I4 radar + 6 rows" }
  - { id: weekly,          type: screen, a11y: weekly_report,                   present: push,       status: STUB-INTENTIONAL, note: "I6 — DELIBERATE empty placeholder (constitution #2: 复盘隐入下一处方). The recap folds into Today's T9 AI finding. DO NOT build this into a report page. The recap card in insights links here on purpose to a near-empty screen." }
  - { id: capability,      type: screen, a11y: capability_vdot,                 present: push,       status: implemented, note: "M1 VDOT decision-growth curve + 6-zone pace ref" }
  - { id: achievements,    type: screen, a11y: achievements_wall,              present: push,       status: implemented, note: "M6 full trophy wall" }
  - { id: notifications,   type: screen, a11y: notification_settings,          present: push,       status: implemented, note: "M2" }
  - { id: paywall,         type: screen, a11y: paywall,                         present: sheet,      status: implemented, param: "targetTier pro/elite" }
  - { id: profileedit,     type: screen, a11y: profile_edit,                    present: push,       status: implemented }
  - { id: pr,              type: screen, a11y: pr_detail,                       present: push,       status: implemented, param: "prKey 5K/10K/半马/全马" }
  - { id: onboarding,      type: screen, a11y: onboarding_flow,                 present: fullscreen, status: implemented, note: "6-step incl. O1 step-5 plan preview" }

# ── EDGES — every tappable entry that reaches a node. `via` = a11y id of the entry; one node, many edges (directed graph, not N trees).
edges:
  # tab bar (RuneticTabBar — 4 tabs, mutual)
  - { from: "*", via: tabbar_today,    to: today.root,    trigger: tab }
  - { from: "*", via: tabbar_plan,     to: plan.root,     trigger: tab }
  - { from: "*", via: tabbar_insights, to: insights.root, trigger: tab }
  - { from: "*", via: tabbar_me,       to: me.root,       trigger: tab }
  # today
  - { from: today.root, via: prescription_card,   to: prescription, trigger: tap, src: "screens-today.jsx:251" }
  - { from: today.root, via: tomorrow_bridge,      to: prescription, trigger: tap, src: "screens-today.jsx:244 (phase=done)" }
  - { from: today.root, via: yesterday_card,       to: workout,      trigger: tap, src: "screens-today.jsx:56", param: YESTERDAY_RUN_ID }
  - { from: today.root, via: history_row,          to: workout,      trigger: tap, src: "screens-today.jsx:595/606/615", param: "run.id" }
  - { from: today.root, via: ai_finding_open_chat, to: coach,        trigger: tap, src: "screens-today.jsx:1263 (AIFeedbackModal)" }
  - { from: today.root, via: empty_set_goal,       to: plan.root,    trigger: tap, src: "screens-today.jsx:41 (TodayEmpty)" }
  - { from: today.root, via: send_to_watch,        to: watchsent,    trigger: tap, src: "prototype-app.jsx sendToWatch" }
  - { from: today.processing, via: auto_done,      to: today.root,   trigger: auto, src: "prototype-app.jsx:95" }
  # prescription
  - { from: prescription, via: rx_back,            to: today.root, trigger: tap, src: "screens-prescription.jsx:28" }
  - { from: prescription, via: rx_send_watch,      to: watchsent,  trigger: tap, src: "screens-prescription.jsx:94" }
  - { from: prescription, via: rx_adjust,          to: coach,      trigger: tap, src: "screens-prescription.jsx:104/109" }
  # watchsent
  - { from: watchsent, via: ws_close,              to: today.root,   trigger: tap, src: "screens-watch-sent.jsx:43/122" }
  - { from: watchsent, via: ws_recall,             to: today.root,   trigger: action, src: "screens-watch-sent.jsx:34 (reverse-flow, 1200ms ack)" }
  - { from: watchsent, via: ws_view_rx,            to: prescription, trigger: tap, src: "screens-watch-sent.jsx:130" }
  # coach
  - { from: coach, via: coach_back,                to: today.root, trigger: tap, src: "screens-coach.jsx:29" }
  # plan
  - { from: plan.root, via: week_link,             to: week,  trigger: tap, src: "screens-plan.jsx:333", param: "3" }
  - { from: plan.root, via: phase_row,             to: phase, trigger: tap, src: "screens-plan.jsx:794", param: "id" }
  - { from: plan.root, via: day_pill,              to: day,   trigger: tap, src: "screens-plan.jsx:361", param: "n" }
  # insights
  - { from: insights.root, via: recap_card,        to: weekly,      trigger: tap, src: "screens-insights.jsx:190 (→ intentional stub)" }
  - { from: insights.root, via: adaptations_card,  to: adaptations, trigger: tap, src: "screens-adaptations.jsx:57" }
  - { from: insights.root, via: empty_start,       to: today.root,  trigger: tap, src: "screens-insights.jsx:16" }
  - { from: weekly,        via: weekly_back,       to: insights.root, trigger: tap, src: "screens-weekly-report.jsx:27" }
  - { from: adaptations,   via: adaptations_back,  to: insights.root, trigger: tap }
  # me
  - { from: me.root, via: edit_profile,            to: profileedit,   trigger: tap, src: "screens-profile.jsx:218" }
  - { from: me.root, via: pr_card,                 to: pr,            trigger: tap, src: "screens-profile.jsx:242-248", param: "5K/10K/半马/全马" }
  - { from: me.root, via: achievements_all,        to: achievements,  trigger: tap, src: "screens-profile.jsx:265" }
  - { from: me.root, via: capability_card,         to: capability,    trigger: tap, src: "screens-profile.jsx:284" }
  - { from: me.root, via: notifications_row,       to: notifications, trigger: tap, src: "screens-profile.jsx:352" }
  - { from: me.root, via: subscription_cta,        to: paywall,       trigger: tap, src: "screens-profile.jsx:952", param: "pro/elite" }
  - { from: achievements,  via: ach_back,          to: me.root,   trigger: tap, src: "screens-achievements.jsx:91" }
  - { from: achievements,  via: ach_medal_run,     to: workout,   trigger: tap, src: "screens-achievements.jsx:116/251", param: "runId" }
  - { from: capability,    via: cap_back,          to: me.root,   trigger: tap, src: "screens-capability.jsx:138" }
  - { from: notifications, via: notif_back,        to: me.root,   trigger: tap, src: "screens-notifications.jsx:104" }
  - { from: profileedit,   via: edit_back,         to: me.root,   trigger: tap, src: "screens-profile-edit.jsx:27" }
  - { from: pr,            via: pr_back,           to: me.root,   trigger: tap, src: "screens-pr.jsx:131" }
  # workout / day / week / phase backs + cross-links
  - { from: workout, via: wo_back,                 to: today.root, trigger: tap, src: "screens-workout.jsx:128" }
  - { from: day, via: day_back,                    to: plan.root,  trigger: tap, src: "screens-day.jsx:37" }
  - { from: day, via: day_send_watch,              to: watchsent,  trigger: tap, src: "screens-day.jsx:163 (status=today)" }
  - { from: day, via: day_view_run,                to: workout,    trigger: tap, src: "screens-day.jsx:186 (status=past)", param: "r-0518" }
  - { from: week, via: week_back,                  to: plan.root,  trigger: tap, src: "screens-week.jsx:192/332" }
  - { from: week, via: week_day_row,               to: day,        trigger: tap, src: "screens-week.jsx:536", param: "day.n" }

# ── LEAVES — clickable but owe NO subview (in-place sheets/modals/inputs). Listed so they are NOT flagged as dead ends.
#    These open via SheetShell / center-modal / inline state, not the router. Spec for each: DESIGN.md sheet/modal pattern library.
leaves:
  - { on: today.root,  control: checkin_sheet,        kind: action, note: "T1 ReadinessCheckinSheet (bottom sheet)" }
  - { on: today.root,  control: load_sheet,           kind: action, note: "T2 load detail sheet" }
  - { on: today.root,  control: rx_alternates_sheet,  kind: action, note: "T5 alternates sheet" }
  - { on: today.root,  control: readiness_info_sheet, kind: action, note: "T7 InfoSheet long-read" }
  - { on: today.root,  control: drift_info_sheet,     kind: action, note: "T7 DriftInfoSheet" }
  - { on: today.root,  control: journal_sheet,        kind: action, note: "T10 JournalSheet per historical run" }
  - { on: today.root,  control: ai_finding_modal,     kind: action, note: "T9 AIFeedbackModal center modal (its CTA edges to coach)" }
  - { on: insights.root, control: time_range_picker,  kind: input,  note: "I1 — lifts range to all charts" }
  - { on: plan.root,   control: phase_timeline,       kind: input,  note: "PhaseTimeline build→peak→taper stepper" }
  - { on: me.root,     control: sync_now,             kind: action, note: "M3 SyncNowRow + sync sheet" }
  - { on: me.root,     control: language_sheet,       kind: action, note: "M7 LanguageSheet" }
  - { on: me.root,     control: settings_toggles,     kind: input,  note: "教练介入 / 提醒 etc. (real settings)" }

# ── EXPORT-TIME SELF-CHECK (run while emitting)
selfCheck:
  deadEdges: 0          # every go() target resolves to a node above
  stubs: 1              # weekly — INTENTIONAL (constitution #2), not a gap
  note: "All 21 screen nodes have an implementing component. The only non-implemented node (weekly) is a deliberate placeholder, not missing work. Handoff is verified-complete intent."
```

---

## Coverage gate (the termination judge — a script, not the agent's claim)

```
N screen nodes              = 21
implemented                 = 20
intentional stub (weekly)   = 1   ← excluded from the "done" target by design
dead edges                  = 0

DONE  ⇔  every node with status `implemented` builds + renders, AND
         grep -rc "FLOW-STUB" == 0 across the SwiftUI target, AND
         dead edges == 0.
```

In the SwiftUI build, every not-yet-written screen carries `#warning("FLOW-STUB: <node-id> — not implemented")`. The single intentional placeholder keeps a self-explanatory marker instead: `#warning("FLOW-INTENTIONAL-STUB: weekly — empty by constitution #2, do not build")`. So the count separates "not done yet" from "deliberately blank," and "done" is decided by `grep`, never by the agent feeling finished.

## Seam with DESIGN.md (no double-coverage)

FLOW guarantees: the node exists, is reachable, isn't an accidental stub. It does **not** re-audit per-screen states — when a node lists `statesRef: DESIGN.md`, that screen's readiness×4 / empty / zero-data / device-missing branches are DESIGN.md 4c/4e's job. Build the screen (FLOW), then fill its states (DESIGN). One concern, one home.
