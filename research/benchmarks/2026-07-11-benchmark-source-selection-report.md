# Benchmark Source Selection Report

- Research date: 2026-07-11
- Status: completed benchmark-level research; source portfolio proposed, not accepted
- Decision record: [ADR-0008](../../docs/adr/0008-primary-benchmark-source-shortlist.md)
- Accepted suite relationship: [ADR-0007](../../docs/adr/0007-nested-smoke-suite.md)
- Scope: benchmark families, score evidence, risks, and task-admission rules
- Not in scope: final task IDs, browser backend selection, executor selection, or judge-panel construction

## Executive conclusion

The first controlled primary suite should be assembled from multiple benchmark families. No single available benchmark simultaneously supplies:

- Reddit-like and LinkedIn-like social interaction;
- checkout, booking, messaging, and account workflows;
- difficult enterprise configuration and forms;
- genuinely visual controls;
- long-horizon memory and recovery pressure;
- disruptive UI conditions such as popups, cookie notices, and delays;
- reproducible reset; and
- trustworthy state-based verification.

The proposed 100-task source portfolio is:

| Source | Primary | Nested smoke | Principal coverage |
|---|---:|---:|---|
| REAL | 20 | 4 | LinkedIn-like networking, checkout, booking, email, calendar, travel, rides, modern app flows |
| WebArena-Verified Hard | 20 | 4 | Reddit, shopping/admin, GitLab, multi-site mutation, audited deterministic evaluation |
| VisualWebArena | 15 | 3 | Visual grounding, spatial interaction, social/shopping/classifieds |
| WorkArena++ | 20 | 4 | Enterprise forms, records, filters, menus, catalogs, configuration, compositional planning |
| WebChoreArena | 10 | 2 | Long-horizon memory, calculation, tedious multi-page workflows |
| WARC-Bench | 10 | 2 | Archived real-site date pickers, menus, nested scrolling, forms, dynamic controls, deterministic rewards |
| WebForge Level 3 | Up to 5 | Up to 1 | Popups, cookie dialogs, latency, noise, risk-heavy workflows; conditional evaluator admission |
| **Total** | **100** | **20** | Smoke is a strict subset of primary |

This is not a decision to admit 100 tasks immediately. It is the allocation to use when building a larger candidate pool and conducting task-level audits.

The allocation changed twice during review, and both changes are retained in ADR-0008. First, WebArena-Verified Hard was reduced from 25 to 20 while conditional WebForge capacity increased from 5 to 10, capping correlated WebArena-family exposure at 45 tasks. Second, after the public WARC-Bench repository, task files, MIT package declaration, and programmatic JavaScript evaluators were located, WARC-Bench received 10 proposed slots. REAL was reduced from 25 to 20 and WebForge returned to up to 5 conditional slots. This adds archived-real UI diversity and deterministic component-level tests without reducing coverage of the project's major workflow classes.

## Decision boundary

The project owner has accepted one suite-structure decision: the 20-task smoke set is contained inside the approximately 100-task primary set. The benchmark sources, quotas, versions, task IDs, verifier revisions, budgets, and regression membership remain open until explicitly approved.

The regression suite is a separate role. It should protect stable capabilities and previously fixed failures; it should not simply be another name for all 100 visible primary tasks.

## Selection criteria

A source was ranked on the following dimensions:

1. browser interaction rather than primarily information retrieval;
2. current difficulty headroom;
3. deterministic and adversarially testable completion verification;
4. reproducible initialization and reset;
5. coverage of social, transactional, enterprise, visual, and recovery behaviors;
6. support for competing observation and action architectures;
7. operational feasibility, licensing, and safety;
8. resistance to shortcuts, contamination, and task-template memorization; and
9. traceability for later review agents.

A high benchmark-level score does not automatically make a source saturated. We intend to select hard slices, not random tasks. Conversely, a low score does not prove the tasks are valid; infrastructure defects and evaluator errors can also create low success.

## Current public score snapshot

