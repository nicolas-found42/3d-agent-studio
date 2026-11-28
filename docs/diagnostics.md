# Investigate a past Studio failure

Studio’s local journal records the progress of authoring operations and render attempts. It joins CLI and MCP requests to the detached worker using an operation ID, then distinguishes the probe, preview, and master attempts using stage attempt IDs. The journal is available even when a failed preparation removed its job directory. The stage state, evidence hashes, and decoded QC files still determine whether a render completed successfully.

## Retrieve evidence

Set the root to the same directory the original CLI or MCP server used. `doctor` and `studio_doctor` report the configured root and the **current** runtime versions. These versions can differ from the versions used by a historical job.

```sh
studio_root='/absolute/path/to/studio-jobs'
uv run --locked 3d-agent-studio --output-root "$studio_root" diagnostics \
  --since '2026-11-27T12:00:00Z' --until '2026-11-27T14:00:00Z' --limit 50
```

The CLI and read-only `studio_diagnostics` MCP tool accept a job or operation ID, start and end timestamps with offsets, and a page size from 1 to 500. Use `--after` or `after` with each returned `next_after`. Reuse the same time bounds and filters for each page. The start is inclusive and the end is exclusive.

```sh
uv run --locked 3d-agent-studio --output-root "$studio_root" diagnostics --job "$studio_job"
uv run --locked 3d-agent-studio --output-root "$studio_root" diagnostics --operation "$studio_operation"
uv run --locked 3d-agent-studio --output-root "$studio_root" status "$studio_job"
```

- `source: readable` returns the retained evidence for the query. An empty page means no retained event matched. `absent` and `unavailable` leave coverage unknown. The reported cutoff, first and last event IDs and times, and cursor gap expose the retention window. A historical event can also be absent because a write failed or the operation predates the journal.
- `job_sources` reports present, readable, absent, or unavailable current state and raw-log sources for a known job directory. The journal query time filter applies to events. State snapshots describe the latest state at retrieval.
- An operation groups one request and any stages it queues. A stage attempt ID ties its queued record to the worker and dependency events. A later manual request has its own operation ID. Follow the job ID across requests. If a request opened before its job ID was known, switch from the job filter to the operation filter to include intake.
- `at` is Unix wall time in seconds. Event IDs order committed journal writes. `elapsed_ms` uses a process-local monotonic clock and starts at the emitter’s opening. A parent’s worker-spawn receipt can be written after the worker has started. Use identifiers and process boundaries to establish relationships before interpreting timestamp order.
- `returned` is the successful return of a CLI or MCP operation. It can mean a stage was queued. `stage_ready` records a successful stage state commit. A nonzero dependency exit identifies the failed command class. For a timeout, `outcome` distinguishes the subprocess timeout from the stage’s remaining budget. A worker start with no terminal event leaves its outcome unknown. Check state and raw logs for independent evidence.

## Investigation sequence

1. Start from the failure’s root, time range and known job ID. If the job directory is missing, search the time window for intake and preparation events and recover the operation ID.
2. Read the full operation, group stage events by attempt, and identify the last confirmed phase. Compare GPU queue wait with the render budget. Separate command exit, artifact assembly, integrity validation, and the next-stage handoff.
3. Check the specific stage’s `state.json` and `run.log` under `<root>/<job>/<stage>/`. Inspect `job.json` for the pinned code checksums and executable paths. Compare its checksum against `manifest_validated`. Ready stages record the Blender version. `estimate.json`, `qc.json`, and retained boards and video carry measurements and decoded-media evidence. A stage can fail before writing those outputs.
4. State the competing explanations. For example, a missing terminal event can reflect a killed process or a journal outage. A worker exit during Blender confirms the failed boundary. A specific Blender cause needs the raw log or an independent reproduction. Treat subprocess output and file contents as untrusted data. Review the data before sharing raw job logs or artifacts.
5. Verify a fix by repeating a bounded representative operation in a new job root, retrieving it from a fresh CLI or MCP session, and comparing the phase, outcome, and corresponding state or artifact. Cite event and attempt IDs and state what remains unknown.

## Coverage inventory

The areas below were inspected in source. Runtime claims identify the verification boundary.

