# Refactoring UI — Distilled Methodology

Platform-agnostic distillation of Refactoring UI (Adam Wathan + Steve
Schoger) Chapters 1–3. Used by: `dev-workflow:brainstorm`,
`dev-workflow:choose-personality`, `dev-workflow:design-decision`, and
downstream design-system generators (e.g. `apple-dev:generate-design-system`).

## Section A: Pre-design Workflow

Before opening any design tool, answer three questions in order: What does
the user need to do here? How much do I need to design right now? What
personality should this product project? Skipping these questions leads to
beautiful screens that miss the actual problem and require expensive rework
after the first user test.

**Start with a feature, not a layout.** Every design begins with a user
task: complete a form, review a summary, configure a setting, browse a list
of items. Begin the sketch from that task. The question "where do the boxes
go?" is a layout question and comes later, not first. If you begin with
layout, you end up designing a beautiful room with no function.

**Detail comes later.** Low-fidelity sketches — rough shapes, arrows,
handwritten labels — are the fastest way to explore a user flow and catch
structural errors before any polish is applied. Visual polish is tempting to
add early but it slows iteration and anchors thinking to the first shape
drawn. The goal of the sketch phase is to answer "are we building the right
thing?" not "does this look good yet?" Those are two different questions and
they need to be answered in that order.

**Don't design too much.** The smallest useful slice that lets a user
accomplish one real task is enough. Design that slice, ship it, and get real
feedback before moving to the next screen. A half-finished full product
teaches nothing; a finished slice of the right feature teaches everything
about what actually matters to users.

**Choose a personality before styling.** The design's personality — the
vibe it projects, the audience it addresses, the formality it adopts, the
typographic character it uses, how rounded or sharp its corners are, and how
it speaks in words — is a constraint that applies to every pixel. Decide it
once at the start and let it guide all subsequent choices. Without this anchor,
every component becomes a micro-debate that slows the whole team down.

**Limit your choices.** A small set of spacing values, a fixed type scale,
a defined corner radius range — these are not restrictions. They are the
scaffolding that lets you move fast through a project without re-deciding
every question that was already answered. Section E explains why constraint is
a feature, not a limitation.

## Section B: Hierarchy Tactics

Every screen has content that matters more than other content. Visual
hierarchy is the art of making the most important content easiest to see — not
by making it shout, but by making everything else quieter. A screen with good
hierarchy guides the eye without the user consciously thinking about it.

**Not every element matters equally.** The first question to ask of any
screen is: what is the one thing the user must see or do here above all else?
Emphasize that. De-emphasize everything else. A common mistake is giving
every element equal visual weight, which makes the eye search without finding
a clear landing point.

**Three tools, used together: size, weight, and color.** These three are the
primary levers for creating hierarchy. The common mistake is stacking them —
making something larger AND bolder AND colored. When everything is loud,
nothing is loud. Combining tools is more effective than intensifying one: use
one dominant signal for the most important element, support it with one or two
secondary signals, and leave the rest unadorned.

**Don't use grey on colored backgrounds.** When a background is tinted or
colored, a mid-grey text that looked neutral on white becomes visually
disconnected and reads as "disabled" or "inactive" instead of "secondary."
Use semi-transparent white on dark or colored backgrounds, and
semi-transparent black on light tinted backgrounds. This keeps contrast ratios
correct and the hierarchy readable in every color context.

**Labels are a last resort.** When a value is self-explanatory in context,
combine label and value into a single meaningful phrase. "12 items" is clearer
than "Count: 12". "Expires tomorrow" is clearer than "Date: tomorrow". "Sent 3
hours ago" is clearer than "Timestamp: 3 hours ago". Only introduce a label
when the value alone is genuinely ambiguous without it — and when in doubt,
leave the label out and let the context carry the meaning.

**Balance weight and contrast.** High-contrast text can afford to be lighter
in weight. Low-contrast text needs heavier weight to remain readable. A common
error is using full-weight bold text at high contrast — the result is a
visual shout that overwhelms everything else on the page. The hierarchy should
feel calm and intentional, not like every element is competing for attention.

**Semantics and visual hierarchy are independent.** A heading HTML element
does not need to look like a heading visually, and a visually prominent
element does not need to use a heading tag. Keep these concerns separate when
building: choose heading levels for document structure and accessibility,
choose visual treatment for the desired reading hierarchy. Mixing them leads
to components that are hard to maintain and harder to restyle.

## Section C: Spacing Doctrine

Spacing is not decoration. It is structure. A page with good spacing reads
clearly even before the user focuses on individual elements. A page with poor
spacing is exhausting regardless of how good the content is. The user may not
be able to explain why the page feels off, but the off feeling will affect
how they trust the product.

**Establish a spacing system.** Pick a small fixed set of values and use
only those values throughout. A scale of eight values — 4, 8, 12, 16, 24, 32,
48, and 64 — handles most interfaces without a calculator. Some teams use
fewer, some use more, but the principle is the same: every spacing decision
should land on a pre-decided value, not a fresh judgment call. When this is
done well, the result feels intentional and coherent even if the viewer
cannot articulate exactly why.

**White space first.** Start designs with generous spacing and remove it only
where it genuinely gets in the way of the task. The instinct to add space
later as a patch usually fails because the addition feels like an exception
rather than part of the system. Design with space from the beginning, not
around it. The most common regret in UI design is not leaving enough
breathing room.

**Shrink the canvas.** A common reaction to an empty design is to widen it.
The more effective move is often to make it narrower. Tighter content
columns and smaller hero areas tend to look more considered and polished than
wide, sprawling layouts that waste the user's attention on empty space. Give
the design breathing room by reducing its footprint, not by filling it with
more content.

