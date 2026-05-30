# Frontend (React)

Added in commit 13. Three views against the frozen `Decision` contract:

- **Submit** — member/claim form + document upload, calls `POST /claims/evaluate`
- **Decision card** — status, approved amount, reason, confidence, member message
- **Trace viewer** — collapsible list of `TraceEvent`s so any decision is
  reconstructable in the UI

Because the `Decision` shape is frozen in `backend/app/models.py` before the UI
exists, the frontend is pure rendering with no contract rework.
