import subprocess
import time
import sys
import os

def run_cmd(command, desc):
    print(f"\n[ACTION] {desc}")
    print(f"Exec: {command}")
    try:
        # Run directly attached to the terminal (No pipes = No buffering/muting)
        result = subprocess.run(command, shell=True)
        
        if result.returncode != 0:
            print(f"[ERROR] Step Failed with Code {result.returncode}")
            return None
        return True
    except Exception as e:
        print(f"[EXCEPTION] {e}")
        return None

def get_url(service_name):
    cmd = f"gcloud run services describe {service_name} --platform managed --region australia-southeast1 --format \"value(status.url)\""
    try:
        val = subprocess.check_output(cmd, shell=True, text=True)
        return val.strip()
    except:
        return None

def main():
    print("🚀 STARTING PYTHON DEPLOYMENT DRIVER 🚀")
    print("----------------------------------------")

    # 1. Project
    run_cmd("gcloud config set project pp-saturday-punter", "Setting Project")

    # 1.5 Fix Permissions (Self-Granting)
    user_email = "practicalpuntingautomations@gmail.com"
    project_id = "pp-saturday-punter"
    roles = [
        "roles/cloudbuild.builds.editor",
        "roles/storage.admin",
        "roles/serviceusage.serviceUsageAdmin",
        "roles/run.admin",
        "roles/viewer"
    ]
    
    print("\n--- FIXING PERMISSIONS ---")
    for role in roles:
        cmd = f"gcloud projects add-iam-policy-binding {project_id} --member=user:{user_email} --role={role}"
        run_cmd(cmd, f"Granting {role}")

    # 2. Bucket (Create if missing)
    bucket_name = "gs://pp-saturday-punter-assets-2026"
    run_cmd(f"gsutil mb -l australia-southeast1 {bucket_name}", f"Creating Bucket {bucket_name}")

    # 3. Enable APIs
    run_cmd("gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com cloudscheduler.googleapis.com", "Enabling Cloud APIs")

    # 4. Build
    print("\n--- BUILDING CONTAINER (This takes ~3 mins) ---")
    # Add Retry Logic
    if not run_cmd("gcloud builds submit --tag gcr.io/pp-saturday-punter/saturday-app .", "Building Docker Image"):
        print("Build Failed. Retrying once...")
        time.sleep(5)
        if not run_cmd("gcloud builds submit --tag gcr.io/pp-saturday-punter/saturday-app .", "Building Docker Image (Retry)"):
             print("Build Failed Again. Stopping.")
             return

    # 5. Deploy Dashboard
    print("\n--- DEPLOYING DASHBOARD ---")
    
    # Credentials
    app_pass = "Saturday2026!"
    web_user = "hugh-manager"
    web_pass = "1503?Evr!4842"
    sys_user = "Hugh"
    sys_pass = "MAXMAX01"
    email_pass = "mudh dhfs kpff onph"
    
    deploy_cmd = (
        f"gcloud run deploy trading-desk "
        f"--image gcr.io/pp-saturday-punter/saturday-app "
        f"--platform managed "
        f"--region australia-southeast1 "
        f"--allow-unauthenticated "
        f"--memory 2Gi "
        f"--set-env-vars GCS_BUCKET_NAME=pp-saturday-punter-assets-2026 "
        f"--set-env-vars APP_PASSWORD={app_pass} "
        f"--set-env-vars WEB_UPLOAD_USER={web_user} "
        f"--set-env-vars WEB_UPLOAD_PASSWORD=\"{web_pass}\""
    )
    
    if run_cmd(deploy_cmd, "Deploying Trading Desk Service"):
        url = get_url("trading-desk")
        print(f"\n✅ DASHBOARD LIVE AT: {url}")
        
        # 5. Deploy Job
        print("\n--- DEPLOYING SCOUT JOB ---")
        job_cmd = (
            f"gcloud run jobs create scout-job "
            f"--image gcr.io/pp-saturday-punter/saturday-app "
            f"--region australia-southeast1 "
            f"--command python,execution/orchestrator.py "
            f"--memory 2Gi "
            f"--set-env-vars GCS_BUCKET_NAME=pp-saturday-punter-assets-2026 "
            f"--set-env-vars DASHBOARD_URL={url} "
            f"--set-env-vars SYSTEM_BUILDER_USER={sys_user} "
            f"--set-env-vars SYSTEM_BUILDER_PASSWORD={sys_pass} "
            f"--set-env-vars NOTIFICATION_EMAIL_PASSWORD=\"{email_pass}\""
        )
        # Job might exist, update it logic? Just run generic create/update logic via 'replace'?
        # Actually 'jobs replace' needs yaml. 'jobs update'?
        # We'll just try create. If it fails, that's fine.
        run_cmd(job_cmd, "Creating Scout Job")

        # 6. Deploy HQ Command (Admin Dashboard)
        print("\n--- DEPLOYING HQ COMMAND ---")
        hq_cmd = (
            f"gcloud run deploy hq-command "
            f"--image gcr.io/pp-saturday-punter/saturday-app "
            f"--platform managed "
            f"--region australia-southeast1 "
            f"--allow-unauthenticated "
            f"--memory 2Gi "
            f"--command sh "
            f"--args -c,\"streamlit run execution/admin_dashboard.py --server.port=8080 --server.address=0.0.0.0\" "
            f"--set-env-vars GCS_BUCKET_NAME=pp-saturday-punter-assets-2026 "
            f"--set-env-vars APP_PASSWORD={app_pass} "
            f"--set-env-vars WEB_UPLOAD_USER={web_user} "
            f"--set-env-vars WEB_UPLOAD_PASSWORD=\"{web_pass}\""
        )
        if run_cmd(hq_cmd, "Deploying HQ Command Service"):
            hq_url = get_url("hq-command")
            print(f"\n✅ HQ COMMAND LIVE AT: {hq_url}")
        
        print("\n✅ DEPLOYMENT FINISHED!")

if __name__ == "__main__":
    main()
