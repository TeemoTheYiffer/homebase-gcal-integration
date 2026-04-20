resource "google_artifact_registry_repository" "containers" {
  location      = var.region
  repository_id = local.artifact_repo
  description   = "Docker images for ${local.job_name}"
  format        = "DOCKER"

  cleanup_policies {
    id     = "keep-last-10"
    action = "KEEP"
    most_recent_versions {
      keep_count = 10
    }
  }
}
