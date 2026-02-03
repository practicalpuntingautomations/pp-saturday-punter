import streamlit as st
import os
import json
import pandas as pd
from datetime import datetime
import altair as alt
import glob
import subprocess
import sys
import time

# --- CONFIGURATION ---
PAGE_TITLE = "Antigravity HQ"
PAGE_ICON = "🚀"
CONFIG_FILE = "config.json"

st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- UTILS ---
def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(config_data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f, indent=4)
    
    # CLOUD SYNC: Upload to GCS if available
    try:
        bucket = os.getenv("GCS_BUCKET_NAME")
        if bucket:
             if cloud_utils.sync_config_to_gcs(bucket, CONFIG_FILE):
                  st.toast("Settings Synced to Cloud!", icon="☁️")
    except Exception as e:
        print(f"Sync failed: {e}")

    st.toast("Settings Saved Successfully!", icon="💾")

# --- AUTHENTICATION ---
def check_password():
    """Returns `True` if the user had the correct password."""
    
    config = load_config()
    real_password = config.get("admin", {}).get("password", "genius")

    def password_entered():
        if st.session_state["password"] == real_password:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show input for password.
        st.markdown("<br><br><br>", unsafe_allow_html=True) # Spacer
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            st.image("https://placehold.co/100x100?text=🔒", width=80) 
            st.title("Practical Punting")
            st.subheader("Workflow Management")
            st.markdown("---")
            st.text_input(
                "Enter Access Code", type="password", on_change=password_entered, key="password"
            )
            st.caption("🔒 Secured Environment")
        return False
        
    elif not st.session_state["password_correct"]:
        # Password incorrect, retry.
        st.markdown("<br><br><br>", unsafe_allow_html=True) 
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
             st.title("Practical Punting")
             st.error("⛔ Access Denied. Incorrect Code.")
             st.text_input(
                "Enter Access Code", type="password", on_change=password_entered, key="password"
            )
        return False
    else:
        # Password correct.
        return True

