# Personio MCP Tool Catalog

This catalog maps each Personio endpoint to assistant-friendly MCP tool names.

## Recommended wrappers

- `list_employees`: simplified employee listing for strict MCP clients.
- `get_employee`: simplified fetch for a single employee by Person ID.
- `personio_mcp_info`: server coverage and diagnostics.
- `personio_auth_token`: validate token issuance (masked by default).
- `personio_auth_revoke`: revoke current token if needed.

## Endpoint mappings

### Absence Periods

| Tool | Endpoint | Purpose | Operation ID | Notes |
| --- | --- | --- | --- | --- |
| `create_absence_period` | `POST /v2/absence-periods` | Creates a new absence period. | `post_v2_absence_periods` | Creates a new absence period. |
| `delete_absence_period` | `DELETE /v2/absence-periods/{id}` | Deletes an absence period by ID. | `delete_v2_absence_periods_by_id` | Deletes an absence period by ID. |
| `get_absence_period` | `GET /v2/absence-periods/{id}` | Retrieves an absence period by ID. | `get_v2_absence_periods_by_id` | Retrieves an absence period by ID. |
| `list_absence_periods` | `GET /v2/absence-periods` | List absence periods. | `get_v2_absence_periods` | - This endpoint returns a list of absence periods. |
| `update_absence_period` | `PATCH /v2/absence-periods/{id}` | Updates an absence period by ID. | `patch_v2_absence_periods_by_id` | Updates an absence period by ID. |

### Absence Periods Breakdowns

| Tool | Endpoint | Purpose | Operation ID | Notes |
| --- | --- | --- | --- | --- |
| `list_absence_period_breakdowns` | `GET /v2/absence-periods/{id}/breakdowns` | Retrieves daily absence period breakdowns for a given absence period. | `get_v2_absence_periods_by_id_breakdowns` | Retrieves daily absence period breakdowns for a given absence period. |

### Absence Types

| Tool | Endpoint | Purpose | Operation ID | Notes |
| --- | --- | --- | --- | --- |
| `get_absence_type` | `GET /v2/absence-types/{id}` | Retrieves an absence type by ID. | `get_v2_absence_types_by_id` | Retrieves an absence type by ID. |
| `list_absence_types` | `GET /v2/absence-types` | List absence types. | `get_v2_absence_types` | List absence type. |

### Applications

| Tool | Endpoint | Purpose | Operation ID | Notes |
| --- | --- | --- | --- | --- |
| `get_recruiting_application` | `GET /v2/recruiting/applications/{id}` | Retrieve an application by ID. | `get_v2_recruiting_applications_by_id` | Retrieves an application for the provided application ID. |
| `list_application_stage_transitions` | `GET /v2/recruiting/applications/{id}/stage-transitions` | List all application stage transitions for an application ID. | `get_v2_recruiting_applications_by_id_stage_transitions` | Returns a list of application stage transitions, ordered by latest-first for the provided application ID. |
| `list_recruiting_applications` | `GET /v2/recruiting/applications` | List all applications. | `get_v2_recruiting_applications` | Returns a list of applications for an authorized company, sorted by last updated date, newest first. |

### Attendances

| Tool | Endpoint | Purpose | Operation ID | Notes |
| --- | --- | --- | --- | --- |
| `create_attendance_period` | `POST /v2/attendance-periods` | Create an attendance period. | `post_v2_attendance_periods` | Create an attendance period and return newly created attendance period ID. |
| `delete_attendance_period` | `DELETE /v2/attendance-periods/{id}` | Delete an attendance period by ID. | `delete_v2_attendance_periods_by_id` | Deletes an attendance period by ID. |
| `get_attendance_period` | `GET /v2/attendance-periods/{id}` | Get an attendance period. | `get_v2_attendance_periods_by_id` | - Retrieves an attendance period by given attendance period ID. |
| `list_attendance_periods` | `GET /v2/attendance-periods` | List attendance periods. | `get_v2_attendance_periods` | List attendance periods by given filters. |
| `update_attendance_period` | `PATCH /v2/attendance-periods/{id}` | Update an attendance period. | `patch_v2_attendance_periods_by_id` | Update an attendance period by given attendance period ID and return the attendance period ID. |

