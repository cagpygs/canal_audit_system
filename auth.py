from crud import (
    get_connection,
    hash_password,
    password_needs_upgrade,
    release_connection,
    verify_password,
)
from error_utils import log_exception


def login(username, password):

    if not username or not password:
        return None, "Missing credentials"

    conn = None
    cur = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        # Fetch user by username, then verify the password in application code.
        cur.execute("""
            SELECT id, username, role, is_active, allowed_modules, password_hash
            FROM users
            WHERE LOWER(username) = LOWER(%s)
        """, (username,))

        row = cur.fetchone()

        if not row:
            return None, "Invalid username or password"

        is_active = row[3]
        if is_active is False:
            return None, "REVOKED"

        stored_hash = row[5] or ""
        if not verify_password(password, stored_hash):
            return None, "Invalid username or password"

        if password_needs_upgrade(stored_hash):
            try:
                cur.execute(
                    "UPDATE users SET password_hash = %s WHERE id = %s",
                    (hash_password(password), row[0]),
                )
                conn.commit()
            except Exception as upgrade_err:
                conn.rollback()
                log_exception(f"auth.login.password_upgrade.user_id={row[0]}", upgrade_err)

        role = (row[2] or "operator").lower()
        return {
            "id": row[0],
            "username": row[1],
            "role": role,
            "allowed_modules": row[4]
        }, None

    except Exception as e:
        log_exception("auth.login", e)
        return None, "System error occurred"

    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


