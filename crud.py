import psycopg2
import datetime
import pandas as pd
import streamlit as st
from psycopg2 import pool, sql
import json
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
import hashlib
import hmac
import io
import os
import re
import secrets
import time

from error_utils import report_error


PASSWORD_HASH_PREFIX = "pbkdf2_sha256"
PASSWORD_HASH_ALGORITHM = "sha256"
PASSWORD_HASH_ITERATIONS = 260000
PASSWORD_SALT_BYTES = 16
TABLE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _read_setting(name, default=None):
    value = os.getenv(name)
    if value not in (None, ""):
        return value

    try:
        secret_value = st.secrets.get(name)
    except Exception:
        secret_value = None

    if secret_value not in (None, ""):
        return str(secret_value)
    return default


def _read_int_setting(name, default, minimum=None, maximum=None):
    raw = _read_setting(name, default)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = int(default)
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _read_float_setting(name, default, minimum=None, maximum=None):
    raw = _read_setting(name, default)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = float(default)
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _is_pbkdf2_hash(stored_hash):
    return isinstance(stored_hash, str) and stored_hash.startswith(f"{PASSWORD_HASH_PREFIX}$")


def ensure_valid_table_name(table):
    if not isinstance(table, str) or not TABLE_NAME_PATTERN.fullmatch(table):
        raise ValueError(f"Invalid table name: {table!r}")
    return table


def hash_password(password):
    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string.")

    salt = secrets.token_bytes(PASSWORD_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        PASSWORD_HASH_ALGORITHM,
        password.encode("utf-8"),
        salt,
        PASSWORD_HASH_ITERATIONS,
    )
    return f"{PASSWORD_HASH_PREFIX}${PASSWORD_HASH_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password, stored_hash):
    if not isinstance(password, str) or not isinstance(stored_hash, str) or not stored_hash:
        return False

    if _is_pbkdf2_hash(stored_hash):
        parts = stored_hash.split("$")
        if len(parts) != 4:
            return False

        _, iteration_text, salt_hex, digest_hex = parts
        try:
            iterations = int(iteration_text)
            salt = bytes.fromhex(salt_hex)
            expected_digest = bytes.fromhex(digest_hex)
        except (TypeError, ValueError):
            return False

        calculated_digest = hashlib.pbkdf2_hmac(
            PASSWORD_HASH_ALGORITHM,
            password.encode("utf-8"),
            salt,
            iterations,
            dklen=len(expected_digest),
        )
        return hmac.compare_digest(calculated_digest, expected_digest)

    # Backward compatibility for legacy rows that still store plain text.
    return hmac.compare_digest(stored_hash, password)


def password_needs_upgrade(stored_hash):
    return not _is_pbkdf2_hash(stored_hash)


# ================= DB CONNECTION =================

@st.cache_resource
def get_db_pool():
    # Using ThreadedConnectionPool for multi-threaded Streamlit application
    db_password = _read_setting("DB_PASSWORD")
    if not db_password:
        raise RuntimeError("DB_PASSWORD is not configured. Set it in environment or Streamlit secrets.")

    min_conn = _read_int_setting("DB_POOL_MINCONN", 1, minimum=1)
    max_conn = _read_int_setting("DB_POOL_MAXCONN", 80, minimum=min_conn)

    return pool.ThreadedConnectionPool(
        min_conn, max_conn,
        host=_read_setting("DB_HOST", "localhost"),
        database=_read_setting("DB_NAME", "Irrigation"),
        user=_read_setting("DB_USER", "postgres"),
        password=db_password,
        port=_read_setting("DB_PORT", "5432")
    )

def get_connection():
    wait_timeout = _read_float_setting("DB_POOL_WAIT_TIMEOUT", 30.0, minimum=0.1)
    wait_poll = _read_float_setting("DB_POOL_WAIT_POLL_INTERVAL", 0.05, minimum=0.01)
    deadline = time.monotonic() + wait_timeout
    db_pool = get_db_pool()
    while True:
        try:
            conn = db_pool.getconn()
            conn.autocommit = False
            return conn
        except pool.PoolError as e:
            if "exhausted" not in str(e).lower():
                raise
            if time.monotonic() >= deadline:
                raise pool.PoolError(
                    f"Timed out waiting for DB connection after {wait_timeout:.2f}s"
                ) from e
            time.sleep(wait_poll)

def release_connection(conn):
    if conn:
        try:
            conn.rollback()
        except Exception:
            pass
        get_db_pool().putconn(conn)


# ================= LOAD TABLES =================

def get_all_tables(conn=None):
    close_conn = False

    if conn is None:
        try:
            conn = get_connection()
            close_conn = True
        except Exception as e:
            report_error("Database connection error.", e, "crud.get_all_tables.connect")
            return []

    try:
        df = pd.read_sql(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema='public'
            AND table_type='BASE TABLE'
            AND (
                table_name LIKE 'contract_management_%'
                OR table_name LIKE 'canal_performance_%'
            )
            ORDER BY table_name
            """,
            conn,
        )
        return df["table_name"].tolist()
    except Exception as e:
        report_error("Error fetching tables.", e, "crud.get_all_tables")
        return []
    finally:
        if close_conn and conn:
            release_connection(conn)


# ================= GET NEXT CYCLE =================
def get_next_cycle(user_id, module):
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT COALESCE(MAX(cycle), 0)
            FROM master_submission
            WHERE user_id=%s
            AND module=%s
        """,
            (user_id, module),
        )

        last_cycle = cur.fetchone()[0]
        return last_cycle + 1
    except Exception as e:
        report_error("Error getting next cycle.", e, "crud.get_next_cycle")
        return 1
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


