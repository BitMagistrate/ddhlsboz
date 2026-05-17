# RoadPulse — VNG Cloud production stack.
#
# The Build Week deployment targets VNG Cloud only — Vietnam-local data
# residency is non-negotiable for the VETC partnership. The same Terraform
# also supports an `aws` provider for the offline-evaluation cluster
# (us-west-2) which has no production data.

terraform {
  required_version = ">= 1.6"
  required_providers {
    vng = {
      source  = "vngcloud/vng"
      version = ">= 1.4.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.27.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = ">= 2.13.0"
    }
  }
  backend "s3" {
    # Configured via -backend-config; do not hardcode bucket here.
  }
}

variable "env" {
  description = "Environment name: dev | staging | prod"
  type        = string
}

variable "region" {
  description = "VNG Cloud region (HCM-1 for prod, HAN-1 for DR)."
  type        = string
  default     = "HCM-1"
}

locals {
  tags = {
    Project = "roadpulse"
    Env     = var.env
    Owner   = "platform"
  }
}

module "vke" {
  source       = "./modules/vke-cluster"
  env          = var.env
  region       = var.region
  node_pool    = "rp-prod-pool"
  min_nodes    = 3
  max_nodes    = 12
  tags         = local.tags
}

module "postgres" {
  source            = "./modules/managed-postgres"
  env               = var.env
  instance_class    = "db.r5.xlarge"
  storage_gb        = 200
  multi_az          = true
  backup_window_utc = "16:00-17:00"
  tags              = local.tags
}

module "clickhouse" {
  source         = "./modules/clickhouse"
  env            = var.env
  replicas       = 3
  storage_gb     = 1024
  retention_days = 30
  tags           = local.tags
}

module "minio" {
  source     = "./modules/minio"
  env        = var.env
  buckets    = ["roadpulse-osm", "roadpulse-sar", "roadpulse-ml"]
  versioning = true
  tags       = local.tags
}

output "vke_kubeconfig" {
  value     = module.vke.kubeconfig_yaml
  sensitive = true
}
