import psycopg2
import datetime
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
    # Using ThreadedConnectionPool for multi-threaded Streamlit application
    return psycopg2.pool.ThreadedConnectionPool(
        1, 50,
        host=os.getenv("DB_HOST", "localhost"),
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
def save_draft_record(table, data, user_id, master_id=None):
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


# ================= CREATE MASTER SUBMISSION =================
def create_master_submission(user_id, module, tables, status='COMPLETED', estimate_number=None, year_of_estimate=None, name_of_project=None):
    user_id = int(user_id)
    
    # Hard uniqueness check for (name_of_project, estimate_number, year_of_estimate) 
    # ONLY for contract management
    if module == "contract_management" and name_of_project and estimate_number and year_of_estimate:

        # Check if exactly this combination already exists 
        existing = get_submissions_by_estimate(estimate_number, year_of_estimate, module=module, name_of_project=name_of_project)

        if existing:
            raise ValueError(f"An application with Name: '{name_of_project}', Estimate No: '{estimate_number}' and Year: '{year_of_estimate}' already exists.")

    cycle = get_next_cycle(user_id, module)


    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

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
            cur.execute(
                f"""
                UPDATE "{table}"
                SET master_id=%s,
                    is_draft=TRUE
                WHERE created_by=%s
                AND master_id IS NULL
            """,
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
        st.error(f"Error updating master status: {e}")
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
        st.error(f"Error getting admin submissions: {e}")
        return []
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)



def get_submissions_by_estimate(est_no, est_yr, user_id=None, module=None, name_of_project=None):
    """
    Returns submissions by exact match of estimate number and financial year string.
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
            WHERE LOWER(m.estimate_number) = LOWER(%s) 
              AND m.year_of_estimate = %s
        """
        params = [est_no, est_yr]

        if name_of_project:
            query += " AND LOWER(m.name_of_project) = LOWER(%s)"
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
        # Avoid showing internal SQL error if we missed a placeholder case, but report generally
        st.error(f"Error fetching applications for this estimate ({module or 'global'}): {e}")
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


# ================= GET FULL DRAFT DATA =================
def get_full_draft_data(user_id, module_tables):
    """
    Fetches all records with is_draft=TRUE for a specific user across a set of tables.
    Returns a dict of {table_name: DataFrame}
    """
    conn = None
    full_data = {}
    try:
        conn = get_connection()
        for table in module_tables:
            df = pd.read_sql(
                f"""
                SELECT *
                FROM "{table}"
                WHERE created_by=%s AND is_draft=TRUE
            """,
                conn,
                params=[user_id],
            )

            if not df.empty:
                full_data[table] = df

    except Exception as e:
        st.error(f"Error getting full draft data: {e}")
    finally:
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
        
        # Use UNION ALL to check all 100+ tables efficiently
        checks = []
        for table in tables:
            if master_id:
                checks.append(f"""
                    SELECT '{table}' WHERE EXISTS (
                        SELECT 1 FROM "{table}" WHERE created_by=%s AND master_id=%s
                    )
                """)
            else:
                checks.append(f"""
                    SELECT '{table}' WHERE EXISTS (
                        SELECT 1 FROM "{table}" WHERE created_by=%s AND master_id IS NULL
                    )
                """)
        
        if checks:
            combined = " UNION ALL ".join(checks)
            params = []
            for _ in tables:
                if master_id:
                    params.extend([user_id, master_id])
                else:
                    params.append(user_id)
            
            cur.execute(combined, params)
            rows = cur.fetchall()
            completed = len(rows)

    except Exception as e:
        raise e
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
            cur.execute(
                f'UPDATE "{table}" SET is_draft=FALSE WHERE master_id=%s',
                (master_id,)
            )
        conn.commit()
    except Exception as e:
        st.error(f"Error finalizing drafts: {e}")
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

    # Calculate incomplete by subtracting completed from total
    percentage, completed_count, total_count = get_user_progress(user_id, tables, master_id=master_id)
    
    # Actually, to get EXACT table names that are incomplete, we need the inverse of the UNION ALL
    conn = None
    cur = None
    incomplete = []
    
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # Get list of completed tables first
        checks = []
        for table in tables:
            if master_id:
                checks.append(f"SELECT '{table}' WHERE EXISTS (SELECT 1 FROM \"{table}\" WHERE created_by=%s AND master_id=%s)")
            else:
                checks.append(f"SELECT '{table}' WHERE EXISTS (SELECT 1 FROM \"{table}\" WHERE created_by=%s AND is_draft=TRUE)")
        
        if checks:
            combined = " UNION ALL ".join(checks)
            params = []
            for _ in tables:
                if master_id:
                    params.extend([user_id, master_id])
                else:
                    params.append(user_id)
                    
            cur.execute(combined, params)
            completed_tables = [row[0] for row in cur.fetchall()]
            incomplete = [t for t in tables if t not in completed_tables]
            
    except Exception as e:
        st.error(f"Error getting incomplete forms: {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)
            
    return incomplete

    return incomplete


def get_user_draft_summaries(user_id, all_modules):
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
        
        # Filter out empty drafts (those with zero progress)
        final_records = []
        for rec in records:
            m_id = rec["id"]
            m_key = rec.get("module")
            if m_key and m_key in all_modules:
                m_tables = all_modules[m_key]
                _, completed, _ = get_user_progress(user_id, m_tables, master_id=m_id)
                if completed > 0:
                    final_records.append(rec)
            else:
                # If module info is missing, we keep it to be safe or skip?
                # For now, let's keep it if we can't verify it's empty.
                final_records.append(rec)
        
        return final_records
    except Exception as e:
        st.error(f"Error getting draft summaries: {e}")
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
    approved = rejected = pending = drafts = 0

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
            draft_list = get_user_draft_summaries(user_id, all_modules)
            drafts = len(draft_list)

    except Exception as e:
        st.error(f"Error getting master status counts: {e}")
    finally:
        if conn:
            release_connection(conn)

    # Return only submitted and drafts
    return submitted, drafts


# ================= EXPORT MASTER PDF =================
def delete_unattached_drafts(user_id, tables):
    """Deletes any records where master_id is NULL for the given user (un-saved lazy drafts)."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        for table in tables:
            # We only delete if master_id is NULL (unattached)
            cur.execute(f'DELETE FROM "{table}" WHERE created_by = %s AND master_id IS NULL', (user_id,))
        conn.commit()
    except Exception as e:
        print(f"Error deleting unattached drafts: {e}")
    finally:
        if 'conn' in locals() and conn:
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

            df = pd.read_sql(
                f'SELECT * FROM "{table}" WHERE master_id=%s', conn, params=[master_id]
            )

            if df.empty:
                continue

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


def get_user_draft(table, user_id, master_id=None):
    conn = None
    cur = None
    try:
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
        st.error(f"Error getting user draft: {e}")
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
        st.error(f"Error getting master status: {e}")
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
