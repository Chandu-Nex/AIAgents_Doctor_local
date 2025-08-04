# File: postgres_utils.py
import psycopg2
from uuid import UUID
from typing import Optional, List, Tuple
import os
from dotenv import load_dotenv
from datetime import datetime
import json

load_dotenv()  # Load .env file

# Postgres connection details (use env vars for security/flexibility)
PG_DB = os.environ.get('PG_DB', 'ai_doctor_db')
PG_USER = os.environ.get('PG_USER', 'postgres')
PG_PASSWORD = os.environ.get('PG_PASSWORD', 'Pg@12345')
PG_HOST = os.environ.get('PG_HOST', 'localhost')
PG_PORT = int(os.environ.get('PG_PORT', 5432))

def get_connection():
    """Get a new Postgres connection."""
    try:
        return psycopg2.connect(dbname=PG_DB, user=PG_USER, password=PG_PASSWORD, host=PG_HOST, port=PG_PORT)
    except psycopg2.Error as e:
        raise ConnectionError(f"Failed to connect to Postgres: {e}")

def log_communication(sender: str, receiver: str, input_msg: str, output_msg: Optional[str] = None, 
                      status: str = 'pending', session_id: Optional[UUID] = None,
                      health_query_response_id: Optional[int] = None) -> int:
    """
    Log a new communication entry in Postgres and return the log ID.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
        INSERT INTO public."AgentCommunications" (sender_agent, receiver_agent, input_message, output_message, status, session_id, health_query_response_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id;
        """
        session_id_str = str(session_id) if session_id is not None else None
        cursor.execute(query, (sender, receiver, input_msg, output_msg, status, session_id_str, health_query_response_id))
        log_id = cursor.fetchone()[0]
        conn.commit()
        return log_id
    except psycopg2.Error as e:
        conn.rollback()
        raise ValueError(f"Failed to log communication: {e}")
    finally:
        cursor.close()
        conn.close()

def update_communication(log_id: int, output_msg: str, status: str = 'completed') -> None:
    """
    Update an existing log entry with output and status.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
        UPDATE public."AgentCommunications" 
        SET output_message = %s, status = %s 
        WHERE id = %s;
        """
        cursor.execute(query, (output_msg, status, log_id))
        conn.commit()
    except psycopg2.Error as e:
        conn.rollback()
        raise ValueError(f"Failed to update communication: {e}")
    finally:
        cursor.close()
        conn.close()

def log_health_query(user_id: int, session_id: str, input_text: str, status: str = 'pending') -> int:
    """
    Log a new health query entry in Postgres and return the log ID.
    """
    now = datetime.now()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
        INSERT INTO public."HealthQueryResponse" (user_id, session_id, input_text, created_at, updated_at, status)
        VALUES (%s, %s, %s, %s, %s, %s) RETURNING id;
        """
        cursor.execute(query, (user_id, session_id, input_text, now, now, status))
        log_id = cursor.fetchone()[0]
        conn.commit()
        return log_id
    except psycopg2.Error as e:
        conn.rollback()
        raise ValueError(f"Failed to log health query: {e}")
    finally:
        cursor.close()
        conn.close()

def update_health_query_response(session_id: str, response_text: str, status: str = 'completed') -> None:
    """
    Update an existing health query log entry with response text, status, and updated_at.
    """
    now = datetime.now()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
        UPDATE public."HealthQueryResponse" 
        SET response_text = %s, status = %s, updated_at = %s 
        WHERE session_id = %s;
        """
        cursor.execute(query, (response_text, status, now, session_id))
        conn.commit()
    except psycopg2.Error as e:
        conn.rollback()
        raise ValueError(f"Failed to update health query response: {e}")
    finally:
        cursor.close()
        conn.close()

# Verification communication functions

