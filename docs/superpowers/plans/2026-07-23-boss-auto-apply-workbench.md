# BOSS 直聘自动求职工作台 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans`. This plan is built for incremental delivery with manual browser checks after each stage.

**Goal:** Rebuild the workbench into a clear, job-seeker-focused UI where the selected job JD drives resume optimization, and the rest of the pipeline grows from that shared target.

**Stage docs:**
- Stage 0: [Workbench Shell](./2026-07-23-boss-auto-apply-workbench/stage-0-shell.md)
- Stage 1: [Resume Module](./2026-07-23-boss-auto-apply-workbench/stage-1-resume.md)
- Stage 2: [Job Pool](./2026-07-23-boss-auto-apply-workbench/stage-2-jobs.md)
- Stage 3: [Research, Diligence, Ranking](./2026-07-23-boss-auto-apply-workbench/stage-3-research-diligence-ranking.md)
- Stage 4: [Message and Send Inbox](./2026-07-23-boss-auto-apply-workbench/stage-4-message-send.md)

**Architecture:** First establish a stable shell, shared selection state, and a clean information hierarchy. Then wire the resume module to the selected job JD, followed by a split job-intake layer (capture + recognition), diligence, ranking, greeting drafts, and the manual send inbox. Keep each stage independently testable and visible in the browser so we stop shipping empty surfaces.

**Tech Stack:** FastAPI, Pydantic, pytest, React, TypeScript, Vite, browser-based manual validation.

---

