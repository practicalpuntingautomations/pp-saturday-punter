$ErrorActionPreference = "Stop"

Write-Host "🚀 STARTING MANUAL DEPLOYMENT (VISIBLE MODE)" -ForegroundColor Green

# 1. Set Project
Write-Host "`n[1/3] Setting Project..."
gcloud config set project pp-saturday-punter

# 2. Build (No Cache)
Write-Host "`n[2/3] Building Container (This will take ~3 mins)..."
gcloud builds submit --tag gcr.io/pp-saturday-punter/saturday-app .

if ($LASTEXITCODE -ne 0) {
    Write-Host "Build Failed!" -ForegroundColor Red
    exit
}

# 3. Deploy
# 3. Deploy
Write-Host "`n[3/3] Deploying Service..."
$env:GCS_BUCKET_NAME = "pp-saturday-punter-assets-2026"

# PREPARE GOOGLE TOKEN (Base64 Encode to avoid quoting issues)
$TokenContent = Get-Content "token.json" -Raw
$TokenBytes = [System.Text.Encoding]::UTF8.GetBytes($TokenContent)
$TokenB64 = [Convert]::ToBase64String($TokenBytes)
Write-Host "Prepared Google Token (Base64) for Cloud Injection."

gcloud run deploy trading-desk `
    --image gcr.io/pp-saturday-punter/saturday-app `
    --platform managed `
    --region australia-southeast1 `
    --allow-unauthenticated `
    --memory 2Gi `
    --set-env-vars GCS_BUCKET_NAME=pp-saturday-punter-assets-2026 `
    --set-env-vars APP_PASSWORD=Saturday2026! `
    --set-env-vars WEB_UPLOAD_USER=hugh-manager `
    --set-env-vars WEB_UPLOAD_PASSWORD="1503?Evr!4842" `
    --set-env-vars SYSTEM_BUILDER_USER=Hugh `
    --set-env-vars SYSTEM_BUILDER_PASSWORD=MAXMAX01 `
    --set-env-vars NOTIFICATION_EMAIL_PASSWORD="mudh dhfs kpff onph" `
    --set-env-vars GOOGLE_TOKEN_JSON_B64=$TokenB64

Write-Host "`n[4/3] Deploying HQ Command (Admin Hub)..."
gcloud run deploy hq-command `
    --image gcr.io/pp-saturday-punter/saturday-app `
    --platform managed `
    --region australia-southeast1 `
    --allow-unauthenticated `
    --memory 2Gi `
    --command python `
    --args="-m,streamlit,run,execution/admin_dashboard.py,--server.port=8080,--server.address=0.0.0.0" `
    --set-env-vars GCS_BUCKET_NAME=pp-saturday-punter-assets-2026 `
    --set-env-vars APP_PASSWORD=Saturday2026! `
    --set-env-vars WEB_UPLOAD_USER=hugh-manager `
    --set-env-vars WEB_UPLOAD_PASSWORD="1503?Evr!4842" `
    --set-env-vars SYSTEM_BUILDER_USER=Hugh `
    --set-env-vars SYSTEM_BUILDER_PASSWORD=MAXMAX01 `
    --set-env-vars NOTIFICATION_EMAIL_PASSWORD="mudh dhfs kpff onph" `
    --set-env-vars DASHBOARD_URL=https://trading-desk-743327487816.australia-southeast1.run.app `
    --set-env-vars GOOGLE_TOKEN_JSON_B64=$TokenB64

Write-Host "`n[5/5] Deploying Scout Job (The Robot)..."
gcloud run jobs deploy scout-job `
    --image gcr.io/pp-saturday-punter/saturday-app `
    --region australia-southeast1 `
    --command python `
    --args execution/orchestrator.py `
    --memory 2Gi `
    --set-env-vars GCS_BUCKET_NAME=pp-saturday-punter-assets-2026 `
    --set-env-vars APP_PASSWORD=Saturday2026! `
    --set-env-vars WEB_UPLOAD_USER=hugh-manager `
    --set-env-vars WEB_UPLOAD_PASSWORD="1503?Evr!4842" `
    --set-env-vars SYSTEM_BUILDER_USER=Hugh `
    --set-env-vars SYSTEM_BUILDER_PASSWORD=MAXMAX01 `
    --set-env-vars NOTIFICATION_EMAIL_PASSWORD="mudh dhfs kpff onph" `
    --set-env-vars DASHBOARD_URL=https://trading-desk-743327487816.australia-southeast1.run.app `
    --set-env-vars GOOGLE_TOKEN_JSON_B64=$TokenB64

Write-Host "`n[6/5] Setting Scheduling Alarm (Every Saturday 9am)..."
# Try delete old one to avoid conflict
try { gcloud scheduler jobs delete pp-weekend-trigger --location australia-southeast1 --quiet } catch {}

gcloud scheduler jobs create http pp-weekend-trigger `
    --location australia-southeast1 `
    --schedule "0 9 * * 6" `
    --time-zone "Australia/Sydney" `
    --uri "https://australia-southeast1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/pp-saturday-punter/jobs/scout-job:run" `
    --http-method POST `
    --oauth-service-account-email "743327487816-compute@developer.gserviceaccount.com"

Write-Host "`n✅ DONE! You have two links now:" -ForegroundColor Green
Write-Host "1. Trading Desk (Email Link)"
Write-Host "2. HQ Command (Fixed Admin Link)"
