# Validation Playbook

**Purpose:** When dimensions score <=3★ or a demand-check returns Caution, what's the lowest-cost experiment to validate or invalidate the uncertain signal?

## Method Library

Indie-specific validation methods. All are designed for one person, <=2 weeks, and <=$200.

### 1. Competitor Review Mining

**Method:** AI-analyze 200+ App Store or web reviews (1★-3★) of top 3 competitors. Extract recurring complaint themes, feature requests, and unmet needs.
**Best for:** Demand unclear, differentiation unclear.
**Success criteria:** >=3 recurring complaint themes that this product directly addresses.
**Failure criteria:** Complaints are about issues this product also has, or complaints are not about the core JTBD.

### 2. Community Resonance Test

**Method:** Post a pain-point description (NOT a product pitch) in 2-3 communities where target users gather (Reddit, Discord, forums). Describe the problem, not your solution. Measure organic response.
**Best for:** Demand unclear, user segmentation unclear.
**Success criteria:** >=20 upvotes or >=5 "I have this problem" replies within 48 hours.
**Failure criteria:** <5 engagements after 48 hours, or responses indicate the problem is already well-solved.

### 3. Small-Market Soft Launch

**Method:** Launch in a small English-speaking market (New Zealand, Australia) at target price. Zero promotion; rely on organic App Store discovery for 2 weeks.
**Best for:** Willingness-to-pay unclear, pricing power uncertain.
**Success criteria:** >=3 paid conversions without promotion.
**Failure criteria:** Zero conversions after 2 weeks of availability.

### 4. Dogfooding Sprint

**Method:** Use your own product as a real user for 2 continuous weeks. Keep a daily friction log: every moment of confusion, delay, or workaround. At the end, honestly answer: "Would I miss this if it disappeared?"
**Best for:** Journey completeness uncertain, value proposition unclear.
**Success criteria:** Friction log has <=5 entries AND you genuinely miss the product when you stop.
**Failure criteria:** Friction log exceeds 15 entries, OR you don't notice when you stop using it.

### 5. AI Discoverability Check

**Method:** Ask ChatGPT, Claude, and Perplexity: "Recommend a tool/app for [this product's core job]." See if this product category appears in the recommendations. Test with 5 different phrasings of the same job.
**Best for:** Moat unclear, AI replacement risk assessment.
**Success criteria:** AI tools recommend the product category but cannot fully replace it; they suggest dedicated apps.
**Failure criteria:** AI tools can solve the job directly in the conversation, or they don't mention this category at all (no demand signal).

## Selection Logic

Match experiments to the specific uncertain signal from the evaluation:

| Uncertain Signal | Primary Method | Secondary Method |
|-----------------|---------------|-----------------|
| Demand existence | Community Resonance Test | Competitor Review Mining |
| Differentiation | Competitor Review Mining | AI Discoverability Check |
| Willingness to pay | Small-Market Soft Launch | Competitor Review Mining |
| Journey quality | Dogfooding Sprint | Community Resonance Test |
| AI replacement risk | AI Discoverability Check | Competitor Review Mining |
| Moat strength | AI Discoverability Check | Dogfooding Sprint |

## Output Format

```markdown
## Validation Playbook

Before investing further, validate these uncertainties:

1. **[Uncertain signal]:** [Method name]
   - Do: [1-2 sentence action description]
   - Success: [measurable criteria]
   - Fail: [measurable criteria]
   - Timeline: [<=2 weeks]

2. **[Uncertain signal]:** [Method name]
   - Do: [action description]
   - Success: [criteria]
   - Fail: [criteria]
   - Timeline: [<=2 weeks]

[2-4 experiments total]
```
