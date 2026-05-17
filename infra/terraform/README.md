# Terraform — RoadPulse infrastructure

Three top-level modules:

- `modules/vke-cluster` — VNG Cloud Kubernetes (VKE) with a tainted GPU pool for
  the SAR classifier and a CPU pool for everything else.
- `modules/managed-postgres` — PostgreSQL 16 + PostGIS, multi-AZ in `HCM-1`.
- `modules/clickhouse` — ClickHouse cluster for hex/time-bucket analytics
  (sharded 3-way, replicated 2-way).

## Workflow

```bash
terraform init -backend-config=envs/dev.s3.tfbackend
terraform plan  -var-file=envs/dev.tfvars
terraform apply -var-file=envs/dev.tfvars
```

The `envs/*.s3.tfbackend` files are kept outside of git — see
`docs/runbooks/terraform.md`.
