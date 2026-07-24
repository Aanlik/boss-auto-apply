# Stage 2 - Job Pool

Goal: build a real job pool with capture, recognition, filtering, selection, and dedupe.

Depends on:
- Stage 0 shell and selection state.

Files:
- `backend/app/models/job.py`
- `backend/app/routes/jobs.py`
- `backend/app/services/job_ingest.py`
- `backend/app/services/job_filters.py`
- `backend/app/services/job_capture.py`
- `backend/app/services/job_recognition.py`
- `frontend/src/pages/jobs.tsx`
- `frontend/src/lib/types.ts`

Tasks:
1. Normalize job records.
2. Split capture from recognition.
3. Keep hard filtering simple.
4. Make job selection obvious.
5. Add browser-friendly empty states.
6. Manually verify in the browser.
7. Add source and dedupe rules.
8. Add the stage 2 smoke check.

Acceptance:
- Every job has a stable id and full JD.
- Duplicate imports do not create duplicate records.
- Selected job syncs back to resume module.

Smoke check:
- Capture or import jobs.
- Normalize them.
- Select one.
- Refresh and confirm the selection remains.

