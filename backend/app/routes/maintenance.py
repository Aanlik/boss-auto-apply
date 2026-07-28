from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.resume import ResumeProfile
from app.services.maintenance_service import (
    cleanup_retention,
    cleanup_dry_run,
    cleanup_confirm,
    create_release_record,
    dependency_vulnerability_audit,
    diagnostic_center,
    export_full_backup,
    export_redacted_backup,
    import_full_backup,
    list_api_calls,
    list_events,
    list_release_records,
    online_acceptance_report,
    privacy_scan,
    release_acceptance_checklist,
    release_acceptance_suite,
    apply_retention_rules,
    migrate_to_sqlite,
    production_guard,
    retention_preview,
    retention_rules,
    release_manifest,
    release_notes,
    release_preflight,
    release_check_suite,
    release_version_snapshot,
    rollback_sqlite_to_json,
    restore_drill,
    security_audit,
    set_primary_storage,
    storage_migration_wizard,
    storage_status,
)
from app.services import sqlite_kv_store, workflow_persistence
from app.services.pdf_visual_regression import inspect_pdf_render
from app.services.report_pdf_exporter import export_deep_report_pdf
from app.services.resume_pdf_exporter import export_resume_pdf


router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


@router.get("/backup/export")
def export_backup() -> dict:
    return export_full_backup()


@router.get("/backup/export-redacted")
def export_backup_redacted() -> dict:
    return export_redacted_backup()


@router.post("/backup/import")
def import_backup(payload: dict) -> dict:
    try:
        return import_full_backup(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/backup/restore-drill")
def preview_backup_restore_drill(payload: dict) -> dict:
    return restore_drill(payload)


@router.get("/logs")
def get_logs(level: str = "", limit: int = 50) -> dict:
    return {"events": list_events(level=level, limit=limit)}


@router.get("/api-logs")
def get_api_logs(category: str = "", limit: int = 100) -> dict:
    return {"logs": list_api_calls(category=category, limit=limit)}


@router.get("/retention/preview")
def preview_retention() -> dict:
    return retention_preview()


@router.post("/retention/cleanup")
def cleanup_retention_endpoint(payload: dict | None = None) -> dict:
    return cleanup_retention(payload or {})


@router.get("/cleanup/dry-run")
def preview_cleanup_dry_run() -> dict:
    return cleanup_dry_run()


@router.post("/cleanup/confirm")
def confirm_cleanup(payload: dict | None = None) -> dict:
    return cleanup_confirm(payload or {})


@router.get("/retention/rules")
def get_retention_rules() -> dict:
    return retention_rules()


@router.post("/retention/rules/apply")
def apply_retention_rules_endpoint(payload: dict | None = None) -> dict:
    return apply_retention_rules(payload or {})


@router.get("/storage")
def get_storage_status() -> dict:
    return storage_status()


@router.get("/release/preflight")
def get_release_preflight() -> dict:
    return release_preflight()


@router.get("/release/check-suite")
def get_release_check_suite() -> dict:
    return release_check_suite()


@router.get("/release/production-guard")
def get_production_guard() -> dict:
    return production_guard()


@router.get("/release/online-report")
def get_online_report() -> dict:
    return online_acceptance_report()


@router.get("/release/acceptance-suite")
def get_release_acceptance_suite() -> dict:
    return release_acceptance_suite()


@router.get("/release/version-snapshot")
def get_release_version_snapshot() -> dict:
    return release_version_snapshot()


@router.get("/release/records")
def get_release_records(limit: int = 20) -> dict:
    return list_release_records(limit=limit)


@router.post("/release/records")
def save_release_record(payload: dict) -> dict:
    return create_release_record(payload)


@router.get("/release/manifest")
def get_release_manifest() -> dict:
    return release_manifest()


@router.get("/release/notes")
def get_release_notes() -> dict:
    return release_notes()


@router.get("/release/acceptance")
def get_release_acceptance() -> dict:
    return release_acceptance_checklist()


@router.get("/security/audit")
def get_security_audit() -> dict:
    return security_audit()


@router.get("/security/privacy-scan")
def get_privacy_scan() -> dict:
    return privacy_scan()


@router.get("/security/dependency-audit")
def get_dependency_audit(dry_run: bool = False) -> dict:
    return dependency_vulnerability_audit(dry_run=dry_run)


@router.get("/diagnostics/center")
def get_diagnostic_center() -> dict:
    return diagnostic_center()


@router.get("/release/pdf-visual-regression")
def get_pdf_visual_regression() -> dict:
    resume_pdf = export_resume_pdf(
        ResumeProfile(name="样例用户", title="产品经理", summary="负责产品规划、用户增长和跨部门协作。"),
        {"tailored_summary": "面向目标岗位突出产品规划、用户增长和业务结果。"},
        "样例公司",
        "产品经理",
    )
    report_pdf = export_deep_report_pdf({
        "company": "样例公司",
        "title": "产品经理",
        "result": {
            "manualReport": {
                "sections": {
                    "summary": "样例报告总结。",
                    "strategy": "优先投递，强调增长经验。",
                    "risk": "暂无明确高风险。",
                    "interview": "准备业务增长案例。",
                    "actions": "先打招呼，再跟进。",
                }
            }
        },
    })
    root = workflow_persistence.DATA_DIR / "visual-regression" / "pdf"
    resume = inspect_pdf_render(resume_pdf, root / "resume")
    report = inspect_pdf_render(report_pdf, root / "deep-report")
    status = "ok" if resume.get("status") == "ok" and report.get("status") == "ok" else "warn"
    return {"status": status, "checks": {"resume": resume, "deepReport": report}}


@router.post("/storage/migrate")
def migrate_storage() -> dict:
    return migrate_to_sqlite()


@router.post("/storage/rollback")
def rollback_storage() -> dict:
    return rollback_sqlite_to_json()


@router.post("/storage/backup")
def backup_storage() -> dict:
    return sqlite_kv_store.create_backup()


@router.get("/storage/migration-wizard")
def get_storage_migration_wizard() -> dict:
    return storage_migration_wizard()


@router.post("/storage/restore-preview")
def preview_storage_restore(payload: dict) -> dict:
    try:
        return sqlite_kv_store.restore_preview(str(payload.get("path") or ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/storage/primary")
def set_primary_storage_endpoint(payload: dict) -> dict:
    try:
        return set_primary_storage(str(payload.get("active_store") or payload.get("activeStore") or ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