# ================= SAVE DRAFT =================
def save_draft_record(table, data, user_id, master_id=None):
    table = ensure_valid_table_name(table)
    user_id = int(user_id)
    conn = None
    cur = None

    clean_cols = []
    clean_vals = []

    for k, v in data.items():
        if not k or not k.strip():
            continue

        clean_cols.append(k)

        if v == "" or v is None:
            clean_vals.append(None)
        elif isinstance(v, (list, tuple)):
            clean_vals.append(str(v))
        else:
            clean_vals.append(v)

    if not clean_cols:
        return

    # Escape % in column names
    safe_cols = [col.replace("%", "%%") for col in clean_cols]

    try:
        conn = get_connection()
        cur = conn.cursor()

        # STEP 1: Fetch existing draft rows for this master_id (or old-style NULL master_id)
        if master_id:
            check_query = sql.SQL("""
                SELECT id FROM {table}
                WHERE created_by=%s AND master_id=%s AND is_draft=TRUE
                ORDER BY id DESC
            """).format(table=sql.Identifier(table))
            cur.execute(check_query, (user_id, master_id))
        else:
            check_query = sql.SQL("""
                SELECT id FROM {table}
                WHERE created_by=%s AND master_id IS NULL AND is_draft=TRUE
                ORDER BY id DESC
            """).format(table=sql.Identifier(table))
            cur.execute(check_query, (user_id,))

        existing_rows = cur.fetchall()

        if existing_rows:

            latest_id = existing_rows[0][0]

            # Delete older duplicates if any
            if len(existing_rows) > 1:
                delete_query = sql.SQL("""
                    DELETE FROM {table}
                    WHERE created_by=%s
                    AND is_draft=TRUE
                    AND id<>%s
                    AND (master_id=%s OR (master_id IS NULL AND %s IS NULL))
                """).format(table=sql.Identifier(table))
                cur.execute(delete_query, (user_id, latest_id, master_id, master_id))

            # Update latest draft
            set_clause = sql.SQL(", ").join(
                sql.SQL("{} = %s").format(sql.Identifier(col)) for col in safe_cols
            )

            # Update latest draft - ensure created_at is set if missing
            update_query = sql.SQL("""
                UPDATE {table}
                SET {fields},
                    created_at = COALESCE(created_at, NOW())
                WHERE id=%s
            """).format(table=sql.Identifier(table), fields=set_clause)

            cur.execute(update_query, clean_vals + [latest_id])

        else:
            # Insert new draft
            all_cols = safe_cols + ["created_by", "is_draft", "created_at"]
            all_vals = clean_vals + [user_id, True, datetime.datetime.now()]
            
            if master_id:
                all_cols.append("master_id")
                all_vals.append(master_id)

            insert_query = sql.SQL("""
                INSERT INTO {table} ({fields})
                VALUES ({placeholders})
            """).format(
                table=sql.Identifier(table),
                fields=sql.SQL(", ").join(map(sql.Identifier, all_cols)),
                placeholders=sql.SQL(", ").join(sql.Placeholder() for _ in all_cols),
            )

            cur.execute(insert_query, all_vals)

        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


def update_master_attachments(master_id, estimate_path=None, sar_path=None):
    """Updates the file attachment paths for a master submission."""
    master_id = int(master_id)
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        updates = []
        params = []
        
        if estimate_path is not None:
            updates.append("estimate_attachment = %s")
            params.append(estimate_path)
        
        if sar_path is not None:
            updates.append("sar_attachment = %s")
            params.append(sar_path)
            
        if not updates:
            return True
            
        params.append(master_id)
        query = f"UPDATE master_submission SET {', '.join(updates)} WHERE id = %s"
        
        cur.execute(query, params)
        conn.commit()
        return True
    except Exception as e:
        report_error("Error updating attachments.", e, "crud.update_master_attachments")
        if conn:
            conn.rollback()
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


def update_master_submission(master_id, estimate_number=None, year_of_estimate=None, name_of_project=None):
    """Updates the core metadata of a master submission."""
    master_id = int(master_id)
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        updates = []
        params = []
        
        if estimate_number is not None:
            updates.append("estimate_number = %s")
            params.append(estimate_number)
            
        if year_of_estimate is not None:
            updates.append("year_of_estimate = %s")
            params.append(year_of_estimate)
            
        if name_of_project is not None:
            updates.append("name_of_project = %s")
            params.append(name_of_project)
            
        if not updates:
            return True
            
        params.append(master_id)
        query = f"UPDATE master_submission SET {', '.join(updates)}, updated_at = NOW() WHERE id = %s"
        
        cur.execute(query, params)
        conn.commit()
        return True
    except Exception as e:
        report_error("Error updating master metadata.", e, "crud.update_master_submission")
        if conn:
            conn.rollback()
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


# ================= CREATE MASTER SUBMISSION =================
def create_master_submission(user_id, module, tables, status='COMPLETED', estimate_number=None, year_of_estimate=None, name_of_project=None):
    user_id = int(user_id)

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # Hard uniqueness check for (name_of_project, estimate_number, year_of_estimate)
        # ONLY for contract management
        if module == "contract_management" and name_of_project and estimate_number and year_of_estimate:
            cur.execute(
                """
                SELECT 1
                FROM master_submission
                WHERE LOWER(estimate_number) = LOWER(%s)
                  AND year_of_estimate = %s
                  AND module = %s
                  AND LOWER(name_of_project) = LOWER(%s)
                LIMIT 1
                """,
                (estimate_number, year_of_estimate, module, name_of_project),
            )
            if cur.fetchone():
                raise ValueError(
                    f"An application with Name: '{name_of_project}', Estimate No: '{estimate_number}' and Year: '{year_of_estimate}' already exists."
                )

        # Compute cycle inside the same DB session to avoid extra connection churn.
        cur.execute(
            """
            SELECT COALESCE(MAX(cycle), 0)
            FROM master_submission
            WHERE user_id=%s
              AND module=%s
            """,
            (user_id, module),
        )
        row = cur.fetchone()
        cycle = (row[0] if row and row[0] is not None else 0) + 1

        cur.execute(
            """
            INSERT INTO master_submission (user_id, cycle, status, module, created_at, estimate_number, year_of_estimate, name_of_project)
            VALUES (%s, %s, %s, %s, NOW(), %s, %s, %s)
            RETURNING id
        """,
            (user_id, cycle, status, module, estimate_number, year_of_estimate, name_of_project),
        )

        master_id = cur.fetchone()[0]

        # Always attach any unattached drafts for this user to the new master_id
        for table in tables:
            table = ensure_valid_table_name(table)
            cur.execute(
                sql.SQL(
                    """
                    UPDATE {table}
                    SET master_id=%s,
                        is_draft=TRUE
                    WHERE created_by=%s
                    AND master_id IS NULL
                    """
                ).format(table=sql.Identifier(table)),
                (master_id, user_id),
            )

        conn.commit()
        return master_id
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


