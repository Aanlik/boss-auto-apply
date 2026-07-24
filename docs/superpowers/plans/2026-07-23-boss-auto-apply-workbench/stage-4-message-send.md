# Stage 4 - Message and Send Inbox

Goal: generate job-specific greeting drafts and keep sending behind a manual confirmation gate.

Depends on:
- Stage 1 resume output.
- Stage 3 scoring and diligence.

Files:
- `backend/app/services/message_generator.py`
- `backend/app/services/send_flow.py`
- `backend/app/routes/messages.py`
- `backend/app/routes/send_inbox.py`
- `backend/app/models/send_record.py`
- `frontend/src/pages/messages.tsx`
- `frontend/src/pages/inbox.tsx`

Tasks:
1. Generate per-job greeting drafts.
2. Preserve the manual confirmation gate.
3. Make the inbox the last stop.
4. Manually verify in the browser.
5. Add send-state protection.
6. Add the stage 4 smoke check.
7. Verify send failure recovery.

Acceptance:
- Drafts are editable.
- Sending cannot happen before explicit confirmation.
- Duplicate send attempts do not create duplicate receipts.

Smoke check:
- Generate a draft.
- Edit it.
- Confirm send.
- Retry confirmation.
- Confirm only one receipt exists.

