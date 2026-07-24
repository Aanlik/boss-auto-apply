# Stage 1 - Resume Module

Goal: make resume parsing and optimization work off the selected job JD instead of a free-text target.

Depends on:
- Stage 0 shell and selection state.

Files:
- `backend/app/models/job.py`
- `backend/app/routes/resumes.py`
- `backend/app/services/resume_optimizer.py`
- `backend/app/services/job_ingest.py`
- `backend/tests/test_resume_optimizer.py`
- `frontend/src/pages/resumes.tsx`
- `frontend/src/lib/api.ts`

Tasks:
1. Change the optimize contract to accept the selected job object.
2. Keep resume parsing visible and honest.
3. Ground optimization in JD text.
4. Add a regression test.
5. Manually verify in the browser.
6. Lock the resume schema.
7. Add the stage 1 smoke check.

Acceptance:
- Uploading a resume shows parsed fields.
- Optimization changes when the selected job changes.
- Optimization is blocked without a selected job.

Smoke check:
- Upload resume.
- Select a job.
- Run optimization.
- Switch to a different job.
- Confirm the output changes.

