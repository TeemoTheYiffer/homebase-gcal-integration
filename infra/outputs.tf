output "image_repository_url" {
  description = "Docker image base URL (push tags here)."
  value       = local.artifact_repo_url
}

output "runner_service_account" {
  description = "Email of the Cloud Run Job runtime SA."
  value       = google_service_account.runner.email
}

output "deployer_service_account" {
  description = "GitHub Actions deployer SA email -- set as GCP_DEPLOYER_SA secret."
  value       = google_service_account.deployer.email
}

output "workload_identity_provider" {
  description = "WIF provider full name -- set as GCP_WORKLOAD_IDENTITY_PROVIDER secret."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "cloud_run_job_name" {
  description = "Cloud Run Job resource name."
  value       = google_cloud_run_v2_job.homebase_sync.name
}

output "scheduler_job_name" {
  description = "Cloud Scheduler job name."
  value       = google_cloud_scheduler_job.daily_sync.name
}