### Authentication

| Tool | Endpoint | Purpose | Operation ID | Notes |
| --- | --- | --- | --- | --- |
| `post_v2_auth_revoke` | `POST /v2/auth/revoke` |  | `post_v2_auth_revoke` | Endpoint to revoke provided access token. |
| `post_v2_auth_token` | `POST /v2/auth/token` |  | `post_v2_auth_token` | Endpoint to obtain an OAuth 2.0 access token using the Client Credentials Grant. Clients authenticate with their ID and secret, receiving an access token for resource access. |

### Candidates

| Tool | Endpoint | Purpose | Operation ID | Notes |
| --- | --- | --- | --- | --- |
| `get_recruiting_candidate` | `GET /v2/recruiting/candidates/{id}` | Retrieve a candidate by ID. | `get_v2_recruiting_candidates_by_id` | Returns a candidate for the provided ID. The endpoint requires the `personio:recruiting:read` scope. |
| `list_recruiting_candidates` | `GET /v2/recruiting/candidates` | List all candidates. | `get_v2_recruiting_candidates` | Returns a list of candidates for an authorized company, sorted by last updated date, newest first. |

### Categories

| Tool | Endpoint | Purpose | Operation ID | Notes |
| --- | --- | --- | --- | --- |
| `get_recruiting_category` | `GET /v2/recruiting/categories/{id}` | Retrieve a job category by its ID. | `get_v2_recruiting_categories_by_id` | Retrieves a job category for the provided category ID. |
| `list_recruiting_categories` | `GET /v2/recruiting/categories` | List all job categories. | `get_v2_recruiting_categories` | Returns a list of job categories for an authorized company. |

### Compensations

| Tool | Endpoint | Purpose | Operation ID | Notes |
| --- | --- | --- | --- | --- |
| `create_compensation` | `POST /v2/compensations` | Create Compensation. | `post_v2_compensations` | **Requires credential with both `personio:compensations:read` and `personio:compensations:write` scopes.** |
| `create_compensation_type` | `POST /v2/compensations/types` | Create Compensation Types. | `post_v2_compensations_types` | Creates a new Compensation Type and returns the created resource with its UUID. This UUID can be used to create a new compensation. The types include one-time and recurring Compensation Types for salary workers. Hourly types are not supported and bonuses should use recurring or one time types. |
| `list_compensation_types` | `GET /v2/compensations/types` | List Compensation Types. | `get_v2_compensations_types` | Returns a list of Compensation Types for an authorized company. The types include one-time and recurring Compensation Types. Bonuses should use recurring or one time types. |
| `list_compensations` | `GET /v2/compensations` | List compensations. | `get_v2_compensations` | Returns a list of payroll compensations of people for an authorized company. Compensations listed include base salary (excluding proration), hourly, one time compensation, recurring compensation, and bonuses. |

### Cost Centers

| Tool | Endpoint | Purpose | Operation ID | Notes |
| --- | --- | --- | --- | --- |
| `list_cost_centers` | `GET /v2/cost-centers` | List cost centers. | `listCostCenters` | - Returns a list of existing cost centers for an authorized company. |

### Document Management

| Tool | Endpoint | Purpose | Operation ID | Notes |
| --- | --- | --- | --- | --- |
| `delete_document` | `DELETE /v2/document-management/documents/{document_id}` | Delete document. | `delete_v2_document_management_documents_by_document_id` | Deletes the Document with the provided Document ID. |
| `download_document_file` | `GET /v2/document-management/documents/{document_id}/download` | Download document file. | `get_v2_document_management_documents_by_document_id_download` | Downloads the file associated with the provided Document ID. |
| `list_documents` | `GET /v2/document-management/documents` | List document metadata. | `get_v2_document_management_documents` | Lists the metadata of Documents belonging to the provided owner ID. |
| `update_document_metadata` | `PATCH /v2/document-management/documents/{document_id}` | Update document metadata. | `patch_v2_document_management_documents_by_document_id` | Updates the metadata of the Document with the provided Document ID. |