# --- MAIN APP ---
def main():
    if not check_password():
        st.stop()
        
    config = load_config()
    
    # --- SIDEBAR NAV ---
    st.sidebar.title(f"{PAGE_ICON} HQ Command")
    st.sidebar.divider()
    
    menu = st.sidebar.radio(
        "Workflow",
        ["🏠 Dashboard", "🏇 Saturday Punter", "⛵ PPD Club", "🧠 Being a Genius"],
    )
    
    st.sidebar.divider()
    if st.sidebar.button("🔒 Logout"):
        del st.session_state["password_correct"]
        st.rerun()

    # --- PAGES ---
    
    if menu == "🏠 Dashboard":
        st.title("Welcome back, Commander. 🫡")
        st.write("System Status: **Operational**")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.info("**Saturday Punter**\n\nStatus: 🟢 Ready\nLast Run: Today")
        with c2:
            st.warning("**PPD Club**\n\nStatus: 🟡 In Development")
        with c3:
            st.success("**Genius Mode**\n\nStatus: 🧠 Always On")
            
        st.divider()
        st.caption("Antigravity Agentic Systems v1.0")

    elif menu == "🏇 Saturday Punter":
        st.title("🏇 Saturday Punter Automation")
        st.write("Manage the automated extraction and reporting workflow.")
        
        tab1, tab2 = st.tabs(["⚙️ Configuration", "🚦 Manual Override"])
        
        with tab1:
            st.subheader("Contact Details")
            
            # Load current values
            sp_config = config.get("saturday_punter", {})
            current_chooser = sp_config.get("chooser_email", "")
            current_notify = sp_config.get("notification_email", "")
            current_url = sp_config.get("system_builder_url", "")
            current_sb_user = sp_config.get("system_builder_user", "")
            # Check for Cloud Mode
            is_cloud = os.getenv("GCS_BUCKET_NAME") is not None
            
            if is_cloud:
                current_dl_path = "☁️ Cloud Temporary Storage (/tmp)"
            else:
                current_dl_path = sp_config.get("download_path", os.path.join(os.path.expanduser("~"), "Downloads"))
            
            with st.form("sp_config_form"):
                st.subheader("🤖 Automation Settings")
                new_url = st.text_input("🌐 System Builder URL", value=current_url)
                new_sb_user = st.text_input("👤 System Builder User ID", value=current_sb_user, help="The username for logging in.")
                
                if is_cloud:
                    st.text_input("📂 Download Directory", value=current_dl_path, disabled=True, help="Managed automatically in Cloud.")
                    new_dl_path = "CLOUD_MANAGED" # Value to ignore/preserve
                else:
                    new_dl_path = st.text_input("📂 Download Directory", value=current_dl_path, help="Where the bot saves files (e.g. C:/Users/Public/Downloads)")
                
                c1, c2 = st.columns(2)
                with c1:
                    new_interval = st.number_input("⏱️ Check Interval (Mins)", value=sp_config.get("check_interval_minutes", 2))
                with c2:
                    new_retries = st.number_input("🔄 Max Retries", value=sp_config.get("max_retries", 3))

                st.markdown("---")
                st.subheader("📧 Notification Settings")
                new_sender = st.text_input("📤 Sender Email (Gmail)", value=sp_config.get("sender_email", ""), help="The email used to SEND the notification (must match the App Password).")
                new_chooser = st.text_input("👤 Chooser Email (Recipient)", value=current_chooser, help="Who gets the link to select horses?")
                new_notify = st.text_input("🛡️ Admin Notification Email", value=current_notify, help="Who gets system alerts?")
                
                st.markdown("---\n")
                st.subheader("📅 Automation Schedule")
                st.info("These settings control when the Windows Task runs automatically.")
                
                days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                current_day = sp_config.get("scheduled_day", "Saturday")
                if current_day not in days_of_week: current_day = "Saturday"
                
                new_day = st.selectbox("Run Day", days_of_week, index=days_of_week.index(current_day))
                
                current_time_str = sp_config.get("scheduled_time", "09:00")
                try:
                    time_obj = datetime.strptime(current_time_str, "%H:%M").time()
                except:
                    time_obj = datetime.strptime("09:00", "%H:%M").time()
                    
                new_time = st.time_input("Run Time", value=time_obj)
                
                st.markdown("---\n")
                st.subheader("🌍 Publishing Website Settings")
                new_web_url = st.text_input("🔗 Website URL", value=sp_config.get("website_url", ""))
                new_web_user = st.text_input("👤 Website Username", value=sp_config.get("website_user", ""))
                
                if st.form_submit_button("Save Configuration"):
                    # Update Config Object
                    if "saturday_punter" not in config: config["saturday_punter"] = {}
                    config["saturday_punter"]["chooser_email"] = new_chooser
                    config["saturday_punter"]["sender_email"] = new_sender
                    config["saturday_punter"]["notification_email"] = new_notify
                    config["saturday_punter"]["system_builder_url"] = new_url
                    config["saturday_punter"]["system_builder_user"] = new_sb_user
                    if new_dl_path != "CLOUD_MANAGED":
                        config["saturday_punter"]["download_path"] = new_dl_path
                        
                    config["saturday_punter"]["check_interval_minutes"] = new_interval
                    config["saturday_punter"]["max_retries"] = new_retries
                    config["saturday_punter"]["website_url"] = new_web_url
                    config["saturday_punter"]["website_user"] = new_web_user
                    save_config(config)

            st.markdown("---")
            
            with st.expander("🧪 Testing & Overrides", expanded=True):
                st.warning("These settings override the normal automated logic. Use for testing only.")
                
                testing_config = config.get("testing", {})
                
                with st.form("testing_config_form"):
                    
                    st.subheader("Global Date Override")
                    enable_date_override = st.checkbox("Enable Global Date Override", value=testing_config.get("enable_date_override", False), help="If checked, all bots/UIs will perform actions as if THIS is the date.")
                    
                    # Default to 31/01/2025 as requested
                    current_override_str = testing_config.get("override_date", "2025-01-31")
                    try:
                        override_val = datetime.strptime(current_override_str, "%Y-%m-%d").date()
                    except:
                        override_val = datetime(2025, 1, 31).date()
                        
                    override_date = st.date_input("Override Date", value=override_val)
                    
                    st.subheader("Product Configuration")
                    default_prod = "Test Saturday Punter (justtext)"
                    current_prod = testing_config.get("product_name_override", default_prod)
                    product_override = st.text_input("Website Product Name", value=current_prod, help="Exact name of the product in the CMS dropdown.")
                    
                    if st.form_submit_button("Save Test Settings"):
                        config["testing"] = {
                            "enable_date_override": enable_date_override,
                            "override_date": override_date.strftime("%Y-%m-%d"),
                            "product_name_override": product_override
                        }
                        save_config(config)
                        st.success("Test Settings Updated.")
                        time.sleep(1); st.rerun()

            st.markdown("---")
            st.markdown("---")
            st.subheader("🔐 Credentials Vault (Secure)")
            try:
                import keyring
                # Check if backend exists by trying a dummy get
                try:
                    keyring.get_password("test", "test")
                except Exception:
                    # If this fails (NoKeyringError), we are likely in Cloud Run
                    raise ImportError("No Keyring Backend")

                # --- System Builder Creds ---
                has_sb_creds = keyring.get_password("system_builder", "admin") is not None
                sb_icon = "🟢" if has_sb_creds else "🔴"
                
                # --- Email Creds ---
                has_email_creds = keyring.get_password("email_sender", "admin") is not None
                email_icon = "🟢" if has_email_creds else "🔴"

                # --- Website Creds ---
                has_web_creds = keyring.get_password("website_publish", "admin") is not None
                web_icon = "🟢" if has_web_creds else "🔴"
                
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.write(f"System Builder Password: **{sb_icon}**")
                    sb_pass = st.text_input("Set System Builder Password", type="password", key="sb_pass_input")
                    if st.button("Save SB Password"):
                        if sb_pass:
                            keyring.set_password("system_builder", "admin", sb_pass)
                            st.success("SB Password Saved.")
                            time.sleep(1); st.rerun()

                with c2:
                    st.write(f"Email Sender Password: **{email_icon}**")
                    email_pass = st.text_input("Set Email App Password", type="password", help="Use Gmail App Password if using Gmail.", key="email_pass_input")
                    if st.button("Save Email Password"):
                        if email_pass:
                            keyring.set_password("email_sender", "admin", email_pass)
                            st.success("Email Password Saved.")
                            time.sleep(1); st.rerun()

                with c3:
                    st.write(f"Website Password: **{web_icon}**")
                    web_pass = st.text_input("Set Website Password", type="password", key="web_pass_input")
                    if st.button("Save Web Password"):
                        if web_pass:
                            keyring.set_password("website_publish", "admin", web_pass)
                            st.success("Website Password Saved.")
                            time.sleep(1); st.rerun()

            except (ImportError, Exception):
                # Fallback for Cloud Run where keyring is not usable
                st.info("ℹ️ Cloud Environment Detected: Keyring disabled. Using Environment Variables.")
                    
        with tab2:
            st.warning("⚠️ **Manual Override Zone**")
            st.write("Triggers for the automation bots.")
            
            if st.button("Trigger 'System Builder' Run (Manual)", type="primary"):
                # Clear old debug images so we know what's new
                try:
                    debug_dir = ".bot_debug"
                    if os.path.exists(debug_dir):
                        for file in os.listdir(debug_dir):
                            if file.endswith(".png") or file.endswith(".html"):
                                os.remove(os.path.join(debug_dir, file))
                    st.toast("🧹 Cleared old debug screenshots")
                except Exception as e:
                    print(f"Failed to clear debug: {e}")

                st.info("🚀 Starting Full Orchestrator (Bot + Email)...")
                
                # Create a placeholder for logs
                log_placeholder = st.empty()
                logs = []
                
                try:
                    process = subprocess.Popen(
                        [sys.executable, "-u", "execution/orchestrator.py"], # CHANGED: Run Orchestrator
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        cwd=os.getcwd()
                    )
                    
                    # Stream logs line by line
                    for line in iter(process.stdout.readline, ''):
                        if line:
                            # Parse emojis for cleaner display? Or just raw.
                            logs.append(line)
                            # Keep last 15 lines only to save space, or show all in a scrollbox
                            log_text = "".join(logs[-20:]) 
                            log_placeholder.code(log_text, language="bash")
                    
                    process.wait()
                    
                    if process.returncode == 0:
                        st.success("✅ Bot Finished Successfully! Check Downloads.")
                    else:
                        st.error(f"❌ Bot Failed with code {process.returncode}")
                        
                except Exception as e:
                    st.error(f"Failed to launch script: {e}")
            debug_dir = ".bot_debug"
            if os.path.exists(debug_dir):
                files = sorted(os.listdir(debug_dir))
                if files:
                    selected_img = st.selectbox("View Screenshot", files)
                    st.image(os.path.join(debug_dir, selected_img))
                else:
                     st.info("No debug images found (Bot hasn't run yet).")

    elif menu == "⛵ PPD Club":
        st.title("⛵ PPD Club")
        st.info("This module is under construction.")
        st.image("https://placehold.co/600x400?text=Future+Expansion", caption="PPD Logic Placeholder")

    elif menu == "🧠 Being a Genius":
        st.title("🧠 Being a Genius")
        st.write("This section is reserved for high-level strategic inputs.")
        st.text_area("Your Genius Idea:", height=150)
        st.button("Save Idea")

if __name__ == "__main__":
    main()