### Stage 0: Rebuild the workbench shell and shared state

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/pages/resumes.tsx`
- Modify: `frontend/src/pages/jobs.tsx`

- [ ] **Step 1: Define the shared job contract**
  Add `id`, `jd_text`, and `keywords` to the frontend job type so every module reads the same selected job payload.

- [ ] **Step 2: Add selected-job persistence**
  Store the selected job in `App` and persist it to `localStorage` so a page switch does not lose the current target.

- [ ] **Step 3: Add a visible current-target strip**
  Show the selected job title, company, and JD presence in the shell header or top strip so the user always knows what is being optimized.

- [ ] **Step 4: Make the job page the selector**
  Replace demo-only job rows with a selectable target job state and clearly mark the current selection.

- [ ] **Step 5: Make the resume page read the shared selection**
  Remove manual target-title input and show a clear empty state when no job is selected.

- [ ] **Step 6: Manually verify in the browser**
  Select a job, switch pages, refresh, and confirm the selection remains visible.

- [ ] **Step 7: Define shared state fallbacks**
  Keep selected job, parsed resume, diligence result, and draft message in a single recoverable client state so refresh or page switch does not wipe the current workflow.

- [ ] **Step 8: Add the stage 0 smoke check**
  Verify the app opens, the selected job survives refresh, and the resume page blocks optimization without a target job.

### Stage 1: Rework the resume module around the selected JD

**Files:**
- Modify: `backend/app/models/job.py`
- Modify: `backend/app/routes/resumes.py`
- Modify: `backend/app/services/resume_optimizer.py`
- Modify: `backend/app/services/job_ingest.py`
- Modify: `backend/tests/test_resume_optimizer.py`
- Modify: `frontend/src/pages/resumes.tsx`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Change the optimize contract**
  Accept the selected job object, not a plain title string, so the backend can read `jd_text`, company, and title together.

- [ ] **Step 2: Keep resume parsing visible and honest**
  Ensure the resume page shows parsing status, parsed summary, and error state instead of silently swallowing failures.

- [ ] **Step 3: Ground optimization in JD text**
  Derive the optimization summary and bullets from JD keywords and responsibilities instead of generic wording.

- [ ] **Step 4: Add a regression test**
  Verify that a specific JD changes the optimization output, and that the result mentions the selected company or JD keywords.

- [ ] **Step 5: Manually verify in the browser**
  Upload a resume, confirm the parsed fields appear, and confirm the optimization output changes when a different job is selected.

- [ ] **Step 6: Lock the resume schema**
  Keep parse output stable enough that optimization and later scoring steps can read the same fields without guessing.

- [ ] **Step 7: Add the stage 1 smoke check**
  Verify parsing, selection-dependent optimization, and empty-state blocking all work together.

### Stage 2: Rebuild the job module as a real job pool

**Files:**
- Modify: `backend/app/models/job.py`
- Modify: `backend/app/routes/jobs.py`
- Modify: `backend/app/services/job_ingest.py`
- Modify: `backend/app/services/job_filters.py`
- Modify: `backend/app/services/job_capture.py`
- Modify: `backend/app/services/job_recognition.py`
- Modify: `frontend/src/pages/jobs.tsx`
- Modify: `frontend/src/lib/types.ts`

- [ ] **Step 1: Normalize job records**
  Ensure every job has `id`, `title`, `company`, `city`, `salary`, `jd_text`, and a structured summary so downstream modules do not guess missing fields.

- [ ] **Step 2: Split capture from recognition**
  Keep browser/page scraping, login, pagination, and detail fetching in the capture layer, then convert raw results into normalized job records in the recognition layer.

- [ ] **Step 3: Keep hard filtering simple**
  Preserve keyword, city, and salary filters, but make the UI show what was filtered out and why.

- [ ] **Step 4: Make job selection obvious**
  Add a single action for choosing the current optimization target and visually mark the active selection.

- [ ] **Step 5: Add browser-friendly empty states**
  If no jobs match filters, show a helpful empty state rather than a blank list.

- [ ] **Step 6: Manually verify in the browser**
  Filter jobs, pick one, and confirm the resume page reflects the same selection.

- [ ] **Step 7: Add source and dedupe rules**
  Treat source type, source id, and dedupe key as required fields so repeated imports do not create duplicate jobs.

- [ ] **Step 8: Add the stage 2 smoke check**
  Verify job source, normalized summary, dedupe behavior, and selection sync all work in one pass.

### Stage 3: Add diligence and ranking as the next layer

**Files:**
- Modify: `backend/app/services/company_diligence.py`
- Modify: `backend/app/services/company_profile.py`
- Modify: `backend/app/services/internet_research.py`
- Modify: `backend/app/services/scoring.py`
- Modify: `backend/app/models/company_diligence.py`
- Modify: `backend/app/models/company_profile.py`
- Modify: `backend/app/models/internet_research.py`
- Modify: `backend/app/models/scoring.py`
- Modify: `backend/app/routes/diligence.py`
- Modify: `backend/app/routes/research.py`
- Modify: `frontend/src/pages/diligence.tsx`
- Modify: `frontend/src/pages/ranked-jobs.tsx`
- Modify: `frontend/src/pages/jobs.tsx`

- [ ] **Step 1: Keep diligence structured**
  Make the diligence output consistent: risk, outlook, evidence, a short summary, and a human-editable note.

- [ ] **Step 2: Define the diligence entry points**
  Allow diligence to open from the job card, job detail area, and ranking page so the user can start from the place they are already in.

- [ ] **Step 3: Keep scoring explainable**
  Preserve separate scores for match, company, outlook, and total so the sort order is readable.

- [ ] **Step 4: Add internet research intake**
  Use AI search to gather company information from the internet, then normalize the result into reusable research evidence before diligence runs.

- [ ] **Step 4a: Define research source priority**
  Prefer company-owned sources first, then news and technical evidence, and keep the search results tagged by source type and URL.

- [ ] **Step 4b: Preserve partial research**
  Allow research to finish with partial evidence when some sources fail, but clearly mark the status and missing coverage.

- [ ] **Step 4c: Generate bounded research queries**
  Build queries from company name, job title, JD keywords, and validation terms, and cap the number of query groups to keep results focused.

- [ ] **Step 4d: Merge duplicate evidence**
  Collapse repeated URLs and duplicate facts into one evidence record while preserving conflicts and the strongest source.

- [ ] **Step 5: Keep ranking tied to the selected job**
  Rankings should clearly reference the same selected job and resume context used in optimization.

- [ ] **Step 6: Manually verify in the browser**
  Confirm that diligence and ranking screens show the same job context as the resume page, and that diligence can be reached from the job page.

- [ ] **Step 7: Require explanation fields**
  Make every diligence and ranking result carry a short rationale so the UI can explain why a company or job scored the way it did.

- [ ] **Step 7a: Stabilize sort order**
  Sort by total score, then company score, then job match score, then source order so the list does not jump around between refreshes.

- [ ] **Step 8: Add the stage 3 smoke check**
  Verify diligence can be entered from multiple places, AI research evidence appears, and ranking explains its score.

- [ ] **Step 9: Add failure handling for research and scoring**
  Keep failed research queries, evidence, and scoring inputs so the user can retry without losing the current job context.

- [ ] **Step 10: Verify partial and conflicting evidence**
  Confirm the UI shows partial research explicitly and keeps conflicting evidence visible instead of merging it away.

- [ ] **Step 11: Lock backend model names**
  Map each field table to the concrete backend model names so implementation can start without rethinking entity boundaries.

- [ ] **Step 12: Lock API route contracts**
  Write the request and response shapes for capture, normalize, parse, optimize, research, diligence, score, draft, and confirm endpoints.

- [ ] **Step 13: Standardize empty states and error codes**
  Define page-level empty states and a shared error/status enum so the UI and backend speak the same language.

- [ ] **Step 14: Add API examples and empty-state copy**
  Include representative request/response examples and final empty-state text so implementation and UI copy do not drift.

- [ ] **Step 15: Define button enablement**
  Write the exact enable/disable rules for upload, capture, select, research, score, draft, and send actions.

- [ ] **Step 16: Standardize API response envelopes**
  Use one response wrapper with `status`, `data`, `warnings`, and `errors` across all routes.

- [ ] **Step 17: Add endpoint field validation**
  Specify which request fields are required, optional, or conditional for each endpoint so implementation does not guess.

- [ ] **Step 18: Finalize page error copy**
  Lock the user-facing error messages for each page so the UI copy stays consistent with the design.

### Stage 4: Add greeting drafts and the manual send inbox

**Files:**
- Modify: `backend/app/services/message_generator.py`
- Modify: `backend/app/services/send_flow.py`
- Modify: `backend/app/routes/messages.py`
- Modify: `backend/app/routes/send_inbox.py`
- Modify: `backend/app/models/send_record.py`
- Modify: `frontend/src/pages/messages.tsx`
- Modify: `frontend/src/pages/inbox.tsx`

- [ ] **Step 1: Generate per-job greeting drafts**
  Make the greeting vary by job title, JD, and resume summary so different roles do not share one generic message.

- [ ] **Step 2: Preserve the manual confirmation gate**
  Keep sending blocked until the user explicitly confirms from the inbox.

- [ ] **Step 3: Make the inbox the last stop**
  The inbox should be the only place that can trigger a send action.

- [ ] **Step 4: Manually verify in the browser**
  Confirm drafts are editable, confirmation is required, and the inbox reflects send state clearly.

- [ ] **Step 5: Add send-state protection**
  Prevent duplicate sends by recording a stable send status and returning the existing result on repeat confirmation requests.

- [ ] **Step 6: Add the stage 4 smoke check**
  Verify draft editing, confirmation gating, and duplicate-send protection in the browser.

- [ ] **Step 7: Verify send failure recovery**
  Ensure failed sends keep the draft, confirmation history, and resend path intact.

---

### Final checks for every stage

- Run backend tests relevant to the changed module.
- Rebuild the frontend after UI changes.
- Verify the actual browser window, not only automated tests.
- Do not move to the next stage until the current stage is understandable in the UI.

### Cross-stage contract rules

- Keep job, resume, diligence, research, scoring, and send records on stable schemas.
- Do not allow any stage to infer missing core fields from UI text alone.
- Preserve enough raw source data to regenerate normalized records later.
- Treat AI search evidence as structured input, not just freeform prose.
- Keep state transitions explicit; do not jump over required editable states.
- Preserve retryable inputs whenever a stage fails.
- Keep research source URLs, timestamps, and evidence tags available for review.
- Allow partial research to flow into diligence only when it is explicitly marked.
- Limit each research run to a bounded number of query groups.
- Preserve conflicting evidence rather than overwriting it.
- Lock the final field tables before implementation begins.
- Lock API route names and payload shapes before coding.
- Keep shared `status` and error code values consistent across all routes and pages.
- Keep sample payloads and page copy aligned with the design doc.
- Keep button enablement rules aligned with the current workflow state.
- Keep API response envelopes identical across routes.
- Keep request field requirements explicit in the API contract.
- Keep user-facing error copy aligned with the page state.

### Failure-path coverage

- Research timeout
- Partial research
- Conflicting evidence
- Duplicate job import
- Resume parse failure
- Send retry after failure

### Stage dependency chain

- Stage 0 must complete before Stage 1 UI work is considered usable.
- Stage 1 depends on the selected job contract from Stage 0.
- Stage 2 depends on the shared job contract and Stage 0 selection state.
- Stage 3 depends on Stage 2 normalized jobs and the research contract.
- Stage 4 depends on Stage 1 resume output, Stage 3 scoring, and selected-job state.

### Remaining gaps to close before coding resumes

- Job source de-duplication and source priority rules.
- Internet research normalization before diligence scoring.
- Editable evidence fields for diligence results.
- A readable ranking explanation panel.
- Persistent current-job state across refresh and module switches.
- Empty, loading, and error states for diligence, ranking, and send inbox.
- Stable schema contracts for job, resume, diligence, and send records.
- Retry and rollback behavior when a later stage fails.
