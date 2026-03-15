import psycopg2
from psycopg2 import pool
import pandas as pd
import streamlit as st
from psycopg2 import sql

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
import io
import os


# ================= DB CONNECTION =================

@st.cache_resource
def get_db_pool():
    # Using SimpleConnectionPool because Streamlit threading model
    # sometimes causes ThreadedConnectionPool to lose track of keys
    return psycopg2.pool.SimpleConnectionPool(
        1, 20,
        host=os.getenv("DB_HOST", "host.docker.internal"),
        database=os.getenv("DB_NAME", "Irrigation"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "123456"),
        port=os.getenv("DB_PORT", "5432")
    )

def get_connection():
    conn = get_db_pool().getconn()
    conn.autocommit = True
    return conn

def release_connection(conn):
    if conn:
        get_db_pool().putconn(conn)


# ================= LOAD TABLES =================

def get_all_tables(conn=None):
    close_conn = False

    if conn is None:
        try:
            conn = get_connection()
            close_conn = True
        except Exception as e:
            st.error(f"Database connection error: {e}")
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
        st.error(f"Error fetching tables: {e}")
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
        st.error(f"Error getting next cycle: {e}")
        return 1
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


# ================= SAVE DRAFT =================
def save_draft_record(table, data, user_id):
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

        # STEP 1: Fetch existing draft rows
        check_query = sql.SQL("""
            SELECT id FROM {table}
            WHERE created_by=%s AND is_draft=TRUE
            ORDER BY id DESC
        """).format(table=sql.Identifier(table))

        cur.execute(check_query, (user_id,))
        existing_rows = cur.fetchall()

        if existing_rows:

            latest_id = existing_rows[0][0]

            # Delete older drafts
            if len(existing_rows) > 1:
                delete_query = sql.SQL("""
                    DELETE FROM {table}
                    WHERE created_by=%s
                    AND is_draft=TRUE
                    AND id<>%s
                """).format(table=sql.Identifier(table))

                cur.execute(delete_query, (user_id, latest_id))

            # Update latest draft
            set_clause = sql.SQL(", ").join(
                sql.SQL("{} = %s").format(sql.Identifier(col)) for col in safe_cols
            )

            update_query = sql.SQL("""
                UPDATE {table}
                SET {fields}
                WHERE id=%s
            """).format(table=sql.Identifier(table), fields=set_clause)

            cur.execute(update_query, clean_vals + [latest_id])

        else:
            # Insert new draft
            insert_query = sql.SQL("""
                INSERT INTO {table} ({fields}, created_by, is_draft)
                VALUES ({placeholders}, %s, TRUE)
            """).format(
                table=sql.Identifier(table),
                fields=sql.SQL(", ").join(map(sql.Identifier, safe_cols)),
                placeholders=sql.SQL(", ").join(sql.Placeholder() for _ in safe_cols),
            )

            cur.execute(insert_query, clean_vals + [user_id])

        conn.commit()
    except Exception as e:
        st.error(f"Error saving draft record: {e}")
        if conn:
            conn.rollback()
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


# ================= CREATE MASTER SUBMISSION =================
def create_master_submission(user_id, module, tables):
    user_id = int(user_id)
    cycle = get_next_cycle(user_id, module)

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # Create module-specific master
        cur.execute(
            """
            INSERT INTO master_submission (user_id, cycle, status, module)
            VALUES (%s, %s, 'PENDING', %s)
            RETURNING id
        """,
            (user_id, cycle, module),
        )

        master_id = cur.fetchone()[0]

        # Attach drafts only for this module
        for table in tables:
            cur.execute(
                f"""
                UPDATE "{table}"
                SET is_draft=FALSE,
                    master_id=%s
                WHERE created_by=%s
                AND is_draft=TRUE
            """,
                (master_id, user_id),
            )

        conn.commit()
    except Exception as e:
        st.error(f"Error creating master submission: {e}")
        if conn:
            conn.rollback()
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
                SELECT *
                FROM master_submission
                WHERE user_id=%s
                AND module=%s
                ORDER BY cycle DESC
            """, (user_id, module))
        else:
            cur.execute("""
                SELECT *
                FROM master_submission
                WHERE user_id=%s
                ORDER BY cycle DESC
            """, (user_id,))
            
        columns = [desc[0] for desc in cur.description]
        records = [dict(zip(columns, row)) for row in cur.fetchall()]
        return records
    except Exception as e:
        st.error(f"Error getting user master submissions: {e}")
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
            SELECT *
            FROM master_submission
            WHERE user_id=%s
            ORDER BY cycle DESC
        """, (user_id,))

        columns = [desc[0] for desc in cur.description]
        records = [dict(zip(columns, row)) for row in cur.fetchall()]
        return records
    except Exception as e:
        st.error(f"Error getting admin submissions: {e}")
        return []
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


