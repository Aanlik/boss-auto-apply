# Stage 0 - Workbench Shell

Goal: establish the shell, shared selection state, and the visible current target so the app stops feeling like disconnected panels.

Depends on:
- Master spec: [boss-auto-apply-workbench-design.md](/Users/alink/Documents/BOSS%20%E7%9B%B4%E8%81%98/docs/superpowers/specs/2026-07-23-boss-auto-apply-workbench-design.md)
- Master plan: [boss-auto-apply-workbench.md](/Users/alink/Documents/BOSS%20%E7%9B%B4%E8%81%98/docs/superpowers/plans/2026-07-23-boss-auto-apply-workbench.md)

Files:
- `frontend/src/App.tsx`
- `frontend/src/lib/types.ts`
- `frontend/src/lib/api.ts`
- `frontend/src/pages/resumes.tsx`
- `frontend/src/pages/jobs.tsx`

Tasks:
1. Define the shared job contract.
2. Persist the selected job in `localStorage`.
3. Show the current target job in the shell.
4. Make the job page the selector.
5. Make the resume page read the shared selection.
6. Keep the selected job across refresh.
7. Add shared state fallbacks for resume, diligence, and draft data.
8. Add the stage 0 smoke check.

Acceptance:
- App opens with a clear current target area.
- Selected job survives page switch and refresh.
- Resume page blocks optimization until a job is selected.

Smoke check:
- Open the app.
- Select a job.
- Switch pages.
- Refresh.
- Confirm the selection is still visible.

