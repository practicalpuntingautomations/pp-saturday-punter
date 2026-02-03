import streamlit as st
import pandas as pd
import sys
import os
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode
from datetime import datetime

# Ensure execution directory is in path to import other modules
sys.path.append(os.path.dirname(__file__))

import process_racing_data
import generate_racing_doc
import send_notification
import cloud_utils
import json
import time

# --- CLOUD CONFIG SYNC ---
# Try to download the shared config from GCS on startup
try:
    bucket = os.getenv("GCS_BUCKET_NAME")
    if bucket:
        print("[INIT] Syncing Config from Cloud Storage...")
        if cloud_utils.sync_config_from_gcs(bucket, "config.json"):
             st.toast("☁️ Configuration Synced from Cloud!", icon="☁️")
except Exception as e:
    print(f"[WARN] Config Sync Failed: {e}")
# -------------------------

st.set_page_config(page_title="Saturday Punter Orchestrator", layout="wide")

# Valid columns in desired order
DESIRED_ORDER = [
    "Venue", "RN", "TN", "Horse Name", "Today Price", "Line of Betting",
    "Race Group", "Race Class", "Today Dist", "Track Condition", "No. Starters",
    "Today Race PM", "OneHundredRatings", "Ultimrating", "Ultimrank",
    "BuccanneerPoints", "BuccanneerRank", "RaceVolatility", "Comments"
]

@st.cache_data
def load_data():
    """Loads and caches the racing data."""
    try:
        latest_file = process_racing_data.get_latest_racing_file()
        df = process_racing_data.load_and_clean_data(latest_file)
        
        # Ensure 'Bet Type' is NOT in the file data yet, we manage it separately
        if 'Bet Type' in df.columns:
             pass
             
        # Generate a unique ID for state management
        # Composite ID: Venue_RN_HorseName
        df['UniqueKey'] = df['Venue'].astype(str) + "_" + df['RN'].astype(str) + "_" + df['Horse Name'].astype(str)
        
        # We don't need to set index for AgGrid, but having UniqueKey is useful
        # Initialize Bet Type column
        df['Bet Type'] = ""
        
        print(f"[DEBUG] Loaded Data: {len(df)} rows.")
        print(df.head())
        return df, latest_file
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None, None

