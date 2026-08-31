# Alpha 10 — Practical Agent Reliability Protocol

Preferred AI-control loop:

```text
1. read state_digest + operation_schema
2. construct semantic operations
3. agent/preflight
4. inspect normalized_operations / repairs / warnings
5. if ok, agent/apply with expected_project_hash
6. render only affected scene/span
7. QA + frame/contact-sheet inspection
8. local correction or undo
9. final / uhd_4k60 render
```

## Safe normalization example

Input:

```json
{"action":"transition","args":{"scene":"s03","type":"fade","duration":0.3}}
```

Canonicalized to:

```json
{"action":"set_transition","args":{"scene_id":"s03","transition":"fade","duration":0.3}}
```

This is safe because the semantic meaning is unique.

## Ambiguous Library names are not auto-fixed

Input:

```json
{"action":"filter","args":{"scene":"s03","filter":"cinematic_cool"}}
```

may plausibly mean `cool` or `cinematic_contrast`. The gateway returns suggestions and requires the Agent to choose.

## 4K60

For an UHD60 project:

```python
editor.set_video_mode("4k60")
# edit and inspect using preview/span renders
editor.render_4k60()
```

Use 720p previews during iteration. Reserve 4K60 for milestone/final renders unless the shot specifically needs UHD inspection.
