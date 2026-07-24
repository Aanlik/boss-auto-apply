# Stage 3 - Research, Diligence, Ranking

Goal: turn company research into structured diligence and sortable scoring.

Depends on:
- Stage 2 normalized jobs.
- Stage 1 resume output.

Files:
- `backend/app/services/company_diligence.py`
- `backend/app/services/company_profile.py`
- `backend/app/services/internet_research.py`
- `backend/app/services/scoring.py`
- `backend/app/models/company_diligence.py`
- `backend/app/models/company_profile.py`
- `backend/app/models/internet_research.py`
- `backend/app/models/scoring.py`
- `backend/app/routes/diligence.py`
- `backend/app/routes/research.py`
- `frontend/src/pages/diligence.tsx`
- `frontend/src/pages/ranked-jobs.tsx`
- `frontend/src/pages/jobs.tsx`

Tasks:
1. Keep diligence structured.
2. Define diligence entry points.
3. Keep scoring explainable.
4. Add internet research intake.
5. Define research source priority.
6. Preserve partial research.
7. Generate bounded research queries.
8. Merge duplicate evidence.
9. Keep ranking tied to the selected job.
10. Verify failure handling.
11. Verify partial and conflicting evidence.
12. Lock backend model names.
13. Lock API route contracts.
14. Standardize empty states and error codes.
15. Add API examples and empty-state copy.

Acceptance:
- Research can be partial without pretending to be complete.
- Diligence shows evidence and rationale.
- Ranking stays stable and explainable.

Smoke check:
- Run research.
- Enter diligence.
- Rank jobs.
- Confirm partial and conflict cases are visible.

