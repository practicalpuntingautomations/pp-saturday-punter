# 🚀 Deployment Guide: Saturday Punter Cloud

This guide will deploy your "Trading Desk" and "Scout" to Google Cloud.

## 1. Prerequisites (Run in Terminal)

Ensure you are authenticated and pointing to the right project:
```powershell
gcloud auth login
gcloud config set project pp-saturday-punter
```

## 2. Create Infrastructure

We need a Storage Bucket for the "Waiting Room" and Artifact Registry for the Docker Image.
```powershell
# Create Bucket for Data
gsutil mb -l australia-southeast1 gs://pp-saturday-punter-data

# Enable Services
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com cloudscheduler.googleapis.com
```

## 3. Build & Publish Container

This packages your entire application (Playwright, Streamlit, Scripts) into a cloud-ready image.
```powershell
# Build using Cloud Build (No local Docker needed)
gcloud builds submit --tag gcr.io/pp-saturday-punter/saturday-app .
```

## 4. Deploy "Trading Desk" (Dashboard)

Deploy the Streamlit App. Replace the `PASSWORD_` placeholders with your real secrets!

```powershell
gcloud run deploy trading-desk `
  --image gcr.io/pp-saturday-punter/saturday-app `
  --platform managed `
  --region australia-southeast1 `
  --allow-unauthenticated `
  --memory 2Gi `
  --set-env-vars GCS_BUCKET_NAME=pp-saturday-punter-data `
  --set-env-vars APP_PASSWORD=YourSecretPassword `
  --set-env-vars WEB_UPLOAD_USER=hugh-manager `
  --set-env-vars WEB_UPLOAD_PASSWORD=REPLACE_WITH_REAL_PASSWORD
```
*Note: We allocate 2Gi memory because Playwright requires it.*

**✅ OUTPUT:** You will get a Service URL (e.g., `https://trading-desk-xyz.a.run.app`). **COPY THIS URL.**

## 5. Deploy "Scout" (Background Job)

Deploy the background worker. **PASTE THE URL FROM STEP 4** into `DASHBOARD_URL`.

```powershell
gcloud run jobs create scout-job `
  --image gcr.io/pp-saturday-punter/saturday-app `
  --region australia-southeast1 `
  --command python,execution/orchestrator.py `
  --memory 2Gi `
  --set-env-vars GCS_BUCKET_NAME=pp-saturday-punter-data `
  --set-env-vars DASHBOARD_URL=PASTE_YOUR_URL_HERE `
  --set-env-vars SYSTEM_BUILDER_USER=Hugh `
  --set-env-vars SYSTEM_BUILDER_PASSWORD=REPLACE_WITH_REAL_PASSWORD `
  --set-env-vars NOTIFICATION_EMAIL_PASSWORD=REPLACE_WITH_REAL_PASSWORD
```

## 6. Schedule the Scout

Set it to run every Saturday at 9 AM Sydney time.
```powershell
gcloud scheduler jobs create http saturday-scout `
  --location australia-southeast1 `
  --schedule="0 9 * * 6" `
  --time-zone="Australia/Sydney" `
  --uri="https://australia-southeast1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/pp-saturday-punter/jobs/scout-job:run" `
  --http-method POST `
  --oauth-service-account-email pp-saturday-punter@appspot.gserviceaccount.com
```
*(Note: If the email above fails, check your default Compute Engine service account email in GCP Console).*

---

## 🚀 How to Use

1.  **Every Saturday at 9 AM**, the **Scout** wakes up.
    *   It downloads the data.
    *   It uploads it to the **Storage Bucket**.
    *   It emails you a link.
2.  **You click the link**.
    *   Enter your `APP_PASSWORD`.
    *   The Dashboard loads the data from the Bucket.
3.  **You make selections and click "Generate & Publish"**.
    *   The App generates the doc.
    *   The App spins up a robot (headless) to upload it to the website.
    *   **Done!** ☕
