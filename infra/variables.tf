variable "project_id" {
  description = "GCP project ID hosting the sync."
  type        = string
  default     = "homebase-gcal-sync"
}

variable "region" {
  description = "GCP region for Cloud Run, Artifact Registry, Cloud Scheduler."
  type        = string
  default     = "us-west1"
}

variable "image_tag" {
  description = "Container image tag to deploy. CI passes the git SHA."
  type        = string
  default     = "latest"
}

variable "cron_schedule" {
  description = "Cloud Scheduler cron expression."
  type        = string
  default     = "0 6 * * *"
}

variable "timezone" {
  description = "Timezone for the cron schedule and the app's time math."
  type        = string
  default     = "America/Los_Angeles"
}

variable "log_level" {
  description = "Python logging level for the Cloud Run Job."
  type        = string
  default     = "INFO"
}

variable "github_repo" {
  description = "GitHub repository slug allowed to assume the deployer SA via OIDC."
  type        = string
  default     = "TeemoTheYiffer/homebase-gcal-integration"
}