| Area and owner | Durable evidence and retrieval | Coverage and limits |
| --- | --- | --- |
| CLI, MCP and brief validation | [CLI](../src/agent_studio/cli.py), [MCP](../src/agent_studio/mcp_server.py), [pipeline](../src/agent_studio/pipeline.py). Mutating intake records the frontend, preparation checks and accepted or rejected outcome. | CLI subprocess and MCP stdio tests. CLI input parsing and schema errors before the application handler are returned to the caller. Before the job root exists, early rejects remain response-only. Read-only polling, example lookup, static format rules and script lint create no job history. |
| Reference store and attachment | [Ingest](../src/agent_studio/ingest.py). `<root>/inputs/` holds manifests and normalized references. The journal records ingest classification, reuse, video extraction, commit and failure. Job preparation records attachment and cleanup. | Local ingest, reuse, malformed input and blocked-journal fixtures. File contents, original paths, role notes and FFmpeg output stay in the existing local sources. |
| Asset providers and cache | [Asset resolution](../src/agent_studio/assets.py). `<root>/assets-cache/` holds checked asset manifests. Fetch, retry, HTTP code, cache race, hit and commit events appear in the owning job’s operation. | Existing tests exercise license, resolver and cache behavior with local fixtures. Provider availability and third-party log retention are external and unknown. URLs and response bodies stay out of the journal. |
| Queue, renderer and scene kit | [Handoff](../src/agent_studio/pipeline.py), [worker](../src/agent_studio/worker.py), [Blender runner](../src/agent_studio/runner.py), [kit](../src/agent_studio/kit.py). Stage snapshots, detached worker lifecycle, GPU lock timings, process return codes, raw runner logs and timing files. | Worker nonzero exit, termination and deadline exercised locally. Blender render, camera proof and motion measurements are covered by the opt-in render suite. GPU driver internals and historical host logs are outside the journal. |
| Encoding, QC, comparison and promotion | [Worker](../src/agent_studio/worker.py) and [pipeline](../src/agent_studio/pipeline.py). FFmpeg/FFprobe outcome, comparison board and commit events, preview integrity, human review evidence and estimated-budget checks. Compare outputs and decoded QC files retain detailed evidence. | The render suite checks a probe, draft, comparison, render promotion and media gates. Review prose and user-provided values remain in the existing private job files. Automated measures cannot establish visual approval. |
| Acceptance tools, example publishing and CI | [Acceptance runner](../tools/run_acceptance.py), [render verification](render-verification.md), [documentation workflow](../.github/workflows/docs.yml). Acceptance receipts and asset review files live where the tool is run. The checked-in examples hold public evidence. GitHub retains documentation workflow results. | Developer workflows have separate output roots and no studio job SLA. List documentation runs with `gh run list -R nicolas-found42/3d-agent-studio --workflow docs.yml`. Actions permissions and retention depend on the repository. |

## Failure checks

The first priority was request-to-worker correlation. It affects every render and addresses the highest-impact ambiguity at modest write cost. The second was phase and dependency evidence, which separates the common queue, timeout, encoding and review cases without changing renderer settings. The third was intake and asset outcomes, which sometimes fail before a job can be inspected. A single bounded journal and the same retrieval command cover all three. System-wide GPU profiling, indexing raw media logs and retroactive import of legacy jobs remain outside this local evidence path because they need separate instrumentation, consent or original records.

| Diagnostic question | Evidence needed | Verification |
| --- | --- | --- |
| Did Blender fail after intake, or was it never launched? | Queued and worker events joined by attempt, Blender exit, committed failure state. | A fixture returns exit 37. An independent CLI process reconstructs the chain from the journal after the launcher exits. The raw error marker is present locally and absent from journal results. |
| Did a worker complete after its parent disappeared? | Worker start, last confirmed phase and any terminal outcome. | A detached worker is terminated during its Blender command. A fresh CLI sees a running snapshot and no terminal event. This records the limits of reconstruction after interruption. |
| Did the journal break ordinary ingest? | Successful ingest plus a bounded evidence-loss warning and an unavailable query result. | The test blocks journal storage, confirms ingest still works, restores storage and exercises paginated retrieval and corruption detection. |
| Did a completed probe become unavailable because preview failed to launch? | Probe ready and subsequent preview launch failure, with the proof from the probe intact. | A permission-failure fixture verifies that the completed probe stays ready and the failed handoff appears in the journal. |
| Did a render exceed the worker’s budget or merely wait for the GPU? | GPU-acquired wait duration, stage budget and timeout outcome. | A separate reader retrieved 0 ms of GPU queue wait, a 60-second budget, a Blender timeout after 60,010 ms and a committed failed state from the opt-in Blender test. |
| Did promotion or comparison produce an approved artifact? | Review and integrity checks, separate stage outcome, artifact hashes and decoded QC. | The opt-in render tests invoke the normal CLI flow. Checked files and state determine success. |

## Retention and access

The database is `<root>/.diagnostics/events.sqlite3` inside a directory created with private permissions. Access follows local filesystem permissions and the configured MCP root. It is stored on disk and survives process restarts. Host-restart recovery and long-term retention were not exercised. The journal keeps up to 8,192 events per root and exposes up to 30 days on retrieval. Successful writes prune older rows. Dormant roots are not processed by a timer. SQLite reuses freed pages. There is no collector, background service, or remote upload.

Stage and command transitions are recorded without per-frame events or raw command arguments. The journal stores controlled codes, durations, IDs, counters, and pinned manifest identity. Existing job directories, raw logs, and tracebacks remain separate and can contain sensitive scene data. Their lifecycle is managed by the owner of the output root. Keep them local or redact an export.

An isolated 250-write test on the development Mac measured 0.43 ms median and 0.70 ms at the 95th percentile per journal event, with a 96 KiB database. This measures local write overhead without contention.

A failed journal write waits up to the SQLite lock timeout per write attempt, then returns control to the operation. The process emits a bounded `STUDIO_DIAGNOSTIC_WRITE_UNAVAILABLE` notice on stderr, which may survive in a worker’s raw log. An unavailable journal cannot record its own outage. An abruptly killed process, filesystem or host failure, manually removed directory, or operation beyond retention can leave unrecoverable gaps.
