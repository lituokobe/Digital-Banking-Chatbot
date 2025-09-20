from datetime import datetime
import pandas as pd
import sqlite3

def create_db_update_date(excel_path: str, db_path: str):
    """
    Create the database from excel and update the date of transactions to today's date
    Parameters:
        excel_path (str): the path of the excel file
        db_path (str): the pat of the database file
    """
    # Load Excel file with all sheets
    sheets = pd.read_excel(excel_path, sheet_name=None)  # Loads all sheets as dict

    # Get today's date
    today = datetime.today().date()

    # Connect to SQLite (creates file if not exists)
    conn = sqlite3.connect(db_path)

    # Loop through each sheet and write to SQLite with date updated
    for sheet_name, df in sheets.items():
        if sheet_name not in ["T8087423", "T9004281", "T3569016", "user", "pm"]:
            # Convert 'date' column to datetime
            df["date"] = pd.to_datetime(df["date"])

            # Find the latest date in the sheet
            max_date = df["date"].max().date()

            # Calculate offset to shift dates so latest becomes today
            date_offset = today - max_date

            # Apply offset to all dates
            df["date"] = df["date"] + pd.to_timedelta(date_offset.days, unit="D")

            if sheet_name == "pending_appointments":
                df["appointment_date_time"] = df["appointment_date_time"] + pd.to_timedelta(date_offset.days, unit="D")
            elif sheet_name == "pending_transfers":
                df["transfer_date"] = df["transfer_date"] + pd.to_timedelta(date_offset.days, unit="D")

        df.to_sql(sheet_name.lower(), conn, if_exists="replace", index=False)

    conn.close()

create_db_update_date("../database/banking_data.xlsx", "../database/banking_data.db")