# ================= UPDATE MASTER STATUS =================
def update_master_status(master_id, status):
    master_id = int(master_id)
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE master_submission SET status = %s WHERE id = %s",
            (status, master_id)
        )
        conn.commit()
        return True
    except Exception as e:
        report_error("Error updating master status.", e, "crud.update_master_status")
        if conn:
            conn.rollback()
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


# ================= GET USER MASTER SUBMISSIONS =================

def get_user_master_submissions(user_id, module):
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        if module:
            cur.execute("""
                SELECT m.*, u.username as created_by_user
                FROM master_submission m
                JOIN users u ON m.user_id = u.id
                WHERE m.user_id=%s
                AND m.module=%s
                AND m.status = 'COMPLETED'
                ORDER BY m.cycle DESC
            """, (user_id, module))
        else:
            cur.execute("""
                SELECT m.*, u.username as created_by_user
                FROM master_submission m
                JOIN users u ON m.user_id = u.id
                WHERE m.user_id=%s
                AND m.status = 'COMPLETED'
                ORDER BY m.cycle DESC
            """, (user_id,))
            
        columns = [desc[0] for desc in cur.description]
        records = [dict(zip(columns, row)) for row in cur.fetchall()]
        return records
    except Exception as e:
        report_error("Error getting user submissions.", e, "crud.get_user_master_submissions")
        return []
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


