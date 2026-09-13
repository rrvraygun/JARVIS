---
name: system-benchmark
description: Design, execute, or interpret safe and reproducible CPU, memory, storage, network, graphics, application, boot, or power benchmarks. Use for performance baselines, regressions, upgrade comparisons, capacity planning, or bottleneck validation; avoid destructive storage tests and uncontrolled stress.
---

# System benchmark

1. Define the decision, metric, workload, baseline, acceptable variance, and stop
   conditions. Read [benchmark-safety.md](references/benchmark-safety.md).
2. Record hardware/software versions, power profile, temperature, background
   load, storage free space, and tool version.
3. Prefer representative application workloads. Use warmups and repeated trials.
4. Request approval for material stress, network traffic, battery drain, paid
   resources, or writes. Never run raw-device or destructive tests.
5. Monitor safety limits and stop on errors, dangerous thermals, throttling that
   invalidates the run, or unexpected system impact.
6. Report raw results, aggregation, variance, confounders, and comparability.
