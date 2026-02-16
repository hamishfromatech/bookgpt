Plan for Expert Mode:
Backend:
Update LLMClient/BookWritingAgent to expose streaming hooks (partial deltas + tool-call telemetry).
Extend /api/projects/<id>/chat (and potentially progress loop) to accept expert=true and emit streaming chunks/tool events.
Expose tool-call summaries via existing progress/task structures so the UI can subscribe.
Frontend:
Add an Expert Mode toggle (global or per-project) that persists in settings/state.
When enabled, switch the progress/chat panel to display a live stream (single card updating in place) and append detailed tool-call cards as they arrive.
---
we are working in this directory:

/Users/hamishfromatech/Downloads/code/cpp/bookgpt