def get_user_master_submissions_admin(user_id):
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT m.*, u.username as created_by_user
            FROM master_submission m
            JOIN users u ON m.user_id = u.id
            WHERE m.user_id=%s
            AND m.status = 'COMPLETED'
            ORDER BY m.cycle DESC
        """, (user_id,))

        columns = [desc[0] for desc in cur.description]
        records = [dict(zip(columns, row)) for row in cur.fetchall()]
        return records
    except Exception as e:
        report_error("Error getting admin submissions.", e, "crud.get_user_master_submissions_admin")
        return []
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)



def get_submissions_by_estimate(est_no, est_yr, user_id=None, module=None, name_of_project=None):
    """
    Returns submissions by normalized match of estimate number and financial year string.
    Optionally filters by name_of_project.
    """
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # Basic validation to avoid SQL errors
        if not est_no or str(est_no).strip() == "---" or not est_yr or str(est_yr).strip() == "---":
            return []

        query = """
            SELECT m.*, u.username as created_by_user
            FROM master_submission m
            JOIN users u ON m.user_id = u.id
            WHERE TRIM(LOWER(COALESCE(m.estimate_number, ''))) = TRIM(LOWER(%s))
              AND TRIM(CAST(m.year_of_estimate AS TEXT)) = TRIM(CAST(%s AS TEXT))
        """
        params = [est_no, est_yr]

        if name_of_project:
            query += " AND TRIM(LOWER(COALESCE(m.name_of_project, ''))) = TRIM(LOWER(%s))"
            params.append(name_of_project)

        if user_id:
            query += " AND m.user_id = %s"
            params.append(user_id)
        
        if module:
            query += " AND m.module = %s"
            params.append(module)

        query += " ORDER BY m.created_at DESC"

        cur.execute(query, params)
        
        columns = [desc[0] for desc in cur.description]
        records = [dict(zip(columns, row)) for row in cur.fetchall()]
        return records
    except Exception as e:
        report_error(
            f"Error fetching applications for this estimate ({module or 'global'}).",
            e,
            "crud.get_submissions_by_estimate",
        )
        return []

    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


def _normalize_project_key(project_name):
    return " ".join(str(project_name or "").split()).lower()


def _get_first_non_empty_value(source_dict, *keys):
    source_dict = source_dict or {}
    for key in keys:
        value = source_dict.get(key)
        if value not in (None, ""):
            return value
    return None


def _normalize_text_value(value):
    if value in (None, ""):
        return None
    if isinstance(value, (list, tuple, set)):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return ", ".join(cleaned) if cleaned else None
    text_value = str(value).strip()
    return text_value if text_value else None


def ensure_project_dpr_table():
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS project_dpr (
                id BIGSERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                module VARCHAR(128) NOT NULL DEFAULT 'contract_management',
                project_name TEXT NOT NULL,
                project_key TEXT NOT NULL,
                dpr_form_data TEXT,
                category_of_project TEXT,
                type_of_project TEXT,
                location_of_head_works TEXT,
                date_of_investement_clearance_by_goi TEXT,
                date_of_cwc_clearence TEXT,
                date_of_approval_of_efc TEXT,
                districts_covered TEXT,
                gross_command_area TEXT,
                cca TEXT,
                irrigation_potential_in_rabi TEXT,
                irrigation_potential_in_kharif TEXT,
                requirement_of_water_for_project TEXT,
                availability_of_water_against_the_requirement TEXT,
                pre_project_crop_pattern_in_rabi TEXT,
                pre_project_crop_pattern_in_kharif TEXT,
                post_project_crop_pattern_in_rabi TEXT,
                post_project_crop_pattern_in_kharif TEXT,
                dpr_file_name TEXT,
                dpr_file_path TEXT,
                upload_complete_dpr_file_name TEXT,
                upload_complete_dpr_file_path TEXT,
                investment_clearence_file_name TEXT,
                investment_clearence_file_path TEXT,
                cwc_clearence_file_name TEXT,
                cwc_clearence_file_path TEXT,
                dpr_approval_by_efc_file_name TEXT,
                dpr_approval_by_efc_file_path TEXT,
                survey_reports_file_name TEXT,
                survey_reports_file_path TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                UNIQUE (user_id, module, project_key)
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_project_dpr_user_module
            ON project_dpr (user_id, module)
            """
        )
        cur.execute(
            """
            ALTER TABLE project_dpr
            ADD COLUMN IF NOT EXISTS dpr_form_data TEXT
            """
        )
        # Migrate legacy dummy column data into canonical columns before cleanup.
        legacy_candidates = [
            "dummmy_field_1",
            "dummmy_field_2",
            "dummmy_field_3",
            "dummmy_field_4",
            "dummmy_field_5",
            "dummy_field_1",
            "dummy_field_2",
            "dummy_field_3",
            "dummy_field_4",
            "dummy_field_5",
        ]
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'project_dpr'
              AND column_name = ANY(%s)
            """,
            (legacy_candidates,),
        )
        existing_legacy_cols = {row[0] for row in cur.fetchall()}

        migration_pairs = [
            ("category_of_project", ["dummmy_field_1", "dummy_field_1"]),
            ("type_of_project", ["dummmy_field_2", "dummy_field_2"]),
            ("location_of_head_works", ["dummmy_field_3", "dummy_field_3"]),
            ("districts_covered", ["dummmy_field_4", "dummy_field_4"]),
            ("gross_command_area", ["dummmy_field_5", "dummy_field_5"]),
        ]
        set_clauses = []
        for canonical_col, legacy_cols in migration_pairs:
            source_cols = [canonical_col] + [col for col in legacy_cols if col in existing_legacy_cols]
            if len(source_cols) <= 1:
                continue
            coalesce_parts = ", ".join([f"NULLIF(TRIM({col}), '')" for col in source_cols])
            set_clauses.append(f"{canonical_col} = COALESCE({coalesce_parts})")
        if set_clauses:
            cur.execute(f"UPDATE project_dpr SET {', '.join(set_clauses)}")
        # Remove legacy dummy columns from older schema versions.
        for legacy_col in [
            "dummmy_field_1",
            "dummmy_field_2",
            "dummmy_field_3",
            "dummmy_field_4",
            "dummmy_field_5",
            "dummy_field_1",
            "dummy_field_2",
            "dummy_field_3",
            "dummy_field_4",
            "dummy_field_5",
        ]:
            cur.execute(f"ALTER TABLE project_dpr DROP COLUMN IF EXISTS {legacy_col}")
        dpr_columns = [
            "category_of_project TEXT",
            "type_of_project TEXT",
            "location_of_head_works TEXT",
            "date_of_investement_clearance_by_goi TEXT",
            "date_of_cwc_clearence TEXT",
            "date_of_approval_of_efc TEXT",
            "districts_covered TEXT",
            "gross_command_area TEXT",
            "cca TEXT",
            "irrigation_potential_in_rabi TEXT",
            "irrigation_potential_in_kharif TEXT",
            "requirement_of_water_for_project TEXT",
            "availability_of_water_against_the_requirement TEXT",
            "pre_project_crop_pattern_in_rabi TEXT",
            "pre_project_crop_pattern_in_kharif TEXT",
            "post_project_crop_pattern_in_rabi TEXT",
            "post_project_crop_pattern_in_kharif TEXT",
            "upload_complete_dpr_file_name TEXT",
            "upload_complete_dpr_file_path TEXT",
            "investment_clearence_file_name TEXT",
            "investment_clearence_file_path TEXT",
            "cwc_clearence_file_name TEXT",
            "cwc_clearence_file_path TEXT",
            "dpr_approval_by_efc_file_name TEXT",
            "dpr_approval_by_efc_file_path TEXT",
            "survey_reports_file_name TEXT",
            "survey_reports_file_path TEXT",
        ]
        for i in range(1, 7):
            dpr_columns.extend(
                [
                    f"date_of_approval_revised_dpr_revision_{i} TEXT",
                    f"amount_of_revised_dpr_revision_{i} TEXT",
                    f"target_date_to_complete_project_revision_{i} TEXT",
                ]
            )
        for col_def in dpr_columns:
            cur.execute(f"ALTER TABLE project_dpr ADD COLUMN IF NOT EXISTS {col_def}")
        conn.commit()
        return True
    except Exception as e:
        report_error("Error ensuring project_dpr table.", e, "crud.ensure_project_dpr_table")
        if conn:
            conn.rollback()
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


def get_project_dpr(user_id, project_name, module="contract_management"):
    user_id = int(user_id)
    project_key = _normalize_project_key(project_name)
    if not project_key:
        return None

    if not ensure_project_dpr_table():
        return None

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT *
            FROM project_dpr
            WHERE user_id = %s
              AND module = %s
              AND project_key = %s
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (user_id, module, project_key),
        )
        row = cur.fetchone()
        if not row:
            return None
        columns = [desc[0] for desc in cur.description]
        return dict(zip(columns, row))
    except Exception as e:
        report_error("Error fetching project DPR.", e, "crud.get_project_dpr")
        return None
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


def upsert_project_dpr(
    user_id,
    project_name,
    fields,
    dpr_file_name,
    dpr_file_path=None,
    module="contract_management",
):
    user_id = int(user_id)
    project_name = (project_name or "").strip()
    project_key = _normalize_project_key(project_name)
    if not project_key:
        return False

    fields = fields or {}
    serialized_fields = json.dumps(fields, ensure_ascii=False)

    category_of_project = _normalize_text_value(
        _get_first_non_empty_value(fields, "Category of Project", "category_of_project")
    )
    type_of_project = _normalize_text_value(
        _get_first_non_empty_value(fields, "Type of Project", "type_of_project")
    )
    location_of_head_works = _normalize_text_value(
        _get_first_non_empty_value(fields, "Location of Head Works", "location_of_head_works")
    )
    date_of_investement_clearance_by_goi = _normalize_text_value(
        _get_first_non_empty_value(
            fields,
            "Date of Investement clearance by GOI",
            "date_of_investement_clearance_by_goi",
        )
    )
    date_of_cwc_clearence = _normalize_text_value(
        _get_first_non_empty_value(fields, "Date of CWC clearence", "date_of_cwc_clearence")
    )
    date_of_approval_of_efc = _normalize_text_value(
        _get_first_non_empty_value(fields, "Date of approval of EFC", "date_of_approval_of_efc")
    )
    districts_covered = _normalize_text_value(
        _get_first_non_empty_value(fields, "Districts covered", "districts_covered")
    )
    gross_command_area = _normalize_text_value(
        _get_first_non_empty_value(fields, "Gross Command area", "gross_command_area")
    )
    cca = _normalize_text_value(_get_first_non_empty_value(fields, "CCA", "cca"))
    irrigation_potential_in_rabi = _normalize_text_value(
        _get_first_non_empty_value(fields, "Irrigation Potential in RABI", "irrigation_potential_in_rabi")
    )
    irrigation_potential_in_kharif = _normalize_text_value(
        _get_first_non_empty_value(fields, "Irrigation Potential in KHARIF", "irrigation_potential_in_kharif")
    )
    requirement_of_water_for_project = _normalize_text_value(
        _get_first_non_empty_value(fields, "Requirement of Water for project", "requirement_of_water_for_project")
    )
    availability_of_water_against_the_requirement = _normalize_text_value(
        _get_first_non_empty_value(
            fields,
            "Availability of Water against the requirement",
            "availability_of_water_against_the_requirement",
        )
    )
    pre_project_crop_pattern_in_rabi = _normalize_text_value(
        _get_first_non_empty_value(fields, "Pre-Project Crop Pattern in RABI", "pre_project_crop_pattern_in_rabi")
    )
    pre_project_crop_pattern_in_kharif = _normalize_text_value(
        _get_first_non_empty_value(fields, "Pre-Project Crop Pattern in KHARIF", "pre_project_crop_pattern_in_kharif")
    )
    post_project_crop_pattern_in_rabi = _normalize_text_value(
        _get_first_non_empty_value(fields, "Post-Project Crop Pattern in RABI", "post_project_crop_pattern_in_rabi")
    )
    post_project_crop_pattern_in_kharif = _normalize_text_value(
        _get_first_non_empty_value(fields, "Post-Project Crop Pattern in KHARIF", "post_project_crop_pattern_in_kharif")
    )

    upload_complete_dpr_file_name = _normalize_text_value(
        _get_first_non_empty_value(fields, "upload_complete_dpr_file_name", "dpr_file_name")
    )
    upload_complete_dpr_file_path = _normalize_text_value(
        _get_first_non_empty_value(fields, "upload_complete_dpr_file_path", "dpr_file_path")
    )
    investment_clearence_file_name = _normalize_text_value(
        _get_first_non_empty_value(fields, "investment_clearence_file_name")
    )
    investment_clearence_file_path = _normalize_text_value(
        _get_first_non_empty_value(fields, "investment_clearence_file_path")
    )
    cwc_clearence_file_name = _normalize_text_value(
        _get_first_non_empty_value(fields, "cwc_clearence_file_name")
    )
    cwc_clearence_file_path = _normalize_text_value(
        _get_first_non_empty_value(fields, "cwc_clearence_file_path")
    )
    dpr_approval_by_efc_file_name = _normalize_text_value(
        _get_first_non_empty_value(fields, "dpr_approval_by_efc_file_name")
    )
    dpr_approval_by_efc_file_path = _normalize_text_value(
        _get_first_non_empty_value(fields, "dpr_approval_by_efc_file_path")
    )
    survey_reports_file_name = _normalize_text_value(
        _get_first_non_empty_value(fields, "survey_reports_file_name")
    )
    survey_reports_file_path = _normalize_text_value(
        _get_first_non_empty_value(fields, "survey_reports_file_path")
    )

    revision_values = {}
    for i in range(1, 7):
        suffix = {1: "1st", 2: "2nd", 3: "3rd"}.get(i, f"{i}th")
        date_label = f"Date of approval revised DPR ({suffix} revision)"
        amount_label = f"Amount of revised DPR ({suffix} revision)"
        target_label = f"Target date to complete the project ({suffix} revision)"

        revision_values[f"date_of_approval_revised_dpr_revision_{i}"] = _normalize_text_value(
            _get_first_non_empty_value(fields, date_label, f"date_of_approval_revised_dpr_revision_{i}")
        )
        revision_values[f"amount_of_revised_dpr_revision_{i}"] = _normalize_text_value(
            _get_first_non_empty_value(fields, amount_label, f"amount_of_revised_dpr_revision_{i}")
        )
        revision_values[f"target_date_to_complete_project_revision_{i}"] = _normalize_text_value(
            _get_first_non_empty_value(fields, target_label, f"target_date_to_complete_project_revision_{i}")
        )

    # Keep legacy DPR file columns synchronized with Upload Complete DPR.
    final_dpr_file_name = _normalize_text_value(dpr_file_name) or upload_complete_dpr_file_name
    final_dpr_file_path = _normalize_text_value(dpr_file_path) or upload_complete_dpr_file_path

    if not ensure_project_dpr_table():
        return False

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        dpr_record = {
            "project_name": project_name,
            "dpr_form_data": serialized_fields,
            "category_of_project": category_of_project,
            "type_of_project": type_of_project,
            "location_of_head_works": location_of_head_works,
            "date_of_investement_clearance_by_goi": date_of_investement_clearance_by_goi,
            "date_of_cwc_clearence": date_of_cwc_clearence,
            "date_of_approval_of_efc": date_of_approval_of_efc,
            "districts_covered": districts_covered,
            "gross_command_area": gross_command_area,
            "cca": cca,
            "irrigation_potential_in_rabi": irrigation_potential_in_rabi,
            "irrigation_potential_in_kharif": irrigation_potential_in_kharif,
            "requirement_of_water_for_project": requirement_of_water_for_project,
            "availability_of_water_against_the_requirement": availability_of_water_against_the_requirement,
            "pre_project_crop_pattern_in_rabi": pre_project_crop_pattern_in_rabi,
            "pre_project_crop_pattern_in_kharif": pre_project_crop_pattern_in_kharif,
            "post_project_crop_pattern_in_rabi": post_project_crop_pattern_in_rabi,
            "post_project_crop_pattern_in_kharif": post_project_crop_pattern_in_kharif,
            "dpr_file_name": final_dpr_file_name,
            "dpr_file_path": final_dpr_file_path,
            "upload_complete_dpr_file_name": upload_complete_dpr_file_name,
            "upload_complete_dpr_file_path": upload_complete_dpr_file_path,
            "investment_clearence_file_name": investment_clearence_file_name,
            "investment_clearence_file_path": investment_clearence_file_path,
            "cwc_clearence_file_name": cwc_clearence_file_name,
            "cwc_clearence_file_path": cwc_clearence_file_path,
            "dpr_approval_by_efc_file_name": dpr_approval_by_efc_file_name,
            "dpr_approval_by_efc_file_path": dpr_approval_by_efc_file_path,
            "survey_reports_file_name": survey_reports_file_name,
            "survey_reports_file_path": survey_reports_file_path,
        }
        dpr_record.update(revision_values)

        update_assignments = ",\n                ".join(
            [f"{col_name} = %s" for col_name in dpr_record.keys()] + ["updated_at = NOW()"]
        )
        update_sql = f"""
            UPDATE project_dpr
            SET
                {update_assignments}
            WHERE user_id = %s
              AND module = %s
              AND project_key = %s
        """
        update_params = list(dpr_record.values()) + [user_id, module, project_key]
        cur.execute(update_sql, update_params)

        if cur.rowcount == 0:
            insert_columns = ["user_id", "module", "project_key"] + list(dpr_record.keys())
            insert_columns_sql = ",\n                    ".join(insert_columns + ["created_at", "updated_at"])
            insert_values_sql = ", ".join(["%s"] * len(insert_columns) + ["NOW()", "NOW()"])
            insert_sql = f"""
                INSERT INTO project_dpr (
                    {insert_columns_sql}
                )
                VALUES (
                    {insert_values_sql}
                )
            """
            insert_params = [user_id, module, project_key] + list(dpr_record.values())
            cur.execute(insert_sql, insert_params)
        conn.commit()
        return True
    except Exception as e:
        report_error("Error saving project DPR.", e, "crud.upsert_project_dpr")
        if conn:
            conn.rollback()
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


def get_master_submission(master_id):
    """Retrieves a single record from master_submission by ID."""
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT m.*, u.username as created_by_user
            FROM master_submission m
            JOIN users u ON m.user_id = u.id
            WHERE m.id = %s
        """, (master_id,))
        
        columns = [desc[0] for desc in cur.description]
        row = cur.fetchone()
        return dict(zip(columns, row)) if row else None
    except Exception as e:
        report_error("Error getting master submission.", e, "crud.get_master_submission")
        return None
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


