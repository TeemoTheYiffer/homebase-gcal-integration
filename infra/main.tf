terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  backend "gcs" {
    bucket = "homebase-gcal-sync-tfstate"
    prefix = "infra"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  job_name           = "homebase-sync"
  artifact_repo      = "containers"
  artifact_repo_url  = "${var.region}-docker.pkg.dev/${var.project_id}/${local.artifact_repo}"
  default_image      = "${local.artifact_repo_url}/${local.job_name}:${var.image_tag}"
}
