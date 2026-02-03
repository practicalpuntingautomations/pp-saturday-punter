import asyncio
from playwright.async_api import async_playwright
try:
    import keyring
except ImportError:
    keyring = None
import json
import os
import sys
import time
from datetime import datetime

# Define Config File logic similar to other scripts
CONFIG_FILE = "config.json"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

async def upload_content(doc_title, doc_date_str, doc_body_text):
    """
    Orchestrates the upload process:
    1. Login
    2. Nav to 'Practical Punting' (Green Star)
    3. Nav to Tips -> New
    4. Fill Form
    5. PAUSE for User Verification
    """
    print("[UPLOAD] Starting Website Upload Bot...")
    
    with open("upload_log.txt", "w") as log:
        log.write(f"[START] Upload Bot triggered at {datetime.now()}\n")
        
        # 1. Load Creds
        config = load_config()
        sp_config = config.get("saturday_punter", {})
        
        url = sp_config.get("website_url", "")
        # Env Var Priority
        username = os.getenv("WEB_UPLOAD_USER") or sp_config.get("website_user", "")
        
        password = os.getenv("WEB_UPLOAD_PASSWORD")
        if not password:
            try:
                password = keyring.get_password("website_publish", "admin")
            except:
                password = None
        
        log.write(f"[INFO] Loaded Config - URL: '{url}', User: '{username}', Pass: {'YES' if password else 'NO'}\n")

        if not url or not username or not password:
            msg = "[ERROR] Missing Website Credentials. Configure Env Vars: WEB_UPLOAD_USER/PASSWORD"
            print(msg)
            log.write(msg + "\n")
            return False

        log.write("[INFO] Starting Playwright...\n"); log.flush()
        
        try:
            async with async_playwright() as p:
                log.write("[INFO] Launching Browser...\n"); log.flush()
                
                # Cloud / Headless Logic
                is_cloud = os.getenv("K_SERVICE") or os.getenv("HEADLESS_MODE")
                use_headless = True if is_cloud else False
                
                print(f"[INFO] Browser Mode: {'Headless' if use_headless else 'Headed'}")
                browser = await p.chromium.launch(headless=use_headless, slow_mo=50)
                context = await browser.new_context()
                page = await context.new_page()
                log.write("[INFO] Browser Launched. Context created.\n"); log.flush()
                
                try:
                    # --- STEP 1: LOGIN ---
                    log.write(f"[UPLOAD] Navigating to {url}...\n"); log.flush()
                    await page.goto(url, timeout=60000) # 60s timeout
                    
                    log.write("[UPLOAD] Logging in...\n"); log.flush()
                    await page.fill("input[name*='UserName']", username) 
                    await page.fill("input[name*='Password']", password)
                    
                    log.write("[UPLOAD] Clicking Log On...\n"); log.flush()
                    await page.click("input[value='Log on'], button:has-text('Log on')") 
                    
                    await page.wait_for_load_state("networkidle")
                    log.write("[UPLOAD] Login submitted. Waiting for dashboard...\n"); log.flush()
                    
                    # --- STEP 2: GREEN STAR ---
                    log.write("[UPLOAD] Looking for 'Practical Punting' Green Star...\n"); log.flush()
                    log.write("[UPLOAD] Finding correct 'Practical Punting' tile...\n"); log.flush()
                    
                    # IFRAME STRATEGY
                    # The Dashboard Tiles usually live inside the 'cmsdesktop' iframe
                    try:
                        log.write("[UPLOAD] Switching to 'cmsdesktop' iframe...\n"); log.flush()
                        frame = page.frame_locator("iframe[name='cmsdesktop']")
                        
                        # Wait for iframe to have content
                        log.write("[UPLOAD] Waiting for tile inside iframe...\n")
                        # We use a broad text match inside the frame, because inside the frame there should be only one main tile
                        target = frame.locator("text='Practical Punting'").first
                        await target.wait_for(state="visible", timeout=10000)
                        
                        log.write("[UPLOAD] Found tile in iframe. Clicking...\n"); log.flush()
                        await target.click()
                        
                    except Exception as e:
                        log.write(f"[WARN] Iframe click failed ({e}). Trying Main Page fallback...\n")
                        # Fallback to main page if iframe logic fails (e.g. if it's not an iframe in some views)
                        await page.click(".app-practicalpunting")
                    
                    await page.wait_for_load_state("networkidle")
                    log.write("[UPLOAD] Entered Practical Punting App.\n"); log.flush()
                    
                    # --- STEP 3: TIPS MENU ---
                    # --- STEP 3: TIPS MENU ---
                    log.write("[UPLOAD] Clicking 'Tips' on left menu...\n"); log.flush()
                    try:
                        # Try clicking inside the iframe first (most likely)
                        frame = page.frame_locator("iframe[name='cmsdesktop']")
                        await frame.locator("text='Tips'").click()
                    except:
                        # Fallback to main page
                        await page.click("text='Tips'")
                        
                    await page.wait_for_load_state("networkidle")
                    await asyncio.sleep(2) 
                    
                    # --- STEP 4: NEW BUTTON ---
                    # --- STEP 4: NEW BUTTON ---
                    log.write("[UPLOAD] Clicking 'New' button...\n"); log.flush()
                    
                    # Define frame contexts
                    # 1. Main Dashboard Frame
                    frame = page.frame_locator("iframe[name='cmsdesktop']")
                    # 2. Nested Content Frame (The 'Center' pane of the layout)
                    nested_frame = frame.frame_locator("iframe[name='c']")
                    
                    # Helper to try finding element in both contexts
                    async def smart_click(selector, desc):
                        try:
                            log.write(f"[DEBUG] Looking for '{desc}' in Nested Frame...\n")
                            await nested_frame.locator(selector).first.click(timeout=2000)
                            return True
                        except:
                            try:
                                log.write(f"[DEBUG] Looking for '{desc}' in Main Frame...\n")
                                await frame.locator(selector).first.click(timeout=2000)
                                return True
                            except:
                                return False
                                
                    # Try text=New
                    if not await smart_click("text=New", "New Button (Text)"):
                        # Try Icon
                        if not await smart_click(".cms-icon-plus, .icon-plus", "New Button (Icon)"):
                             log.write("[CRITICAL] 'New' button not found inside Nested OR Main frame.\n")
                             await page.screenshot(path=".bot_debug/new_button_nested_fail.png")
                             raise Exception("New Button not found.")

                    await page.wait_for_load_state("networkidle")
                    await asyncio.sleep(2)
                    
                    # --- STEP 5: PRODUCT SELECTION ---
                    # Determine Product Name (Config or Default)
                    test_config = config.get("testing", {})
                    target_product = test_config.get("product_name_override", "Saturday Punter (justtext)")
                    
                    log.write(f"[UPLOAD] Selecting Product: '{target_product}'...\n"); log.flush()
                    try:
                        # Try nested first
                        await nested_frame.locator("select:near(:text('Product:'))").select_option(label=target_product)
                    except:
                        try:
                             # Try main frame
                             await frame.locator("select:near(:text('Product:'))").select_option(label=target_product)
                        except:
                            # Fallback to name attribute
                            try:
                                await nested_frame.locator("select[name*='Product']").select_option(label=target_product)
                            except:
                                await frame.locator("select[name*='Product']").select_option(label=target_product)
    
                    log.write("[UPLOAD] Waiting for form update...\n"); log.flush()
                    await asyncio.sleep(5) # INCREASED WAIT
                    
                    # --- STEP 6: FILL FORM ---
                    log.write(f"[UPLOAD] Filling Form: {doc_title}...\n"); log.flush()
                    
                    # Target correct frame for inputs
                    target_frame = nested_frame # Default assumption
                    
                    async def robust_fill(field_name, search_terms, value, tag="input"):
                         log.write(f"[DEBUG] Filling '{field_name}'...\n")
                         # 1. Try Name Attribute (Most Robust)
                         for term in search_terms:
                             try:
                                 selector = f"{tag}[name*='{term}']"
                                 await target_frame.locator(selector).first.fill(value, timeout=1000)
                                 return # Success
                             except:
                                 pass
                         
                         # 2. Try :near Label (Visual Fallback)
                         for term in search_terms:
                             try:
                                 await target_frame.locator(f"{tag}:near(:text('{term}'))").first.fill(value, timeout=1000)
                                 return # Success
                             except:
                                 pass
                         
                         # 3. Main Frame Fallback?
                         # (Only if we were wrong about the frame)
                         raise Exception(f"Could not find field: {field_name}")

                    try:
                        # Title
                        await robust_fill("Title", ["Title", "CodeName", "name"], doc_title)
                    except Exception as e:
                        # Fallback to main frame just in case
                        target_frame = frame
                        try:
                            await robust_fill("Title (MainFrame)", ["Title", "CodeName"], doc_title)
                        except:
                            log.write(f"[WARN] Title fill failed. Dumping HTML.\n")
                            html = await target_frame.locator("body").inner_html()
                            with open(".bot_debug/form_page_dump.html", "w", encoding="utf-8") as f:
                                f.write(html)
                            raise e

                    # Date
                    # Usually "TipDate" or "Date"
                    await robust_fill("Date", ["Date", "TipDate"], doc_date_str)
                    
                    # WAITING FOR EDITOR TO APPEAR
                    log.write("[UPLOAD] Date Filled. Waiting for Editor to load...\n"); log.flush()
                    await asyncio.sleep(3)
                    
                    log.write("[UPLOAD] Filling Body Content (HTML Injection)...\n"); log.flush()
                    # Body
                    # Rich Text Editors (CKEditor) often hide the textarea and use an iframe or contenteditable div
                    filled_body = False
                    
                    # RETRY LOOP FOR EDITOR (Wait up to 15s)
                    for attempt in range(5):
                        log.write(f"[DEBUG] Looking for Editor... (Attempt {attempt+1}/5)\n"); log.flush()
                        
                        # Strategy 1: CKEditor Iframe (Direct HTML Injection)
                        try:
                            # Look for iframe with class usually associated with CKEditor
                            editor_frame_selector = "iframe[class*='cke_wysiwyg_frame'], iframe[title*='Rich Text Editor']"
                            if await target_frame.locator(editor_frame_selector).count() > 0:
                                log.write("[DEBUG] Found CKEditor Iframe. Injecting...\n")
                                # FrameLocator
                                frame_loc = target_frame.locator(editor_frame_selector).first.content_frame
                                
                                # We must target an ELEMENT inside the frame to evaluate
                                # frame_loc is a FrameLocator, not a Frame
                                await frame_loc.locator("body").evaluate(f"(el, html) => {{ el.innerHTML = html; }}", doc_body_text)
                                
                                filled_body = True
                                break # Success
                        except Exception as e:
                            log.write(f"[DEBUG] CKEditor Frame attempt failed: {e}\n")

                        # Strategy 2: ContentEditable Div (HTML Injection)
                        if not filled_body:
                            try:
                                # For div, we also need to set innerHTML because .fill() escapes HTML
                                div_selector = "div[contenteditable='true'], body[contenteditable='true']"
                                if await target_frame.locator(div_selector).count() > 0:
                                    log.write("[DEBUG] Found ContentEditable Div. Injecting...\n")
                                    div_loc = target_frame.locator(div_selector).first
                                    js_code = f"arguments[0].innerHTML = {json.dumps(doc_body_text)};"
                                    await div_loc.evaluate(f"(el) => {{ {js_code} }}")
                                    filled_body = True
                                    break
                            except:
                                pass
                                
                        # Strategy 3: Force Visible on Hidden Textarea AND Set Value
                        if not filled_body:
                            try:
                                 # This is a last resort, usually available immediately
                                 if await target_frame.locator("textarea").count() > 0:
                                      # Check if it looks like the main body (often has specific names)
                                      # We don't break immediately here maybe?
                                      # Actually, if we find it, let's try it.
                                      log.write("[DEBUG] Trying text area value set...\n")
                                      await target_frame.locator("textarea").first.evaluate("el => el.style.display = 'block'")
                                      await target_frame.locator("textarea").first.fill(doc_body_text, timeout=2000)
                                      filled_body = True
                                      break
                            except:
                                 pass
                        
                        # Wait before retry
                        await asyncio.sleep(3)

                    if not filled_body:
                        log.write("[CRITICAL] Could not fill Body. Dumping State.\n")
                        html = await target_frame.locator("body").inner_html()
                        with open(".bot_debug/body_fail_dump.html", "w", encoding="utf-8") as f:
                            f.write(html)
                        raise Exception("Failed to fill Body content (Editor not found)")

                    if not filled_body:
                        log.write("[CRITICAL] Could not fill Body. Dumping State.\n")
                        html = await target_frame.locator("body").inner_html()
                        with open(".bot_debug/body_fail_dump.html", "w", encoding="utf-8") as f:
                            f.write(html)
                        raise Exception("Failed to fill Body content")
    
                    # [PAUSE HERE]
                    screenshot_path = ".bot_debug/upload_verification.png"
                    await page.screenshot(path=screenshot_path, full_page=True)
                    log.write(f"[SUCCESS] Form Filled. Saved to {screenshot_path}\n"); log.flush()
                    
                    # Wait 5 Seconds after Body Fill (User Requirement)
                    log.write("[UPLOAD] Waiting 5s after Fill Body...\n")
                    await asyncio.sleep(5)
                    
                    # --- STEP 7: SET STATUS TO PUBLISHED ---
                    log.write("[UPLOAD] Setting Status to 'Published'...\n"); log.flush()
                    try:
                        # Try finding Select near Label
                        await nested_frame.locator("select:near(:text('Tip Status:'))").select_option(label="Published")
                    except:
                        try:
                            # Fallback to name attribute (guessing common CMS names)
                            await nested_frame.locator("select[name*='Status']").select_option(label="Published")
                        except Exception as e:
                             log.write(f"[WARN] Failed to set Status: {e}\n")
                    
                    await asyncio.sleep(1)

                    # --- STEP 8: SAVE TIP DETAILS ---
                    log.write("[UPLOAD] Clicking 'Save tip details'...\n"); log.flush()
                    try:
                        # Green button at top
                        await nested_frame.locator("text=Save tip details").click()
                        await page.wait_for_load_state("networkidle")
                    except Exception as e:
                        log.write(f"[WARN] Failed to click 'Save tip details': {e}\n")

                    # Wait for Save to Process (Crucial for next button enablement)
                    log.write("[UPLOAD] Waiting 5s for Save to complete...\n")
                    await asyncio.sleep(5)

                    # --- STEP 9: GENERATE EMAIL (Handle Popup) ---
                    log.write("[UPLOAD] Clicking 'Generate new email content'...\n"); log.flush()
                    
                    # Setup Dialog Handler (Accept "Overwrite" popup)
                    page.on("dialog", lambda dialog: dialog.accept())
                    
                    try:
                        # Grey button - Wait for it to be clickable
                        btn = nested_frame.locator("text=Generate new email content")
                        
                        # Wait logic: loop check? Or just force wait.
                        # Simple robust approach: Wait, then click
                        await btn.click(timeout=10000, force=True) 
                        
                        # Wait for processing
                        await asyncio.sleep(5)
                    except Exception as e:
                         log.write(f"[WARN] Failed to Generate Email: {e}\n")

                    # --- STEP 10: SAVE AND SEND ---
                    log.write("[UPLOAD] Clicking 'Save and send to...' ...\n"); log.flush()
                    try:
                        # Button text changes (0 users vs 100 users), so partial match
                        btn_send = nested_frame.locator("text=Save and send to")
                        await btn_send.click(timeout=10000, force=True)
                        
                        await page.wait_for_load_state("networkidle")
                        log.write("[SUCCESS] FINAL SAVE CLICKED.\n")
                    except Exception as e:
                         log.write(f"[WARN] Failed to click 'Save and send': {e}\n")
                    
                    # --- FINAL VERIFICATION PAUSE ---
                    log.write("[INFO] Work Complete. Pausing for 10s...\n"); log.flush()
                    print("[CLI] Work Complete. Pausing...")
                    await asyncio.sleep(10)
                    
                    return True
                    
                except Exception as e:
                    msg = f"[ERROR] Execution Failed: {e}"
                    print(msg)
                    log.write(msg + "\n"); log.flush()
                    await page.screenshot(path=".bot_debug/upload_error.png")
                    return False
                finally:
                    await browser.close()
        except Exception as e:
             import traceback
             tb = traceback.format_exc()
             log.write(f"[CRITICAL] Playwright Failed to Launch: {e}\nTraceback:\n{tb}\n"); log.flush()
             return False

if __name__ == "__main__":
    import sys
    import json
    
    # Check if a payload file is provided
    if len(sys.argv) > 1:
        payload_path = sys.argv[1]
        try:
            with open(payload_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            print(f"[CLI] Received Payload from {payload_path}")
            # Ensure upload_content is awaited correctly
            result = asyncio.run(upload_content(
                data.get("title"),
                data.get("date"),
                data.get("body")
            ))
            
            # Clean up payload
            try:
                os.remove(payload_path)
            except:
                pass
                
            if result:
                sys.exit(0) # Success
            else:
                sys.exit(1) # Failure
                
        except Exception as e:
            print(f"[CLI ERROR] {e}")
            sys.exit(1)
            
    else:
        # Test Run
        asyncio.run(upload_content("Test Title", "01/01/2026", "Test Body"))