The following are the strongest recent public results that could be verified from an official repository, official leaderboard, or primary paper during this review. They are examples of the current frontier, not guaranteed universal records.

| Benchmark | Recent public result | What it means for this project |
|---|---|---|
| REAL v1 | Frontier systems reached at most 41% in the original 112-task study | Large headroom on realistic replicas. REAL v2 is now live, but no directly comparable public v2 result was located. |
| WebArena-Verified, full | 53.7% single-round success with SKILL.nb | The verified family remains unsolved. This is not a score on the 258-task Hard subset, and SKILL.nb reuses governed workflows. |
| VisualWebArena, all 910 tasks | 58.3% with PANDO; the official board separately lists SGV at 54.0% | Substantial visual headroom remains. PANDO distills online skills, so its result is a harness-plus-model result rather than a static model score. |
| WorkArena++ Level 2 | 69.4% ± 3.0 with GenericAgent and GPT-5 under the recorded standard protocol | L2 is useful selectively, but random L2 sampling risks including tasks that are no longer discriminative. |
| WorkArena++ Level 3 | 11.5% ± 2.1 with the same system after increasing the step budget from 50 to 100 | L3 has exceptional headroom, but this public number is explicitly non-protocol and cannot be used as a clean baseline. |
| WebChoreArena, full | 47.4% with ColorBrowserAgent plus GPT-5; 44.9% with BrowserGym plus Gemini 2.5 Pro | The 47.4% system includes a human-in-the-loop knowledge-adaptation mechanism. The 44.9% BrowserGym result is the cleaner autonomous reference. |
| WARC-Bench, test | 64.8% with Claude Sonnet 4.0 (2025-05-14) | The benchmark remains discriminative while supplying deterministic, real-UI component checks. It is short-horizon, so it complements rather than replaces workflow benchmarks. |
| WebForge, all / L3 | 75.9% overall and 58.0% on L3 with Gemini-3-Pro; only 23.1% on the L3 risk-factor dimension | Only difficult and risk-heavy tasks are suitable. The default final-answer LLM judge is not acceptable without independent verification. |

### Interpretation rule

Every score above describes a complete system: model snapshot, prompt, observation representation, action set, memory or skill mechanism, step budget, retry policy, and evaluator. Our result records must preserve those fields. We should never label a human-assisted, modified-budget, cross-task-memory, or different-version number as directly comparable without the qualifier.

## Source analysis

### 1. REAL — core source for LinkedIn-like and transactional workflows

REAL provides deterministic high-fidelity replicas across e-commerce, travel, communication, and professional networking. The current site lists Airbnb-, Amazon-, DoorDash-, Google Calendar-, Gmail-, OpenTable-, LinkedIn-, Uber-, United-, Upwork-, Zillow-, and Marriott-like applications. It advertises locked data, fixed dates, replayability, pre-authenticated sessions, cross-tab persistence, configurable latency, and unexpected-behavior flags.

This is the closest controlled match to the project's stated interest in LinkedIn, checkout or payment-like steps, reservations, messaging, calendars, travel, and modern multipage applications. The published v1 benchmark contains 112 tasks across 11 sites and evaluates action tasks with programmatic state checks while using rubric-based LLM evaluation for retrieval tasks. Its paper reports that the tested frontier systems reached at most 41% overall; this review did not locate a directly comparable aggregate for v2.

**Why 20 candidate slots**

Twenty tasks can still cover at least eight app families while limiting dependence on one shared modern front-end stack. The five slots removed during review were reassigned to WARC-Bench after its runnable release and deterministic evaluators were verified.

**Admission restrictions**

- Prefer action tasks with direct state-difference checks.
- Exclude retrieval-only tasks from the primary aggregate until the judge workstream validates their evaluator.
- Use only synthetic payment details and simulated purchases.
- Pin REAL version, site build, task file, and evaluator revision.
- Test for false positives caused by merely visiting a confirmation page or generating plausible text.

**Open issue**

REAL v2 is live, while the independently published at-most-41% result belongs to v1. The task manifests and evaluator semantics must be compared before choosing a version.

