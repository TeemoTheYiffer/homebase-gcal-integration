# Identity that the Cloud Run Job runs AS. Doesn't need any GCP perms --
# all external auth (Homebase, GCal) is via env-injected user OAuth.
resource "google_service_account" "runner" {
  account_id   = "homebase-sync-runner"
  display_name = "Cloud Run Job runtime SA for homebase-sync"
}

# Identity that Cloud Scheduler uses to invoke the Job.
resource "google_service_account" "scheduler" {
  account_id   = "homebase-sync-scheduler"
  display_name = "Cloud Scheduler invoker SA for homebase-sync"
}

# Identity that GitHub Actions impersonates via OIDC for deploys.
resource "google_service_account" "deployer" {
  account_id   = "github-deployer"
  display_name = "GitHub Actions deployer for homebase-sync"
}

# Deployer needs to: push images, manage Cloud Run Jobs, act as the runner SA.
resource "google_project_iam_member" "deployer_artifact_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_project_iam_member" "deployer_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

# Required so deployer can attach the runner SA to the Job revision.
resource "google_service_account_iam_member" "deployer_act_as_runner" {
  service_account_id = google_service_account.runner.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}

# Deployer needs to read/write Terraform state in the GCS backend bucket.
# The bucket itself is created out-of-band (chicken-and-egg with the backend).
# Note: this binding must also exist before the FIRST CI run; granted via
# `gcloud storage buckets add-iam-policy-binding` during bootstrap.
resource "google_storage_bucket_iam_member" "deployer_tfstate" {
  bucket = "homebase-gcal-sync-tfstate"
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.deployer.email}"
}
