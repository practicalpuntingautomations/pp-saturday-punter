import pandas as pd
import glob
import os
import sys

import cloud_utils

def get_latest_racing_file():
    """Finds the latest 'The Buccaneer' CSV file."""
    
    # 1. Cloud Mode
    bucket_name = os.getenv("GCS_BUCKET_NAME")
    if bucket_name:
        print(f"[INFO] Cloud Mode Detected. Checking Bucket: {bucket_name}")
        latest_blob = cloud_utils.get_latest_file_from_gcs(bucket_name, prefix="raw_data/")
        
        if not latest_blob:
             raise FileNotFoundError(f"No files found in GCS bucket {bucket_name}")
             
        # Download to .tmp
        local_dest = os.path.join(os.path.dirname(__file__), "..", ".tmp", os.path.basename(latest_blob))
        os.makedirs(os.path.dirname(local_dest), exist_ok=True)
        
        cloud_utils.download_from_gcs(bucket_name, latest_blob, local_dest)
        return local_dest

    # 2. Local Mode
    # Note: Adjust pattern if needed
    source_pattern = r"C:\Users\Jodie Ralph\Downloads\C__inetpub_wwwroot_EQ_SystemBuilder_App_Data_ExportSelections_The Buccaneer_*.csv"
    
    files = glob.glob(source_pattern)
    if not files:
        # Fallback for generic location
        source_pattern = os.path.expanduser("~/Downloads/ExportSelections*.csv")
        files = glob.glob(source_pattern)
        
    if not files:
        raise FileNotFoundError(f"No files found matching pattern: {source_pattern}")
    
    # Sort by modification time, newest first
    latest_file = max(files, key=os.path.getmtime)
    print(f"Found latest file: {latest_file}")
    return latest_file

def load_and_clean_data(filepath):
    """Loads the CSV, filters columns, cleans headers, and sorts data."""
    
    # Columns to keep (Strictly these 19)
    # Note: Ensure these match the CSV headers exactly (case-sensitive usually, but we'll strip whitespace)
    columns_to_keep = [
        "Venue", "RN", "TN", "Horse Name", "Today Price", "Line of Betting", 
        "Race Group", "Race Class", "Today Dist", "Track Condition", "No. Starters", 
        "Today Race PM", "Comments", "OneHundredRatings", "Ultimrating", 
        "Ultimrank", "RaceVolatility", "BuccaneerRank", "BuccanneerPoints"
    ]
    
    try:
        # Load CSV
        df = pd.read_csv(filepath)
        
        # 1. Clean Headers: Strip leading/trailing whitespace
        df.columns = df.columns.str.strip()
        
        # Check if all required columns exist
        missing_cols = [col for col in columns_to_keep if col not in df.columns]
        if missing_cols:
             # Try case-insensitive matching if direct match fails
            print(f"Warning: Exact column match failed for {missing_cols}. Attempting case-insensitive match...")
            existing_cols_lower = {col.lower(): col for col in df.columns}
            mapped_cols = []
            for target_col in columns_to_keep:
                if target_col in df.columns:
                    mapped_cols.append(target_col)
                elif target_col.lower() in existing_cols_lower:
                    mapped_cols.append(existing_cols_lower[target_col.lower()])
                else:
                    raise KeyError(f"Critical Column Missing: {target_col}")
            
            # Re-select using the found actual column names
            df = df[mapped_cols]
            # Rename back to the standard names we expect
            df.columns = columns_to_keep
        else:
            df = df[columns_to_keep]

        # 2. Sorting
        # Venue (A-Z), then RN (1, 2, 3...), then Ultimrating (Highest to Lowest)
        # Ensure RN and Ultimrating are numeric
        df['RN'] = pd.to_numeric(df['RN'], errors='coerce')
        df['Ultimrating'] = pd.to_numeric(df['Ultimrating'], errors='coerce')
        
        df = df.sort_values(
            by=["Venue", "RN", "Ultimrating"], 
            ascending=[True, True, False]
        )
        
        return df

    except Exception as e:
        print(f"Error processing file: {e}")
        raise

if __name__ == "__main__":
    try:
        if len(sys.argv) > 1:
            filepath = sys.argv[1]
        else:
            filepath = get_latest_racing_file()
            
        cleaned_df = load_and_clean_data(filepath)
        print("Data processed successfully.")
        print(cleaned_df.head())
        
        # Optional: Save to temp for verify
        # output_path = os.path.join(os.path.dirname(__file__), "..", ".tmp", "processed_racing_data.csv")
        # cleaned_df.to_csv(output_path, index=False)
        # print(f"Saved to: {output_path}")

    except Exception as e:
        print(str(e))
        sys.exit(1)