# ================= GET FULL SUBMISSION DATA =================
def get_full_submission_data(master_id):
    conn = None
    cur = None
    full_data = {}
    try:
        conn = get_connection()
        cur = conn.cursor()
        tables = get_all_tables(conn)
        for table in tables:
            table = ensure_valid_table_name(table)
            query = sql.SQL(
                """
                SELECT *
                FROM {table}
                WHERE master_id=%s
                """
            ).format(table=sql.Identifier(table))
            cur.execute(query, (master_id,))
            rows = cur.fetchall()
            if rows:
                columns = [desc[0] for desc in cur.description]
                full_data[table] = pd.DataFrame(rows, columns=columns)

    except Exception as e:
        report_error("Error getting full submission data.", e, "crud.get_full_submission_data")
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)
    return full_data


# ================= GET FULL DRAFT DATA =================
def get_full_draft_data(user_id, module_tables):
    """
    Fetches all records with is_draft=TRUE for a specific user across a set of tables.
    Returns a dict of {table_name: DataFrame}
    """
    conn = None
    cur = None
    full_data = {}
    try:
        conn = get_connection()
        cur = conn.cursor()
        for table in module_tables:
            table = ensure_valid_table_name(table)
            query = sql.SQL(
                """
                SELECT *
                FROM {table}
                WHERE created_by=%s AND is_draft=TRUE
                """
            ).format(table=sql.Identifier(table))
            cur.execute(query, (user_id,))
            rows = cur.fetchall()
            if rows:
                columns = [desc[0] for desc in cur.description]
                full_data[table] = pd.DataFrame(rows, columns=columns)

    except Exception as e:
        report_error("Error getting full draft data.", e, "crud.get_full_draft_data")
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)
    return full_data




