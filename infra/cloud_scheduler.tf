# Scheduler SA needs invoker rights on the specific Job (least privilege).
resource "google_cloud_run_v2_job_iam_member" "scheduler_invoker" {
  project  = google_cloud_run_v2_job.homebase_sync.project
  location = google_cloud_run_v2_job.homebase_sync.location
  name     = google_cloud_run_v2_job.homebase_sync.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_cloud_scheduler_job" "daily_sync" {
  name        = "${local.job_name}-daily"
  description = "Daily Homebase -> GCal sync trigger"
  schedule    = var.cron_schedule
  time_zone   = var.timezone
  region      = var.region

  retry_config {
    retry_count = 1
  }

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.homebase_sync.name}:run"
    body        = base64encode("{}")

    headers = {
      "Content-Type" = "application/json"
    }

    oauth_token {
      service_account_email = google_service_account.scheduler.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }

  depends_on = [google_cloud_run_v2_job_iam_member.scheduler_invoker]
}
