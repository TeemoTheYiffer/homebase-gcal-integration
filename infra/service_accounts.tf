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

# NOTE: roles/viewer is also granted to the deployer for read access during
# `terraform plan`. Managed out-of-band via:
#   gcloud projects add-iam-policy-binding homebase-gcal-sync \
#     --member="serviceAccount:github-deployer@homebase-gcal-sync.iam.gserviceaccount.com" \
#     --role="roles/viewer"
# Not declared here because TF would need roles/resourcemanager.projectIamAdmin
# to manage it, which broadens the deployer's blast radius too much.

# Required so deployer can attach the runner SA to the Job revision.
resource "google_service_account_iam_member" "deployer_act_as_runner" {
  service_account_id = google_service_account.runner.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}

# NOTE: roles/storage.objectAdmin on the TF state bucket is also granted to
# the deployer. Managed out-of-band via:
#   gcloud storage buckets add-iam-policy-binding gs://homebase-gcal-sync-tfstate \
#     --member="serviceAccount:github-deployer@homebase-gcal-sync.iam.gserviceaccount.com" \
#     --role="roles/storage.objectAdmin"
# Not declared here because TF would need roles/storage.admin on the bucket
# to read/manage its IAM policy, beyond what the deployer otherwise needs.