Primary sources:

- https://arxiv.org/abs/2504.11543
- https://www.realevals.xyz/
- https://github.com/agi-inc/REAL

### 2. WebArena-Verified Hard — core deterministic foundation

WebArena-Verified re-audits WebArena tasks, reference answers, and evaluators. It removes LLM and brittle substring matching in favor of structured responses, type-aware normalization, and network-event checks that can be replayed offline. Evaluation outputs include task and evaluator checksums and distinguish evaluator errors from task failures.

Its Hard subset contains 258 of the 812 verified tasks: 55 Shopping Admin, 57 GitLab, 42 Reddit, 56 Shopping, and 48 multi-site tasks. The maintainers report that 48.1% have predicted success at or below 20%, and that the hardest categories are multi-step state-changing forms and data updates.

**Why 20 candidate slots**

This source gives the suite its strongest ready-made deterministic evaluation backbone and covers Reddit-like interaction directly. Twenty tasks are enough to span sites and mutation classes while leaving room for non-WebArena UI families.

**Admission restrictions**

- Prefer mutation and difficult navigation tasks over pure retrieval.
- Include Reddit, shopping/admin, GitLab, and multi-site coverage.
- Audit each HAR/network evaluator against fabricated near-miss traces.
- Pin task revision, dataset checksum, evaluator checksum, and environment image.
- Avoid duplicated intent templates and equivalent state changes.

**Score caveat**

SKILL.nb reports 53.7% on the full verified benchmark. No directly comparable public score for the 258-task Hard subset was located, so local baselines are essential.

Primary sources:

- https://servicenow.github.io/webarena-verified/latest/
- https://servicenow.github.io/webarena-verified/latest/getting_started/hard_subset/
- https://arxiv.org/abs/2606.08049

### 3. VisualWebArena — core visual and social source

VisualWebArena contains 910 multimodal tasks across Reddit, shopping, and classifieds. It is valuable because screenshots contain information that text-only structure may omit, and because it stresses spatial grounding and visually ambiguous controls.

**Why 15 candidate slots**

Fifteen tasks are sufficient to ensure visual-first systems receive a fair test without overconcentrating the suite on three sites or on another WebArena-derived environment family.

**Admission restrictions**

- Demonstrate that the chosen task is genuinely vision-sensitive by ablating screenshots or masking the relevant visual evidence.
- Reject tasks solvable through hidden labels, metadata, or a trivial DOM shortcut when the intended challenge is visual.
- Include Reddit as well as shopping and classifieds.
- Audit execution evaluators and confirmation-state assumptions.

**Score evidence**

PANDO reports 58.3% on all 910 tasks, compared with SGV at 54.0% and its WALT reproduction at 45.2%. Human performance reported by the benchmark is about 88.7%, leaving a large gap.

Primary sources:

- https://github.com/web-arena-x/visualwebarena
- https://docs.google.com/spreadsheets/d/1M801lEpBbKSNwP-vDBkC_pF7LdyGU1f_ufZb_NWNBZQ/edit?gid=2044883967
- https://arxiv.org/abs/2605.24785

### 4. WorkArena++ — core source for enterprise configuration

WorkArena uses ServiceNow to test knowledge-work interfaces. WorkArena++ contains 682 compositional tasks built from atomic interactions involving knowledge bases, complex forms, service catalogs, lists and filters, menus, dashboards, and records. Level 3 tasks provide implicit instructions and difficult planning requirements.

**Why 20 candidate slots**

WorkArena++ is the strongest candidate for configuration-heavy, form-heavy enterprise interaction. The proposed pool should be mostly Level 3 with a small number of independently hard Level 2 tasks to avoid relying on a nonstandard doubled action budget.

**Admission restrictions**

- Obtain and document gated instance access before committing slots.
- Verify instance reset, seeded state, task validation, and concurrency behavior.
- Limit repeated templates and cover distinct UI mechanisms.
- Record standard and extended-budget results separately.
- Reject tasks whose failures are predominantly environment provisioning failures.