# ================= GET FULL SUBMISSION DATA =================
def get_full_submission_data(master_id):
    conn = None
    full_data = {}
    try:
        conn = get_connection()
        tables = get_all_tables(conn)


        for table in tables:
            df = pd.read_sql(
                f"""
                SELECT *
                FROM "{table}"
                WHERE master_id=%s
            """,
                conn,
                params=[master_id],
            )

            if not df.empty:
                full_data[table] = df

    except Exception as e:
        st.error(f"Error getting full submission data: {e}")
    finally:
        if conn:
            release_connection(conn)
    return full_data


# ================= APPROVE MASTER =================
def approve_master_submission(master_id):
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # 1️⃣ Update master table
        cur.execute(
            """
            UPDATE master_submission
            SET status='APPROVED',
                approved_at=NOW()
            WHERE id=%s
        """,
            (master_id,),
        )

        # 2️⃣ Update all related form tables
        tables = get_all_tables(conn)

        for table in tables:
            update_query = sql.SQL("""
                UPDATE {table}
                SET approval_status='APPROVED'
                WHERE master_id=%s
            """).format(table=sql.Identifier(table))

            cur.execute(update_query, (master_id,))

        conn.commit()
    except Exception as e:
        st.error(f"Error approving master submission: {e}")
        if conn:
            conn.rollback()
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


# ================= REJECT MASTER =================
def reject_master_submission(master_id, reason):
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # 1️⃣ Update master table
        cur.execute(
            """
            UPDATE master_submission
            SET status='REJECTED',
                rejection_reason=%s,
                rejected_at=NOW()
            WHERE id=%s
        """,
            (reason, master_id),
        )

        # 2️⃣ Update all related form tables
        tables = get_all_tables(conn)

        for table in tables:
            update_query = sql.SQL("""
                UPDATE {table}
                SET approval_status='REJECTED'
                WHERE master_id=%s
            """).format(table=sql.Identifier(table))

            cur.execute(update_query, (master_id,))

        conn.commit()
    except Exception as e:
        st.error(f"Error rejecting master submission: {e}")
        if conn:
            conn.rollback()
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