def log_verification(action_type: str, entity_type: str, entity_id: Optional[int] = None, old_data: dict = {}, new_data: dict = {}, 
                     details: dict = {}, actor: str = '', status: str = 'pending', session_id: UUID = None, 
                     agent_communication_id: int = None) -> int:
    """
    Log a new verification entry in the VerificationAgentCommunication table and return the log ID.
    """
    if session_id is None or agent_communication_id is None:
        raise ValueError("session_id and agent_communication_id are required")
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
        INSERT INTO public."VerificationAgentCommunication" 
        (action_type, entity_type, entity_id, old_data, new_data, details, actor, status, session_id, agent_communication_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
        """
        session_id_str = str(session_id)
        cursor.execute(query, (
            action_type,
            entity_type,
            entity_id,
            json.dumps(old_data),
            json.dumps(new_data),
            json.dumps(details),
            actor,
            status,
            session_id_str,
            agent_communication_id
        ))
        log_id = cursor.fetchone()[0]
        conn.commit()
        return log_id
    except psycopg2.Error as e:
        conn.rollback()
        raise ValueError(f"Failed to log verification: {e}")
    finally:
        cursor.close()
        conn.close()

def get_all_verification_logs() -> List[Tuple[int, datetime, str, str, Optional[int], str, str, str, str, str, str, int]]:
    """
    Retrieve all entries from the VerificationAgentCommunication table.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
        SELECT id, "timestamp", action_type, entity_type, entity_id, old_data, new_data, details, actor, status, session_id, agent_communication_id
        FROM public."VerificationAgentCommunication";
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        return rows
    except psycopg2.Error as e:
        raise ValueError(f"Failed to retrieve verification logs: {e}")
    finally:
        cursor.close()
        conn.close()

# User functions (unchanged as per note)

def create_user(username: str, email: str, password_hash: str, first_name: Optional[str] = None, 
                last_name: Optional[str] = None, phone_number: Optional[str] = None) -> int:
    """
    Create a new user in the Users table and return the user ID.
    """
    now = datetime.now()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
        INSERT INTO public."Users" 
        (username, email, password_hash, first_name, last_name, phone_number, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
        """
        cursor.execute(query, (
            username,
            email,
            password_hash,
            first_name,
            last_name,
            phone_number,
            now,
            now
        ))
        user_id = cursor.fetchone()[0]
        conn.commit()
        return user_id
    except psycopg2.Error as e:
        conn.rollback()
        raise ValueError(f"Failed to create user: {e}")
    finally:
        cursor.close()
        conn.close()

def update_user(user_id: int, username: Optional[str] = None, email: Optional[str] = None, 
                password_hash: Optional[str] = None, first_name: Optional[str] = None, 
                last_name: Optional[str] = None, phone_number: Optional[str] = None) -> None:
    """
    Update an existing user in the Users table.
    """
    now = datetime.now()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        updates = []
        params = []
        if username is not None:
            updates.append("username = %s")
            params.append(username)
        if email is not None:
            updates.append("email = %s")
            params.append(email)
        if password_hash is not None:
            updates.append("password_hash = %s")
            params.append(password_hash)
        if first_name is not None:
            updates.append("first_name = %s")
            params.append(first_name)
        if last_name is not None:
            updates.append("last_name = %s")
            params.append(last_name)
        if phone_number is not None:
            updates.append("phone_number = %s")
            params.append(phone_number)
        if not updates:
            return  # Nothing to update
        updates.append("updated_at = %s")
        params.append(now)
        params.append(user_id)
        query = f"""
        UPDATE public."Users" 
        SET {', '.join(updates)}
        WHERE id = %s;
        """
        cursor.execute(query, params)
        conn.commit()
    except psycopg2.Error as e:
        conn.rollback()
        raise ValueError(f"Failed to update user: {e}")
    finally:
        cursor.close()
        conn.close()

def delete_user(user_id: int) -> None:
    """
    Delete a user from the Users table.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
        DELETE FROM public."Users" 
        WHERE id = %s;
        """
        cursor.execute(query, (user_id,))
        conn.commit()
    except psycopg2.Error as e:
        conn.rollback()
        raise ValueError(f"Failed to delete user: {e}")
    finally:
        cursor.close()
        conn.close()

def fetch_all_users() -> List[Tuple[int, str, str, str, str, str, str, datetime, datetime]]:
    """
    Fetch all users from the Users table.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
        SELECT id, username, email, password_hash, first_name, last_name, phone_number, created_at, updated_at
        FROM public."Users";
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        return rows
    except psycopg2.Error as e:
        raise ValueError(f"Failed to fetch users: {e}")
    finally:
        cursor.close()
        conn.close()

def fetch_user_by_id(user_id: int) -> Optional[Tuple[int, str, str, str, str, str, str, datetime, datetime]]:
    """
    Fetch a user by ID from the Users table.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
        SELECT id, username, email, password_hash, first_name, last_name, phone_number, created_at, updated_at
        FROM public."Users"
        WHERE id = %s;
        """
        cursor.execute(query, (user_id,))
        row = cursor.fetchone()
        return row
    except psycopg2.Error as e:
        raise ValueError(f"Failed to fetch user: {e}")
    finally:
        cursor.close()
        conn.close()

def store_structured_medical_data(session_id: str, health_query_id: int, parsed_content: dict) -> int:
    """
    Store structured medical data extracted from LLM response.
    This function stores the parsed JSON content in a structured format.
    """
    now = datetime.now()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Extract common medical fields from parsed content
        symptoms = parsed_content.get('symptoms', [])
        diagnoses = parsed_content.get('diagnoses', [])
        treatments = parsed_content.get('treatments', [])
        precautions = parsed_content.get('precautions', [])
        severity = parsed_content.get('severity', '')
        duration = parsed_content.get('duration', '')
        
        # Convert lists to JSON strings for storage
        symptoms_json = json.dumps(symptoms) if isinstance(symptoms, list) else str(symptoms)
        diagnoses_json = json.dumps(diagnoses) if isinstance(diagnoses, list) else str(diagnoses)
        treatments_json = json.dumps(treatments) if isinstance(treatments, list) else str(treatments)
        precautions_json = json.dumps(precautions) if isinstance(precautions, list) else str(precautions)
        
        # Store in a new table for structured medical data
        query = """
        INSERT INTO public."StructuredMedicalData" 
        (session_id, health_query_response_id, symptoms, diagnoses, treatments, precautions, severity, duration, parsed_content, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
        """
        
        cursor.execute(query, (
            session_id,
            health_query_id,
            symptoms_json,
            diagnoses_json,
            treatments_json,
            precautions_json,
            severity,
            duration,
            json.dumps(parsed_content),  # Store full parsed content as JSON
            now
        ))
        
        data_id = cursor.fetchone()[0]
        conn.commit()
        return data_id
        
    except psycopg2.Error as e:
        conn.rollback()
        raise ValueError(f"Failed to store structured medical data: {e}")
    finally:
        cursor.close()
        conn.close()

def get_structured_medical_data(session_id: str) -> Optional[Tuple]:
    """
    Retrieve structured medical data for a session.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
        SELECT id, session_id, health_query_response_id, symptoms, diagnoses, treatments, 
               precautions, severity, duration, parsed_content, created_at
        FROM public."StructuredMedicalData"
        WHERE session_id = %s
        ORDER BY created_at DESC
        LIMIT 1;
        """
        cursor.execute(query, (session_id,))
        row = cursor.fetchone()
        return row
    except psycopg2.Error as e:
        raise ValueError(f"Failed to retrieve structured medical data: {e}")
    finally:
        cursor.close()
        conn.close()