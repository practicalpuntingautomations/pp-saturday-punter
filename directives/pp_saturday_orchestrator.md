# PP Saturday Orchestrator (Phase 1)

**Goal**: Transform raw Saturday racing data (CSV) into a formatted Google Doc report via a Streamlit interface.

## Inputs
- **Source Data**: CSV file located at `C:\Users\Jodie Ralph\Downloads\C__inetpub_wwwroot_EQ_SystemBuilder_App_Data_ExportSelections_The Buccaneer_*.csv`.
  - *Note*: Use the most recent file matching this pattern.
- **Credentials**:
  - `credentials.json` (Google OAuth)
  - `.env` (Gmail SMTP settings: `GMAIL_USER`, `GMAIL_APP_PASSWORD`)

## Tools & Scripts
- `execution/process_racing_data.py`: Cleans, filters, and sorts the raw CSV.
- `execution/saturday_ui.py`: Streamlit app for user selection and review.
- `execution/generate_racing_doc.py`: Generates the Google Doc using the selected data.
- `execution/send_notification.py`: Sends an email alert when data is ready.

## Process Flow

1.  **Data Ingest (`process_racing_data.py`)**:
    -   Find the latest CSV in the source path.
    -   Load data and keep only these 19 columns:
        `Venue`, `RN`, `TN`, `Horse Name`, `Today Price`, `Line of Betting`, `Race Group`, `Race Class`, `Today Dist`, `Track Condition`, `No. Starters`, `Today Race PM`, `Comments`, `OneHundredRatings`, `Ultimrating`, `Ultimrank`, `RaceVolatility`, `BuccaneerRank`, `BuccanneerPoints`.
    -   Clean headers (strip whitespace).
    -   Sort by: `Venue` (A-Z) -> `RN` (Ascending) -> `Ultimrating` (Descending).
    -   Output: DataFrame (passed to UI).

2.  **Notification (`send_notification.py`)**:
    -   Triggered by the Orchestrator (or manually at start of UI).
    -   Send email to `jlralph@gmail.com`.
    -   Subject: "Saturday Data Ready".
    -   Body: "The Saturday racing data is ready for selection. Please access the interface."

3.  **User Selection (`saturday_ui.py`)**:
    -   Launch Streamlit app.
    -   Display interactive table of the cleaned data.
    -   **Bet Type Selection**: User selects "Ultimate Bet", "Standout Bets", or "Outsider Bets" (or leaves blank) for each row.
    -   **Constraint**: "Generate Report" button filters for 2-99 selected rows.
    -   **Vibe Check**: Show a summary table of selected horses before final generation.

4.  **Report Generation (`generate_racing_doc.py`)**:
    -   Authenticate with Google Docs API using `credentials.json`.
    -   Create a new doc from Template ID: `1w0Qik0Df67e0O9bzXgbbljw-NfkvBAqNlC_Uhob0g24`.
    -   Title: "Saturday Punter for [Current Date]".
    -   **Formatting**:
        -   Group selections by Bet Type (Ultimate, Standout, Outsider).
        -   Row format: `Venue`<tab>`RN`<tab>`TN`<tab>`Horse Name`<tab>`Today Price`<tab>`Comments`.
    -   Save to Folder: `G:\My Drive\Practical Punting\Output of Custom Agent for Saturday`.

## Outputs
- **Google Doc**: The final formatted racing tip sheet.

## Edge Cases
- **No CSV found**: Script should error gracefully and prompt user to check specific path.
- **API Quota**: Handle rate limits for Google Docs API (exponential backoff).
- **Token Expiry**: `token.json` should be refreshed automatically if valid `credentials.json` is present.
