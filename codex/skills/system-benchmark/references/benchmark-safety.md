# Benchmark safety

Use dedicated temporary files on an explicitly approved mounted filesystem for
storage writes; validate available capacity and delete only the exact created
file after results are secured. Never target a block device. Define duration,
concurrency, temperature, memory, and latency limits. Do not compare results from
different versions, power profiles, thermal states, or workloads without naming
the confounder.