def get_user_progress(user_id, tables, master_id=None):
    """Returns (percentage, completed_count, total_count) based on master_id."""
    user_id = int(user_id)
    if not tables:
        return 0, 0, 0
        
    conn = None
    cur = None
    completed = 0
    total = len(tables)

    try:
        conn = get_connection()
        cur = conn.cursor()

        if not master_id:
            return 0, 0, total

        for table in tables:
            table = ensure_valid_table_name(table)
            query = sql.SQL(
                """
                SELECT EXISTS (
                    SELECT 1 FROM {table}
                    WHERE created_by=%s AND master_id=%s
                )
                """
            ).format(table=sql.Identifier(table))
            cur.execute(query, (user_id, master_id))
            exists = cur.fetchone()[0]
            if exists:
                completed += 1

    except Exception as e:
        report_error("Error calculating user progress.", e, "crud.get_user_progress")
        return 0, 0, total
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)

    percentage = (completed / total) * 100 if total > 0 else 0
    return percentage, completed, total


def set_drafts_to_final(master_id, tables):
    """Marks all rows for a master_id as is_draft=FALSE."""
    master_id = int(master_id)
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        for table in tables:
            table = ensure_valid_table_name(table)
            cur.execute(
                sql.SQL("UPDATE {table} SET is_draft=FALSE WHERE master_id=%s").format(
                    table=sql.Identifier(table)
                ),
                (master_id,)
            )
        conn.commit()
    except Exception as e:
        report_error("Error finalizing drafts.", e, "crud.set_drafts_to_final")
        if conn:
            conn.rollback()
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


# ================= INCOMPLETE SECTIONS =================
def get_incomplete_forms(user_id, tables, master_id=None):
    """Returns a list of tables missing a completed entry for the specific application."""
    user_id = int(user_id)
    if not tables:
        return []

    # Actually, to get EXACT table names that are incomplete, we need the inverse of the UNION ALL
    conn = None
    cur = None
    incomplete = []
    
    try:
        conn = get_connection()
        cur = conn.cursor()

        if not master_id:
            return tables

        completed_tables = []
        for table in tables:
            table = ensure_valid_table_name(table)
            query = sql.SQL(
                """
                SELECT EXISTS (
                    SELECT 1 FROM {table}
                    WHERE created_by=%s AND master_id=%s
                )
                """
            ).format(table=sql.Identifier(table))
            cur.execute(query, (user_id, master_id))
            if cur.fetchone()[0]:
                completed_tables.append(table)

        incomplete = [t for t in tables if t not in completed_tables]

    except Exception as e:
        report_error("Error getting incomplete forms.", e, "crud.get_incomplete_forms")
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)
            
    return incomplete


