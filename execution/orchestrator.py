import asyncio
import os
import sys

# Ensure this directory is in path for imports
sys.path.append(os.path.dirname(__file__))

import run_system_builder
import process_racing_data
import send_notification

async def main():
    print("[INFO] Starting Orchestrator Pipeline...")
    
    # --- STEP 1: DOWNLOADING ---
    print("\n--- STEP 1: DOWNLOADING ---")
    try:
        # Run the bot and await the result (File Path)
        file_path = await run_system_builder.run_bot()
    except Exception as e:
        print(f"[ERROR] Critical Bot Failure: {e}")
        file_path = None

    if not file_path or not os.path.exists(file_path):
        print("[ERROR] Pipeline Stopped: Download Failed or File Not Found.")
        print("[TIP] Check 'debug_error.png' or logs for details.")
        return
        
    filename = os.path.basename(file_path)
    print(f"[SUCCESS] File Ready: {filename}")
    
    # --- STEP 2: PROCESSING ---
    print("\n--- STEP 2: PROCESSING ---")
    stats = {}
    try:
        # Load and validate the data
        print(f"[PROCESS] Validating: {file_path}")
        df = process_racing_data.load_and_clean_data(file_path)
        
        # Gather Stats for the Email
        stats['Rows'] = len(df)
        stats['Venues'] = df['Venue'].nunique() if 'Venue' in df else 0
        stats['Ultimates'] = len(df[df['Ultimrating'] > 90]) if 'Ultimrating' in df else 0
        
        print(f"[SUCCESS] Data Validated. {stats['Rows']} Runners found.")
        
    except Exception as e:
        print(f"[ERROR] Processing Validation Failed: {e}")
        print("[WARN] Continuing, but email will warn about validation failure.")
        stats['Error'] = str(e)
        # We might still want to notify on error?
        # For now, let's stop pipeline if data is garbage.
        return

    # --- STEP 2.5: CLOUD UPLOAD ---
    print("\n--- STEP 2.5: CLOUD UPLOAD ---")
    bucket_name = os.getenv("GCS_BUCKET_NAME")
    if bucket_name:
        import cloud_utils
        print(f"[CLOUD] Uploading {filename} to {bucket_name}...")
        try:
             # Upload to raw_data/ folder
             if cloud_utils.upload_to_gcs(file_path, bucket_name, f"raw_data/{filename}"):
                 print("[SUCCESS] Uploaded to Cloud Storage.")
             else:
                 print("[ERROR] Cloud Upload Failed.")
        except Exception as e:
            print(f"[ERROR] Cloud Upload Exception: {e}")
    else:
        print("[INFO] No GCS_BUCKET_NAME set. Skipping Cloud Upload.")

    # --- STEP 3: NOTIFYING ---
    print("\n--- STEP 3: NOTIFYING ---")
    
    dashboard_url = os.getenv("DASHBOARD_URL", "http://localhost:8501")
    
    # Construct HTML Email
    body = f"""
    <h2>Saturday Racing Data Ready</h2>
    <p>The system has successfully downloaded and processed the latest data.</p>
    <ul>
        <li><b>Source File:</b> {filename}</li>
        <li><b>Total Runners:</b> {stats.get('Rows', 'N/A')}</li>
        <li><b>Venues:</b> {stats.get('Venues', 'N/A')}</li>
    </ul>
    <p>
        <a href="{dashboard_url}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;">
            Open Trading Desk
        </a>
    </p>
    <p style="color: #666; font-size: 12px; margin-top: 20px;">
        <i>- Antigravity Orchestrator</i><br>
        <i>Processed at: {os.path.basename(file_path)}</i>
    </p>
    """
    
    subject = f"Please choose Saturday Punter selections ({stats.get('Rows', 0)} Runners)"
    
    success = send_notification.send_email_notification(
        subject=subject,
        body_html=body
    )
    
    print("\n-----------------------------------")
    if success:
        print("[SUCCESS] PIPELINE COMPLETE. Email Sent.")
    else:
        print("[WARN] PIPELINE COMPLETE. Email Failed (Check Config/Password).")
    print("-----------------------------------")

if __name__ == "__main__":
    asyncio.run(main())
