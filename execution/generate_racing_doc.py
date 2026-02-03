import os
from datetime import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import json

# If modifying these scopes, delete the file token.json.
SCOPES = [
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/drive'
]

TEMPLATE_ID = '1w0Qik0Df67e0O9bzXgbbljw-NfkvBAqNlC_Uhob0g24'
FOLDER_NAME = 'Output of Custom Agent for Saturday'

def authenticate():
    creds = None
    
    # 1. Try Memory (Env Var) - Best for Cloud
    token_json_str = os.getenv("GOOGLE_TOKEN_JSON")
    token_b64 = os.getenv("GOOGLE_TOKEN_JSON_B64")
    
    if token_b64:
        import base64
        try:
            print("[AUTH] Loading Token from Base64 Env Var...")
            token_json_str = base64.b64decode(token_b64).decode('utf-8')
        except Exception as e:
            print(f"[ERROR] Base64 Decode Failed: {e}")

    if token_json_str:
        print("[AUTH] Loading Token from Environment Variable...")
        try:
            # We must parse it to a dict, then use Credentials.from_authorized_user_info
            # Note: from_authorized_user_info is the correct method for a dict
            info = json.loads(token_json_str)
            creds = Credentials.from_authorized_user_info(info, SCOPES)
        except Exception as e:
            print(f"[ERROR] Failed to load token from env: {e}")

    # 2. Try File (Local)
    if not creds and os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("[AUTH] Refreshing Token...")
            creds.refresh(Request())
        else:
            # CRITICAL: This flow fails in Cloud Run (Headless)
            # We only run this if we are interactive
            print("[AUTH] Starting Local Server Login Flow...")
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Save the credentials for the next run (Local only)
        # In cloud, we relying on the Env Var being stable or updated elsewhere
        try:
             with open('token.json', 'w') as token:
                token.write(creds.to_json())
        except:
             pass # Read-only file system
    
    return creds

def find_target_folder(drive_service, folder_name):
    """Finds the folder ID for the given folder name."""
    try:
        query = f"mimeType = 'application/vnd.google-apps.folder' and name = '{folder_name}' and trashed = false"
        results = drive_service.files().list(q=query, fields="nextPageToken, files(id, name)").execute()
        items = results.get('files', [])
        
        if not items:
            print(f"Folder '{folder_name}' not found. Creating it...")
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            file = drive_service.files().create(body=file_metadata, fields='id').execute()
            print(f"Created folder with ID: {file.get('id')}")
            return file.get('id')
        else:
            print(f"Found folder '{items[0]['name']}' with ID: {items[0]['id']}")
            return items[0]['id']
            
    except HttpError as error:
        print(f"An error occurred searching for folder: {error}")
        return None

