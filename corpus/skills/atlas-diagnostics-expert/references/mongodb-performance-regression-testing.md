<!-- hub-reference-banner -->
> **Reference file — part of the `atlas-diagnostics-expert` hub.** Sibling of
> `mongodb-performance-benchmarking.md` (tools, workload characterization, Atlas tier
> selection) and `mongodb-performance-troubleshooting.md` (live symptom diagnosis). This file
> is the **methodology layer above benchmarking**: what to do with two (or many) benchmark
> runs to decide, defensibly, whether performance actually got worse. It is not statistical
> regression modeling (GLMs) — see `da-analytical-methods` for that — and it does not
> re-document YCSB/Locust/k6/sysbench mechanics, which live in the benchmarking reference.

---
name: mongodb-performance-regression-testing
title: MongoDB Performance Regression Detection and Testing Methodology
version: "1.0.0"
updated: "2026-07-14"
category: mongodb
description: >
  MongoDB performance regression detection and testing methodology — the analysis layer
  applied on top of benchmark results to decide, with statistical defensibility, whether a
  MongoDB/Atlas deployment got slower after a version upgrade, schema/index change, config
  change, or driver bump. Covers baseline capture and versioning discipline, run-to-run noise
  vs. real signal (coefficient of variation, Welch's t-test, change point detection),
  CI perf-gating patterns and flaky-benchmark mitigation, canary/shadow-traffic comparison
  techniques, and the MongoDB-specific case of detecting a real regression after a 7.0→8.0 (or
  any N→N+1) major-version bump. TRIGGER: "did this upgrade make things slower or is it noise",
  "how do I know this regression is real", "compare benchmark runs across MongoDB versions",
  "set a threshold for failing a perf-regression gate", "shadow/canary test a MongoDB version
  or config change before cutover", "detect a real 7.0→8.0 (or similar) regression vs. run
  variance". SKIP: the benchmarking tools and workload taxonomy themselves (YCSB/Locust/k6/
  sysbench, tier selection, connection-pool sizing) — use mongodb-performance-benchmarking;
  live symptom-driven troubleshooting of an already-slow production system — use
  mongodb-performance-troubleshooting; the upgrade procedure/FCV mechanics themselves — use
  mongodb-operations-expert (references/mongodb-upgrade-paths.md); statistical regression
  modeling / GLMs — use da-analytical-methods.
tags:
  - performance-regression
  - regression-testing
  - change-point-detection
  - continuous-benchmarking
  - ci-perf-gating
  - canary-testing
  - shadow-traffic
  - upgrade-validation
  - statistical-significance
keywords:
  - performance regression detection
  - regression testing methodology
  - change point detection
  - ED-PELT
  - Welch's t-test
  - coefficient of variation
  - continuous benchmarking
  - CI perf gate
  - flaky benchmark
  - shadow traffic
  - canary deployment
  - dual read dual write
  - MongoDB 7.0 to 8.0
  - MongoDB upgrade regression
  - baseline versioning
  - minimum detectable effect
whenToUse:
  - Deciding whether a benchmark delta after a MongoDB version upgrade is a real regression or run-to-run noise
  - Designing a CI gate that fails a build/release on a genuine performance regression without flaking on noise
  - Setting up a canary or shadow-traffic comparison before cutting over to a new MongoDB version, index, or config
  - Establishing a versioned baseline-capture practice so "before" is always available for comparison
  - Investigating a customer-reported "it got slower after the upgrade" claim with statistical rigor
  - Choosing a statistical method (t-test vs. change point detection) for a given regression-testing situation
whenNotToUse:
  - Picking a benchmarking tool or characterizing a workload — use mongodb-performance-benchmarking
  - Diagnosing an already-slow production system with no before/after comparison — use mongodb-performance-troubleshooting
  - The mechanics of a MongoDB major-version upgrade itself (FCV, rolling upgrade order, driver compatibility) — use mongodb-operations-expert (references/mongodb-upgrade-paths.md)
  - The specific, ticket-level MongoDB 7.0-vs-8.0 regression/engine-change catalog — use mongodb-expert (references/mongodb-80-performance-changes.md)
  - Statistical regression modeling (GLMs, mixed models) — use da-analytical-methods
