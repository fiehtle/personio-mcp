from __future__ import annotations

from typing import Any

OPERATION_NAME_OVERRIDES: dict[str, str] = {
    # Absence periods
    "get_v2_absence_periods": "list_absence_periods",
    "post_v2_absence_periods": "create_absence_period",
    "get_v2_absence_periods_by_id": "get_absence_period",
    "patch_v2_absence_periods_by_id": "update_absence_period",
    "delete_v2_absence_periods_by_id": "delete_absence_period",
    "get_v2_absence_periods_by_id_breakdowns": "list_absence_period_breakdowns",
    # Absence types
    "get_v2_absence_types": "list_absence_types",
    "get_v2_absence_types_by_id": "get_absence_type",
    # Attendance periods
    "get_v2_attendance_periods": "list_attendance_periods",
    "post_v2_attendance_periods": "create_attendance_period",
    "get_v2_attendance_periods_by_id": "get_attendance_period",
    "patch_v2_attendance_periods_by_id": "update_attendance_period",
    "delete_v2_attendance_periods_by_id": "delete_attendance_period",
    # Compensations
    "get_v2_compensations": "list_compensations",
    "post_v2_compensations": "create_compensation",
    "get_v2_compensations_types": "list_compensation_types",
    "post_v2_compensations_types": "create_compensation_type",
    # Documents
    "get_v2_document_management_documents": "list_documents",
    "patch_v2_document_management_documents_by_document_id": "update_document_metadata",
    "delete_v2_document_management_documents_by_document_id": "delete_document",
    "get_v2_document_management_documents_by_document_id_download": "download_document_file",
    # Persons and employments
    "get_v2_persons": "list_persons",
    "post_v2_persons": "create_person_and_employment",
    "get_v2_persons_by_id": "get_person",
    "patch_v2_persons_by_person_id": "update_person",
    "delete_v2_persons_by_person_id": "delete_person",
    "get_v2_persons_by_person_id_employments": "list_person_employments",
    "get_v2_persons_by_person_id_employments_by_id": "get_person_employment",
    "patch_v2_persons_by_person_id_employments_by_employment_id": "update_person_employment",
    # Projects and members
    "get_v2_projects": "list_projects",
    "post_v2_projects": "create_project",
    "get_v2_projects_by_id": "get_project",
    "patch_v2_projects_by_id": "update_project",
    "delete_v2_projects_by_id": "delete_project",
    "get_v2_projects_by_id_members": "list_project_members",
    "post_v2_projects_by_id_members": "add_project_members",
    "delete_v2_projects_by_id_members": "remove_project_members",
    # Recruiting
    "get_v2_recruiting_applications": "list_recruiting_applications",
    "get_v2_recruiting_applications_by_id": "get_recruiting_application",
    "get_v2_recruiting_applications_by_id_stage_transitions": "list_application_stage_transitions",
    "get_v2_recruiting_candidates": "list_recruiting_candidates",
    "get_v2_recruiting_candidates_by_id": "get_recruiting_candidate",
    "get_v2_recruiting_categories": "list_recruiting_categories",
    "get_v2_recruiting_categories_by_id": "get_recruiting_category",
    "get_v2_recruiting_jobs": "list_recruiting_jobs",
    "get_v2_recruiting_jobs_by_id": "get_recruiting_job",
    # Webhooks
    "get_v2_webhooks": "list_webhooks",
    "post_v2_webhooks": "create_webhook",
    "get_v2_webhooks_by_id": "get_webhook",
    "patch_v2_webhooks_by_id": "update_webhook",
    "delete_v2_webhooks_by_id": "delete_webhook",
    "get_v2_webhooks_by_id_activity": "list_webhook_activity",
    "get_v2_webhooks_by_id_events": "list_webhook_events",
    "post_v2_webhooks_by_id_ping": "send_webhook_ping",
    "post_v2_webhooks_by_id_redelivery": "redeliver_webhook_events",
    "post_v2_webhooks_by_id_test_event": "send_webhook_test_event",
    # Org, legal, reports, workplaces
    "listCostCenters": "list_cost_centers",
    "listLegalEntities": "list_legal_entities",
    "getLegalEntityById": "get_legal_entity",
    "getOrgUnit": "get_org_unit",
    "listCompanyReports": "list_reports",
    "listReportsAttributes": "list_report_attributes",
    "getReport": "get_report",
    "listWorkplaces": "list_workplaces",
}


def build_mcp_names(spec: dict[str, Any]) -> dict[str, str]:
    names: dict[str, str] = {}
    used_names: set[str] = set()
    methods = ("get", "post", "put", "patch", "delete", "options", "head", "trace")

    for path_item in spec.get("paths", {}).values():
        for method in methods:
            operation = path_item.get(method)
            if not operation:
                continue
            operation_id = operation.get("operationId")
            if not operation_id:
                continue

            candidate = OPERATION_NAME_OVERRIDES.get(operation_id, operation_id)
            if candidate in used_names:
                suffix = 2
                while f"{candidate}_{suffix}" in used_names:
                    suffix += 1
                candidate = f"{candidate}_{suffix}"

            names[operation_id] = candidate
            used_names.add(candidate)

    return names

