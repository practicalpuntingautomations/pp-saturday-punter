import asyncio
import re # Added for Regex matching
from playwright.async_api import async_playwright
try:
    import keyring
except ImportError:
    keyring = None
import json
import os
import datetime
import time

# --- CONFIG ---
DOWNLOAD_DIR = os.path.expanduser("~/Downloads")
CONFIG_FILE = "config.json"
DEBUG_SCREENSHOT_DIR = ".bot_debug"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def get_next_saturday():
    # 1. CHECK FOR CONFIG OVERRIDE
    try:
         config = load_config()
         test_cfg = config.get("testing", {})
         if test_cfg.get("enable_date_override"):
             ov_date_str = test_cfg.get("override_date")
             if ov_date_str: # Format is YYYY-MM-DD from Streamlit
                 # Parse and Reformat to DD/MM/YYYY
                 d = datetime.datetime.strptime(ov_date_str, "%Y-%m-%d")
                 formatted = d.strftime("%d/%m/%Y")
                 print(f"[INFO] [TEST MODE] Date Overridden to {formatted}")
                 return formatted
    except Exception as e:
        print(f"[WARN] Config Check Failed: {e}")

    # 2. NORMAL LOGIC: Target = Next Saturday ("Upcoming Saturday").
    # If Today is Saturday -> Target = Today.
    # Else -> Target = Next Saturday.
    today = datetime.date.today()
    weekday = today.weekday() # Mon=0, Sat=5
    
    if weekday == 5:
        target = today
    else:
        # (5 - current) % 7 give days until Saturday
        days_ahead = (5 - weekday) % 7
        target = today + datetime.timedelta(days=days_ahead)
        
    formatted = target.strftime("%d/%m/%Y")
    print(f"[INFO] Calculated Target Date: {formatted} (Today is {today.strftime('%A')})")
    return formatted