related_skills:
  - atlas-diagnostics-expert
  - mongodb-operations-expert
  - mongodb-expert
  - da-analytical-methods
verified-as-of: "2026-07-14"
---

# MongoDB Performance Regression Detection and Testing Methodology

## Overview

Benchmarking (see `mongodb-performance-benchmarking.md`) produces numbers. This reference is
about what happens next: given two (or many) sets of benchmark results — before/after a
MongoDB version upgrade, an index change, a config change, or a driver bump — how do you
decide, defensibly, whether performance actually got *worse*, as opposed to run-to-run noise?

This is a **methodology problem, not a modeling problem**. It does not involve fitting a
statistical regression model (GLM) to data — that concept lives in `da-analytical-methods`.
"Regression" here means the older software-engineering sense: a measured capability that used
to hold and no longer does, applied to performance instead of correctness.

MongoDB's own engineering team has invested more in this exact problem than almost any other
production practice discussed in this hub, and has published in detail about it — their
account is the anchor primary source for this reference.[^1]

## Core Concepts

### Why naive before/after comparison fails

No two runs of the same benchmark, on the same hardware, produce identical numbers. Modern
systems have layers of non-determinism — CPU dynamic frequency scaling, OS scheduling, cache
warmth, network jitter, noisy neighbors on shared cloud instances, memory-layout ASLR — that
stack up into **run-to-run variation** (measurement noise).[^1][^2] A benchmark showing "5%
faster" might be a real improvement, might be noise, or might be masking a real regression
underneath a larger amount of noise in the other direction.[^1]

MongoDB's team started (in 2015) with the simplest possible approach — flag any run that
differs from the prior run by more than a fixed threshold (originally 10%) — and found it
"awful": it missed small regressions, threw false positives on noisy tests, and sometimes
flagged real changes at the wrong commit.[^1] The fundamental problem: a fixed-threshold
direct comparison answers the wrong question ("did the numbers move more than X%?") instead of
the right one ("which change altered performance?").[^1]

### Change point detection (CPD)

**Change point detection** is the general statistical problem of finding when the underlying
distribution of a time series shifted, in the presence of noise — the same class of problem
used to detect shifts in electricity consumption, stock prices, or weather.[^1][^3] Applied to
a stream of benchmark results ordered by commit, CPD finds the exact point in the series where
performance stepped to a new level, distinguishing that step from ordinary noise around a
stable mean.

MongoDB adopted CPD after two summer interns (2017) reviewed the change-point literature and
built a working prototype; production rollout followed a proof-of-concept comparison against
the old fixed-threshold system, which the CPD approach "clearly" beat.[^1] MongoDB has since
published multiple peer-reviewed papers on this system (ICPE 2020, DBTest.io 2020, ICPE 2021)
and open-sourced their performance-test result corpus as a research dataset via the SPEC
Research Group's ICPE Data Challenge Track.[^1]

The **e-divisive (ED-PELT)** algorithm is a commonly cited, effective change-point method for
noisy benchmark time series: it handles non-normal distributions and detects multiple change
points in one pass, which suits how real benchmark histories look (a series of step changes,
not one clean before/after).[^4] The open-source **Hunter** tool (SPEC ICPE 2023) implements
CPD specifically to "hunt" for performance regressions and improvements in time-series
benchmark data.[^5] **Apache Otava** (incubating; formerly Nyrkio) packages CPD as a
standalone performance-change-point-detection service usable outside any one company's
internal tooling.[^4]

### Run-to-run noise: quantifying it before trusting a number

Before applying any statistical test, quantify how noisy your own measurement pipeline is,
using the **coefficient of variation (CoV)** — standard deviation divided by the mean, as a
percentage. A CoV of ~12% on a benchmark means "before/after" deltas smaller than roughly that
much are indistinguishable from noise without a lot more samples.[^2]

A documented case: a Java/Spring instrumentation-overhead benchmark measured with a 20-second
warmup and 15 one-second samples had an 11.80% CoV — "far too noisy to detect real changes."
Root cause: JIT warmup was far from complete at 20 seconds. Extending warmup to 160 seconds,
collecting ≥30 samples per run, and rerunning ≥5 times to average out random initial-state
effects (cache layout, memory placement) cut CoV from 11.80% to 2.94% — a 4x improvement from
benchmark design alone, before any environment-level noise control.[^2]

