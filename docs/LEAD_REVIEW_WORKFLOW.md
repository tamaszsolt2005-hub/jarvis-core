# Lead Review Workflow

The Leadkezelő is a human review queue over existing company leads.

- Leads are ordered by the existing 0–100 research-priority score. Unscored leads remain visible after scored leads.
- The country flag is extracted from the grounded research note; missing country data is shown as unknown.
- The expanded card shows the saved research summary, fit hypothesis, business need, source-linked dossier facts and publicly sourced decision-maker snapshot.
- SaaS product suggestions are generated only on explicit request and are labeled as hypotheses.
- Approval and rejection are stored through `record_lead_review_event`; review events are append-only and the current state is a separate projection.
- Rejection requires a human note. AI discussion responses are stored as review events. The human then chooses keep, recommend an alternative SaaS product, or wait.
- This review state is deliberately separate from `leads.approved_to_contact`, consent fields, opt-out state and the outbound email pipeline. Approval never sends email or grants contact permission.
- Mutations require an authenticated Supabase user with the trusted `admin` or `operator` app role. Reader and legacy shared-password sessions are read-only.
- Apply `20261127160000_lead_review_workflow.sql` only through the reviewed deployment/migration process; it has not been applied to production by this change.


## E-mail előkészítés

A lead review jóváhagyás után az [E-mail központ](LEAD_EMAIL_WORKFLOW.md) külön piszkozatot készít. A lead jóváhagyása nem jelent e-mail-jóváhagyást, consentet vagy küldési engedélyt.