**Score evidence**

The official BrowserGym leaderboard records GenericAgent with `gpt-5-2025-08-07`, AXTree observations, no screenshots, and bid actions at 69.4% ± 3.0 on L2 under the standard protocol. It records 11.5% ± 2.1 on L3 after increasing the maximum steps from 50 to 100, so the L3 number is evidence of difficulty, not a clean protocol reference.

Primary sources:

- https://github.com/ServiceNow/WorkArena
- https://huggingface.co/spaces/ServiceNow/browsergym-leaderboard/blob/main/results/GenericAgent-GPT-5/workarena-l2.json
- https://huggingface.co/spaces/ServiceNow/browsergym-leaderboard/blob/main/results/GenericAgent-GPT-5/workarena-l3.json
- https://huggingface.co/spaces/ServiceNow/browsergym-leaderboard/blob/main/results/GenericAgent-GPT-5/README.md

### 5. WebChoreArena — targeted long-horizon source

WebChoreArena contains 532 tasks built on four WebArena simulation environments. It targets Massive Memory, Calculation, and Long-Term Memory tasks and includes shopping, administration, Reddit, GitLab, and cross-site work.

**Why 10 candidate slots**

Long-horizon memory and calculation failures are central to harness research, but WebChoreArena overlaps heavily with the WebArena family and inherits evaluator assumptions that require auditing. Ten tasks provide the pressure without letting correlated infrastructure dominate.

**Admission restrictions**

- Prefer tasks whose browser interaction is substantial rather than mostly arithmetic or answer generation.
- Audit or replace inherited evaluators.
- Deduplicate against selected WebArena-Verified and VisualWebArena templates.
- Exclude tasks requiring the executor to retain benchmark-specific knowledge across nominally independent runs.

**Score evidence**

The official leaderboard lists ColorBrowserAgent plus GPT-5 at 47.4% and BrowserGym plus Gemini 2.5 Pro at 44.9%. ColorBrowserAgent explicitly includes human-in-the-loop knowledge adaptation, so 44.9% is the cleaner autonomous comparison.

Primary sources:

- https://github.com/WebChoreArena/WebChoreArena
- https://docs.google.com/spreadsheets/d/1RGyJ0QOxGj196KTfUK0SZeVl5IkM928_38wzIkQVxCs/edit
- https://arxiv.org/abs/2506.01952
- https://arxiv.org/abs/2601.07262

### 6. WARC-Bench — core source for realistic component execution

WARC-Bench provides 438 short-horizon GUI tasks rendered from archived real webpages. It covers date pickers, nested scrolling, dropdown and multi-level menus, forms, sliders, hover, and asynchronous JavaScript controls. Each task carries a programmatic reward; the public task files include explicit JavaScript matchers, and the repository includes the archived environments, evaluation runner, and trajectory viewer.

**Why 10 candidate slots**

Most workflow benchmarks reveal that an agent failed but do not isolate whether it failed at a date picker, nested scroll region, dropdown, hover interaction, or dynamic control. Ten WARC-Bench tasks give the suite a realistic component-skill layer with deterministic rewards. The cap prevents short-horizon subtasks from displacing the project's main long-horizon objective.

**Admission restrictions**

- Sample distinct UI mechanisms and unrelated archived sites rather than near-duplicate parameter variations.
- Prefer the held-out test split and pin the repository commit, WACZ archive, task file, and JavaScript evaluator.
- Inspect every matcher for hidden-state shortcuts and verify that a visually plausible near miss fails.
- Reject tasks that can be solved by direct script execution or DOM mutation if that mechanism is outside the lane being evaluated.
- Keep WARC subtasks as 10% of the aggregate and report their score separately.

**Score evidence**

The official repository reports 64.8% test success for Claude Sonnet 4.0 (2025-05-14), 48.8% for its 72B SFT system, and 52.8% after RLVR. This leaves useful headroom while giving us reproducible, realistic UI primitives.

Primary sources:

