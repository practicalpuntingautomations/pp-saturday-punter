# Auto-Deployment Script
# Automated by Antigravity

$ErrorActionPreference = "Stop"

Write-Host "🚀 Starting Automated Deployment..." -ForegroundColor Green

# 1. Project
Write-Host "-> Setting Project..."
cmd /c "gcloud config set project pp-saturday-punter"

# 2. Infrastructure
Write-Host "-> Checking Bucket..."
$bucket = "gs://pp-saturday-punter-data"
try {
    cmd /c "gsutil ls -b $bucket 2>&1" | Out-Null
    Write-Host "   Bucket exists."
}
catch {
    Write-Host "   Creating bucket..."
    cmd /c "gsutil mb -l australia-southeast1 $bucket"
}

# 3. Enable APIs (Quietly)
Write-Host "-> Enabling APIs..."
cmd /c "gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com cloudscheduler.googleapis.com"

# 4. Build (This takes time)
Write-Host "-> Building Container (This may take 2-3 minutes)..."
cmd /c "gcloud builds submit --tag gcr.io/pp-saturday-punter/saturday-app ."

# 5. Credentials
$AppPass = "Saturday2026!"
$WebUser = "hugh-manager"
$WebPass = "1503?Evr!4842"
$SysUser = "Hugh"
$SysPass = "MAXMAX01"
$EmailPass = "mudh dhfs kpff onph"

# 6. Deploy Dashboard
Write-Host "-> Deploying Dashboard..."
cmd /c "gcloud run deploy trading-desk --image gcr.io/pp-saturday-punter/saturday-app --platform managed --region australia-southeast1 --allow-unauthenticated --memory 2Gi --set-env-vars GCS_BUCKET_NAME=pp-saturday-punter-data --set-env-vars APP_PASSWORD=$AppPass --set-env-vars WEB_UPLOAD_USER=$WebUser --set-env-vars WEB_UPLOAD_PASSWORD=$WebPass"

# Capture URL
$urlInfo = cmd /c "gcloud run services describe trading-desk --platform managed --region australia-southeast1 --format 'value(status.url)'"
$DashboardUrl = $urlInfo.Trim()
Write-Host "✅ Dashboard URL: $DashboardUrl" -ForegroundColor Cyan

# 7. Deploy Scout
Write-Host "-> Deploying Scout Job..."
cmd /c "gcloud run jobs create scout-job --image gcr.io/pp-saturday-punter/saturday-app --region australia-southeast1 --command python,execution/orchestrator.py --memory 2Gi --set-env-vars GCS_BUCKET_NAME=pp-saturday-punter-data --set-env-vars DASHBOARD_URL=$DashboardUrl --set-env-vars SYSTEM_BUILDER_USER=$SysUser --set-env-vars SYSTEM_BUILDER_PASSWORD=$SysPass --set-env-vars NOTIFICATION_EMAIL_PASSWORD=$EmailPass"

# 8. Schedule
Write-Host "-> Scheduling Job..."
# Use || true logic in PS roughly by ignoring error if job exists
try {
    cmd /c "gcloud scheduler jobs create http saturday-scout --location australia-southeast1 --schedule='0 9 * * 6' --time-zone='Australia/Sydney' --uri='https://australia-southeast1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/pp-saturday-punter/jobs/scout-job:run' --http-method POST --oauth-service-account-email pp-saturday-punter@appspot.gserviceaccount.com"
}
catch {
    Write-Host "   Job might already exist (skipping creation)."
}

Write-Host "Done! 🏁" -ForegroundColor Green
