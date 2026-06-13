# Evidence Index

All files here are copied from `output/` and sanitized for handoff. They preserve real request/response evidence while redacting credentials, cookies, and bearer keys.

## Files

- `live_retest_after_restart.sanitized.json`: latest broad live retest after restarting `8081`.
- `real_model_port_matrix_8081.sanitized.json`: model matrix for `Who are you` and `1+1=?`.
- `real_latency_probe_20260609.sanitized.json`: latency and timeout comparison evidence.
- `original_10009_core_probe_20260609.sanitized.json`: upstream-original service comparison on port `10009`.
- `ide_protocol_real_verify_after_tool_fix_20260609.sanitized.json`: IDE/LAN client compatibility checks.
- `ide_stream_tool_live_20260609.sanitized.json`: streaming tool-call compatibility checks.
- `multimodal_real_verify_after_restart.sanitized.json`: multimodal fallback/upload checks.
- `lan_responses_upload_verify_8081.sanitized.json`: LAN Responses/upload checks.
- `media_endpoints_live_20260609.sanitized.json`: image/video/audio endpoint live checks.
- `artifact_media_real_checks_8081.sanitized.json`: local artifact/media materialization checks.
- `manifest.json`: source-to-handoff copy manifest.

## Reading Rules

- `ok: true` or HTTP 200 is not enough by itself.
- Check semantic fields such as `semantic_ok`, `text_excerpt`, `output_text_preview`, `runtime_status`, `artifact_count`, `files_count`, and saved download entries.
- Treat media `runtime_status: limited` as not fully implemented.
- Treat upload answers containing `NOT_INSPECTED` as a fallback path, not a successful content inspection.
