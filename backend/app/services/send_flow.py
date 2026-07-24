from app.models.send_record import SendInboxItem, SendRecord


def can_send_job(job: dict) -> bool:
    return job.get("manual_confirmed") is True


def build_inbox_item(job: dict) -> SendInboxItem:
    return SendInboxItem(
        job_title=job.get("title", ""),
        company=job.get("company", ""),
        draft=job.get("draft", ""),
        manual_confirmed=bool(job.get("manual_confirmed", False)),
        status=job.get("status", "pending"),
        note=job.get("note", ""),
    )


def confirm_send(job: dict) -> SendRecord:
    if not can_send_job(job):
        return SendRecord(
            job_title=job.get("title", ""),
            company=job.get("company", ""),
            manual_confirmed=False,
            status="blocked",
            note="需要人工确认后才能发送",
        )
    return SendRecord(
        job_title=job.get("title", ""),
        company=job.get("company", ""),
        manual_confirmed=True,
        status="sent",
        note="已人工确认并进入发送流程",
    )