def main():
    st.title("🏇 Saturday Punter - Trading Desk")
    
    # --- SECURITY GATE ---
    app_password = os.getenv("APP_PASSWORD")
    if app_password:
        if "authenticated" not in st.session_state:
            st.session_state.authenticated = False
            
        if not st.session_state.authenticated:
            st.markdown("### 🔒 Login Required")
            pwd_input = st.text_input("Enter Access Password", type="password")
            if pwd_input:
                if pwd_input == app_password:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Incorrect Password")
            st.stop()
    
    # 1. Load Data
    if 'data' not in st.session_state:
        df, filename = load_data()
        if df is not None:
            st.session_state.data = df
            st.session_state.filename = filename
            

        else:
            st.stop()
            
    # Always work with the MASTER dataframe
    df = st.session_state.data
    
    # --- REORDER COLUMNS ---
    # Enforce exact order requested by user
    # 1. Bet Type, 2. Venue, 3. RN, 4. TN, 5. Horse Name, etc...
    
    # Base columns from DESIRED_ORDER
    ordered_cols = [c for c in DESIRED_ORDER if c in df.columns]
    
    # Prepend Bet Type if it exists (it should)
    final_order = []
    if "Bet Type" in df.columns:
        final_order.append("Bet Type")
    
    # Add the rest
    final_order.extend(ordered_cols)
    
    # Add any other existing columns (like UniqueKey) at the end just in case, or filter them out
    # We'll just select the specific ones we want to show/manage
    # But we MUST keep 'UniqueKey' for referencing, though AgGrid handles rows by index internally well enough
    if "UniqueKey" in df.columns and "UniqueKey" not in final_order:
        final_order.append("UniqueKey")

    # Reorder DataFrame
    df = df[final_order]
    
    st.markdown(f"**Source:** `{st.session_state.filename}` | **Rows:** {len(df)}")

    # --- CUSTOM SORTING ENGINE (Sidebar) ---
    with st.sidebar.expander("🚀 Advanced Sorting (Multi-Level)", expanded=False):
        st.caption("Sort by up to 8 levels without license limits.")
        
        # Initialize sort state
        if "sort_rules" not in st.session_state:
            st.session_state.sort_rules = [] # List of dicts: {'col': str, 'asc': bool}

        # Controls to add rules
        col_options = list(df.columns)
        
        # UI for managing rules
        c1, c2 = st.columns([3, 1])
        with c1:
            new_sort_col = st.selectbox("Column", col_options, key="new_sort_col_picker")
        with c2:
            new_sort_dir = st.selectbox("Dir", ["Asc", "Desc"], key="new_sort_dir_picker")
            
        if st.button("➕ Add Sort Rule"):
            # Avoid duplicates? Or allow? Usually unique cols.
            if new_sort_col not in [r['col'] for r in st.session_state.sort_rules]:
                is_asc = (new_sort_dir == "Asc")
                st.session_state.sort_rules.append({'col': new_sort_col, 'asc': is_asc})
            else:
                st.warning(f"{new_sort_col} already added.")

        # Display current rules
        if st.session_state.sort_rules:
            st.write("---")
            st.caption("Active Sort Order:")
            for i, rule in enumerate(st.session_state.sort_rules):
                direction = "⬆️ Asc" if rule['asc'] else "⬇️ Desc"
                c_rule, c_del = st.columns([4, 1])
                with c_rule:
                    st.markdown(f"**{i+1}. {rule['col']}** ({direction})")
                with c_del:
                    if st.button("❌", key=f"del_sort_{i}"):
                        st.session_state.sort_rules.pop(i)
                        st.rerun()
            
            if st.button("Clear All Sorts"):
                st.session_state.sort_rules = []
                st.rerun()
        
        # APPLY SORT TO DATAFRAME
        if st.session_state.sort_rules:
            sort_cols = [r['col'] for r in st.session_state.sort_rules]
            sort_ascs = [r['asc'] for r in st.session_state.sort_rules]
            try:
                df = df.sort_values(by=sort_cols, ascending=sort_ascs)
            except Exception as e:
                st.error(f"Sort Error: {e}")

    # --- AG-GRID SETUP ---
    
    gb = GridOptionsBuilder.from_dataframe(df)
    
    # 1. Configure Columns
    gb.configure_default_column(
        resizable=True,
        sortable=True,
        filterable=True,
        editable=False, # Default read-only
        minWidth=50,
        # maxWidth=150, # REMOVED: This was capping columns!
    )
    
    # 2. Bet Type - The only editable column (Column 1)
    bet_options = ["", "Ultimate Bet", "Standout Bets", "Outsider Bets"]
    gb.configure_column(
        "Bet Type",
        headerName="Bet Type",
        editable=True,
        cellEditor="agSelectCellEditor",
        cellEditorParams={"values": bet_options},
        pinned="left", # Pin to left as it is Column 1 and vital
        width=130,
        minWidth=130
    )
    
    # 3. Specific Column Configs
    # Hide UniqueKey
    gb.configure_column("UniqueKey", hide=True)
    
    # Pin Horse Name? User put it at pos 4. 
    # Usually better to pin identifiers. 
    # Let's Unpin Horse Name based on "order" request, 
    # or keep it pinned but ensure correct order visually.
    # If we pin "Bet Type" (left), "Venue" (?), "RN" (?), "TN" (?), "Horse Name" (?)
    # Pinning too many columns on small screens is bad.
    # Pin Horse Name (Unpinned as per user request for visual match)
    # Added suppressSizeToFit=True to forcing strict pixel width
    gb.configure_column("Horse Name", pinned=False, width=200, suppressSizeToFit=True) 
    
    # Specific widths based on "Trading Desk" Density
    gb.configure_column("Venue", width=110, suppressSizeToFit=True)
    # Widen specific columns as requested (120px)
    for col in ["Today Price", "Race Class", "Today Race PM"]:
        gb.configure_column(col, width=120, suppressSizeToFit=True)
        
    # HUGE COMMENTS COLUMN (User Request)
    gb.configure_column("Comments", width=600, suppressSizeToFit=True)
    
    # Configure Advanced Filters
    # Numeric Columns: Enable "Greater/Less Than" logic
    numeric_cols = ["RN", "TN", "Today Price", "No. Starters", "OneHundredRatings", "Ultimrating", "Ultimrank", "RaceVolatility", "BuccaneerRank", "BuccanneerPoints"]
    for col in numeric_cols:
         gb.configure_column(col, filter="agNumberColumnFilter")
         
    # Text Columns: Enable "Contains/Starts With" logic (Default but explicit is good)
    text_cols = ["Venue", "Horse Name", "Comments", "Line of Betting", "Race Group", "Race Class", "Track Condition"]
    for col in text_cols:
         gb.configure_column(col, filter="agTextColumnFilter")

    # Standard compact columns (90px)
    for col in ["Line of Betting", "Race Group", "No. Starters"]:
         gb.configure_column(col, width=90)
    
    # 5. Build Options
    gridOptions = gb.build()
    gridOptions['enableRangeSelection'] = True 
    # SideBar is Enterprise only, removing to avoid confusion if it fails to load.
    # Floating Filters (configured above) are the best Community way to filter.
    
    # --- SIDEBAR: LAYOUT RESET ---
    with st.sidebar:
        st.header("⚙️ Desk Config")
        if "layout_version" not in st.session_state:
            st.session_state.layout_version = 100 # FORCE RESET
            
        if st.button("⚠️ Reset Grid Layout", help="Click this if filters don't appear."):
            st.session_state.layout_version += 1
            st.rerun()

        st.caption(f"Layout Version: {st.session_state.layout_version}")

        # --- MANUAL CLOUD SYNC ---
        st.divider()
        if st.button("🔄 Sync Cloud Config"):
            try:
                bucket = os.getenv("GCS_BUCKET_NAME")
                if bucket:
                    if cloud_utils.sync_config_from_gcs(bucket, "config.json"):
                        # Clear widget state to force re-render with new values
                        if "race_date_picker" in st.session_state:
                            del st.session_state["race_date_picker"]
                            
                        st.toast("Config Synced! Reloading...", icon="✅")
                        time.sleep(1)
                        st.rerun()
            except Exception as e:
                st.error(f"Sync Failed: {e}")
        
        with st.expander("🛠️ Debug Config", expanded=False):
            if os.path.exists("config.json"):
                with open("config.json", "r") as f:
                     st.json(json.load(f))
            else:
                st.error("config.json Missing!")
        # -------------------------

    # --- DISPLAY GRID ---
    # The grid will return the STATE of the data.
    # We update_mode=GridUpdateMode.VALUE_CHANGED so it updates instantly when user selects a bet.
    
    # FORCE NEW KEY PREFIX to ensure users see the new filters without manual reset
    grid_response = AgGrid(
        df,
        gridOptions=gridOptions,
        update_mode=GridUpdateMode.VALUE_CHANGED, 
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED, 
        fit_columns_on_grid_load=False,
        height=600,
        theme="streamlit", 
        key=f"racing_grid_ultimate_v{st.session_state.layout_version}" # NEW KEY PREFIX
    )
    
    # --- PROCESS SELECTIONS ---
    # grid_response['data'] contains the updated dataframe (as a simple list of dicts or dataframe)
    
    updated_df = grid_response['data'] # This is a DataFrame
    
    # Filter for selected bets
    # We filter purely based on the "Bet Type" column in the returned data
    # This matches EXACTLY what is in the grid. No index mapping needed.
    
    if 'Bet Type' in updated_df.columns:
        selections_df = updated_df[updated_df['Bet Type'].isin(["Ultimate Bet", "Standout Bets", "Outsider Bets"])].copy()
    else:
        selections_df = pd.DataFrame()
        
    num_selected = len(selections_df)
    
    st.divider()
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.subheader("📝 Review Selected Bets")
        if num_selected > 0:
            review_cols = ["Bet Type", "Venue", "RN", "Horse Name", "Today Price", "Comments"]
            # Ensure cols exist
            valid_cols = [c for c in review_cols if c in selections_df.columns]
            st.dataframe(
                selections_df[valid_cols],
                hide_index=True,
                use_container_width=True,
                height=250
            )
        else:
            st.info("No bets selected. Use the 'Bet Type' dropdown in the grid above.")
            
    with col2:
        st.subheader("Generate Report")
        st.metric("Total Selections", num_selected)
        
        can_generate = 2 <= num_selected <= 99
        
        # --- DATE SELECTOR (Moved here for "One Flow" Logic) ---
        today = datetime.now()
        days_ahead = 5 - today.weekday()
        if days_ahead < 0: 
            days_ahead += 7
        next_saturday = today + pd.Timedelta(days=days_ahead)
        
        # --- TEST OVERRIDE LOGIC ---
        try:
            if os.path.exists("config.json"):
                with open("config.json", "r") as f:
                    cfg = json.load(f)
                    test_cfg = cfg.get("testing", {})
                    if test_cfg.get("enable_date_override"):
                        ov_date_str = test_cfg.get("override_date")
                        if ov_date_str:
                             next_saturday = datetime.strptime(ov_date_str, "%Y-%m-%d")
                             st.toast(f"🧪 Test Mode: Date Overridden to {next_saturday.strftime('%d %b %Y')}", icon="🧪")
        except Exception as e:
            print(f"Config Error: {e}")
        # ---------------------------
        
        selected_date = st.date_input(
            "📅 Target Race Date",
            value=next_saturday,
            key="race_date_picker"
        )
        # Store in session state for downstream use
        st.session_state['race_date'] = selected_date
                
        if st.button("🚀 Generate & Publish", disabled=not can_generate, type="primary", use_container_width=True):
            st.write("---")
            st.subheader("1. 📄 Generating Document...")
            
            with st.spinner("Creating Google Doc..."):
                data_dict = {
                    "Ultimate Bets": selections_df[selections_df["Bet Type"] == "Ultimate Bet"].to_dict('records'),
                    "Standout Bets": selections_df[selections_df["Bet Type"] == "Standout Bets"].to_dict('records'),
                    "Outsider Bets": selections_df[selections_df["Bet Type"] == "Outsider Bets"].to_dict('records')
                }
                
                doc_success = False
                try:
                    # Pass source filename to extract correct date
                    doc_link = generate_racing_doc.create_and_populate_doc(
                        data_dict, 
                        source_filename=st.session_state.filename,
                        manual_date=selected_date
                    )
                    st.success("Google Doc Created!")
                    st.markdown(f"### [📂 Open Document]({doc_link})")
                    doc_success = True
                    
                    # Store data for next step (legacy)
                    st.session_state['latest_data_dict'] = data_dict
                    
                except Exception as e:
                    st.error(f"Document Generation Error: {e}")

            # 2. PROCEED TO UPLOAD
            if doc_success:
                st.write("---")
                st.subheader("2. 🌍 Publishing to Website...")
                
                # --- PREPARE CONTENT (HTML Table) ---
                lines = []
                lines.append("<table style='width:100%; border-collapse: collapse; font-family: Arial, sans-serif; font-size: 14px;'>")
                
                for category, rows in data_dict.items():
                    if rows:
                        # Category Header
                        lines.append(f"<tr><td colspan='6' style='padding-top: 20px; padding-bottom: 10px;'><strong style='font-size: 24px;'>{category}</strong></td></tr>")
                        
                        for r in rows:
                            # Row Format: [Bold Columns] [Normal Comment]
                            # Venue | RN | TN | Horse | Price | Comment
                            
                            row_html = "<tr>"
                            # Venue
                            row_html += f"<td style='padding: 4px; font-weight: bold;'>{r['Venue']}</td>"
                            # RN
                            row_html += f"<td style='padding: 4px; font-weight: bold;'>{r['RN']}</td>"
                            # TN
                            row_html += f"<td style='padding: 4px; font-weight: bold;'>{r['TN']}</td>"
                            # Horse
                            row_html += f"<td style='padding: 4px; font-weight: bold;'>{r['Horse Name']}</td>"
                            # Price
                            row_html += f"<td style='padding: 4px; font-weight: bold;'>{r['Today Price']}</td>"
                            # Comment (Normal)
                            row_html += f"<td style='padding: 4px;'>{r['Comments']}</td>"
                            row_html += "</tr>"
                            
                            lines.append(row_html)
                        
                        # Spacer Row
                        lines.append("<tr><td colspan='6' style='height: 10px;'></td></tr>")

                lines.append("</table>")
                final_body = "".join(lines)
                
                # --- PREPARE DATA ---
                date_str = selected_date.strftime("%d/%m/%Y") 
                title_date = selected_date.strftime("%d %B %Y")
                doc_title = f"Saturday Punter for {title_date}"
                
                # --- RUN BOT ---
                with st.status("🤖 Bot is uploading content...", expanded=True) as status:
                    st.write("Current Status: Preparing secure environment...")
                    try:
                        # Save payload to json
                        payload = {
                            "title": doc_title,
                            "date": date_str,
                            "body": final_body
                        }
                        payload_path = os.path.abspath("upload_payload.json")
                        with open(payload_path, "w", encoding="utf-8") as f:
                            json.dump(payload, f)
                            
                        st.write("Launching Upload Bot (Isolated Process)...")
                        
                        # Run external script
                        import subprocess
                        # Using subprocess.Popen to stream output if needed, but run() is simpler for blocking
                        # We want it to block here so we can show result
                        process = subprocess.run(
                            ["python", "execution/upload_to_website.py", payload_path],
                            capture_output=True,
                            text=True
                        )
                        
                        # CHECK RESULT
                        if process.returncode == 0:
                            st.write("Bot finished successfully!")
                            status.update(label="✅ Upload Complete!", state="complete", expanded=False)
                            st.success("Successfully uploaded to Website!")
                            st.balloons()
                        else:
                            st.write(f"Bot encountered an error (Exit Code {process.returncode})")
                            st.code(process.stderr)
                            st.code(process.stdout)
                            status.update(label="❌ Upload Failed", state="error", expanded=True)

                    except Exception as e:
                        st.error(f"Launch Error: {e}")
                        status.update(label="❌ System Error", state="error")


if __name__ == "__main__":
    main()
