# Saturday Punter Deployment Wizard 🧙‍♂️
# run this with: .\deploy_wizard.ps1

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "   🚀 SATURDAY PUNTER CLOUD LAUNCHER     " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# 1. Project Setup
Write-Host "`n[Step 1/6] Setting Google Cloud Project..." -ForegroundColor Yellow
cmd /c "gcloud config set project pp-saturday-punter"

# 2. Infrastructure (Bucket)
Write-Host "`n[Step 2/6] Checking 'Waiting Room' (Storage Bucket)..." -ForegroundColor Yellow
$bucket = "gs://pp-saturday-punter-data"
$check = cmd /c "gsutil ls -b $bucket 2>&1"
if ($check -match "BucketNotFound") {
    Write-Host "Creating bucket..."
    cmd /c "gsutil mb -l australia-southeast1 $bucket"
} else {
    Write-Host "Bucket already exists. Skiping creation." -ForegroundColor Green
}

# 3. Services
Write-Host "`n[Step 3/6] Waking up Cloud Services (APIs)..." -ForegroundColor Yellow
Write-Host "This might take a minute..."
cmd /c "gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com cloudscheduler.googleapis.com"

# 4. Build
Write-Host "`n[Step 4/6] Packaging the App (Building Container)..." -ForegroundColor Yellow
Write-Host "This uploads your code to Google's build servers."
cmd /c "gcloud builds submit --tag gcr.io/pp-saturday-punter/saturday-app ."

# 5. Secrets Collection
Write-Host "`n=========================================" -ForegroundColor Magenta
Write-Host "   🔑 SECURITY CHECK    " -ForegroundColor Magenta
Write-Host "=========================================" -ForegroundColor Magenta
Write-Host "I need the passwords to lock the doors properly."

$AppPassword = Read-Host "Type a password for the Dashboard (so strangers can't see it)"
$WebUploadUser = Read-Host "Type the Website Username (e.g. hugh-manager)"
$WebUploadPass = Read-Host "Type the Website Password"
$SysBuildUser = Read-Host "Type the System Builder Username (e.g. Hugh)"
$SysBuildPass = Read-Host "Type the System Builder Password"
$EmailPass = Read-Host "Type the Notification Email Password"

# 6. Deploy Dashboard
Write-Host "`n[Step 5/6] Deploying 'Trading Desk' (Dashboard)..." -ForegroundColor Yellow
cmd /c "gcloud run deploy trading-desk --image gcr.io/pp-saturday-punter/saturday-app --platform managed --region australia-southeast1 --allow-unauthenticated --memory 2Gi --set-env-vars GCS_BUCKET_NAME=pp-saturday-punter-data --set-env-vars APP_PASSWORD=$AppPassword --set-env-vars WEB_UPLOAD_USER=$WebUploadUser --set-env-vars WEB_UPLOAD_PASSWORD=$WebUploadPass"

# Get URL
Write-Host "Fetching Dashboard URL..." 
$urlInfo = cmd /c "gcloud run services describe trading-desk --platform managed --region australia-southeast1 --format 'value(status.url)'"
$DashboardUrl = $urlInfo.Trim()
Write-Host "✅ Dashboard is Live at: $DashboardUrl" -ForegroundColor Green

# 7. Deploy Scout
Write-Host "`n[Step 6/6] Deploying 'Scout' (Background Job)..." -ForegroundColor Yellow
cmd /c "gcloud run jobs create scout-job --image gcr.io/pp-saturday-punter/saturday-app --region australia-southeast1 --command python,execution/orchestrator.py --memory 2Gi --set-env-vars GCS_BUCKET_NAME=pp-saturday-punter-data --set-env-vars DASHBOARD_URL=$DashboardUrl --set-env-vars SYSTEM_BUILDER_USER=$SysBuildUser --set-env-vars SYSTEM_BUILDER_PASSWORD=$SysBuildPass --set-env-vars NOTIFICATION_EMAIL_PASSWORD=$EmailPass"

Write-Host "`n=========================================" -ForegroundColor Cyan
Write-Host "   🎉 DEPLOYMENT COMPLETE!    " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "1. Your Dashboard is here: $DashboardUrl"
Write-Host "2. Your Scout is ready to run."
Write-Host "Run this command to schedule the Scout for Saturdays:"
Write-Host "gcloud scheduler jobs create http saturday-scout --location australia-southeast1 --schedule='0 9 * * 6' --time-zone='Australia/Sydney' --uri='https://australia-southeast1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/pp-saturday-punter/jobs/scout-job:run' --http-method POST --oauth-service-account-email pp-saturday-punter@appspot.gserviceaccount.com"