def get_user_draft_summaries(user_id):
    """
    Fetches all master_submission records for a user that have status='DRAFT'.
    """
    user_id = int(user_id)
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT m.*, u.username as created_by_user
            FROM master_submission m
            JOIN users u ON m.user_id = u.id
            WHERE m.user_id=%s AND m.status='DRAFT'
            ORDER BY m.created_at DESC
        """, (user_id,))
            
        columns = [desc[0] for desc in cur.description]
        records = [dict(zip(columns, row)) for row in cur.fetchall()]
        
        # Include all drafts, regardless of progress
        final_records = [rec for rec in records]
        
        return final_records
    except Exception as e:
        report_error("Error getting draft summaries.", e, "crud.get_user_draft_summaries")
        return []
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


# ================= STATUS COUNTS =================
def get_user_master_status_counts(user_id, all_modules=None):
    user_id = int(user_id)

    conn = None
    cur = None
    submitted = 0
    drafts = 0

    try:
        conn = get_connection()

        cur = conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*)
            FROM master_submission
            WHERE user_id=%s AND status='COMPLETED'
        """,
            (user_id,),
        )
        submitted = cur.fetchone()[0]
        
        # If all_modules provided, count modules with drafts
        if all_modules:
            draft_list = get_user_draft_summaries(user_id)
            drafts = len(draft_list)

    except Exception as e:
        report_error("Error getting master status counts.", e, "crud.get_user_master_status_counts")
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)

    # Return only submitted and drafts
    return submitted, drafts


# ================= EXPORT MASTER PDF =================
def delete_unattached_drafts(user_id, tables):
    """Deletes any records where master_id is NULL for the given user (un-saved lazy drafts)."""
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        for table in tables:
            table = ensure_valid_table_name(table)
            cur.execute(
                sql.SQL("DELETE FROM {table} WHERE created_by = %s AND master_id IS NULL").format(
                    table=sql.Identifier(table)
                ),
                (user_id,),
            )
        conn.commit()
    except Exception as e:
        report_error("Error deleting unattached drafts.", e, "crud.delete_unattached_drafts")
        if conn:
            conn.rollback()
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


def export_master_submission_pdf(master_id):
    conn = None
    cur = None
    buffer = io.BytesIO()

    try:
        conn = get_connection()

        # Fetch master info
        cur = conn.cursor()
        cur.execute(
            """
            SELECT u.username as created_by_user, m.module, m.estimate_number, m.year_of_estimate
            FROM master_submission m
            JOIN users u ON m.user_id = u.id
            WHERE m.id=%s
        """,
            (master_id,),
        )

        master_row = cur.fetchone()

        created_by_user = master_row[0] if master_row else "Unknown"
        module_val = master_row[1] if master_row else ""
        est_no = master_row[2] if master_row else "---"
        est_yr = master_row[3] if master_row else "---"
        
        # Format the year (est_yr is now a string like '2024-25')
        formatted_yr = str(est_yr) if est_yr else "---"
        
        display_key = f"{est_no} ({formatted_yr})" if est_no != "---" else "---"

        tables = get_all_tables(conn)

        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=20,
            leftMargin=20,
            topMargin=20,
            bottomMargin=20,
        )

        elements = []
        styles = getSampleStyleSheet()

        elements.append(
            Paragraph(f"<b>Application Record</b>", styles["Title"])
        )
        elements.append(Spacer(1, 12))
        
        elements.append(
            Paragraph(f"<b>Submitted By:</b> {created_by_user}", styles["Heading2"])
        )
        elements.append(
            Paragraph(f"<b>Module:</b> {module_val.replace('_', ' ').title()}", styles["Heading2"])
        )
        if module_val == "contract_management":
            elements.append(
                Paragraph(f"<b>Estimate Key:</b> {display_key}", styles["Heading2"])
            )
        elements.append(Spacer(1, 20))

        wrap_style = ParagraphStyle(
            name="wrap", parent=styles["Normal"], fontSize=7, leading=9
        )

        page_width = landscape(A4)[0] - 40
        MAX_COLS_PER_TABLE = 15  # 🔥 change if needed

        for table in tables:
            table = ensure_valid_table_name(table)
            cur.execute(
                sql.SQL("SELECT * FROM {table} WHERE master_id=%s").format(
                    table=sql.Identifier(table)
                ),
                (master_id,),
            )
            rows = cur.fetchall()
            if not rows:
                continue
            columns = [desc[0] for desc in cur.description]
            df = pd.DataFrame(rows, columns=columns)

            # 🔥 Filter out system columns requested by user
            cols_to_exclude = [
                'status', 'approval_status', 'created_by', 'approved_by', 
                'approved_at', 'rejected_at', 'is_draft', 'master_id', 
                'id', 'created_at', 'updated_at', 'draft_id'
            ]
            df = df.drop(columns=[c for c in cols_to_exclude if c in df.columns])

            if df.empty:
                continue

            clean_table_name = table.replace("_", " ").title()
            elements.append(Paragraph(f"<b>{clean_table_name}</b>", styles["Heading2"]))
            elements.append(Spacer(1, 10))

            total_cols = len(df.columns)

            # 🔥 Split into column chunks
            for start in range(0, total_cols, MAX_COLS_PER_TABLE):

                end = start + MAX_COLS_PER_TABLE
                df_chunk = df.iloc[:, start:end]

                data = []

                # Header
                header = [Paragraph(str(col).replace("_", " ").title(), wrap_style) for col in df_chunk.columns]
                data.append(header)

                # Rows
                for row in df_chunk.itertuples(index=False):
                    row_data = [
                        Paragraph("" if val is None else str(val), wrap_style)
                        for val in row
                    ]
                    data.append(row_data)

                num_cols = len(df_chunk.columns)
                col_width = page_width / num_cols

                table_obj = Table(data, colWidths=[col_width] * num_cols, repeatRows=1)

                table_obj.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("FONTSIZE", (0, 0), (-1, -1), 7),
                            ("LEFTPADDING", (0, 0), (-1, -1), 2),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                        ]
                    )
                )

                elements.append(table_obj)
                elements.append(Spacer(1, 15))

        if not elements:
            elements.append(Paragraph("No Data Available", styles["Normal"]))

        doc.build(elements)
    except Exception as e:
        report_error("Error exporting PDF.", e, "crud.export_master_submission_pdf")
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)

    buffer.seek(0)
    return buffer


