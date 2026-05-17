# Runbook — k-anonymity violation spike

* Severity ladder: SEV-3 (slow drift) → SEV-1 (legal exposure under Decree 13/2023).
* Service: any ingestion pipeline; `roadpulse_audit.kanon_violations`.

## Symptoms

* Grafana panel "k-anon violations / 5-min" crosses 100.
* On-call PagerDuty fires `kanon_violation_rate_high`.

## Triage

1. Find the dominant `source` from the audit Postgres mirror:
   ```sql
   SELECT source, count(*) FROM roadpulse_audit.kanon_violations
   WHERE dropped_at > now() - interval '30 min'
   GROUP BY 1 ORDER BY 2 DESC;
   ```
2. If `source = 'vetc'`: VETC traffic dropped — likely an upstream outage,
   not a privacy bug. Confirm with VETC partner ops.
3. If `source = 'sdk-collector'`: a fleet may have churned. Slack the BD
   lead for that fleet.

## Mitigations

* **Do not lower the k threshold.** Always 50 in production.
* If a single hex is the offender for > 2 hours, mark it as "low-confidence"
  in the feature store so downstream models stop pretending coverage exists.

## Communication

Any SEV-1 here triggers the legal hold playbook (`docs/runbooks/legal-hold.md`).