### Employments

| Tool | Endpoint | Purpose | Operation ID | Notes |
| --- | --- | --- | --- | --- |
| `get_person_employment` | `GET /v2/persons/{person_id}/employments/{id}` | Retrieve an employment. | `get_v2_persons_by_person_id_employments_by_id` | Retrieves an employment for the provided ID. |
| `list_person_employments` | `GET /v2/persons/{person_id}/employments` | List employments of a given Person. | `get_v2_persons_by_person_id_employments` | Returns a list of employments of a given person. The employments are returned in sorted order, with the most recent employments appearing first. |
| `update_person_employment` | `PATCH /v2/persons/{person_id}/employments/{employment_id}` | Update an Employment. | `patch_v2_persons_by_person_id_employments_by_employment_id` | - This endpoint enables the update of an Employment resource. |

### Jobs

| Tool | Endpoint | Purpose | Operation ID | Notes |
| --- | --- | --- | --- | --- |
| `get_recruiting_job` | `GET /v2/recruiting/jobs/{id}` | Retrieve an job by ID. | `get_v2_recruiting_jobs_by_id` | Retrieves an job for the provided job ID. |
| `list_recruiting_jobs` | `GET /v2/recruiting/jobs` | List all jobs. | `get_v2_recruiting_jobs` | Returns a list of jobs for an authorized company, sorted by last updated date, newest first. |

### Legal Entities

| Tool | Endpoint | Purpose | Operation ID | Notes |
| --- | --- | --- | --- | --- |
| `get_legal_entity` | `GET /v2/legal-entities/{id}` | Retrieves a legal entity. | `getLegalEntityById` | Returns a legal entity for the provided ID. |
| `list_legal_entities` | `GET /v2/legal-entities` | List legal entities. | `listLegalEntities` | - Returns a list of existing legal entities for an authorized company. The legal entities are returned sorted by their creation date, with the most recent appearing first. |

### Org Units

| Tool | Endpoint | Purpose | Operation ID | Notes |
| --- | --- | --- | --- | --- |
| `get_org_unit` | `GET /v2/org-units/{id}` | Retrieves an Org Unit. | `getOrgUnit` | - Returns the requested Org Unit. |

### Persons

| Tool | Endpoint | Purpose | Operation ID | Notes |
| --- | --- | --- | --- | --- |
| `create_person_and_employment` | `POST /v2/persons` | Create a new Person and Employment. | `post_v2_persons` | - This endpoint enables the creation of a Person resource and an associated Employment resource. |
| `delete_person` | `DELETE /v2/persons/{person_id}` | Delete a Person. | `delete_v2_persons_by_person_id` | - This endpoint enables the deletion of a Person resource. |
| `get_person` | `GET /v2/persons/{id}` | Retrieve a person. | `get_v2_persons_by_id` | This endpoint returns a specific person identified by the ID parameter. The endpoint requires the personio:persons:read scope. |
| `list_persons` | `GET /v2/persons` | List persons. | `get_v2_persons` | - This endpoint returns a list of persons. |
| `update_person` | `PATCH /v2/persons/{person_id}` | Update a Person. | `patch_v2_persons_by_person_id` | - This endpoint enables the update of a Person resource. |

### Project Members

| Tool | Endpoint | Purpose | Operation ID | Notes |
| --- | --- | --- | --- | --- |
| `add_project_members` | `POST /v2/projects/{id}/members` | Add Project Members | `post_v2_projects_by_id_members` | Adds a list of project members to a project. When the project is already assigned to all employees, it will be converted to a project with members. (`assigned_to_all` will be set to false) If the person is already a member of the project, the request is a no-op. |
| `list_project_members` | `GET /v2/projects/{id}/members` | List Project Members | `get_v2_projects_by_id_members` | List all project members by given project ID. |
| `remove_project_members` | `DELETE /v2/projects/{id}/members` | Remove Project Members | `delete_v2_projects_by_id_members` | Remove project members from a project. |

### Projects

