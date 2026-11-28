-- Cover the company_research_jobs.lead_id foreign key for parent deletes and lead-scoped lookups.
CREATE INDEX IF NOT EXISTS company_research_jobs_lead_id_idx
  ON public.company_research_jobs (lead_id);
