# Benchmarking VM launch latency

Use `slicer bench` to measure how long Slicer takes to launch a requested
number of VMs at once. It runs controlled experiments at explicit concurrency
levels, repeats each level independently, and summarizes successful per-VM
latencies. The command connects to a running Slicer API; it does not generate a
config or start the daemon.

Before constructing a run, inspect the installed command and the target:

```bash
slicer bench --help
slicer info
slicer vm group --json
```

If `bench` or a documented flag is unavailable, update the CLI or use a build
that includes the command. Do not translate examples from the old standalone
`slicer-bench` tool: its flags and experiment model are obsolete.

## Run the benchmark

The conservative defaults launch one VM at a time, repeat that experiment
three times, wait for guest-agent readiness, and delete each run's VMs before
starting the next run:

```bash
slicer bench
```

To measure scaling under load, provide comma-separated concurrency levels and
the number of independent runs per level:

```bash
slicer bench \
  --hostgroup sbox \
  --concurrency 1,5,10 \
  --runs 3
```

This performs nine independent runs: three each at concurrency 1, 5, and 10.
Within a run, create requests wait at a barrier and are released at
approximately the same time. After all observations for that run complete,
Slicer removes its VMs before proceeding. `--runs` is not a total launch count:
at concurrency 10 with three runs, the benchmark records 30 VM observations.

When `--hostgroup` is omitted, Slicer uses the first available host group
returned by the server. On Slicer for Mac, automatic selection skips the
persistent `slicer` group and selects the next group, normally `sbox`. Pass
`--hostgroup` explicitly whenever selection must be reproducible.

Use the standard API connection flags and environment variables: `--url`,
`--socket`, `--token`, `--token-file`, `SLICER_URL`, `SLICER_SOCKET`,
`SLICER_TOKEN`, and `SLICER_TOKEN_FILE`. An auth-disabled Unix socket needs no
token flag.

## Set up a dedicated Linux benchmark daemon

Generate the benchmark preset and start it in one terminal:

```bash
mkdir -p ~/slicer-bench
cd ~/slicer-bench
slicer new bch --bench > bench.yaml
sudo -E slicer up bench.yaml
```

Run the benchmark from another terminal in the same directory:

```bash
cd ~/slicer-bench
slicer bench --concurrency 1,5,10 --runs 3
```

The generated config uses the `bch` host-group name, zero initial VMs, the
minimal image, devmapper storage, isolated networking, 1 vCPU, 1 GiB RAM,
non-persistent disks, no graceful shutdown, no SSH-key discovery, and
`./slicer.sock` for the API.

Explicit `slicer new` flags override the related preset. Devmapper must already
be configured on the host; otherwise select a configured backend, for example:

```bash
slicer new bch --bench --storage image > bench.yaml
```

The minimal image is appropriate for launch-latency measurements but lacks the
broader kernel-module surface of the default image. Use an image representative
of the workload when measuring Docker, k3s, or another full-system use case.

## Choose the completion condition

`--wait` determines when an individual VM observation finishes:

| Mode | Measurement |
|------|-------------|
| `agent` (default) | From issuing create until the guest agent reports ready |
| `userdata` | From issuing create until userdata completes; use only with non-empty userdata |
| `none` | From issuing create until the create response returns, without guest readiness |

For example:

```bash
slicer bench --hostgroup bch \
  --concurrency 1,5,10 \
  --runs 3 \
  --wait userdata
```

Do not compare `--wait none` results with `agent` or `userdata` as though they
measure the same endpoint.

## Interpret the results

The default text output starts with a benchmark receipt and then summarizes all
successful VM observations at each concurrency level:

```text
Benchmarking VM launch to guest-agent readiness
Client: 0.1.227-8-ga64d271b-dirty-a64d271b973d302e441171920da9a9cb3e996663 (linux/amd64)
Server: 0.1.225-1-gd5a1f5fe-d5a1f5fe94b43474fbf3cb1353aed4b3ffef9e3e (linux/amd64)
Host group: sbox
VM config: ram=4GiB  cpus=2
Runs: 3

CONCURRENCY  P50    P95    MAX    FAILURES
1            0.85s  1.01s  1.01s  0/3
```

P50, P95, and MAX are calculated from the successful per-VM observations
across all runs at that concurrency. Percentiles use observed values rather
than interpolation. `FAILURES` is failed launches over total launches. If every
launch at a level fails, its latency columns contain `-`. Any launch failure
makes the command exit non-zero.

Use `-v` / `--verbose` to print every observation before the summary. Each row
shows concurrency, run number, VM hostname, duration, and status:

```bash
slicer bench --hostgroup bch --concurrency 1,5,10 --runs 3 --verbose
```

Use `--json` for automation. It emits one document containing:

- `receipt.client`: client version, commit, and platform
- `receipt.server`: server version, commit, and platform
- `receipt.vm`: selected host-group RAM bytes and CPU count
- benchmark configuration: `hostgroup`, `concurrency`, `runs`, `wait`, `keep`
- `observations`: concurrency, run, index, hostname, IP, duration, status, and
  any error
- `summary`: P50, P95, max, failures, and total per concurrency level

```bash
slicer bench --hostgroup bch --concurrency 1,5,10 --runs 3 --json \
  > results.json
```

JSON includes raw observations even without `--verbose`; verbose controls only
the text presentation.

## Cleanup and debugging

By default, Slicer removes every run's VMs after that run, including the final
run. Later experiments therefore start without VMs retained by the preceding
run. There are no configurable cleanup modes or between-run pause flags. Use
`--keep` only when the VMs must remain available for failure investigation:

```bash
slicer bench --hostgroup bch --concurrency 5 --runs 1 --keep
```

Kept VMs consume host resources and invalidate the clean-start assumption for
later comparisons. Inspect and remove them before another benchmark.

On SIGINT or SIGTERM, Slicer cancels active launches and attempts cleanup for
the current run unless `--keep` is set. A second signal, SIGKILL, client crash,
or cleanup failure can still leave benchmark-tagged VMs. Inspect tags with
`slicer vm list --json`, confirm ownership, and delete only the affected VMs.

## Report enough context to compare results

Retain the benchmark receipt and record at least:

- concurrency levels, runs, and wait mode
- image name and variant
- storage backend
- whether images and disks were already cached
- whether the host was otherwise busy

The receipt already captures client/server version and platform plus the
selected host group's RAM and CPU configuration. Use identical completion
conditions and comparable image, storage, resource, cache, and host-load
conditions when comparing runs.