# ================= GET TABLE COLUMNS =================

def get_table_columns(table, is_admin=False):
    conn = None
    cur = None
    try:
        table = ensure_valid_table_name(table)
        conn = get_connection()
        cur = conn.cursor()

        query = """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema='public'
            AND table_name=%s
            ORDER BY ordinal_position
        """

        cur.execute(query, (table,))
        columns = [desc[0] for desc in cur.description]
        records = [dict(zip(columns, row)) for row in cur.fetchall()]

        system_fields = (
            "id",
            "created_by",
            "is_draft",
            "master_id",
            "submitted_at",
            "approval_status",
            "approved_at",
            "submission_cycle",
            "created_at",
            "status",
            "approved_by",
            "draft_id",
        )

        if not is_admin:
            records = [r for r in records if r["column_name"] not in system_fields]
        return records
    except Exception as e:
        report_error("Error getting table columns.", e, "crud.get_table_columns")
        return []
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


def get_user_draft(table, user_id, master_id=None):
    conn = None
    cur = None
    try:
        table = ensure_valid_table_name(table)
        conn = get_connection()
        cur = conn.cursor()

        if master_id:
            query = sql.SQL("""
                SELECT * FROM {table}
                WHERE created_by=%s 
                AND master_id=%s
                AND is_draft=TRUE
                ORDER BY id DESC
                LIMIT 1
            """).format(table=sql.Identifier(table))
            cur.execute(query, (user_id, master_id))
        else:
            query = sql.SQL("""
                SELECT * FROM {table}
                WHERE created_by=%s 
                AND is_draft=TRUE
                AND master_id IS NULL
                ORDER BY id DESC
                LIMIT 1
            """).format(table=sql.Identifier(table))
            cur.execute(query, (user_id,))
            
        row = cur.fetchone()

        if not row:
            return None

        columns = [desc[0] for desc in cur.description]

        return dict(zip(columns, row))
    except Exception as e:
        report_error("Error getting user draft.", e, "crud.get_user_draft")
        return None
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)




def can_user_edit(master_id):
    status = get_master_status(master_id)

    if status == "DRAFT":
        return True

    return False



# ================= RESTORE DRAFT =================


def get_master_status(master_id):
    master_id = int(master_id)
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        query = """
            SELECT status
            FROM master_submission
            WHERE id = %s
        """

        cur.execute(query, (master_id,))
        result = cur.fetchone()

        if result:
            return result[0]
        return None
    except Exception as e:
        report_error("Error getting master status.", e, "crud.get_master_status")
        return None
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)
def create_user(username, password, role="operator", allowed_modules=""):
    """
    Creates a new user. Returns (True, "Success message") or (False, "Error message").
    """
    username = (username or "").strip()
    role = (role or "operator").strip().lower()
    allowed_modules = (allowed_modules or "").strip()

    if not username:
        return False, "Username cannot be empty."
    if not isinstance(password, str) or len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if role not in {"admin", "operator"}:
        return False, "Invalid role selected."

    conn = get_connection()
    cur = conn.cursor()

    try:
        # Check if username already exists (case-insensitive)
        cur.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(%s)", (username,))
        if cur.fetchone():
            return False, f"Username '{username}' already exists. Please choose a unique username."

        # Insert new user
        password_hash = hash_password(password)
        cur.execute(
            "INSERT INTO users (username, password_hash, role, is_active, allowed_modules) VALUES (%s, %s, %s, TRUE, %s)",
            (username, password_hash, role, allowed_modules)
        )
        conn.commit()
        return True, f"User '{username}' created successfully!"

    except Exception as e:
        conn.rollback()
        report_error("Error creating user.", e, "crud.create_user")
        return False, "Database error while creating user."
    finally:
        cur.close()
        release_connection(conn)

def get_all_users_admin():
    conn = None
    try:
        conn = get_connection()
        df = pd.read_sql("SELECT id, username, role, is_active, allowed_modules FROM users ORDER BY id", conn)
        return df
    except Exception as e:
        report_error("Error getting users list.", e, "crud.get_all_users_admin")
        return pd.DataFrame(columns=["id", "username", "role", "is_active"])
    finally:
        if conn:
            release_connection(conn)

def get_user_by_id(uid):
    """
    Fetches user information by ID.
    """
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, username, role, is_active, allowed_modules FROM users WHERE id = %s", (uid,))
        row = cur.fetchone()
        if row:
            return {
                "id": row[0],
                "username": row[1],
                "role": row[2],
                "is_active": row[3],
                "allowed_modules": row[4]
            }
        return None
    except Exception as e:
        report_error("Error fetching user.", e, "crud.get_user_by_id")
        return None
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)

def toggle_user_status(user_id, current_status):
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        new_status = not current_status
        cur.execute("UPDATE users SET is_active = %s WHERE id = %s", (new_status, user_id))
        conn.commit()
    except Exception as e:
        report_error("Error toggling user status.", e, "crud.toggle_user_status")
        if conn:
            conn.rollback()
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)

def update_user_modules(user_id, modules_list):
    """
    Updates the allowed_modules for a user. modules_list is a list of module prefixes.
    """
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        modules_str = ",".join(modules_list)
        cur.execute("UPDATE users SET allowed_modules = %s WHERE id = %s", (modules_str, user_id))
        conn.commit()
    except Exception as e:
        report_error("Error updating user modules.", e, "crud.update_user_modules")
        if conn:
            conn.rollback()
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)
