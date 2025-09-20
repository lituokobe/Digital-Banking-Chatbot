from datetime import datetime, timedelta
import pandas as pd
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from typing import List, Dict, Optional
from sqlite3 import connect
from tools import banking_data_db

@tool
def fetch_user_information(config: RunnableConfig) -> List[Dict]:
    """
    Fetch client's information based on user id
    Args:
        config: :param config: config object that contains user id

    Returns:
    :return: a dictionary that includes information of the user and their relationship manager
    """
    configuration = config.get("configurable", {})
    user_id = configuration.get("user_id", None)

    if not user_id:
        raise ValueError("User id is required")

    conn = connect(banking_data_db)
    cursor = conn.cursor()

    # SQL query to fetch user information
    query = """
        SELECT 
            u.user_id, u.user_surname, u.user_given_name, u.client_since, u.nationality,
            p.pm_surname, p.pm_given_name
        FROM 
            user u
            JOIN pm p ON u.pm_id = p.pm_id
        WHERE 
            u.user_id = ?
        """
    cursor.execute(query, (user_id,))
    rows = cursor.fetchall()
    column_names = [column[0] for column in cursor.description]
    results = [dict(zip(column_names, row)) for row in rows]

    cursor.close()
    conn.close()

    return results

@tool
def contact_rm(user_id: str, appointment_date_time: Optional[str] = None) -> str:
    """
    Check the schedules of appoint with the relationship manager (RM) or schedule a new appointment with the RM.
    Args:
        user_id: user's id
        appointment_date_time: proposed new appointment date time by user (YYYY-MM-DD hh:mm:ss).

    Returns:
        Information about user's existing appointments with their RM or the status of new appointment booking.
    """
    # Have the pending appointments first
    conn = connect(banking_data_db)
    query = "SELECT * FROM pending_appointments WHERE user_id = ?"
    df_appointments = pd.read_sql_query(query, conn, params=(user_id,)).sort_values(
        "appointment_date_time").reset_index(drop=True)
    dict_appointments = df_appointments.to_dict(orient="records")

    # If the user only wants to check the pending appointments
    if appointment_date_time is None:
        conn.close()
        if len(dict_appointments) == 0:
            return "The user has no appointment with the relationship manager."
        else:
            appointment_summary = "Below are the user's pending appointments with the relationship manger:\n"
            for item in dict_appointments:
                appt_dt = datetime.strptime(item['appointment_date_time'], "%Y-%m-%d %H:%M:%S")
                appointment_summary += (
                    f"- On {item['date'][:10]}, the user made an appointment with the relationship manager on "
                    f"{appt_dt.strftime('%A, %B %d, %Y at %I:%M %p')}.\n"
                )
            return appointment_summary

    # If the user wants to schedule a new appointment
    else:
        try:
            appointment_dt = datetime.strptime(appointment_date_time, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return "The appointment date time format is invalid. Please use 'YYYY-MM-DD hh:mm:ss'."

        # Get time difference to today
        today = datetime.today()
        time_diff = appointment_dt - today

        # Check if appointment is in the past
        if time_diff.total_seconds() < 0:
            conn.close()
            return "You cannot make an appointment in the past. Please select a future date that is at least one day later."

        # Check if appointment is less than one day away
        if time_diff < timedelta(days=1):
            conn.close()
            return "The appointment time must be scheduled at least one day in advance. Please choose a later time."

        # Check conflicts with existing appointment
        if len(dict_appointments) > 0:
            for item in dict_appointments:
                existing_app_datetime = datetime.strptime(item['appointment_date_time'], "%Y-%m-%d %H:%M:%S")
                time_diff_existing = appointment_dt - existing_app_datetime
                if abs(time_diff_existing) < timedelta(hours=2):
                    conn.close()
                    return (
                        f"You already have an appointment with your relationship manager on "
                        f"{existing_app_datetime.strftime('%A, %B %d, %Y at %I:%M %p')}. "
                        f"Your new appointment must be scheduled at least 2 hours earlier or later than this time."
                    )

        # The appointment is OK to schedule
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO pending_appointments (date, user_id, appointment_date_time)
            VALUES (?, ?, ?)
            """,
            (today.strftime("%Y-%m-%d %H:%M:%S"), user_id, appointment_dt)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return f"Your new appointment with your relationship manager is scheduled at {appointment_dt.strftime('%A, %B %d, %Y at %I:%M %p')}."