# ================= USER PROGRESS =================
def get_user_progress(user_id, tables):
    user_id = int(user_id)

    conn = None
    cur = None
    total = len(tables)
    completed = 0

    try:
        conn = get_connection()
        cur = conn.cursor()

        if tables:
            union_queries = []
            for table in tables:
                union_queries.append(f"""
                    SELECT '{table}'
                    WHERE EXISTS (
                        SELECT 1 FROM "{table}" WHERE created_by=%s AND is_draft=TRUE
                    )
                """)
            combined_query = " UNION ALL ".join(union_queries)
            cur.execute(combined_query, [user_id] * len(tables))
            completed = len(cur.fetchall())

    except Exception as e:
        st.error(f"Error getting user progress: {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)

    percentage = int((completed / total) * 100) if total > 0 else 0

    return percentage, completed, total


# ================= INCOMPLETE SECTIONS =================
def get_incomplete_forms(user_id, tables):
    user_id = int(user_id)
    conn = None
    cur = None
    incomplete = []

    try:
        conn = get_connection()
        cur = conn.cursor()

        if tables:
            union_queries = []
            params = []
            for table in tables:
                columns = get_table_columns(table, is_admin=False)
                business_cols = [col["column_name"] for col in columns]

                if not business_cols:
                    incomplete.append(table)
                    continue

                conditions = " OR ".join([f'"{col}" IS NOT NULL' for col in business_cols])

                union_queries.append(f"""
                    SELECT '{table}'
                    WHERE NOT EXISTS (
                        SELECT 1 FROM "{table}"
                        WHERE created_by=%s AND is_draft=TRUE AND ({conditions})
                    )
                """)
                params.append(user_id)
            
            if union_queries:
                combined_query = " UNION ALL ".join(union_queries)
                cur.execute(combined_query, params)
                incomplete.extend([row[0] for row in cur.fetchall()])

    except Exception as e:
        st.error(f"Error getting incomplete forms: {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)

    return incomplete


# ================= STATUS COUNTS =================
def get_user_master_status_counts(user_id):
    user_id = int(user_id)

    conn = None
    approved = rejected = pending = 0

    try:
        conn = get_connection()

        df = pd.read_sql(
            """
            SELECT status, COUNT(*)
            FROM master_submission
            WHERE user_id=%s
            GROUP BY status
        """,
            conn,
            params=[user_id],
        )

        for _, row in df.iterrows():
            if row["status"] == "APPROVED":
                approved = row["count"]
            elif row["status"] == "REJECTED":
                rejected = row["count"]
            else:
                pending = row["count"]

    except Exception as e:
        st.error(f"Error getting master status counts: {e}")
    finally:
        if conn:
            release_connection(conn)

    return approved, rejected, pending


# ================= EXPORT MASTER PDF =================
def export_master_submission_pdf(master_id):
    conn = None
    cur = None
    buffer = io.BytesIO()

    try:
        conn = get_connection()

        # 🔥 Fetch master status and rejection reason
        cur = conn.cursor()
        cur.execute(
            """
            SELECT status, rejection_reason, module
            FROM master_submission
            WHERE id=%s
        """,
            (master_id,),
        )

        master_row = cur.fetchone()

        status = master_row[0] if master_row else ""
        rejection_reason = master_row[1] if master_row else None

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

        # 🔥 Add Application Status at top
        elements.append(
            Paragraph(f"<b>Application Status:</b> {status}", styles["Heading2"])
        )
        elements.append(Spacer(1, 12))

        # 🔥 If Rejected → Show Reason
        if status == "REJECTED" and rejection_reason:
            elements.append(
                Paragraph(f"<b>Rejection Reason:</b> {rejection_reason}", styles["Normal"])
            )
            elements.append(Spacer(1, 20))

        wrap_style = ParagraphStyle(
            name="wrap", parent=styles["Normal"], fontSize=7, leading=9
        )

        page_width = landscape(A4)[0] - 40
        MAX_COLS_PER_TABLE = 8  # 🔥 change if needed

        for table in tables:

            df = pd.read_sql(
                f'SELECT * FROM "{table}" WHERE master_id=%s', conn, params=[master_id]
            )

            if df.empty:
                continue

            elements.append(Paragraph(f"<b>{table}</b>", styles["Heading2"]))
            elements.append(Spacer(1, 10))

            total_cols = len(df.columns)

            # 🔥 Split into column chunks
            for start in range(0, total_cols, MAX_COLS_PER_TABLE):

                end = start + MAX_COLS_PER_TABLE
                df_chunk = df.iloc[:, start:end]

                data = []

                # Header
                header = [Paragraph(str(col), wrap_style) for col in df_chunk.columns]
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
        st.error(f"Error exporting PDF: {e}")
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
        st.error(f"Error getting table columns: {e}")
        return []
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


def get_user_draft(table, user_id):
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

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
        st.error(f"Error getting user draft: {e}")
        return None
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


def get_users_with_data():
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # Users with submitted master or drafts
        tables = get_all_tables(conn)
        
        draft_queries = ""
        if tables:
            union_parts = [f'SELECT created_by AS user_id FROM "{table}" WHERE is_draft=TRUE' for table in tables]
            draft_queries = " UNION " + " UNION ".join(union_parts)

        combined_query = f"""
            SELECT DISTINCT user_id FROM (
                SELECT user_id FROM master_submission
                {draft_queries}
            ) as all_users
            WHERE user_id IS NOT NULL
        """

        cur.execute(combined_query)
        all_user_ids = [row[0] for row in cur.fetchall()]
        
        if not all_user_ids:
            return pd.DataFrame(columns=["id", "username"])
            
        users_query = f"""
            SELECT id, username
            FROM users
            WHERE id IN ({','.join(map(str, all_user_ids))})
            ORDER BY username
        """
        
        users_df = pd.read_sql(users_query, conn)
        return users_df
        
    except Exception as e:
        st.error(f"Error getting users with data: {e}")
        return pd.DataFrame(columns=["id", "username"])
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


def can_user_edit(master_id):
    status = get_master_status(master_id)

    if status in ["DRAFT", "REJECTED"]:
        return True

    return False


def get_total_master_submissions():
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM master_submission;")
        result = cur.fetchone()[0]
        return result
    except Exception as e:
        st.error(f"Error getting total master submissions: {e}")
        return 0
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


def get_global_status_counts():
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                SUM(CASE WHEN status = 'APPROVED' THEN 1 ELSE 0 END) AS approved,
                SUM(CASE WHEN status = 'REJECTED' THEN 1 ELSE 0 END) AS rejected,
                SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) AS pending
            FROM master_submission;
        """)
        result = cur.fetchone()
        if result:
            approved = result[0] or 0
            rejected = result[1] or 0
            pending = result[2] or 0
            return approved, rejected, pending
        return 0, 0, 0
    except Exception as e:
        st.error(f"Error getting global status counts: {e}")
        return 0, 0, 0
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


def get_monthly_submission_trend():
    conn = None
    try:
        conn = get_connection()
        query = """
            SELECT 
                TO_CHAR(created_at, 'YYYY-MM') AS month,
                SUM(CASE WHEN status = 'APPROVED' THEN 1 ELSE 0 END) AS approved,
                SUM(CASE WHEN status = 'REJECTED' THEN 1 ELSE 0 END) AS rejected,
                SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) AS pending
            FROM master_submission
            GROUP BY month
            ORDER BY month;
        """
        df = pd.read_sql(query, conn)
        return df
    except Exception as e:
        st.error(f"Error getting monthly submission trend: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            release_connection(conn)


# ================= RESTORE DRAFT =================
def restore_draft_to_session(table, columns, user_id):
    draft_data = get_user_draft(table, user_id)

    if not draft_data:
        return

    for col_info in columns:

        col = col_info["column_name"]
        dtype = col_info["data_type"]

        key = f"{table}_{col}"

        if col not in draft_data:
            continue

        value = draft_data[col]

        if value is None:
            continue

        if dtype in ("integer", "bigint", "smallint"):
            st.session_state[key] = int(value)

        elif dtype in ("numeric", "double precision", "real"):
            st.session_state[key] = float(value)

        elif dtype == "date":
            st.session_state[key] = value

        else:
            st.session_state[key] = str(value)


def get_master_status(user_id, module_name):
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        query = """
            SELECT status
            FROM master_submission
            WHERE user_id = %s
            AND module = %s
            ORDER BY created_at DESC
            LIMIT 1
        """

        cur.execute(query, (user_id, module_name))
        result = cur.fetchone()

        if result:
            return result[0]
        return None
    except Exception as e:
        st.error(f"Error getting master status: {e}")
        return None
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


def get_estimate_details(user_id):
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT estimate_number, year_of_estimate
            FROM contract_management_admin_financial_sanction
            WHERE user_id=%s
            LIMIT 1
        """,
            (user_id,),
        )

        row = cur.fetchone()

        if row:
            return {"estimate_number": row[0], "year_of_estimate": row[1]}

        return None
    except Exception as e:
        st.error(f"Error getting estimate details: {e}")
        return None
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


