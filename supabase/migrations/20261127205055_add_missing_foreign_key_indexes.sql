-- Add covering indexes for foreign keys identified by the production Supabase Advisor.
-- Safe additive performance change; no row data is modified.
BEGIN;

CREATE INDEX IF NOT EXISTS business_pain_hypotheses_lead_snapshot_fk_idx
  ON public.business_pain_hypotheses (lead_id, snapshot_id);
CREATE INDEX IF NOT EXISTS email_style_feedback_draft_fk_idx
  ON public.email_style_feedback (draft_id);
CREATE INDEX IF NOT EXISTS email_style_feedback_lead_fk_idx
  ON public.email_style_feedback (lead_id);
CREATE INDEX IF NOT EXISTS lead_email_contact_permission_events_lead_fk_idx
  ON public.lead_email_contact_permission_events (lead_id);
CREATE INDEX IF NOT EXISTS lead_email_draft_revisions_draft_fk_idx
  ON public.lead_email_draft_revisions (draft_id);
CREATE INDEX IF NOT EXISTS lead_email_events_draft_fk_idx
  ON public.lead_email_events (draft_id);
CREATE INDEX IF NOT EXISTS lead_email_send_queue_lead_fk_idx
  ON public.lead_email_send_queue (lead_id);
CREATE INDEX IF NOT EXISTS lead_email_send_queue_events_queue_fk_idx
  ON public.lead_email_send_queue_events (queue_id);

COMMIT;
