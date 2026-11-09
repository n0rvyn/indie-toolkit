# Evidence before risk disposition

Used by change-classifier when proposing risks and by review-before-commit when checking them. The classifier reads the diff once; the caller checks decisive premises before presenting choices. A user's acceptance is a decision about a demonstrated consequence, not a substitute for factual verification.

## Evidence record

For each risk, retain its ID and record:

- **Location:** actual producer and affected consumer, with `file:line`.
- **Kind:** runtime failure, repository-rule violation, checker limitation or conditional portability. Name multiple kinds when the evidence supports them separately.
- **Trigger:** the condition that reaches the affected behavior, including guards and fallback order.
- **Consequence:** what actually fails or changes, and for whom.
- **Evidence:** observed output, traced caller, applicable local rule, or current official documentation with URL and version/date. Distinguish an observed failure from an inference.
- **Verification:** `confirmed`, `unverified` or `contradicted`, with the missing premise where applicable.
- **Severity rationale:** proposed severity and, after the caller's check, final severity and reason. Preserve the original proposal when correcting it.

Use safe checks within the existing scope. Do not deploy, write production data, invoke paid providers or change security settings to prove a review finding. Read available code, configuration and official sources first. If a required check remains unavailable, name the specific missing evidence and retain a warning about incomplete verification.

## Distinctions that change the verdict

| Evidence | Supported conclusion | Additional evidence needed for a stronger claim |
|---|---|---|
| Current official platform documentation supports a setting; the repository forbids it | Repository-rule violation | A demonstrated effect before claiming platform incompatibility or runtime failure |
| A static graph omits a call, while the source contains that call | Checker limitation | Actual dispatch failure before claiming the skill never runs |
| A machine-specific fallback path is absent; a package-relative path is tried first | Conditional portability risk when the first path is unavailable | Trace both branches; do not claim every installation fails |
| A renamed function still has a reachable old-name caller that fails | Runtime failure with a specific consumer | Retain high/medium severity according to demonstrated impact; verification must not erase a real defect |

These examples are distinctions, not automatic severity assignments. A checker can block a critical release; a repository rule can protect a safety boundary. Grade the demonstrated consequence. A changed test count, TODO, missing test, or pattern match alone does not prove user-visible breakage.

## Current platform claims

Use current official documentation for capabilities, supported fields, limits and policy. Record what it establishes for the applicable version; do not generalize beyond it. Local policy, community reports and historical probes remain evidence about their own scope. If official pages conflict, report the conflict and the narrower verified conclusion rather than choosing whichever supports the initial risk.

## Corrections and unresolved evidence

The caller reads every proposed high/medium risk's decisive evidence and corrects unsupported statements before prompting. It records proposed → final severity and updates the report's counts and verdict. Confirmed informational issues remain visible without acceptance questions. Unverified material proposals retain their proposed severity and missing evidence, stay out of acceptance choices, and prevent a clean verdict. Confirmed high/medium risks continue through the existing user disposition step.