**Environment-level noise control** (bare-metal instances instead of shared VMs, CPU affinity/
pinning, disabling SMT, disabling dynamic frequency scaling/Turbo Boost, deliberate cache
warm/cold state) compounds with benchmark-design controls. In one measured example, disabling
SMT cut CoV on a CPU-bound task from ~24% to ~0.04–0.24% — a 100x to 540x reduction depending
on which of the two paired tasks was measured; disabling dynamic frequency scaling cut
single-task CoV roughly 10x.[^2] MongoDB's own engineering blog on
reducing EC2 performance-test variability is cited as a reference implementation of this
practice.[^2][^1]

### Statistical significance vs. practical significance

**Welch's t-test** is the standard formal test for "is this before/after difference real, or
could it plausibly be noise": it computes a test statistic that is (roughly) the ratio of the
mean difference to the standard error, and compares it against a critical value set by your
chosen false-positive rate (alpha).[^2] MongoDB's own 7.0/8.0 performance program used a related
**Z-score** threshold (Z > 1) as its practical significance bar for accepting a proposed
performance fix — some proposed 7.0 fixes were rejected specifically because they "didn't
deliver statistically significant performance improvements."[^6]

**Which method fits which situation:** a two-sample test (Welch's t-test or equivalent) fits a
clean, single before/after comparison — exactly the shape of a version-upgrade evaluation (one
"before" version, one "after" version, N runs on each side). Change point detection fits a
different shape: a continuous time series of results ordered by commit or build, where there
is no single clean "before" and "after" to compare, only a stream that may contain zero, one,
or several unlabeled shifts somewhere in its history — the shape produced by continuous
benchmarking in CI.[^2] Use a two-sample test when you already know which two points you're
comparing (a version bump, a config change); use CPD when you're monitoring an ongoing stream
and need it to tell you *where* a shift happened.

The key caveat, stated directly by practitioners in this space: **a statistically significant
result tells you the difference is unlikely to be exactly zero — not that it is large or
practically meaningful.** Always pair a significance test with an effect-size number. A 0.1%
improvement can be "statistically significant" with enough samples and still not be worth
shipping the added code complexity for.[^2] The inverse also holds for regressions: a
technically-significant but operationally tiny regression may not warrant blocking a release,
while an operationally large one under the significance threshold (because the test was
underpowered — too few samples) should not be waved through either.

### Minimum detectable effect and sample size

Before trusting "no regression detected" as a verdict, know what size of regression your test
setup could even detect. A test with high noise (high CoV) and few samples has a large
**minimum detectable effect (MDE)** — it can only reliably catch large regressions and will
systematically miss small ones. The practical levers to shrink MDE, in order of typical
leverage: (1) reduce environment noise (bare metal, CPU pinning, disabled SMT/DFS — often a
10–100x variance reduction[^2]), (2) fix benchmark-design issues (adequate warmup, N≥30
samples per run, M≥5 reruns[^2]), (3) only then consider a more sensitive statistical test or
more samples. A regression-testing program that skips (1) and (2) and tries to compensate
purely with more statistical sophistication is optimizing the wrong variable.

### CI perf-gating patterns

**Continuous Benchmarking (CB)** is the performance analogue of Continuous Integration: run
performance tests on every (or most) code changes, verified automatically, to catch
performance regressions before they reach production — the same argument Martin Fowler made
for CI applied to performance instead of correctness.[^7] "Performance bugs are bugs."[^7]

Concrete, documented CI perf-gating patterns:

- **Revert-on-regression thresholds.** MongoDB's CI reverts any commit that regresses their
  most-important benchmarks by more than a fixed percentage (historically 5%) — a coarse gate
  that catches large regressions immediately but, by construction, cannot catch the ~9,000+
  commits/release scale of tiny (0.1%-class) regressions that accumulate into meaningful loss
  over time.[^6]
- **Low-noise micro-signals for small regressions.** To catch sub-percent regressions without
  drowning in false positives from noisy wall-clock measurements, MongoDB built a benchmark
  that counts CPU instructions (via the Linux `perf_event_open` syscall) executing a simple
  MongoDB `ping` command in a loop, instead of measuring wall-clock latency/throughput.
  Instruction counts are near-deterministic on the same hardware, so this test runs with a
  0.2% tolerance — tight enough to catch tiny regressions, without becoming a flaky/ignored
  test.[^6] The general pattern: **when you need to catch very small regressions, look for a
  lower-noise proxy metric (instruction count, syscall count, allocation count) rather than
  trying to statistically rescue a noisy wall-clock signal.**
- **Patch builds / pre-merge verification.** Developers can run the full regression-detection
  pipeline against a proposed, not-yet-merged change ("patch build" in MongoDB's Evergreen CI)
  before committing — shifting regression detection left, from post-merge triage to pre-merge
  gating.[^1]
- **Bare-metal CI runners for repeatable comparison.** General-purpose CI runners (shared,
  virtualized) are measurably noisier than dedicated/bare-metal runners — one continuous-
  benchmarking vendor cites >30% run-to-run variance on shared GitHub Actions runners vs. <2%
  on their bare-metal runners.[^7] Running the *exact same* hardware for local dev and CI
  comparison (not just "CI vs. CI") removes an entire class of "works on my machine, regresses
  in CI" ambiguity.[^7]
- **Flaky-benchmark mitigation.** The same anti-flake principles used for correctness tests
  apply to perf tests: fix inputs (deterministic, not random, benchmark data[^2]), rerun
  multiple times and report a robust statistic (median across ≥3–5 runs, not the single best
  run[^2][^8]), and prefer a benchmarking harness/dedicated runner over ad hoc scripts on
  shared infrastructure specifically because harness-level warmup and pinning logic is where
  most flake gets eliminated.[^2][^7]

### Canary and shadow-traffic comparison

Where a synthetic benchmark cannot fully capture production reality (real query-shape mix,
real data skew, real concurrency), compare a candidate version/config against the current one
using **real production traffic**, without exposing users to risk:

- **Shadow (dark) traffic testing**: mirror a copy of live production traffic to the candidate
  system (e.g., a new MongoDB version, a re-indexed collection, a new driver version) and
  compare response latency/content against the current system, without ever serving the
  candidate's response to a real user.[^9] Purpose-built tools (e.g., GoReplay) capture traffic
  at the network layer, replay it against a target, and compare responses/latency;
  request/response scrubbing middleware is used to avoid replaying sensitive data into a
  non-production target.[^9]
- **Dual-read / dual-write validation during a migration**: when running old and new systems
  in parallel during a cutover (e.g., MongoDB version migration, or database-platform
  migration), issue every read (and sometimes write) to both systems and diff the responses
  and latencies — this is standard practice specifically called out as "critical" during
  high-traffic production database migrations.[^10]
- **Comparison-library pattern (GitHub's "Scientist")**: wrap the call site so that, for a
  sampled fraction of real requests, both the old code path and the new code path execute; the
  old path's result is what's actually returned to the user (safety), while the new path's
  result and timing are recorded for offline comparison — used specifically to validate
  behavioral and performance parity of a new implementation against production traffic before
  fully cutting over.[^11]
- **General shadow-deployment framing**: mirroring real traffic to a build under test gives
  production-grade performance signal without user-facing risk, at the cost of doubled
  resource consumption for the shadow path and the engineering effort to safely discard its
  side effects (writes, external calls) if it must not affect real state.[^12]

For a MongoDB-specific cutover (e.g., validating a new Atlas tier, a new index, or a version
upgrade before flipping production traffic), the same dual-read pattern applies at the
application or driver layer: route a sampled fraction of reads to both the old and new
cluster/config, and compare `explain()` output, latency percentiles, and (if feasible)
result-set equality, before fully cutting over.

## Methodology: applying this to a MongoDB version upgrade (e.g., 7.0 → 8.0)

This is the direct MongoDB application of everything above. Detecting a *real* regression
after a major-version bump — as opposed to noise, a misconfiguration, or an unfair comparison
baseline — requires all of the following:

1. **Establish which version you're actually comparing against, explicitly.** Vendor
   "N% faster" claims are usually relative to the immediately preceding major version, not to
   whatever version the customer is currently running. MongoDB's own engineering blog is
   explicit that "8.0 is 36% faster in read workloads... than MongoDB 7.0"[^6] — the comparison
   base is stated there — but that qualifier is easy to drop in secondary coverage or in a
   reader's own recollection of the headline number, which is exactly the gap a public critique
   of the claim called out.[^13] A customer upgrading directly from an older version (a common
   "straight-to-8"-style jump — see `mongodb-operations-expert` for that upgrade path) should
   not assume a "faster than 7.0" figure describes their own upgrade delta from, say, 4.4 or
   5.0 — as the write-concern-driven regression documented immediately below shows, jumping
   multiple versions can introduce behavior changes the single-version comparison never
   measured.[^14] Always ask/state "faster than which version, on which benchmark" before
   accepting or citing a headline number.
2. **Re-benchmark on your own representative workload and data, not just trust the release
   note.** MongoDB's internal benchmarking runs industry-standard workloads (YCSB, Linkbench,
   TPCC, TPCH) *and* custom benchmarks derived from real customer workloads, because
   industry-standard workloads alone did not fully represent what regresses in practice.[^6]
   The `mongodb-performance-benchmarking` reference's baseline-methodology section (matching
   production data volume, schema, indexes, and document shape) is the prerequisite step here
   — a regression-testing verdict is only as good as the benchmark it's built on.
3. **Know the upgrade-sensitive defaults before you benchmark.** Several MongoDB major-version
   bumps changed a default that materially affects write latency, independent of any engine
   regression:
   - **5.0**: default write concern changed from `w:1` to implicit `"majority"` for replica
     sets and sharded clusters — this alone can look like a severe write-throughput regression
     if a benchmark or workload was implicitly relying on the old `w:1` default, because the
     primary now waits for a majority-acknowledged (and, depending on
     `writeConcernMajorityJournalDefault`, journaled) write instead of a local one.[^14]
     A documented case: a 1M-document insert loop ran at ~4,500 ops/sec (~4–5 minutes total)
     under v4.4 defaults and dropped to ~250 ops/sec (~127 minutes total) under v7.0 defaults
     on the *same single-member replica set* — an ~18x throughput drop (~27x longer wall-clock
     duration), entirely attributable to the majority/journal write-concern default change,
     confirmed via flamegraph showing the Journal Flusher as the bottleneck, and reproduced by
     explicitly setting `writeConcern: 1` (which restored the original ~10-minute runtime).[^14]
     This is **not a MongoDB engine regression** — it is a durability-for-performance tradeoff
     baked into the new default — but it is exactly the kind of result a naive before/after
     benchmark comparison will flag as a severe regression, so the regression-testing
     methodology must separate "default behavior change" from "engine regression" before
     escalating.
   - **7.0's SBE (slot-based query execution engine) rollout** is associated with multiple,
     still openly discussed community reports of real query-latency regressions after
     6.0→7.0 upgrades. One report on identical hardware, with the number of scanned/returned
     documents unchanged, went from 2ms to 50ms (a 25x increase) for the same indexed query;
     other reports describe going from sub-second to multi-minute execution for the same
     query shape after upgrading (order-of-magnitude-larger regressions). In every case,
     downgrading to 6.0 reliably restored the prior performance.[^15] These reports remained
     open and unresolved in MongoDB's community forum for over a year, with users reporting
     they postponed or reversed their 7.0 upgrade specifically because of this.[^15] Treat
     community-forum "performance drop after upgrade" threads as a *leading indicator* worth
     searching before a customer upgrade — they surface exactly the query-shape-specific
     regressions (in the reports read for this reference, large `$or` clause counts were
     implicated at least once) that a generic industry-standard benchmark (YCSB workload A–F)
     may not reproduce.
   - **8.0's stated performance program** deliberately targeted regaining ground lost across
     the 5.0→7.0 default-write-concern transition and closing thousands of small per-commit
     regressions, using the Z-score and instruction-count gating methodology above; MongoDB
     explicitly did not ship 7.0 until it matched 6.0's performance on its most important
     benchmarks, and set the bar for 8.0 at matching 4.4's performance.[^6] This is useful
     context for reading any "version X is faster" claim: it may describe *recovering* lost
     ground from several versions back, not a new absolute high. For the specific,
     ticket-level 7.0-vs-8.0 regression/engine-change catalog (SBE-vs-classic default flip,
     TCMalloc rewrite, express-path plans, named SERVER tickets, and a ready-made 7→8
     diagnostic checklist) — as opposed to the general methodology this file covers — see
     `mongodb-expert` (`references/mongodb-80-performance-changes.md`); that reference's own
     net assessment is that no widespread, confirmed 8.0 read-latency regression vs. 7.0
     exists in the public record as of its research date, which is itself a useful
     data point when a customer asserts otherwise.
4. **Re-benchmark the specific metrics known to be upgrade-sensitive**, not just an aggregate
   ops/sec number: write latency (majority/journal-related), simple `_id`-lookup / point-query
   latency (IDHACK/ExpressPlan-class optimizations changed across 7.0→8.0[^6]), replication
   apply latency, and any query shape using `$or` with a large number of clauses (implicated in
   at least one community-reported SBE regression[^15]).
5. **Cross-check FCV state.** A cluster can be running new binaries while pinned to the old
   Feature Compatibility Version; some reported "no regression" or "regression only after FCV
   bump" results in the community threads are explicitly tied to whether `setFeatureCompatibilityVersion`
   had been raised yet.[^15] Confirm FCV state as part of recording *which* configuration was
   actually benchmarked — see `mongodb-operations-expert` (`references/mongodb-upgrade-paths.md`)
   for FCV mechanics themselves.
6. **Apply the change-point / significance methodology above, not a single before/after
   sample.** Capture ≥3–5 runs pre-upgrade and ≥3–5 runs post-upgrade (median, not best-of),
   compute CoV on each side first, and only then judge whether the delta exceeds what noise
   alone would produce. If pre-upgrade noise is unknown, you cannot honestly say whether a
   post-upgrade delta is real.
7. **Use a canary/shadow-read comparison for the final go/no-go**, where feasible: run the
   candidate version alongside the current one (secondary member, or a shadow read path) under
   real production query shapes before fully cutting the primary role over, per the
   canary/shadow-traffic techniques above.

## Practical Patterns

- **Version every baseline.** Store benchmark results tagged with exact MongoDB version,
  storage engine/query-engine mode (e.g., SBE vs. classic), FCV, write concern, hardware/tier,
  and dataset fingerprint (size, schema, index set) — not just a date. A baseline you cannot
  attribute to an exact configuration is not reusable for the next comparison.
- **Separate "default changed" from "engine regressed."** Before escalating any upgrade
  regression, explicitly test with the old default restored (e.g., `writeConcern: 1` instead
  of majority) to see whether the "regression" disappears — if it does, it's a durability
  tradeoff decision for the customer, not a bug to chase.[^14]
- **Report a distribution, not a mean.** Two means that look 2.3% apart can come from heavily
  overlapping distributions and be statistically indistinguishable — always look at (or plot)
  the individual measurements, not just the summary mean.[^2] Strip plots (one dot per sample)
  reveal bimodality and outlier clusters that a mean or even a boxplot hides.[^2]
- **Match the CI gate strategy to the risk.** A combination — lightweight benchmarks gating
  every PR/commit, comprehensive macrobenchmarks run nightly, deep on-demand investigation for
  suspected regressions — is the pattern used in practice, rather than one gate tier trying to
  do everything.[^2]
- **Prefer a low-noise proxy metric when chasing sub-1% regressions.** Wall-clock latency
  under real scheduling/network noise cannot reliably resolve changes below roughly its own
  CoV; an instruction-count or similarly deterministic proxy can, at the cost of not directly
  measuring user-facing latency.[^6]

## Anti-Patterns

1. **Trusting a single before/after run.** One sample on each side cannot distinguish "real
   regression" from "this run happened to land in the noisy tail." Always use multiple runs
   and report a robust statistic (median).[^1][^2]
2. **Citing a vendor's relative-improvement percentage as your own expected delta.** "X% faster
   than the previous version" says nothing about your upgrade unless you are also jumping
   exactly one version and your workload matches the benchmark used to produce that number.[^13][^14]
3. **Ignoring the comparison baseline ambiguity.** If a regression-testing report doesn't state
   which exact version, workload, and configuration a percentage is relative to, treat the
   number as directional marketing, not an engineering input.[^13]
4. **Fixed-percentage thresholds with no noise-awareness.** A flat "fail if >10% slower" gate
   both misses small real regressions on noisy tests and false-positives constantly on tests
   whose natural noise exceeds the threshold — MongoDB's own history is a documented case study
   of this exact anti-pattern and why they moved to change-point detection instead.[^1]
5. **Benchmarking on shared/virtualized infrastructure and trusting sub-5% deltas.** Reported
   noise differentials between shared CI runners and bare-metal runners can exceed 30% vs.
   <2%[^7] — a "regression" inside that band, measured on shared infrastructure, is
   unfalsifiable without a re-run on quieter hardware.
6. **Treating a default-behavior change (e.g., write concern) as an engine regression** without
   first testing with the old default explicitly restored.[^14]
7. **Skipping the FCV check.** Comparing "before" (old binary, old FCV) against "after" (new
   binary, FCV not yet raised) silently under-tests the real upgrade — FCV state changes engine
   behavior independent of the binary version.[^15]
8. **Treating statistical significance as sufficient justification to ship or block a change**
   without also checking effect size — a significant-but-tiny result may not be worth acting
   on, and an operationally large-but-underpowered result should not be waved through as
   "not significant."[^2]

## Troubleshooting: "the customer says it's slower after the upgrade"

1. Get the exact before/after versions, FCV state on both sides, and write concern
   configuration — not just "we upgraded MongoDB."
2. Ask whether the specific default write-concern/journal behavior changed between their old
   and new version (any jump crossing the 5.0 boundary is the first thing to check).[^14]
3. Search MongoDB's community forum for the specific version pair — community-reported,
   still-open regression threads exist for at least 6.0→7.0 (SBE-related query latency).[^15]
   If a hit exists, this shortcuts significant diagnostic effort.
4. Reproduce with the customer's actual query shapes and dataset scale (per
   `mongodb-performance-benchmarking`'s baseline methodology), not a generic workload — the
   documented 6.0→7.0 regressions were often shape-specific (e.g., large `$or` clause
   counts[^15]), not a uniform slowdown.
5. Quantify noise on both sides (CoV across ≥3 runs each) before asserting the delta is real.
6. If real and reproducible, check whether downgrading (binary only, not FCV, if FCV wasn't
   raised) restores performance — this isolates engine-version behavior from data/schema
   drift that happened to occur around the same time.
7. Escalate to `mongodb-performance-troubleshooting` for live symptom-level diagnosis
   (explain plans, profiler, FTDC) once the regression is confirmed real and reproducible; use
   this reference again only for the before/after comparison judgment itself.

## References

[^1]: [Using Change Point Detection to Find Performance Regressions — MongoDB Engineering Blog](https://www.mongodb.com/company/blog/engineering/using-change-point-detection-find-performance-regressions) — primary account of MongoDB's internal regression-detection system, its history (2015 fixed-threshold → 2017 CPD prototype → production), and its published research.
[^2]: [Measuring Software Performance: Why Your Benchmarks Are Probably Lying — kakkoyun.me (FOSDEM 2026 Software Performance Devroom)](https://kakkoyun.me/posts/fosdem-2026-measuring-software-performance/) — environment-noise control, benchmark-design controls (warmup, N/M sample counts), Welch's t-test, CoV data, change-point detection (ED-PELT), tool landscape.
[^3]: [Change detection — Wikipedia](https://en.wikipedia.org/wiki/Change_detection) — general definition of the change-point-detection problem class, cited by MongoDB's own account.
[^4]: [Apache Otava (incubating) announcement — Nyrkio blog](https://blog.nyrkio.com/2025/05/08/welcome-apache-otava-incubating-project/) — ED-PELT-based change-point-detection service, cited via kakkoyun.me's tool list.
[^5]: [Hunter: Using Change Point Detection to Hunt for Performance Regressions — SPEC ICPE 2023 proceedings](https://research.spec.org/icpe_proceedings/2023/proceedings/p199.pdf) — open-source CPD tool for time-series benchmark regression/improvement detection.
[^6]: [MongoDB 8.0: Improving Performance, Avoiding Regressions — MongoDB Engineering Blog](https://www.mongodb.com/company/blog/engineering/mongodb-8-0-improving-performance-avoiding-regressions) — MongoDB's internal 7.0/8.0 performance program: revert-on->5%-regression CI gate, Z-score significance bar, the low-noise instruction-count benchmark (0.2% tolerance), IDHACK/ExpressPlan optimization, replication-latency change.
[^7]: [What is Continuous Benchmarking? — Bencher docs](https://bencher.dev/docs/explanation/continuous-benchmarking/) — CB-as-CI-for-performance framing, bare-metal-runner noise comparison (>30% vs. <2%), CB vs. APM/observability/load-testing distinctions.
[^8]: MongoDB's own median-of-100-samples benchmark-reporting convention — cross-referenced in `mongodb-performance-benchmarking.md` §Statistical Significance.
[^9]: [Shadow Testing with GoReplay — goreplay.org](https://goreplay.org/shadow-testing/) — dark-traffic mirroring architecture, response comparison, performance monitoring between current/candidate versions.
[^10]: [How to Handle a Production Database Migration with High Traffic — Medium/Predict](https://medium.com/predict/how-to-handle-a-production-database-migration-with-high-traffic-c6290b01e60f) — shadow-read validation as a stated requirement during dual-database migration cutover.
[^11]: [Authorization Migrations: From Chaos to Clarity with Oso — Oso blog](https://www.osohq.com/post/launching-oso-migrate) — describes the GitHub "Scientist" comparison-library pattern for validating new-code-path behavior/performance against production traffic before cutover.
[^12]: [Shadow deployment: Risk-free performance comparison — Statsig Perspectives](https://www.statsig.com/perspectives/shadow-deployment-comparison) — general shadow-deployment framing, tradeoffs (doubled resource cost, side-effect handling).
[^13]: [MongoDB 8.0 Performance is 36% higher, nope it's not! — dev.to](https://dev.to/manoj_from_revisit_dot_tech/mongodb-80-performance-is-36-higher-nope-its-not--35jk) `verified-as-of: 2026-07-14` — critique noting the MongoDB 8.0 "36% faster" claim's comparison base (7.0, not the reader's own current version) is not stated in the headline claim, and links the same community regression thread cited below.
[^14]: [MongoDB Performance Regression Benchmarking and the Truth Behind Journaling — Percona Blog](https://www.percona.com/blog/mongodb-performance-regression-benchmarking-and-the-truth-behind-journaling/) — documented v4.4→v7.0 benchmark showing a ~4.5-minute vs. ~127-minute 1M-document insert delta, root-caused via flamegraph to the majority/journal write-concern default change, and reversed by explicitly setting `writeConcern: 1`; links the relevant MongoDB JIRA tickets (SERVER-92018, SERVER-91298).
[^15]: [Performance Drop After Upgrade 6.0.10 > 7.0.1 — MongoDB Community Forum](https://www.mongodb.com/community/forums/t/performance-drop-after-upgrade-6-0-10-7-0-1/246712) `verified-as-of: 2026-07-14` — multi-year, multi-user community thread reporting real, reproducible 6.0→7.0 query-latency regressions (including SBE `queryFramework` explain output, large-`$or`-clause query shapes, and FCV-state-dependent reports), several confirming that downgrading to 6.0 restored performance and that they postponed or avoided the 7.0 upgrade as a result.

## See Also

- [[mongodb-performance-benchmarking]] — benchmarking tools (YCSB/Locust/k6/sysbench), workload characterization, Atlas tier selection, and baseline-capture methodology this reference builds on
- [[mongodb-performance-troubleshooting]] — live symptom diagnosis once a regression is confirmed real
- `mongodb-operations-expert` (`references/mongodb-upgrade-paths.md`) — the upgrade procedure itself: version paths, FCV mechanics, rolling-upgrade order, driver compatibility
- `mongodb-expert` (`references/mongodb-80-performance-changes.md`) — the specific, ticket-level MongoDB 7.0-vs-8.0 regression/engine-change catalog (SBE-vs-classic flip, TCMalloc, express-path plans, named SERVER tickets, diagnostic checklist); this file is the general methodology, that one is the version-pair fact base
- `da-analytical-methods` — statistical regression modeling (GLMs) — a different concept from the regression-*testing* methodology in this file
