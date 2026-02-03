import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
try:
    import keyring
except ImportError:
    keyring = None
import os
import sys

CONFIG_FILE = "config.json"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def send_email_notification(subject, body_html, to_email=None):
    """
    Sends an email using credentials from Admin Dashboard.
    If to_email is None, sends to the 'chooser_email' defined in config.
    """
    print("[EMAIL] Initializing email sequence...")
    
    # 1. Load Config
    config = load_config()
    sp_config = config.get("saturday_punter", {})
    
    # Fetch Email Config
    notification_email = sp_config.get("notification_email", "") 
    sender_email = sp_config.get("sender_email", "")
    
    # Logic: 
    # SENDER = sender_email (if set) -> else notification_email
    # RECIPIENT = to_email (if set) -> else chooser_email
    
    from_email = sender_email if sender_email else notification_email
    
    if not to_email:
        to_email = sp_config.get("chooser_email", "")
        
    if not from_email or not to_email:
        print("[ERROR] Missing Email Config. Please configure 'Sender Email' and 'Chooser Email' in Admin Dashboard.")
        return False

    # 2. Load Password
    # Try Env Var first (Cloud), then Keyring (Local)
    password = os.getenv("NOTIFICATION_EMAIL_PASSWORD")
    if not password:
         try:
             password = keyring.get_password("email_sender", "admin")
         except:
             pass
    
    if not password:
        print("[ERROR] Email Password not found (Set NOTIFICATION_EMAIL_PASSWORD env var or use Keyring).")
        return False
        
    # SANITIZE: Remove spaces if user pasted "xxxx xxxx xxxx"
    password = password.replace(" ", "").strip()
    
    print(f"[EMAIL] Attempting Login...")
    print(f"[EMAIL] User: {from_email}")
    if len(password) > 4:
        print(f"[EMAIL] Pass Hint: {password[:2]}...{password[-2:]} (Length: {len(password)})")
    else:
        print(f"[EMAIL] Pass Hint: **** (Length: {len(password)})")

    # 3. Construct Message
    msg = MIMEMultipart('alternative')
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = f"🏇 {subject}"

    dashboard_url = os.getenv("DASHBOARD_URL", "http://localhost:8501")

    # Create plain text version (Always include the link!)
    text_content = f"""
    {subject}
    
    The system has processed the latest data.
    
    OPEN TRADING DESK: {dashboard_url}
    
    (If the link above is not clickable, copy and paste it into your browser)
    """
    text_part = MIMEText(text_content, 'plain')
    
    # Update HTML to also include a text link backup
    html_content = body_html.replace("</body>", f"<p>Or open: <a href='{dashboard_url}'>{dashboard_url}</a></p></body>")
    html_part = MIMEText(html_content, 'html')

    # Attach parts: Text FIRST, then HTML (Standard)
    msg.attach(text_part)
    msg.attach(html_part)

    # 4. Connect and Send
    try:
        import ssl
        # Create secure connection context
        context = ssl.create_default_context()

        # Connect to Gmail SMTP (SSL Port 465)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(from_email, password)
            server.sendmail(from_email, to_email, msg.as_string())
        
        print(f"[SUCCESS] Email sent to {to_email}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")
        return False

if __name__ == "__main__":
    # Test Mode
    # Test Mode
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("[TEST] Sending Simulation Email...")
        test_body = """
        <h2>Saturday Racing Data Ready</h2>
        <p>The system has successfully downloaded and processed the latest data.</p>
        <ul>
            <li><b>Source File:</b> Simulation_File.csv</li>
            <li><b>Total Runners:</b> 999 (Simulation)</li>
            <li><b>Venues:</b> 12</li>
        </ul>
        <p>
            <a href="http://localhost:8501" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                Open Trading Desk
            </a>
        </p>
        <p style="color: #666; font-size: 12px; margin-top: 20px;">
            <i>- Antigravity Orchestrator (Test Mode)</i>
        </p>
        """
        send_email_notification("Please choose Saturday Punter selections (Simulation)", test_body)