| Tool | Endpoint | Purpose | Operation ID | Notes |
| --- | --- | --- | --- | --- |
| `create_project` | `POST /v2/projects` | Create a project. | `post_v2_projects` | Create a project and return the newly created project ID. |
| `delete_project` | `DELETE /v2/projects/{id}` | Delete a Project. | `delete_v2_projects_by_id` | Delete a project by given project ID. All its sub projects will be deleted as well. |
| `get_project` | `GET /v2/projects/{id}` | Get a Project. | `get_v2_projects_by_id` | Retrieves a project by given project ID. |
| `list_projects` | `GET /v2/projects` | List Projects | `get_v2_projects` | List all projects by given filters. |
| `update_project` | `PATCH /v2/projects/{id}` | Update a Project. | `patch_v2_projects_by_id` | Update a project by given project ID. |

### Reports

| Tool | Endpoint | Purpose | Operation ID | Notes |
| --- | --- | --- | --- | --- |
| `get_report` | `GET /v2/reports/{id}` | Retrieves a report. | `getReport` | Retrieves a report for the provided ID. |
| `list_report_attributes` | `GET /v2/reports/attributes` | Lists all report attributes for a company. | `listReportsAttributes` | Returns a list of the reports company attributes. The attributes response also contains the attribute details, such as type, display, filtering, etc. |
| `list_reports` | `GET /v2/reports` | Lists all reports for a company. | `listCompanyReports` | Returns a list of reports available for the company. The reports are returned in a sorted order, with the most recent appearing first. |

### Webhooks

| Tool | Endpoint | Purpose | Operation ID | Notes |
| --- | --- | --- | --- | --- |
| `create_webhook` | `POST /v2/webhooks` | Create new webhook. | `post_v2_webhooks` | Create a new webhook. This endpoint requires the `personio:webhooks:write` scope. |
| `delete_webhook` | `DELETE /v2/webhooks/{id}` | Delete a webhook. | `delete_v2_webhooks_by_id` | Delete a webhook. This endpoint requires the `personio:webhooks:write` scope. |
| `get_webhook` | `GET /v2/webhooks/{id}` | Get a webhook. | `get_v2_webhooks_by_id` | Get a webhook. This endpoint requires the `personio:webhooks:read` scope. |
| `list_webhook_activity` | `GET /v2/webhooks/{id}/activity` | Get webhook delivery activity. | `get_v2_webhooks_by_id_activity` | Returns delivery activity for a specific webhook. Only activities in the last 30 days will be included. This endpoint requires the `personio:webhooks:read` scope. |
| `list_webhook_events` | `GET /v2/webhooks/{id}/events` | Get webhook events. | `get_v2_webhooks_by_id_events` | Returns events for a specific webhook. Only events in the last 30 days will be included. This endpoint requires the `personio:webhooks:read` scope. |
| `list_webhooks` | `GET /v2/webhooks` | List webhooks. | `get_v2_webhooks` | Returns a list of webhooks. This endpoint requires the `personio:webhooks:read` scope. |
| `redeliver_webhook_events` | `POST /v2/webhooks/{id}/redelivery` | Redeliver events for a webhook. | `post_v2_webhooks_by_id_redelivery` | Redelivers events selected by the request parameters. Only events from the last 30 days can be redelivered. |
| `send_webhook_ping` | `POST /v2/webhooks/{id}/ping` | Send a ping event. | `post_v2_webhooks_by_id_ping` | Use this endpoint to trigger a test event of type `ping` for a specific webhook. |
| `send_webhook_test_event` | `POST /v2/webhooks/{id}/test-event` | Send a test event with custom payload. | `post_v2_webhooks_by_id_test_event` | Triggers a test event with a specific event type and custom payload data for a webhook. |
| `update_webhook` | `PATCH /v2/webhooks/{id}` | Update a webhook. | `patch_v2_webhooks_by_id` | Update a webhook. This endpoint requires the `personio:webhooks:write` scope. |

### Workplaces

| Tool | Endpoint | Purpose | Operation ID | Notes |
| --- | --- | --- | --- | --- |
| `list_workplaces` | `GET /v2/workplaces` | List all workplaces. | `listWorkplaces` | - Returns a list of existing workplaces for an authorized company. |