def delete_user_drafts(master_id, tables):
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        for table in tables:
            cur.execute(
                sql.SQL("DELETE FROM {} WHERE master_id=%s").format(sql.Identifier(table)),
                (master_id,)
            )

        conn.commit()
    except Exception as e:
        st.error(f"Error deleting user drafts: {e}")
        if conn:
            conn.rollback()
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)


def delete_draft_by_user(user_id, tables):
    """Delete in-progress drafts (is_draft=TRUE, master_id IS NULL) for a user."""
    user_id = int(user_id)
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        for table in tables:
            cur.execute(
                sql.SQL(
                    "DELETE FROM {} WHERE created_by=%s AND is_draft=TRUE AND master_id IS NULL"
                ).format(sql.Identifier(table)),
                (user_id,)
            )

        conn.commit()
    except Exception as e:
        st.error(f"Error deleting drafts by user: {e}")
        if conn:
            conn.rollback()
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)

def create_user(username, password, role="USER", allowed_modules=""):
    """
    Creates a new user. Returns (True, "Success message") or (False, "Error message").
    """
    conn = get_connection()
    cur = conn.cursor()

    try:
        # Check if username already exists (case-insensitive)
        cur.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(%s)", (username,))
        if cur.fetchone():
            return False, f"Username '{username}' already exists. Please choose a unique username."

        # Insert new user
        cur.execute(
            "INSERT INTO users (username, password_hash, role, is_active, allowed_modules) VALUES (%s, %s, %s, TRUE, %s)",
            (username, password, role, allowed_modules)
        )
        conn.commit()
        return True, f"User '{username}' created successfully!"

    except Exception as e:
        conn.rollback()
        return False, f"Database error: {str(e)}"
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
        st.error(f"Error getting all users admin: {e}")
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
        st.error(f"Error fetching user by ID: {e}")
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
        st.error(f"Error toggling user status: {e}")
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
        st.error(f"Error updating user modules: {e}")
        if conn:
            conn.rollback()
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)
