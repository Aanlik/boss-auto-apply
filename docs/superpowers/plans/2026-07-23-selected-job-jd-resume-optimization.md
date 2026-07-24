# Selected Job JD Resume Optimization Implementation Plan

> **Note:** This is the first implementation slice under the broader workbench plan. It focuses only on connecting resume optimization to the currently selected job JD.

> **For agentic workers:** This plan is executed inline in the current session. Manual browser testing is the acceptance test for each module.

**Goal:** Make resume optimization use the JD from the job selected in the job pool instead of a manually entered job title or JD.

**Architecture:** Extend the shared job record with `id` and `jd_text`, keep the selected job in `App` state with localStorage persistence, and pass it from `JobsPage` to `ResumesPage`. The optimize API will accept the selected job object and return suggestions grounded in its JD. No automatic sending is included.

**Tech Stack:** React, TypeScript, FastAPI, Pydantic, pytest, Vite.

---

### Task 1: Extend the job and optimizer contracts

**Files:**
- Modify: `backend/app/models/job.py`
- Modify: `backend/app/routes/jobs.py`
- Modify: `backend/app/routes/resumes.py`
- Modify: `backend/app/services/resume_optimizer.py`
- Test: `backend/tests/test_resume_optimizer.py`

- [ ] Add a stable job id and `jd_text` to `JobRecord`.
- [ ] Change resume optimization input from `target_title` to `target_job`.
- [ ] Include JD keywords and responsibilities in deterministic suggestions.
- [ ] Preserve the existing response shape (`summary`, `bullets`) for the current UI.
- [ ] Add backend tests proving the selected JD affects the summary and bullets.

### Task 2: Add selected-job state to the frontend

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/pages/jobs.tsx`
- Modify: `frontend/src/pages/resumes.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/types.ts`

- [ ] Define a shared `JobPosting` type with `id`, `jd_text`, and existing fields.
- [ ] Store the selected job in `App` and persist it to localStorage.
- [ ] Let the job page select one job as the resume optimization target.
- [ ] Remove the manual target-title input from the resume page.
- [ ] Send the selected job object to `/api/resumes/optimize`.
- [ ] Show a clear empty state when no job is selected.

### Task 3: Verify the module in the visible browser

**Files:**
- Modify: `frontend/dist` via `pnpm build`

- [ ] Build the frontend.
- [ ] Restart or refresh the local app.
- [ ] Manually select a job in the job pool.
- [ ] Navigate to the resume page and confirm the selected company/title/JD appears.
- [ ] Upload a resume and generate optimization suggestions.
- [ ] Confirm the result reflects the selected JD.
- [ ] Confirm optimization is blocked when no job is selected.
