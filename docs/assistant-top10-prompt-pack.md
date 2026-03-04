# Personio MCP - Top 10 Prompt Pack (Assistant-Friendly)

Use these prompts in your AI assistant to improve tool selection and reduce write mistakes.

## Global safety preamble (recommended)
"Before any write action, always do a read preflight, show exact target IDs, and ask me to confirm with `YES` before executing writes."

## 1) Employee card by name or email
"Find the employee by name/email, then return person ID, employment ID, legal entity, team/department, and status."
Tools: `list_employees` -> `get_employee` -> `get_person_employment` -> `get_legal_entity`/`get_org_unit`.

## 2) Company employee roster page
"List the first 50 employees with ID, full name, email, status, and legal entity."
Tools: `list_employees` (+ pagination).

## 3) Time-off snapshot for one employee
"For person ID <ID>, list absence types and all absence periods in the last 90 days and next 30 days."
Tools: `list_absence_types` -> `list_absence_periods`.

## 4) Attendance drilldown for one employee
"For person ID <ID>, list recent attendance periods and fetch details of the latest one."
Tools: `list_attendance_periods` -> `get_attendance_period`.

## 5) Compensation visibility check
"For person ID <ID>, list compensation types and compensations; summarize base pay records and effective dates."
Tools: `list_compensation_types` -> `list_compensations`.

## 6) Reporting discovery
"List available reports and attributes, then fetch report <ID> and summarize top rows."
Tools: `list_report_attributes` -> `list_reports` -> `get_report`.

## 7) Project staffing lookup
"List active projects, then for project <ID> return members and owner context."
Tools: `list_projects` -> `get_project` -> `list_project_members`.

## 8) Document retrieval flow
"For person ID <ID>, list documents, then download document <DOCUMENT_ID> and summarize metadata."
Tools: `list_documents` -> `download_document_file`.

## 9) Webhook diagnostics
"List all webhooks, then show latest activity/events for webhook <ID>; if none exist, return a clean not-configured message."
Tools: `list_webhooks` -> `get_webhook` -> `list_webhook_activity` -> `list_webhook_events`.

## 10) Safe write workflow template
"I want to update Personio data. First run a read preflight, show exact before/after payload, ask for confirmation, then execute one write call only."
Write tools to use only after confirmation: `create_*`, `update_*`, `delete_*`, `add_*`, `remove_*`, `send_*`, `redeliver_*`.

## Recommended confirmation format for writes
"Planned write: <tool_name>\nTarget IDs: <id list>\nExpected effect: <one sentence>\nReply `YES` to execute or `NO` to cancel."