async def run_bot():
    print(f"[{datetime.datetime.now()}] [INFO] System Builder Bot Initiated...")
    
    # Ensure debug dir exists
    if not os.path.exists(DEBUG_SCREENSHOT_DIR):
        os.makedirs(DEBUG_SCREENSHOT_DIR)

    # Load Config
    config = load_config()
    sp_config = config.get("saturday_punter", {})
    url = sp_config.get("system_builder_url", "http://equest.optimalsolutions.com.au/")
    
    # User / Pass (Env Var Priority)
    username = os.getenv("SYSTEM_BUILDER_USER") or sp_config.get("system_builder_user", "")
    
    password = os.getenv("SYSTEM_BUILDER_PASSWORD")
    if not password:
         try:
             password = keyring.get_password("system_builder", "admin")
         except Exception:
             password = None

    # Configure Download Dir
    if os.getenv("GCS_BUCKET_NAME"):
        # Force tmp in cloud
        DOWNLOAD_DIR = "/tmp"
        print(f"[INFO] Cloud Mode: Forcing Download Path to {DOWNLOAD_DIR}")
    else:
        raw_dl_path = sp_config.get("download_path", "~/Downloads")
        DOWNLOAD_DIR = os.path.expanduser(raw_dl_path)
    
    if not os.path.exists(DOWNLOAD_DIR):
        print(f"[WARN] Configured download path '{DOWNLOAD_DIR}' does not exist. Creating it.")
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        
    print(f"[INFO] Download Directory: {DOWNLOAD_DIR}")

    if not password:
        print("[ERROR] Password not found (Set SYSTEM_BUILDER_PASSWORD env var or use Vault).")
        return False

    MAX_RETRIES = 3
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n[INFO] --- Attempt {attempt} of {MAX_RETRIES} ---")
        
        async with async_playwright() as p:
            # Launch Browser (Headless=True for production, False for debugging if needed)
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(accept_downloads=True)
            page = await context.new_page()

            try:
                print(f"[NAV] Navigating to {url}")
                try:
                    await page.goto(url, timeout=60000) # Extended timeout
                except Exception as e:
                    print(f"[WARN] Navigation Warning: {e}")
                    
                await page.wait_for_load_state("domcontentloaded")
                
                # DUMP HTML FOR DEBUGGING
                content = await page.content()
                with open("debug_login_source.html", "w", encoding="utf-8") as f:
                    f.write(content)
                print("[FILE] Saved debug_login_source.html")
                
                await page.screenshot(path=f"{DEBUG_SCREENSHOT_DIR}/01_login_page.png")
                
                # Selectors (Best Guess - Standard System Builder)
                # If these fail, we look at the screenshot
                # Correct ASP.NET Selectors found via debug_login_source.html
                print("[ACTION] Attempting Login (ASP.NET IDs)...")
                await page.fill("input[id='MainContent_txtUserName']", username) 
                await page.fill("input[id='MainContent_txtPassword']", password)
                await page.click("input[id='MainContent_btnLogin']")
                
                await page.wait_for_load_state("networkidle")
                await page.screenshot(path=f"{DEBUG_SCREENSHOT_DIR}/02_dashboard.png")
                print("[SUCCESS] Login Attempted.")

                # DUMP DASHBOARD HTML FOR DEBUGGING
                content = await page.content()
                with open("debug_dashboard_source.html", "w", encoding="utf-8") as f:
                    f.write(content)
                print("[FILE] Saved debug_dashboard_source.html")

                # 2. NAVIGATE TO GENERATE
                print("[NAV] Navigating to Generate Selections...")
                
                # STEP 2A: Handle "Show Selections" / "Hide Selections" Toggle
                # User Feedback: "Looks like it was not pressed".
                # Cause: force=True might be ignoring JS handlers or validators.
                # Fix: Use human-like interaction (Scroll -> Hover -> Click).
                try:
                    show_btn_sel = "#MainContent_lbtnShowSelections"
                    
                    # Wait for element availability
                    await page.wait_for_selector(show_btn_sel, state="attached")
                    
                    # Check text state
                    btn_text = await page.inner_text(show_btn_sel)
                    print(f"[INFO] 'Show/Hide' Button Text: '{btn_text}'")
                    
                    if "Show" in btn_text:
                        print("[ACTION] Clicking 'Show Selections' (Human emulation)...")
                        
                        # 1. Scroll into view
                        await page.locator(show_btn_sel).scroll_into_view_if_needed()
                        
                        # 2. Hover first
                        await page.hover(show_btn_sel)
                        await asyncio.sleep(0.5)
                        
                        # 3. Click WITHOUT force (requires element to be interactive)
                        # This ensures JS handlers fire correctly.
                        await page.click(show_btn_sel)

                        # 4. Wait for PostBack or Network
                        print("[WAIT] Waiting for 'Show' action to complete...")
                        await page.wait_for_load_state("networkidle")
                        await asyncio.sleep(2)
                        
                    elif "Hide" in btn_text:
                        print("[INFO] Panel is already open. Skipping click.")
                    else:
                        # Fallback click
                        await page.click(show_btn_sel)
                        
                except Exception as e:
                    print(f"[WARN] Failed to handle 'Show Selections': {e}")
                    # Take debug shot specifically for this failure
                    await page.screenshot(path=f"{DEBUG_SCREENSHOT_DIR}/98_show_btn_fail.png")

                # STEP 2B: Click "Generate Selections"
                try:
                    # Setup Dialog Handler in case of alerts
                    page.on("dialog", lambda dialog: dialog.accept())
                    
                    print("[ACTION] Clicking 'Generate Selections'...")
                    # Click the ID with force=True
                    await page.click("#MainContent_lbtnGenerateSelections", timeout=10000, force=True)
                    print("[SUCCESS] Clicked 'Generate Selections'.")
                    
                except Exception as e:
                    print(f"[WARN] Standard ID Click Failed: {e}")
                    # Try via text as backup
                    try:
                        print("[ACTION] Trying Click via Text='Generate Selections'...")
                        await page.click("text=Generate Selections", force=True)
                    except Exception as e2:
                        print(f"[ERROR] All click methods failed: {e2}")
                
                # Check if we moved?
                print("[WAIT] Waiting for Generate Panel (looking for 'Selections Date' label)...")
                try:
                    # Wait for the specific element that confirms we are on the new page
                    # We use a compassionate timeout of 10s
                    await page.wait_for_selector("text=Selections Date", timeout=10000)
                    print("[SUCCESS] 'Selections Date' label found! Navigation Successful.")
                except:
                    print("[WARN] 'Selections Date' NOT found. Navigation likely failed.")
                    
                    # Check for validation errors again
                    visible_errors = await page.locator(".failureNotification, .validation-summary-errors").all_inner_texts()
                    if any(e.strip() for e in visible_errors):
                        print(f"[ERROR] Post-click Validation Errors: {visible_errors}")
                    
                # Screenshot regardless
                screenshot_path = f"{DEBUG_SCREENSHOT_DIR}/03_generate_page.png"
                await page.screenshot(path=screenshot_path)
                print(f"[FILE] Saved Screenshot: {screenshot_path}")

                # DUMP GENERATE PAGE HTML
                content = await page.content()
                with open("debug_generate_source.html", "w", encoding="utf-8") as f:
                    f.write(content)
                print("[FILE] Saved debug_generate_source.html")
                
                # 3. SET DATE
                target_date = get_next_saturday()
                print(f"[ACTION] Setting Date to {target_date}...")
                
                try:
                    # Use precise ID found in debug dump
                    date_input_id = "#MainContent_txtSelectionsDate"
                    
                    # Wait for it to be visible first
                    await page.wait_for_selector(date_input_id, state="visible", timeout=10000)
                    
                    # Clear and Fill with human delay
                    await page.fill(date_input_id, "") 
                    await page.type(date_input_id, target_date, delay=100) # Type slowly
                    print("[SUCCESS] Date Typed (Exact ID).")
                    
                    # CRITICAL: Trigger validation by clicking outside
                    print("[ACTION] Clicking background to trigger date validation...")
                    await page.click("body") 
                    await asyncio.sleep(1) # Wait for JS validation
                    
                except Exception as e:
                    print(f"[ERROR] Date Set Failed: {e}")
                    # If date fails, maybe retry loop?
                    raise e # Let retry loop catch it

                # 4. EXPORT
                print("[ACTION] Clicking 'Export Selections'...")
                
                try:
                     export_btn_id = "#MainContent_lbtnExportSelections"
                     # Hover first for safety
                     if await page.locator(export_btn_id).is_visible():
                         await page.hover(export_btn_id)
                         await asyncio.sleep(0.5)
                         await page.click(export_btn_id)
                         print("[SUCCESS] Export Clicked (Exact ID).")
                     else:
                         print("[WARN] Exact Export ID not found. Trying text fallback...")
                         await page.click("text=Export Selections", force=True)
                         print("[SUCCESS] Export Clicked (Text).")
                         
                except Exception as e:
                    print(f"[ERROR] Export Click Failed: {e}")
                    raise e

                # 5. WAIT FOR FILE & DOWNLOAD
                # 5. WAIT FOR PROCESSING (Handle "Please Wait" Modal)
                print("[WAIT] Checking for 'Please Wait' modal...")
                
                # The modal has ID 'lblProgress' or 'MainContent_Img1'
                try:
                    # Wait for modal to APPEAR (confirming the click worked)
                    modal_selector = "#lblProgress" 
                    try:
                        await page.wait_for_selector(modal_selector, state="visible", timeout=5000)
                        print("[INFO] 'Please Wait' modal appeared. Processing started...")
                    except:
                        print("[WARN] 'Please Wait' modal didn't appear instantly. It might be fast or missed.")

                    # Wait for modal to DISAPPEAR (This is the real wait)
                    # Max wait 5 minutes for generation
                    print("[WAIT] Waiting for 'Please Wait' to vanish (Generation in progress)...")
                    await page.wait_for_selector(modal_selector, state="hidden", timeout=300000)
                    print("[SUCCESS] 'Please Wait' vanished. File should be ready.")
                    
                    # Small buffer for DOM update
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    print(f"[WARN] Modal wait logic had an issue (continuing to poll): {e}")

                # 6. FIND & DOWNLOAD FILE (Structured Parsing)
                print("[ACTION] Scanning file list for 'The Buccaneer'...")
                
                found_download = False
                for i in range(5): # Review list a few times if needed
                    try:
                        # BEST PRACTICE: Fix Selector to target TEXT, not HREF
                        # The href is javascript:..., so we must grab the links by location or tag
                        # We target the Export Grid 'gvExportSelection' specifically
                        file_links = await page.locator("#MainContent_gvExportSelection a").all()
                        
                        if len(file_links) == 0:
                            # Fallback if ID changes
                            file_links = await page.locator("a").all()

                        candidates = []
                        for link in file_links:
                            text = await link.inner_text()
                            clean_text = text.strip()
                            
                            # Filter: Must start with ExportSelections
                            if not clean_text.startswith("ExportSelections"):
                                continue

                            # STRICT FILTER: Start with "ExportSelections" + Separator + "The" + Separator + "Buccaneer"
                            # Use [ _] to allow Space OR Underscore.
                            # Matches: "ExportSelections The Buccaneer 20..." (14 digits?)
                            # Regex updated to \d+ to handle 12, 14, or more digits.
                            regex = re.compile(r"^ExportSelections[ _]The[ _]Buccaneer[ _]+(\d+)\.csv", re.IGNORECASE)
                            match = regex.search(clean_text)
                            
                            if match:
                                # Extract Timestamp (Handle any length)
                                timestamp = int(match.group(1))
                                
                                candidates.append({
                                    "element": link,
                                    "name": clean_text,
                                    "timestamp": timestamp
                                })
                            else:
                                 # Debug: Print close calls (starts with ExportSelections but failing regex)
                                 if "Buccaneer" in clean_text:
                                     print(f"[DEBUG] Rejected candidate: '{clean_text}' (Regex mismatch. Check timestamp/separators)")
                                
                        # Start Debug: Show what we saw
                        if len(file_links) > 0:
                            # Log meaningful sample: Find first 5 that look like "ExportSelections"
                            sample_files = []
                            count = 0
                            for link in file_links:
                                 txt = await link.inner_text()
                                 if "ExportSelections" in txt:
                                     sample_files.append(txt.strip())
                                     count += 1
                                 if count >= 5: break
                            print(f"[DEBUG] Saw {len(file_links)} total links. Sample Exports: {sample_files}")
                        # End Debug

                        # Sort candidates (Newest First)
                        if candidates:
                            candidates.sort(key=lambda x: x["timestamp"], reverse=True)
                            best_match = candidates[0]
                            
                            print(f"[SUCCESS] Found {len(candidates)} candidates. Best Match: '{best_match['name']}'")
                            
                            async with page.expect_download() as download_info:
                                # SCROLL + CLICK (User Requirement)
                                # Use JS scroll to be 100% sure it's centered
                                await best_match["element"].scroll_into_view_if_needed()
                                await best_match["element"].evaluate("el => el.scrollIntoView({block: 'center'})")
                                await asyncio.sleep(1.0) # Stability wait
                                await best_match["element"].click()
                                await best_match["element"].click()
                                
                            download = await download_info.value
                            save_path = os.path.join(DOWNLOAD_DIR, download.suggested_filename)
                            await download.save_as(save_path)
                            print(f"[FILE] Downloaded to: {save_path}")
                            found_download = True
                            break
                    except Exception as e:
                        print(f"[ERROR] Parsing error: {e}")
                        pass
                    
                    if found_download: break
                    
                    # Rescan logic
                    print(f"[INFO] 'The Buccaneer' not found in list yet. Retrying scan ({i+1}/5)...")
                    await asyncio.sleep(10) # Wait 10 seconds between scans
                    
                    # Take debug shot if failing
                    if i == 2:
                         await page.screenshot(path=f"{DEBUG_SCREENSHOT_DIR}/97_poll_mid.png")


                if not found_download:
                    print("[ERROR] Timeout: File did not appear within 15 minutes.")
                    
                    # Dump HTML at timeout for analysis
                    content = await page.content()
                    with open("debug_timeout_source.html", "w", encoding="utf-8") as f:
                        f.write(content)
                    print("[FILE] Saved debug_timeout_source.html")
                    
                    # Print ALL links to see what was there
                    links = await page.locator("a").all_inner_texts()
                    print(f"[DEBUG] Visible Links at timeout: {links[:20]}...") # Show first 20
                    
                    await page.screenshot(path=f"{DEBUG_SCREENSHOT_DIR}/99_timeout.png")
                    
                    # CRITICAL: RAISE Exception to trigger Retry Loop
                    raise Exception("File list was empty or file not found.")

                if found_download:
                    # SUCCESS - Return Path
                    await browser.close()
                    print("[INFO] Bot Finished Successfully.")
                    return save_path

            except Exception as e:
                print(f"[ERROR] Attempt {attempt} Failed: {e}")
                await page.screenshot(path=f"{DEBUG_SCREENSHOT_DIR}/99_error_attempt_{attempt}.png")
                # Loop will continue to next attempt
            
            finally:
                if 'browser' in locals():
                    await browser.close()
        
        # End of Attempt Loop
        print(f"[INFO] End of Attempt {attempt}. Retrying in 10s...")
        await asyncio.sleep(10)

    print("[CRITICAL] All Attempts Failed.")
    return None

if __name__ == "__main__":
    asyncio.run(run_bot())
