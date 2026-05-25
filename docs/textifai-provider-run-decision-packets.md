# TextifAI Provider Run Decision Packets

## Product Value

When TextifAI resumes real provider experiments, decision quality depends on private audit packets, not only public summaries. The packet must let Codex and ChatGPT inspect what happened without committing prompts, outputs, or secrets.

## Private Decision Packet

Root path pattern:

- `/tmp/textifai_private_provider_runs/<matrix_or_run_id>`

Per run files:

- `run_manifest.json`
- `final_prompt_sent.md`
- `system_prompt.md`
- `user_prompt.md`
- `provider_profile_or_overlay.md`
- `provider_request_payload.redacted.json`
- `provider_response_raw.txt`
- `provider_response_parsed.json`
- `validation_report.json`
- `failure_mode_report.json`
- `variant_diff_and_hypothesis.json`
- `codex_interpretation.md`

Per matrix files:

- `matrix_summary_private.md`
- `matrix_comparison_private.md`
- `decision_notes_private.md`
- `README.md`

## Privacy Rules

- Never commit packet contents.
- Never copy packet contents to Desktop.
- Never include API keys.
- Always redact `Authorization` headers.
- Handoffs must list packet root path and priority files.
- Handoffs must summarize enough to decide without opening every file.

## Long Provider Run Handling

Required incremental progress log fields:

- `run_index`
- `run_total`
- `started_at`
- `last_output_activity_at`
- `finished_at`
- `output_file_size_bytes`
- `status`

Operational rules:

- track output file growth during long runs;
- detect stalls from lack of output activity;
- write cancellation report before aborting stalled runs;
- support manual cancellation and cancel-on-stall.

## Not In Scope

- provider calls in provider-free phases;
- committing raw provider outputs;
- automatic provider/model switching.