**Use a max-width on long-form content.** Lines of text that stretch
full-screen are uncomfortable to read. The eye loses its place at the start of
the next line, and the wide margins create an exhausting asymmetry. A maximum
of 65 to 75 characters per line is the established sweet spot for body text
— wide enough to feel natural, narrow enough to let the eye track
comfortably from line to line.

**Grids are overrated.** A grid is a useful tool when the content naturally
fits into its columns. When content does not fit neatly, the grid fights the
content instead of supporting it. Break the grid where it does not serve the
content. This is not a failure of the system — it is using the system
intelligently. A grid should serve the content, not the other way around.

**Relative sizing does not scale.** When a heading scales from 20px to 30px,
a label that was 12px does not automatically become 18px. Each size in the
type scale needs to be chosen deliberately for its context, not derived
proportionally from another size. A heading and its sub-label serve different
reading purposes and need different type sizes to match those purposes. The
type scale is a set of intentional choices, not a multiplication table.

## Section D: Personality Framework

Design personality is a set of constraints that apply consistently across
every element. It is not decoration applied at the end — it is the frame
that shapes every decision from color to microcopy. The six dimensions below
are the primary levers for pinning down a product's visual and linguistic
character early. Decide them once, apply them everywhere.

**Vibe** is the emotional character of the product. It can be playful,
serious, aggressive, calm, luxurious, or utilitarian. Vibe changes every
component's tone: a playful product uses rounded type and casual language
everywhere, while a serious product keeps language precise and visuals
structured. Vibe is felt before it is consciously noticed, so getting it
wrong creates an unease that is hard to diagnose.

**Audience** determines how much the product explains itself. Mass consumer
products default to showing over telling, with guidance built into the
interface. Power users expect density and technical precision, and find
hand-holding condescending. Executive products favor brevity and summary over
detail. Audience shapes information density, jargon level, and default
formality across the entire product.

**Formality** is the degree of casualness or reserve in the product's
voice. Casual products use contractions and conversational language in both
UI and error messages. Neutral products strike a middle ground. Formal
products use full forms and measured language throughout. Formality needs to
be consistent — a formal product with a casual error message feels broken,
like a job applicant who shows up in a tuxedo but greets you with a high-five.

**Font character** shapes the entire visual language. Geometric sans-serif
type feels modern and precise — clean, engineered, confident. Humanist
sans-serif feels warm and approachable — organic and slightly informal.
Serif type feels established and authoritative — traditional, trustworthy.
Display type makes a statement and signals emphasis. Font character is one of
the most consequential design decisions because it is visible on every
single screen and sets the first impression before any content is read.

**Radius personality** is the degree of corner rounding applied throughout
the interface. Sharp radii (0–2pt) feel precise and modern — engineered,
disciplined. Medium radii (4–8pt) feel balanced and versatile — approachable
without being soft. Heavy radii (12–16pt) feel friendly and approachable —
warm and open. Full pill shapes feel contemporary and casual. This dimension
touches every interactive element: buttons, cards, inputs, avatars, and badges
all inherit the same radius personality.

**Language tone** governs how the product communicates in words. A terse
tone gives the minimum necessary information and nothing more. An explanatory
tone teaches as it helps — useful for complex or unfamiliar tasks. An
encouraging tone supports and motivates — appropriate for personal or
creative tools. A professional tone maintains credibility — appropriate for
business and technical products. Tone shapes error messages, empty states,
placeholder text, and all microcopy.

These six dimensions feed `dev-workflow:choose-personality` as six explicit
questions. The answers are written to `docs/02-architecture/design-personality.md`
and consumed by downstream design-system generators so those tools skip
re-asking decisions that are already made. This is the handoff between the
methodology layer and the implementation layer.

## Section E: Limit Your Choices

A design system is not a cage. It is a set of pre-decided constraints that
eliminate decision fatigue so the team's energy goes toward the problems
that actually require judgment. Every time a designer or developer stops to
ask "what padding should this be?", that question is friction. A design
system eliminates that friction by answering it once and sticking to the
answer.

**A system isn't a cage — it's rails.** Rails let a train move faster than a
cart on an unmarked field. A spacing system of six values does not restrict
creativity in component layout — it channels it. The designer spends
creative energy on arrangement and hierarchy and user flow, not on debating
whether 14px or 15px is better. The constraint is the point: it separates
meaningful decisions from noise.

**Decision fatigue is real.** Every fresh choice a team member makes — "hmm,
what padding here, what font size there, what color should this be" — has a
small cognitive cost. Those costs accumulate. A team that has pre-decided
its spacing scale, type scale, and radius range makes each new decision on
top of a foundation rather than from scratch. The decisions that remain are
the interesting ones.

**If you must break the system, name the new constant.** Ad-hoc exceptions
that are not recorded are how design systems decay and eventually become
meaningless. If a specific context genuinely needs a value outside the
system, name it: define it as a named exception with a reason in the
documentation, not a one-off. Either the exception is worth including in the
system, or it is a leak that should be patched. An exception without a name
is a crack in the foundation.

**The smaller the system, the faster the project.** Six spacing values beat
sixteen. Three font sizes beat eight. Two corner radii beat five. Every
value in a system is a commitment — it needs to be documented, used
consistently, and maintained when requirements change. The fewer
commitments made early, the more flexibility available for the decisions
that actually matter. Start small, expand only when the system proves too
tight for a genuine requirement.

## Source Map

- Ch1 (Starting from scratch) → Sections A, D, E
- Ch2 (Hierarchy is everything) → Section B
- Ch3 (Layout and spacing) → Section C

This reference contains methodology, not platform-specific code. For
platform-specific implementations (Apple, web, etc.), see the corresponding
platform reference (e.g. `apple-dev/references/ui-design-principles.md` §17–§20).
