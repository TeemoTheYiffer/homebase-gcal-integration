resource "google_cloud_run_v2_job" "homebase_sync" {
  name                = local.job_name
  location            = var.region
  deletion_protection = false

  template {
    template {
      service_account = google_service_account.runner.email
      timeout         = "600s"
      max_retries     = 1

      containers {
        image = local.default_image

        # Env vars are managed entirely out-of-band via gcloud post-apply
        # (see .github/workflows/deploy.yml). Keeping them here would either
        # leak secrets into TF state or fight with gcloud on every run.
        # We accept that the Job's first execution requires env vars to be
        # set by the deploy workflow before it succeeds.

        resources {
          limits = {
            cpu    = "1"
            memory = "1Gi"
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [
      # Env vars and (transitively) container metadata are owned by the
      # deploy pipeline post-apply; don't reconcile against them.
      template[0].template[0].containers[0].env,
    ]
  }

  depends_on = [google_artifact_registry_repository.containers]
}