- https://github.com/sanjari-orb/warc-bench
- https://arxiv.org/abs/2510.09872

### 7. WebForge Level 3 — conditional source for controlled nuisance conditions

WebForge provides 934 generated, self-contained tasks across seven domains and three difficulty levels. Its refinement pipeline injects popups, cookie dialogs, network delays, and other noise, and its validation agent replays solution paths in Chromium.

**Why up to 5 candidate slots**

It directly targets conditions missing from most controlled benchmarks. However, the default evaluator asks an LLM to compare the final answer with ground truth. That is insufficient for a primary gate whose purpose is to minimize false positives and false negatives. WARC-Bench now supplies the main realistic component layer, so WebForge is reserved for nuisance conditions not otherwise covered.

**Admission restrictions**

- Select only Level 3, risk-heavy tasks.
- Require a deterministic operation code or an independently implemented state verifier.
- Reject direct-answer-only tasks unless their answer is mechanically checkable and navigation—not retrieval—is the dominant work.
- Run false-completion and shortcut probes.
- Treat all five slots as conditional until the independent evaluator passes calibration.

**Score evidence**

The repository reports Gemini-3-Pro at 75.9% overall and 58.0% on Level 3. Its Level 3 risk-factor accuracy is only 23.1%, supporting selective use of disruptive tasks rather than random sampling.

Primary sources:

- https://github.com/yuandaxia2001/WebForge
- https://arxiv.org/abs/2604.10988

## High-priority candidates not yet admitted

### EntWorld

EntWorld reports 1,756 enterprise tasks across six domains, schema-grounded generation, SQL-based state-transition verification, and 47.61% success for GPT-4.1. It could diversify or partly replace WorkArena++ because it covers CRM, ITIL, ERP, and other enterprise interfaces without relying on one ServiceNow product family. No authoritative public code or dataset repository was located in this review, so reproducibility, licensing, and task access remain unverified.

Primary source:

- https://arxiv.org/abs/2601.17722

### RiskWebWorld

RiskWebWorld reports 1,513 tasks across eight e-commerce risk domains, uncooperative sites, partial environmental hijackings, a Gymnasium-compatible environment, and 49.1% success for top generalist systems. It is highly relevant to recovery and hostile-interface research. No authoritative public release was located, so it cannot yet supply primary tasks.

Primary source:

- https://arxiv.org/abs/2604.13531

## Sources not proposed for the first primary aggregate

### TimeWarp

Useful as a paired robustness experiment across six historical UI versions of Wiki, News, and Shop. It measures layout drift well, but counting correlated UI variants as separate primary tasks would inflate the sample and overrepresent three environment families. Keep it as a later robustness track.

### OpenApps

Useful for lightweight state-based tests and controlled appearance/content variations. Its core tasks are comparatively simple, so it is better suited to adapter tests, perturbation experiments, and fallback smoke coverage than the hard primary score.

### MiniWoB++

Useful for atomic action-interface unit tests, but too synthetic and too saturated to represent the central objective.

### WebSP-Eval

A high-priority candidate for the later permitted-account transfer suite. It contributes 200 security and privacy configuration tasks across 28 live websites, including cookie preferences, privacy settings, session revocation, toggles, and checkboxes, with account-state management and automated evaluation. It is not proposed for the controlled primary score because website drift, account policy, regional variation, and extension-based state management create a different validity regime. Reassess it immediately after ADR-0006 and the live-site judge protocol are accepted.

Primary source:

- https://arxiv.org/abs/2604.06367

### WebVoyager, Online-Mind2Web, WebCanvas, Odysseys, and other live-web suites

Valuable for later transfer testing, but live drift, regional differences, account state, anti-bot measures, and judge dependence make them unsuitable for the repeatedly optimized controlled core. They belong in a separately reported permitted-account suite after the live-site policy and judge panel are accepted.

### BrowseComp and retrieval-heavy research benchmarks

Not central because they measure information discovery more than reliable browser operation and state-changing interaction.

## Diversity and anti-overfitting constraints