def create_and_populate_doc(data_dict, source_filename=None, manual_date=None):
    """
    Creates a new doc from the template and populates it.
    """
    creds = authenticate()
    try:
        docs_service = build('docs', 'v1', credentials=creds)
        drive_service = build('drive', 'v3', credentials=creds)

        # 1. Target Folder
        target_folder_name = 'Output of Custom Agent for Saturday'
        folder_id = find_target_folder(drive_service, target_folder_name)
        
        # 2. Determine Date
        import re
        file_date_str = datetime.now().strftime("%d %B %Y") # Default
        
        if manual_date:
            # If provided explicitly from UI
            file_date_str = manual_date.strftime("%d %B %Y")
        elif source_filename:
             # Fallback to filename extraction
             match = re.search(r"(\d{8})", source_filename)
             if match:
                 d_str = match.group(1)
                 try:
                     dt = datetime.strptime(d_str, "%Y%m%d")
                     file_date_str = dt.strftime("%d %B %Y") 
                 except:
                     pass
                     
        # Title logic: "Saturday Punter for [Date]" 
        # But maybe we verify if the template has a placeholder? 
        # The prompt implies we create a new doc. 
        # We will set the Document Name to this, but the Title inside the doc 
        # is preserved from the template (which we just wiped everything AFTER).
        # Wait, if we wiped "AFTER title", we assume the Title in the doc is correct or generic?
        # User screenshot shows: "Saturday Punter for 24 January \n 2026".
        # If the template has a title, we might need to update it?
        # Let's assume the Template has a generic Title and we are appending. 
        # BUT, if we want to be safe, we should probably update the Title text too?
        # The user said "except for the main title at the very top".
        # So we assume the Template *has* the title "Saturday Punter..."
        # We won't touch the title text, just the content below it.
        
        doc_title_name = f"Saturday Punter for {file_date_str}" 
        
        # 3. Copy the template
        body = {
            'name': doc_title_name
        }
        if folder_id:
            body['parents'] = [folder_id]

        drive_response = drive_service.files().copy(
            fileId=TEMPLATE_ID, body=body).execute()
        document_id = drive_response.get('id')
        print(f"Created document with ID: {document_id}")

        # 4. CLEAN SLATE: Wipe existing content AND Update Title
        doc = docs_service.documents().get(documentId=document_id).execute()
        content = doc.get('body').get('content')
        
        title_end_index = 1
        if len(content) > 1:
            try:
                first_paragraph = content[1] 
                title_end_index = first_paragraph.get('endIndex')
            except:
                title_end_index = 1
        
        doc_end_index = content[-1].get('endIndex') - 1
        
        queries = []
        
        # A. Delete Content AFTER Title
        if doc_end_index > title_end_index:
             queries.append({
                 'deleteContentRange': {
                     'range': { 'startIndex': title_end_index, 'endIndex': doc_end_index }
                 }
             })

        # B. Update Title Text (Index 1 to title_end_index - 1, excluding newline)
        # We assume Title is the first paragraph ending with \n.
        # title_end_index is the position AFTER the \n.
        # We want to replace text from 1 to title_end_index - 1
        curr_title_text_len = title_end_index - 1 - 1 # (end - start - newline char)
        
        if curr_title_text_len > 0:
             # Delete old title text
             queries.append({
                 'deleteContentRange': {
                     'range': { 'startIndex': 1, 'endIndex': title_end_index - 1 }
                 }
             })
        
        # Insert New Title Text
        queries.append({
            'insertText': {
                'text': doc_title_name,
                'location': {'index': 1}
            }
        })

        # 5. REBUILD CONTENT (Pixel Perfect)
        def create_requests(start_index):
            reqs = []
            current_idx = start_index
            
            # TAB STOPS (Approximate points based on visual)
            # 1 inch = 72 pt. 
            # Venue (0), RN (~80), TN (~110), Horse (~140), Price (~280), Comments (~340)
            tab_stops = [
                {'offset': {'magnitude': 90, 'unit': 'PT'}, 'alignment': 'START'},  # RN
                {'offset': {'magnitude': 120, 'unit': 'PT'}, 'alignment': 'START'}, # TN
                {'offset': {'magnitude': 150, 'unit': 'PT'}, 'alignment': 'START'}, # Horse
                {'offset': {'magnitude': 300, 'unit': 'PT'}, 'alignment': 'START'}, # Price
                {'offset': {'magnitude': 360, 'unit': 'PT'}, 'alignment': 'START'}, # Comments
            ]
            
            for section, rows in data_dict.items():
                if not rows:
                    continue
                
                # --- HEADER ---
                # Spacing: ~2 lines above (24pt), 1 line below (12pt)
                header_text = f"\n{section}\n"
                reqs.append({
                    'insertText': { 'text': header_text, 'location': {'index': current_idx} }
                })
                
                header_start = current_idx + 1 
                header_end = current_idx + len(header_text)
                
                # Link Header Style: Arial 30.5pt NORMAL (User Request)
                # User said 30.5 specifically.
                reqs.append({
                    'updateTextStyle': {
                        'range': {'startIndex': header_start, 'endIndex': header_end},
                        'textStyle': {
                            'bold': False, 
                            'fontSize': {'magnitude': 30.5, 'unit': 'PT'},
                            'weightedFontFamily': {'fontFamily': 'Arial'}
                        },
                        'fields': 'bold,fontSize,weightedFontFamily'
                    }
                })
                
                # Header Spacing (Apply Spacing ONLY, do not reset style)
                reqs.append({
                    'updateParagraphStyle': {
                         'range': {'startIndex': header_start, 'endIndex': header_end},
                         'paragraphStyle': {
                             'spaceAbove': {'magnitude': 24, 'unit': 'PT'},
                             'spaceBelow': {'magnitude': 12, 'unit': 'PT'},
                             'keepWithNext': True
                         },
                         'fields': 'spaceAbove,spaceBelow,keepWithNext'
                    }
                })
                
                current_idx += len(header_text)
                
                # --- ROWS ---
                for row in rows:
                    # ROW FORMAT: [Bold Part] [Tab] [Normal Part]
                    
                    part_a = f"{row['Venue']}\t\t{row['RN']}\t{row['TN']}\t{row['Horse Name']}\t{row['Today Price']}"
                    part_b = f"\t{row['Comments']}\n"
                    
                    # Insert Part A
                    reqs.append({
                        'insertText': { 'text': part_a, 'location': {'index': current_idx} }
                    })
                    end_a = current_idx + len(part_a)
                    
                    # Style Part A: BOLD 12pt
                    reqs.append({
                        'updateTextStyle': {
                            'range': {'startIndex': current_idx, 'endIndex': end_a},
                            'textStyle': {
                                'bold': True,
                                'fontSize': {'magnitude': 12, 'unit': 'PT'}
                            },
                            'fields': 'bold,fontSize'
                        }
                    })
                    
                    current_idx = end_a
                    
                    # Insert Part B
                    reqs.append({
                        'insertText': { 'text': part_b, 'location': {'index': current_idx} }
                    })
                    end_b = current_idx + len(part_b)
                    
                    # Style Part B: NORMAL 12pt
                    reqs.append({
                        'updateTextStyle': {
                            'range': {'startIndex': current_idx, 'endIndex': end_b},
                            'textStyle': {
                                'bold': False,
                                'fontSize': {'magnitude': 12, 'unit': 'PT'}
                            },
                            'fields': 'bold,fontSize'
                        }
                    })
                    
                    # Paragraph Style for the WHOLE ROW (Clean Spacing)
                    # Note: We must not touch namedStyleType or it will reset our 12pt formatting.
                    row_start_idx = end_a - len(part_a) 
                    reqs.append({
                        'updateParagraphStyle': {
                             'range': {'startIndex': row_start_idx, 'endIndex': end_b},
                             'paragraphStyle': {
                                 'spaceAbove': {'magnitude': 0, 'unit': 'PT'},
                                 'spaceBelow': {'magnitude': 10, 'unit': 'PT'}
                             },
                             'fields': 'spaceAbove,spaceBelow'
                        }
                    })
                    
                    current_idx = end_b

            return reqs
            
        # EXECUTE DELETE
        if queries:
             docs_service.documents().batchUpdate(
                documentId=document_id, body={'requests': queries}).execute()
             print("Cleaned existing content.")
             
        # EXECUTE INSERTS
        doc = docs_service.documents().get(documentId=document_id).execute()
        content = doc.get('body').get('content')
        insert_start_index = content[-1].get('endIndex') - 1 
        
        insert_reqs = create_requests(insert_start_index)
        
        if insert_reqs:
            docs_service.documents().batchUpdate(
                documentId=document_id, body={'requests': insert_reqs}).execute()
            print("Populated new content.")

        return f"https://docs.google.com/document/d/{document_id}"

    except HttpError as err:
        raise err

if __name__ == "__main__":
    # Mock data for testing
    from datetime import datetime
    
    mock_data = {
        "Ultimate Bets": [
            {"Venue": "Randwick", "RN": 1, "TN": 5, "Horse Name": "Winx", "Today Price": "1.10", "Comments": "Unbeatable"},
        ],
        "Standout Bets": [],
        "Outsider Bets": [
            {"Venue": "Flemington", "RN": 4, "TN": 2, "Horse Name": "Roughie", "Today Price": "21.00", "Comments": "Place chance"},
        ]
    }
    
    # print(create_and_populate_doc(mock_data))
    print("Run via import in main orchestrator or UI.")
