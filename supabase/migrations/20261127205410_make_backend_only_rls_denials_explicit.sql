-- Explicitly deny API roles on backend-only tables; service_role continues to bypass RLS.
BEGIN;
CREATE POLICY company_research_jobs_api_deny
  ON public.company_research_jobs AS PERMISSIVE FOR ALL TO anon, authenticated
  USING (false) WITH CHECK (false);
CREATE POLICY company_research_budget_api_deny
  ON public.company_research_budget_reservations AS PERMISSIVE FOR ALL TO anon, authenticated
  USING (false) WITH CHECK (false);
CREATE POLICY company_research_audit_api_deny
  ON public.company_research_job_audit AS PERMISSIVE FOR ALL TO anon, authenticated
  USING (false) WITH CHECK (false);
CREATE POLICY company_research_runtime_control_api_deny
  ON public.company_research_runtime_control AS PERMISSIVE FOR ALL TO anon, authenticated
  USING (false) WITH CHECK (false);
CREATE POLICY company_research_runtime_events_api_deny
  ON public.company_research_runtime_control_events AS PERMISSIVE FOR ALL TO anon, authenticated
  USING (false) WITH CHECK (false);
CREATE POLICY jarvis_proactive_state_api_deny
  ON public.jarvis_proactive_state AS PERMISSIVE FOR ALL TO anon, authenticated
  USING (false) WITH CHECK (false);
COMMIT;
