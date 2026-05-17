# Runbook — Flood trigger not firing

* Severity ladder: SEV-2 (one insurer affected) → SEV-1 (≥ 2 insurers or
  > 30 min outage).
* Service: `trigger-feed`
* On-call dashboard: <https://grafana.roadpulse.vn/d/trigger-feed>

## Symptoms

* No new events for ≥ 10 min on `GET /v1/trigger-feed/{policy_id}` despite
  flood score > policy threshold visible in Grafana.

## Triage (first 5 min)

1. Confirm flood-service is publishing — check `flood.hex.score` topic lag:
   ```bash
   kubectl exec -n roadpulse svc/redpanda -- rpk topic describe flood.hex.score
   ```
2. Confirm trigger-feed pod is healthy: `kubectl get pods -n roadpulse -l
   app.kubernetes.io/name=trigger-feed -o wide`.
3. Check signing-key rotation: `kubectl describe configmap trigger-keys`.

## Common causes & fixes

| Cause                              | Fix                                                   |
| ---------------------------------- | ----------------------------------------------------- |
| Signing key expired                | Rotate via `kubectl rollout restart deploy/trigger-feed` |
| Flood score < policy threshold     | Confirm threshold in Postgres `roadpulse.policies`    |
| Kafka consumer group fell behind   | `rpk group describe trigger-feed`, increase replicas  |
| Bao Việt webhook returns 5xx       | Failover to passive carrier URL in policy record      |

## Post-incident

* Update `roadpulse.policies.last_incident_at` for affected policy IDs.
* Open ADR if root cause forces architectural change.
* Notify carrier compliance team within 4 h per the SLA addendum.
