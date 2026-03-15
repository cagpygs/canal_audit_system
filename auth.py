
import streamlit as st

from crud import get_connection, release_connection


def login(username, password):

    if not username or not password:
        return None, "Missing credentials"

    conn = get_connection()
    cur = None

    try:
        cur = conn.cursor()

        # First, check if user exists and password matches
        cur.execute("""
            SELECT id, username, role, is_active, allowed_modules
            FROM users
            WHERE LOWER(username) = LOWER(%s)
            AND password_hash = %s
            AND (is_active IS TRUE OR is_active IS NULL)
        """, (username, password))

        row = cur.fetchone()

        if row:
            is_active = row[3]
            if is_active is False:
                return None, "REVOKED"
            
            return {
                "id": row[0],
                "username": row[1],
                "role": row[2],
                "allowed_modules": row[4]
            }, None

        return None, "Invalid username or password"

    except Exception as e:
        st.error(f"Database error during login: {e}")
        return None, "System error occurred"

    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