The final 100-task manifest should satisfy all of the following unless an explicit exception is approved:

- no source contributes more than 20 tasks;
- no rendered site or application replica contributes more than 5 tasks;
- WebArena-derived sources together contribute no more than 45 tasks;
- at least 60 tasks require a state change rather than a final text answer;
- at least 20 tasks contain genuinely visual or spatial evidence;
- at least 20 tasks exercise forms, filters, configuration, or structured editors;
- at least 15 tasks require recovery-relevant behavior such as re-navigation, stale-state handling, interrupted workflows, or ambiguity resolution;
- at least 10 tasks include popups, cookie notices, delays, dynamic updates, or comparable interface interference;
- social interaction includes both Reddit-like and LinkedIn-like environments;
- transactional coverage uses simulations only and never real payment credentials or purchases; and
- near-duplicate intent templates and equivalent state transitions are counted once.

These are proposed audit constraints, not accepted quotas.

## Nested 20-task smoke hypothesis

The smoke set should be selected only after the primary manifest is stable. The provisional source split is:

- 4 REAL;
- 4 WebArena-Verified Hard;
- 3 VisualWebArena;
- 4 WorkArena++;
- 2 WebChoreArena;
- 2 WARC-Bench; and
- up to 1 deterministically verified WebForge task.

Smoke tasks should be stable and reasonably fast while still covering every adapter and major interaction mechanism. They do not need to estimate the primary score accurately.

## Regression-suite treatment

The initial regression suite should not be all 100 tasks. It should begin with stable tasks that the accepted baseline passes repeatedly and with infrastructure invariants such as reset and verifier checks. When a previously failing primary task is fixed, it can be promoted only after:

1. repeated success under the treatment;
2. no regression in the existing suite;
3. a valid implementation audit;
4. verifier and environment checks; and
5. confirmation on a broader evaluation than the motivating task alone.

This preserves the gate-and-promotion discipline from `auto-harness` while avoiding a regression suite that is impossible for the initial baseline to satisfy.

## Task-level execution plan

Before freezing the 100 tasks:

1. Export a candidate pool of roughly 200–250 tasks from the proposed sources.
2. Pin upstream commits, environment images, task revisions, evaluator revisions, and licenses.
3. Complete one [task audit record](TASK_AUDIT_TEMPLATE.md) per candidate.
4. Run oracle or human completion trials and verify reset behavior.
5. Generate deliberate near-miss, false-completion, and shortcut trajectories for the evaluator.
6. Run a simple baseline and a known strong harness with exact protocol records.
7. Prefer tasks on which the strong harness remains below 80% repeated success; prioritize the 10–70% band when the environment and verifier are reliable.
8. Reject tasks that are broken, saturated, unsafe, dependent on hidden benchmark leakage, or dominated by retrieval rather than interaction.
9. Select the exact 100 and replacement pool by coverage, not by benchmark quotas alone.
10. Select the nested 20 smoke tasks from the frozen 100 and present the manifest for explicit approval.

## Falsification conditions for the proposed portfolio

The recommendation should be revised if:

- REAL does not expose enough deterministic hard action tasks;
- WebArena-derived tasks remain too correlated after deduplication;
- WorkArena cannot be provisioned and reset reliably;
- WebChore evaluators cannot meet the judge-calibration standard;
- WARC-Bench tasks are too short-horizon, duplicated, or shortcut-prone to provide ten useful slots;
- WebForge tasks cannot be independently verified;
- a known strong harness already exceeds 80% on most selected tasks;
- EntWorld, RiskWebWorld, or another source becomes runnable and offers better diversity or verification than an allocated source; or
- the resulting suite undercovers a failure class central to the project charter.

## Research conclusion

Proceed to task-level inventory using the proposed 20/20/15/20/10/10/5 allocation, but keep ADR-0008 in **Proposed** status. The next legitimate decision is not “accept these benchmarks wholesale”; it is whether the audited candidate pool supports an exact, runnable, verifier-sound 100-task manifest.
