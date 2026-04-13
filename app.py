from auth import login
from crud import (
    can_user_edit,
    create_master_submission,
    create_user,
    delete_unattached_drafts,
    export_master_submission_pdf,
    get_all_tables,
    get_all_users_admin,
    get_full_draft_data,
    get_full_submission_data,
    get_incomplete_forms,
    get_master_submission,
    get_submissions_by_estimate,
    get_table_columns,
    get_project_dpr,
    get_user_by_id,
    get_user_draft,
    get_user_draft_summaries,
    get_user_master_status_counts,
    get_user_master_submissions,
    get_user_master_submissions_admin,
    get_user_progress,
    save_draft_record,
    ensure_project_dpr_table,
    set_drafts_to_final,
    toggle_user_status,
    upsert_project_dpr,
    update_master_attachments,
    update_master_status,
    update_master_submission,
    update_user_modules,
)
from streamlit_cookies_manager.encrypted_cookie_manager import EncryptedCookieManager
import datetime
import base64
import html
import json
import os
from urllib.parse import quote
import streamlit as st

from error_utils import log_exception, report_error

st.set_page_config(
    page_title="CAG Audit Management System",
    page_icon="A",
    layout="wide",
)


# =====================================================
# ================= LOGO LOADING ======================
# =====================================================
_base_dir = os.path.dirname(os.path.abspath(__file__))
_logo_path = os.path.join(_base_dir, "logo.png")
if os.path.exists(_logo_path):
    with open(_logo_path, "rb") as _f:
        _logo_b64 = base64.b64encode(_f.read()).decode()
    LOGO_IMG   = f'<img src="data:image/png;base64,{_logo_b64}" style="width:110px;height:110px;object-fit:contain;">'
    LOGO_SMALL = f'<img src="data:image/png;base64,{_logo_b64}" style="width:36px;height:36px;object-fit:contain;vertical-align:middle;">'
else:
    LOGO_IMG   = "[LOGO]"
    LOGO_SMALL = "[LOGO]"


# =====================================================
# ================= COOKIES / CONFIG ==================
# =====================================================
def _get_runtime_secret(name):
    value = os.getenv(name)
    if value not in (None, ""):
        return value
    try:
        secret_value = st.secrets.get(name)
    except Exception:
        secret_value = None
    if secret_value not in (None, ""):
        return str(secret_value)
    return None


cookie_password = _get_runtime_secret("COOKIE_PASSWORD") or _get_runtime_secret("COOKIE_SECRET")
if not cookie_password or len(cookie_password) < 16:
    st.error("Missing secure cookie secret. Set COOKIE_PASSWORD (minimum 16 chars).")
    st.stop()

cookies = EncryptedCookieManager(
    prefix="canal_app",
    password=cookie_password,
)
if not cookies.ready():
    st.stop()

money_keywords = ["expenditure", "amount", "cost", "payment", "value", "budget"]

# =====================================================
# ====  URL QUERY PARAM HANDLER (global, top) =========
# =====================================================
try:
    if "status_filter" in st.query_params:
        target = st.query_params["status_filter"]
        st.session_state.status_filter = target
        st.session_state.admin_review_page = 1
        st.query_params.clear()
        st.rerun()
    elif "user_status_filter" in st.query_params:
        target = st.query_params["user_status_filter"]
        st.session_state.user_status_filter = target
        st.session_state.dashboard_page = 1
        st.query_params.clear()
        st.rerun()
    elif "mini_filter" in st.query_params:
        target = st.query_params["mini_filter"]
        if isinstance(target, list):
            target = target[0] if target else "DPR"
        st.session_state.mini_dashboard_filter = str(target or "DPR").upper()
        st.session_state.dashboard_projects_page = 1
        st.query_params.clear()
        st.rerun()
except Exception as e:
    log_exception("app.query_param_handler", e)

# Hidden developer info
st.markdown("""
<div id="dev-info" style="display:none;" data-developer="Latief" data-contact="+91-8951352811"
     data-system="Audit Management System" data-built-for="CAG India" aria-hidden="true"></div>
""", unsafe_allow_html=True)


# =====================================================
# ================= CSS LOADING =======================
# =====================================================
def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name, encoding='utf-8') as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

load_css('style.css')


# =====================================================
# ================= FOOTER ============================
# =====================================================
def render_footer():
    st.markdown("""
    <div class="cag-footer">
        <div>
            <div class="cag-footer-left-title">Comptroller &amp; Auditor General of India</div>
            <div class="cag-footer-left-sub">
                Irrigation Audit Wing &nbsp;-&nbsp; Uttar Pradesh &nbsp;-&nbsp; Secure Government Portal
            </div>
        </div>
        <div>
            <div class="cag-footer-right-slogan">SATYAMEVA JAYATE</div>
            <div class="cag-footer-right-sub">Developed by DAC Cell - Latief</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# =====================================================
# ================= SESSION STATE =====================
# =====================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = cookies.get("logged_in") == "1"
if "user_id" not in st.session_state:
    st.session_state.user_id = cookies.get("user_id")
if "username" not in st.session_state:
    st.session_state.username = cookies.get("username")
if "role" not in st.session_state:
    st.session_state.role = cookies.get("role")
if "allowed_modules" not in st.session_state:
    st.session_state.allowed_modules = cookies.get("allowed_modules", "")
if "logging_out" not in st.session_state:
    st.session_state.logging_out = False
if "current_view" not in st.session_state:
    st.session_state.current_view = "Main"
if "master_id" not in st.session_state:
    st.session_state.master_id = None
if "flow_page" not in st.session_state:
    st.session_state.flow_page = None
if "flow_data" not in st.session_state:
    st.session_state.flow_data = {}
if "flow_history" not in st.session_state:
    st.session_state.flow_history = []
if "module_return_flow_page" not in st.session_state:
    st.session_state.module_return_flow_page = None
if "module_return_flow_data" not in st.session_state:
    st.session_state.module_return_flow_data = {}
if "module_return_flow_history" not in st.session_state:
    st.session_state.module_return_flow_history = []
if "project_dpr_table_ready" not in st.session_state:
    st.session_state.project_dpr_table_ready = ensure_project_dpr_table()
if "mini_dashboard_filter" not in st.session_state:
    st.session_state.mini_dashboard_filter = "DPR"

# --- Live Permission Sync ---
if st.session_state.get("logged_in") and st.session_state.get("user_id"):
    try:
        current_user_info = get_user_by_id(st.session_state.user_id)
        if current_user_info:
            if current_user_info.get("is_active") is False:
                cookies["logged_in"] = "0"
                cookies["user_id"] = ""
                cookies.save()
                st.session_state.logged_in = False
                st.session_state.user_id = None
                st.session_state.username = None
                st.session_state.role = None
                st.session_state.allowed_modules = ""
                st.error("Your permission has been revoked. You have been logged out.")
                st.rerun()
            changed = False
            if st.session_state.role != current_user_info["role"]:
                st.session_state.role = current_user_info["role"]
                cookies["role"] = st.session_state.role
                changed = True
            new_allowed = current_user_info["allowed_modules"] or ""
            if st.session_state.allowed_modules != new_allowed:
                st.session_state.allowed_modules = new_allowed
                cookies["allowed_modules"] = st.session_state.allowed_modules
                changed = True
            if changed:
                cookies.save()
        else:
            cookies["logged_in"] = "0"
            cookies.save()
            st.session_state.logged_in = False
            st.session_state.user_id = None
            st.rerun()
    except Exception as e:
        log_exception("app.live_permission_sync", e)


# =====================================================
# ================= LOGIN PAGE ========================
# =====================================================
if not st.session_state.logged_in or not st.session_state.user_id:
    # Decrease the global top gap specifically for the login page
    st.markdown("<style>.block-container { padding-top: 20px !important; }</style>", unsafe_allow_html=True)

    _, col, _ = st.columns([1, 1.3, 1])
    with col:
        # Ashoka Chakra SVG + branding
        st.markdown(f"""
        <div class="login-container">
            <div class="login-logo">{LOGO_IMG}</div>
            <div style="font-size:11px; font-weight:700; color:#9ca3af; letter-spacing:1.2px;
                        text-transform:uppercase; margin-bottom:10px;">
                Government of India
            </div>
            <div class="login-title">Audit Management System</div>
            <div class="login-subtitle">Comptroller &amp; Auditor General of India</div>
            <div style="width:48px; height:3px; background:linear-gradient(90deg,#FF9933 33%,#fff 33% 66%,#138808 66%);
                        margin:14px auto 0; border-radius:2px;"></div>
        </div>
        """, unsafe_allow_html=True)

        with st.container():
            st.markdown(
                "<p style='font-size:13px; font-weight:700; color:#374151; "
                "text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px;'>"
                "Officer Sign In</p>",
                unsafe_allow_html=True
            )
            u = st.text_input("Username", placeholder="Enter your username")
            p = st.text_input("Password", type="password", placeholder="Enter your password")
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

            if st.button("Sign In", use_container_width=True, type="primary"):
                if not u or not p:
                    st.error("Please enter both username and password.")
                else:
                    user, error_msg = login(u, p)
                    if user:
                        st.session_state.logged_in = True
                        st.session_state.user_id = user["id"]
                        st.session_state.username = user["username"]
                        st.session_state.role = user["role"]
                        st.session_state.allowed_modules = user["allowed_modules"] or ""
                        cookies["logged_in"] = "1"
                        cookies["user_id"] = str(user["id"])
                        cookies["username"] = user["username"]
                        cookies["role"] = user["role"]
                        cookies["allowed_modules"] = user["allowed_modules"] or ""
                        cookies.save()
                        st.rerun()
                    else:
                        if error_msg == "REVOKED":
                            st.error("Your permission has been revoked. Please contact Administrator.")
                        else:
                            st.error("Incorrect username or password. Please try again.")

        st.session_state.logging_out = False

    st.markdown("""
    <div style="text-align:center; margin-top:24px; color:#9ca3af; font-size:12px;">
        Having trouble signing in? Contact your system administrator.
    </div>
    """, unsafe_allow_html=True)
    st.stop()


# =====================================================
# ================= USER INFO =========================
# =====================================================
user_id   = st.session_state.get("user_id")
is_admin  = st.session_state.role == "admin"
role_label = "Administrator" if is_admin else "Engineer"
active_flow_page = st.session_state.get("flow_page")
active_flow_data = st.session_state.get("flow_data", {}) or {}
show_create_estimate_link = (
    (not is_admin)
    and (
        active_flow_page in ("project_detail", "create_dpr", "create_estimate", "dpr_view")
        or bool((st.session_state.get("current_project_name") or "").strip())
    )
    and (
        bool((active_flow_data.get("project_name") or "").strip())
        or bool((st.session_state.get("current_project_name") or "").strip())
    )
)
nav_links_html = (
    '<a href="./?nav=Main" target="_self" class="nav-item-minimal">Dashboard</a>'
    '<a href="./?nav=NewApp" target="_self" class="nav-item-minimal">Start New Project</a>'
)
active_project_for_link = (active_flow_data.get("project_name") or "").strip()
if not active_project_for_link:
    active_project_for_link = (st.session_state.get("current_project_name") or "").strip()
if show_create_estimate_link:
    create_estimate_href = "./?nav=CreateEstimate"
    if active_project_for_link:
        create_estimate_href += f"&project={quote(active_project_for_link)}"
    nav_links_html += f'<a href="{create_estimate_href}" target="_self" class="nav-item-minimal">Create Estimate</a>'

# =====================================================
# ================= TOP NAVIGATION BAR ================
# =====================================================
username_value = st.session_state.get("username") or "User"
username_initial = username_value[0].upper() if username_value else "U"

nav_html = f"""
<div id="sticky-header-container">
    <div class="nav-brand">
        {LOGO_SMALL}
        <div style="margin-left:2px;">
            <div style="font-size:15px; font-weight:700; color:#fff; letter-spacing:0.2px;">
                Audit Management System
            </div>
            <div class="nav-brand-sub">Comptroller &amp; Auditor General of India</div>
        </div>
    </div>
    <div class="nav-links-left">{nav_links_html}</div>
    <div class="nav-right-actions">
        <span style="font-size:11px; color:rgba(255,255,255,0.45); letter-spacing:0.3px;">
            {html.escape(str(role_label))}
        </span>
        <a href="./?nav=Logout" target="_self" class="logout-link">Sign Out</a>
        <div class="user-pill">
            <div class="avatar-mini">
                {html.escape(str(username_initial))}
            </div>
            <div style="font-size:13px; font-weight:600; color:#fff;">
                {html.escape(str(username_value))}
            </div>
        </div>
    </div>
</div>
"""
st.markdown(nav_html, unsafe_allow_html=True)


# =====================================================
# ================= HELPER: MODULE STATE ==============
# =====================================================
def clear_module_state(m_key=None):
    for key in list(st.session_state.keys()):
        if "_initialized" in key or "display_" in key:
            del st.session_state[key]
    for k in ["initial_estimate_number", "initial_year_of_estimate", "initial_name_of_project"]:
        if k in st.session_state:
            del st.session_state[k]
    if m_key:
        m_tables = all_modules.get(m_key, [])
        uid = st.session_state.get("user_id")
        delete_unattached_drafts(uid, m_tables)
        for table in m_tables:
            for key in list(st.session_state.keys()):
                if key.startswith(f"{table}_"):
                    del st.session_state[key]


# =====================================================
# ================= HELPER FUNCTIONS ==================
# =====================================================
def fmt_dt(value):
    if not value:
        return "-"
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return "-"
        try:
            value = datetime.datetime.fromisoformat(value)
        except ValueError:
            return value[:16]
    if isinstance(value, datetime.datetime):
        return value.strftime("%d %b %Y, %I:%M %p")
    if isinstance(value, datetime.date):
        return value.strftime("%d %b %Y")
    return str(value)[:16]


def esc_html(value):
    return html.escape("" if value is None else str(value))


def _safe_key(value):
    return "".join(ch if ch.isalnum() else "_" for ch in str(value))


def open_flow_page(page_name, data=None, push_history=True):
    current_page = st.session_state.get("flow_page")
    current_data = st.session_state.get("flow_data", {})
    if push_history and current_page:
        history = st.session_state.setdefault("flow_history", [])
        history.append({"page": current_page, "data": current_data})
    elif current_page and current_page != page_name:
        # Preserve one-step back navigation even for lightweight transitions.
        history = st.session_state.setdefault("flow_history", [])
        if not history or history[-1].get("page") != current_page:
            history.append({"page": current_page, "data": current_data})
    st.session_state.flow_page = page_name
    st.session_state.flow_data = data or {}


def back_flow_page():
    history = st.session_state.get("flow_history", [])
    if history:
        previous = history.pop()
        st.session_state.flow_history = history
        st.session_state.flow_page = previous.get("page")
        st.session_state.flow_data = previous.get("data", {})
        return
    st.session_state.pop("flow_page", None)
    st.session_state.pop("flow_data", None)
    st.session_state.pop("show_up_id", None)


def close_flow_page():
    st.session_state.pop("flow_page", None)
    st.session_state.pop("flow_data", None)
    st.session_state.pop("flow_history", None)
    st.session_state.pop("show_up_id", None)


def clear_module_return_flow():
    st.session_state.pop("module_return_flow_page", None)
    st.session_state.pop("module_return_flow_data", None)
    st.session_state.pop("module_return_flow_history", None)


def remember_flow_return_for_module():
    current_page = st.session_state.get("flow_page")
    if current_page:
        st.session_state.module_return_flow_page = current_page
        st.session_state.module_return_flow_data = dict(st.session_state.get("flow_data", {}))
        st.session_state.module_return_flow_history = list(st.session_state.get("flow_history", []))
    else:
        clear_module_return_flow()


def restore_module_return_flow():
    return_page = st.session_state.get("module_return_flow_page")
    if not return_page:
        return False
    st.session_state.flow_page = return_page
    st.session_state.flow_data = st.session_state.get("module_return_flow_data", {})
    st.session_state.flow_history = list(st.session_state.get("module_return_flow_history", []))
    clear_module_return_flow()
    return True


def render_flow_header(title, back_key):
    c1, c2 = st.columns([1, 6])
    with c1:
        if st.button("← Back", key=back_key, type="tertiary", width="content"):
            st.session_state.pop("show_up_id", None)
            back_flow_page()
            st.rerun()
    with c2:
        st.markdown(f"### {title}")


def normalize_year_option(raw_value):
    if raw_value is None:
        return None
    if hasattr(raw_value, "year"):
        raw_value = raw_value.year
    y_str = str(raw_value).strip()
    if not y_str:
        return None
    if "-" in y_str:
        return y_str
    try:
        y_int = int(y_str[:4])
        return f"{y_int}-{str(y_int + 1)[2:]}"
    except (TypeError, ValueError):
        return y_str


def is_date_picker_field(column_name, data_type):
    col = (column_name or "").strip().lower()
    dtype = (data_type or "").strip().lower()

    if col in {"created_at", "updated_at"}:
        return False

    # Keep existing year-of-estimate behavior unchanged.
    if col == "year_of_estimate":
        return False

    if dtype == "date":
        return True

    parts = col.split("_")
    if "date" in parts:
        return True
    if col.startswith("date_") or col.endswith("_date") or "_date_" in col:
        return True
    return False


def parse_date_for_input(value):
    if value in (None, ""):
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value

    text = str(value).strip()
    if not text:
        return None

    try:
        return datetime.date.fromisoformat(text[:10])
    except (TypeError, ValueError):
        pass

    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except (TypeError, ValueError):
            continue
    return None


def normalize_date_for_storage(value):
    if value in (None, ""):
        return None
    if isinstance(value, datetime.datetime):
        return value.date().isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()

    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.date.fromisoformat(text[:10]).isoformat()
    except (TypeError, ValueError):
        return text


def serialize_date_fields_as_text(form_data, columns):
    if not isinstance(form_data, dict):
        return form_data
    for col_info in columns:
        col_name = col_info.get("column_name")
        data_type = col_info.get("data_type")
        if col_name in form_data and is_date_picker_field(col_name, data_type):
            form_data[col_name] = normalize_date_for_storage(form_data.get(col_name))
    return form_data


def render_submission_details_page(sub):
    sub_id = _safe_key(sub.get("id", "unknown")) if sub else "unknown"
    render_flow_header("Submission Details", back_key=f"back_sub_top_{sub_id}")

    if not sub:
        st.warning("No submission details found.")
        return

    module_key = sub.get("module") or ""
    module_label = module_key.replace("_", " ").title()
    module_label_safe = esc_html(module_label)
    status = sub["status"]
    is_synthetic_draft = str(sub.get("id", "")).startswith("draft_")

    created_at = sub.get("created_at", "")
    created_by_user = sub.get("created_by_user") or "Unknown"
    created_by_user_safe = esc_html(created_by_user)
    created_at_safe = esc_html(fmt_dt(created_at))

    status_color = "#d97706" if status == "DRAFT" else "#059669"

    if module_key == "contract_management":
        est_no = sub.get("estimate_number") or "---"
        est_yr = sub.get("year_of_estimate") or "---"
        y_val = est_yr.year if hasattr(est_yr, "year") else est_yr
        display_key = f"{est_no} ({y_val})" if est_no != "---" else "---"
        est_html = (
            f'<div style="font-size:12px; font-weight:600; color:#374151; margin-bottom:4px;">'
            f'Estimate: {esc_html(display_key)}</div>'
        )
    else:
        est_html = ""

    st.markdown(
        f"""
    <div style="padding:14px 18px; border-radius:8px; background:#f8f9fc; margin-bottom:18px;
                border-left:4px solid {status_color}; border:1px solid #e5e8ef;
                border-left:4px solid {status_color};">
        <div style="font-weight:700; font-size:14px; color:#1a3a6b; margin-bottom:4px;">{module_label_safe}</div>
        {est_html}
        <div style="font-size:12px; color:#6b7280; margin-bottom:2px;">
            <b>{"Submitted By" if status != "DRAFT" else "Created By"}:</b> {created_by_user_safe}
        </div>
        <div style="font-size:12px; color:#6b7280;">
            <b>{"Submitted on" if status != "DRAFT" else "Last Updated"}:</b> {created_at_safe}
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    if is_synthetic_draft:
        uid = sub.get("user_id")
        module_tables = all_modules.get(module_key, [])
        full_data = get_full_draft_data(uid, module_tables)
    else:
        full_data = get_full_submission_data(sub["id"])

    if not full_data:
        st.info("No data entries found yet for this draft.")

    for section_name, df_section in full_data.items():
        clean_name = section_name.replace(module_key + "_", "").replace("_", " ").title()
        st.markdown(f"#### {clean_name}")
        st.dataframe(df_section, use_container_width=True)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    est_path = sub.get("estimate_attachment")
    sar_path = sub.get("sar_attachment")
    if est_path or sar_path:
        st.markdown("#### Attached Documents")
        col_at1, col_at2 = st.columns(2)
        if est_path and os.path.exists(est_path):
            with col_at1:
                with open(est_path, "rb") as f:
                    st.download_button(
                        "Download Estimate",
                        data=f,
                        file_name=os.path.basename(est_path),
                        key=f"dl_est_{sub['id']}",
                        use_container_width=True,
                    )
        if sar_path and os.path.exists(sar_path):
            with col_at2:
                with open(sar_path, "rb") as f:
                    st.download_button(
                        "Download SAR",
                        data=f,
                        file_name=os.path.basename(sar_path),
                        key=f"dl_sar_{sub['id']}",
                        use_container_width=True,
                    )

    st.markdown("---")

    if not is_synthetic_draft and status != "DRAFT":
        pdf = export_master_submission_pdf(sub["id"])
        st.download_button(
            "Download PDF Record",
            pdf,
            file_name=f"submission_{sub['id']}.pdf",
            mime="application/pdf",
            key=f"dlg_pdf_{sub['id']}",
            use_container_width=True,
            type="primary",
        )

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    if st.button("<- Back", key=f"back_sub_bottom_{sub_id}", use_container_width=True):
        back_flow_page()
        st.rerun()


def render_estimate_group_page(est_no, est_yr, user_id=None, module=None):
    if est_no is None and est_yr is None:
        render_flow_header("Estimate Applications", back_key="back_est_missing")
        st.warning("No estimate selected.")
        return

    y_val = est_yr.year if hasattr(est_yr, "year") else est_yr
    safe_est = _safe_key(est_no)
    render_flow_header(
        f"Contract for Estimate: {est_no} ({y_val})",
        back_key=f"back_est_group_top_{safe_est}",
    )

    is_admin_user = st.session_state.get("role") == "admin"

    if not is_admin_user:
        start_contract_href = (
            f'./?contract_action=start_new&est_no={quote(str(est_no))}&est_yr={quote(str(est_yr))}'
        )
        st.markdown(
            (
                f'<div style="text-align:center; margin:2px 0 10px 0;">'
                f'<a href="{start_contract_href}" target="_self" class="dashboard-project-link" '
                f'style="font-weight:800; font-size:15px;">Start New Contract for this Estimate</a>'
                f'</div>'
            ),
            unsafe_allow_html=True,
        )

    st.markdown("<hr style='margin:8px 0;'>", unsafe_allow_html=True)

    submissions = get_submissions_by_estimate(est_no, est_yr, user_id=user_id, module=module)
    if submissions:
        submissions.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)

    if not submissions:
        st.info("No applications found for this estimate.")
    else:
        h1, h_id, h2, h3, h4, r_spacer, h6 = st.columns([0.6, 0.7, 1.6, 1.4, 1.4, 0.4, 1.8])
        h1.markdown("**S.No**"); h_id.markdown("**ID**"); h2.markdown("**User**")
        h3.markdown("**Date**"); h4.markdown("**Status**"); h6.markdown("**Action**")
        st.markdown("<hr style='margin:0 0 8px 0;'>", unsafe_allow_html=True)

        for i, s in enumerate(submissions, 1):
            r1, r_id, r2, r3, r4, r_spacer2, r6 = st.columns([0.6, 0.7, 1.6, 1.4, 1.4, 0.4, 1.8])
            status = s.get("status", "DRAFT")
            status_bg = "#fffbeb" if status == "DRAFT" else "#ecfdf5"
            status_text_c = "#92400e" if status == "DRAFT" else "#065f46"
            status_bdr = "#fcd34d" if status == "DRAFT" else "#a7f3d0"
            row_id = _safe_key(s.get("id"))

            with r1:
                st.write(f"**{i}**")
            with r_id:
                st.code(f"{s['id']}")
            with r2:
                st.write(s.get("created_by_user", "Unknown"))
            with r3:
                st.write(fmt_dt(s.get("created_at")))
            with r4:
                st.markdown(
                    f'<span style="background:{status_bg}; color:{status_text_c}; '
                    f'border:1px solid {status_bdr}; padding:2px 10px; border-radius:4px; '
                    f'font-size:11px; font-weight:700;">{status}</span>',
                    unsafe_allow_html=True,
                )
                if status == "COMPLETED":
                    cnt = sum([
                        1 if (s.get("estimate_attachment") or "").strip() else 0,
                        1 if (s.get("sar_attachment") or "").strip() else 0,
                    ])
                    if cnt == 0:
                        st.markdown(
                            "<div style='margin-top:4px;font-size:11px;font-weight:600;color:#dc2626;'>Missing Files</div>",
                            unsafe_allow_html=True,
                        )
                    elif cnt == 1:
                        st.markdown(
                            "<div style='margin-top:4px;font-size:11px;font-weight:600;color:#d97706;'>1/2 Uploaded</div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            "<div style='margin-top:4px;font-size:11px;font-weight:600;color:#059669;'>Both Uploaded</div>",
                            unsafe_allow_html=True,
                        )

            with r6:
                if status == "DRAFT" and not is_admin_user:
                    resume_href = (
                        f'./?contract_action=resume&sub_id={s["id"]}'
                        f'&est_no={quote(str(est_no))}&est_yr={quote(str(est_yr))}'
                    )
                    st.markdown(
                        f'<a href="{resume_href}" target="_self" class="dashboard-project-link">Resume</a>',
                        unsafe_allow_html=True,
                    )
                else:
                    view_href = (
                        f'./?contract_action=view&sub_id={s["id"]}'
                        f'&est_no={quote(str(est_no))}&est_yr={quote(str(est_yr))}'
                    )
                    action_links = [
                        f'<a href="{view_href}" target="_self" class="dashboard-project-link">View</a>'
                    ]
                    if status == "COMPLETED":
                        upload_href = (
                            f'./?contract_action=upload&sub_id={s["id"]}'
                            f'&est_no={quote(str(est_no))}&est_yr={quote(str(est_yr))}'
                        )
                        action_links.append(
                            f'<a href="{upload_href}" target="_self" class="dashboard-project-link">Upload</a>'
                        )
                    st.markdown(
                        f'<div class="inline-link-actions">{" | ".join(action_links)}</div>',
                        unsafe_allow_html=True,
                    )

            st.markdown(
                "<hr style='margin:8px 0; border:0; border-top:1px solid #f3f4f6;'>",
                unsafe_allow_html=True,
            )

        if st.session_state.get("show_up_id"):
            up_id = st.session_state.show_up_id
            st.markdown("---")
            st.markdown(f"#### Upload Documents for ID: `{up_id}`")
            m_info = get_master_submission(up_id)
            f_data = get_full_submission_data(up_id)
            m_key = m_info.get("module")
            m_tables = all_modules.get(m_key, [])
            first_t = m_tables[0] if m_tables else None
            sub_d = f_data.get(first_t)

            def clean_n(s):
                return "".join([c if c.isalnum() or c in ("-", "_") else "_" for c in str(s)])

            if sub_d is not None and not sub_d.empty:
                t_row = sub_d.iloc[0]
                e_no = clean_n(t_row.get("estimate_number", m_info.get("estimate_number", "NA")))
                p_nm = clean_n(t_row.get("name_of_project", m_info.get("name_of_project", "NA")))
                e_yr = clean_n(t_row.get("year_of_estimate", m_info.get("year_of_estimate", "NA")))
            else:
                e_no = clean_n(m_info.get("estimate_number", "NA"))
                p_nm = clean_n(m_info.get("name_of_project", "NA"))
                e_yr = clean_n(m_info.get("year_of_estimate", "NA"))

            c1, c2 = st.columns(2)
            with c1:
                curr_est = m_info.get("estimate_attachment")
                if curr_est and os.path.exists(curr_est):
                    st.success(f"Estimate on record: `{os.path.basename(curr_est)}`")
                est_f = st.file_uploader(
                    "Upload / Replace Estimate",
                    type=["pdf", "docx", "xlsx", "jpg", "png"],
                    key=f"dlg_up_est_{up_id}",
                )
                if est_f:
                    fid = f"{est_f.name}_{est_f.size}"
                    if st.session_state.get(f"last_up_est_{up_id}") != fid:
                        ext = os.path.splitext(est_f.name)[1]
                        spath = os.path.join("uploads", f"Estimate_{e_no}_{p_nm}_{e_yr}{ext}")
                        with open(spath, "wb") as f:
                            f.write(est_f.getbuffer())
                        update_master_attachments(up_id, estimate_path=spath)
                        st.session_state[f"last_up_est_{up_id}"] = fid
                        st.success("Estimate uploaded successfully!")
                        st.rerun()
            with c2:
                curr_sar = m_info.get("sar_attachment")
                if curr_sar and os.path.exists(curr_sar):
                    st.success(f"SAR on record: `{os.path.basename(curr_sar)}`")
                sar_f = st.file_uploader(
                    "Upload / Replace SAR",
                    type=["pdf", "docx", "xlsx", "jpg", "png"],
                    key=f"dlg_up_sar_{up_id}",
                )
                if sar_f:
                    fid = f"{sar_f.name}_{sar_f.size}"
                    if st.session_state.get(f"last_up_sar_{up_id}") != fid:
                        ext = os.path.splitext(sar_f.name)[1]
                        spath = os.path.join("uploads", f"SAR_{e_no}_{p_nm}_{e_yr}{ext}")
                        with open(spath, "wb") as f:
                            f.write(sar_f.getbuffer())
                        update_master_attachments(up_id, sar_path=spath)
                        st.session_state[f"last_up_sar_{up_id}"] = fid
                        st.success("SAR uploaded successfully!")
                        st.rerun()
            if st.button("Close Upload Panel", key=f"close_dlg_up_{safe_est}"):
                del st.session_state.show_up_id
                st.rerun()


def render_duplicate_submission_page(data=None):
    payload = data or {}
    if payload and "data" in payload:
        payload = payload["data"]

    render_flow_header("Application Already Exists", back_key="back_duplicate_top")

    if not payload:
        st.warning("No application data found.")
        return

    m_key = payload["module"]
    est_no = payload["est_no"]
    est_yr = payload["est_yr"]
    sub = payload["sub"]
    status = sub["status"]
    yr_val = getattr(est_yr, "year", est_yr)

    st.markdown(f"An application for **{est_no}** ({yr_val}) already exists.")
    if status == "DRAFT":
        st.warning("Existing draft found with same Estimate Number and Year.")
        if st.button("Resume Existing Draft", type="primary", use_container_width=True):
            clear_module_state(m_key)
            st.session_state.master_id = sub["id"]
            st.session_state.current_view = m_key
            remember_flow_return_for_module()
            close_flow_page()
            st.rerun()
    else:
        st.error("Submission already completed. This estimate cannot be modified or duplicated.")

    if st.button("<- Back to Start", key="back_duplicate_bottom", use_container_width=True):
        back_flow_page()
        st.rerun()


def build_contract_project_catalog(prefill_project=None):
    created_projects_key = "created_projects_store"
    if created_projects_key not in st.session_state:
        st.session_state[created_projects_key] = []

    project_catalog = {}
    estimate_sets = {}

    for item in st.session_state.get(created_projects_key, []):
        pname = (item.get("project_name") or "").strip()
        if not pname:
            continue
        pkey = pname.lower()
        project_catalog[pkey] = {
            "project_name": pname,
            "created_at": item.get("created_at") or datetime.datetime.now().isoformat(),
            "estimate_count": int(item.get("estimate_count") or 0),
        }
        estimate_sets[pkey] = set()

    completed_projects = get_user_master_submissions(user_id, module="contract_management")
    draft_projects = [d for d in get_user_draft_summaries(user_id) if d.get("module") == "contract_management"]

    for rec in completed_projects + draft_projects:
        pname = (rec.get("name_of_project") or "").strip()
        if not pname:
            continue

        pkey = pname.lower()
        rec_created = rec.get("created_at") or datetime.datetime.now().isoformat()
        if pkey not in project_catalog:
            project_catalog[pkey] = {
                "project_name": pname,
                "created_at": rec_created,
                "estimate_count": 0,
            }
            estimate_sets[pkey] = set()
        elif str(rec_created) > str(project_catalog[pkey].get("created_at") or ""):
            project_catalog[pkey]["created_at"] = rec_created

        est_no = (rec.get("estimate_number") or "").strip()
        est_yr = rec.get("year_of_estimate")
        if est_no and est_yr:
            y_val = est_yr.year if hasattr(est_yr, "year") else est_yr
            estimate_sets[pkey].add((est_no.lower(), str(y_val)))

    if prefill_project:
        pkey = prefill_project.lower()
        if pkey not in project_catalog:
            project_catalog[pkey] = {
                "project_name": prefill_project,
                "created_at": datetime.datetime.now().isoformat(),
                "estimate_count": 0,
            }
            estimate_sets[pkey] = set()

    merged_projects = []
    for pkey, pdata in project_catalog.items():
        pdata["estimate_count"] = len(estimate_sets.get(pkey, set()))
        merged_projects.append(pdata)

    merged_projects.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
    st.session_state[created_projects_key] = merged_projects
    return merged_projects


def get_project_estimate_groups(project_name):
    project_key = " ".join((project_name or "").split()).lower()
    if not project_key:
        return []

    completed = get_user_master_submissions(user_id, module="contract_management")
    drafts = [d for d in get_user_draft_summaries(user_id) if d.get("module") == "contract_management"]

    grouped = {}
    for rec in completed + drafts:
        pname = " ".join((rec.get("name_of_project") or "").split()).lower()
        if pname != project_key:
            continue

        est_no = (rec.get("estimate_number") or "").strip()
        est_yr = rec.get("year_of_estimate")
        if not est_no or not est_yr:
            continue

        y_val = est_yr.year if hasattr(est_yr, "year") else est_yr
        grp_key = (est_no.lower(), str(y_val))
        if grp_key not in grouped:
            grouped[grp_key] = {
                "estimate_number": est_no,
                "year_of_estimate": est_yr,
                "status": rec.get("status", "DRAFT"),
                "latest_date": rec.get("created_at"),
                "contract_count": 1,
            }
        else:
            existing = grouped[grp_key]
            existing["contract_count"] = int(existing.get("contract_count") or 0) + 1
            if str(rec.get("created_at") or "") > str(existing.get("latest_date") or ""):
                existing["latest_date"] = rec.get("created_at")
            if rec.get("status") == "COMPLETED":
                existing["status"] = "COMPLETED"

    results = list(grouped.values())
    for item in results:
        est_no = item.get("estimate_number")
        est_yr = item.get("year_of_estimate")
        if not est_no or not est_yr:
            continue

        # Reconcile contract totals from master_submission source to avoid undercount
        # when drafts/completed lists are out-of-sync.
        same_est = get_submissions_by_estimate(
            est_no,
            est_yr,
            user_id=user_id,
            module="contract_management",
        )
        item["contract_count"] = len(same_est)

    results.sort(key=lambda x: str(x.get("latest_date") or ""), reverse=True)
    return results


def get_contract_mini_dashboard_stats(project_catalog=None):
    completed_contracts = get_user_master_submissions(user_id, module="contract_management")
    draft_contracts = [d for d in get_user_draft_summaries(user_id) if d.get("module") == "contract_management"]

    estimate_groups = {}

    def _add_estimate_record(rec, is_draft):
        est_no = (rec.get("estimate_number") or "").strip()
        est_yr = rec.get("year_of_estimate")
        if not est_no or not est_yr:
            return

        project_key = " ".join((rec.get("name_of_project") or "").split()).lower()
        y_val = est_yr.year if hasattr(est_yr, "year") else est_yr
        group_key = (project_key, est_no.lower(), str(y_val))
        group = estimate_groups.setdefault(
            group_key,
            {
                "project_key": project_key,
                "project_name": (rec.get("name_of_project") or "").strip(),
                "estimate_number": est_no,
                "year_of_estimate": str(y_val),
                "has_completed": False,
                "has_incomplete": False,
                "latest_date": rec.get("created_at"),
            },
        )

        status = str(rec.get("status") or "").strip().upper()
        if is_draft or status == "DRAFT":
            group["has_incomplete"] = True
        else:
            group["has_completed"] = True
        if str(rec.get("created_at") or "") > str(group.get("latest_date") or ""):
            group["latest_date"] = rec.get("created_at")

    for rec in completed_contracts:
        _add_estimate_record(rec, is_draft=False)
    for rec in draft_contracts:
        _add_estimate_record(rec, is_draft=True)

    completed_estimates = sum(
        1 for grp in estimate_groups.values() if grp.get("has_completed") and not grp.get("has_incomplete")
    )
    incomplete_estimates = len(estimate_groups) - completed_estimates

    project_catalog = project_catalog if project_catalog is not None else build_contract_project_catalog()
    groups_by_project = {}
    for grp in estimate_groups.values():
        groups_by_project.setdefault(grp.get("project_key", ""), []).append(grp)

    completed_projects = 0
    incomplete_projects = 0
    for proj in project_catalog:
        project_key = " ".join((proj.get("project_name") or "").split()).lower()
        project_groups = groups_by_project.get(project_key, [])
        is_project_complete = bool(project_groups) and all(
            g.get("has_completed") and not g.get("has_incomplete") for g in project_groups
        )
        if is_project_complete:
            completed_projects += 1
        else:
            incomplete_projects += 1

    dpr_finished = "N"
    dpr_completed = 0
    dpr_incomplete = 0
    dpr_details = []
    if project_catalog:
        for proj in project_catalog:
            pname = (proj.get("project_name") or "").strip()
            if not pname:
                continue
            project_dpr = get_project_dpr(user_id, pname, module="contract_management")
            has_dpr = bool(project_dpr)
            if has_dpr:
                dpr_completed += 1
            else:
                dpr_incomplete += 1
            dpr_details.append(
                {
                    "Project Name": pname,
                    "DPR Status": "Y" if has_dpr else "N",
                    "Updated": fmt_dt(project_dpr.get("updated_at")) if has_dpr else "-",
                }
            )
        dpr_finished = "Y" if dpr_incomplete == 0 and dpr_completed > 0 else "N"
    else:
        dpr_details = []

    estimate_details = []
    for grp in estimate_groups.values():
        status = "Completed" if grp.get("has_completed") and not grp.get("has_incomplete") else "Incomplete"
        estimate_details.append(
            {
                "Project Name": grp.get("project_name") or "-",
                "Estimate Number": grp.get("estimate_number") or "-",
                "Year": grp.get("year_of_estimate") or "-",
                "Status": status,
                "Last Updated": fmt_dt(grp.get("latest_date")),
            }
        )
    estimate_details.sort(key=lambda x: str(x.get("Last Updated") or ""), reverse=True)

    project_details = []
    for proj in project_catalog:
        pname = (proj.get("project_name") or "").strip()
        pkey = " ".join(pname.split()).lower()
        project_groups = groups_by_project.get(pkey, [])
        is_project_complete = bool(project_groups) and all(
            g.get("has_completed") and not g.get("has_incomplete") for g in project_groups
        )
        project_details.append(
            {
                "Project Name": pname or "-",
                "Status": "Completed" if is_project_complete else "Incomplete",
                "Estimates": int(proj.get("estimate_count") or 0),
            }
        )
    project_details.sort(key=lambda x: x.get("Project Name") or "")

    contract_details = []
    for rec in completed_contracts + draft_contracts:
        est_yr = rec.get("year_of_estimate")
        y_val = est_yr.year if hasattr(est_yr, "year") else est_yr
        status = str(rec.get("status") or "").strip().upper()
        contract_details.append(
            {
                "Project Name": (rec.get("name_of_project") or "-").strip() or "-",
                "Estimate Number": (rec.get("estimate_number") or "-").strip() or "-",
                "Year": str(y_val) if y_val not in (None, "") else "-",
                "Status": "Completed" if status != "DRAFT" else "Incomplete",
                "Last Updated": fmt_dt(rec.get("created_at")),
            }
        )
    contract_details.sort(key=lambda x: str(x.get("Last Updated") or ""), reverse=True)

    return {
        "dpr_finished": dpr_finished,
        "dpr_completed": dpr_completed,
        "dpr_incomplete": dpr_incomplete,
        "estimates_completed": completed_estimates,
        "estimates_incomplete": incomplete_estimates,
        "projects_completed": completed_projects,
        "projects_incomplete": incomplete_projects,
        "contracts_completed": len(completed_contracts),
        "contracts_incomplete": len(draft_contracts),
        "dpr_details": dpr_details,
        "estimate_details": estimate_details,
        "project_details": project_details,
        "contract_details": contract_details,
    }


def get_dpr_field_configs():
    def _rev_label(index):
        suffix = {1: "1st", 2: "2nd", 3: "3rd"}.get(index, f"{index}th")
        return f"{suffix} revision"

    up_districts = [
        "Agra",
        "Aligarh",
        "Ambedkar Nagar",
        "Amethi",
        "Amroha",
        "Auraiya",
        "Ayodhya",
        "Azamgarh",
        "Baghpat",
        "Bahraich",
        "Ballia",
        "Balrampur",
        "Banda",
        "Barabanki",
        "Bareilly",
        "Basti",
        "Bhadohi",
        "Bijnor",
        "Budaun",
        "Bulandshahr",
        "Chandauli",
        "Chitrakoot",
        "Deoria",
        "Etah",
        "Etawah",
        "Farrukhabad",
        "Fatehpur",
        "Firozabad",
        "Gautam Buddha Nagar",
        "Ghaziabad",
        "Ghazipur",
        "Gonda",
        "Gorakhpur",
        "Hamirpur",
        "Hapur",
        "Hardoi",
        "Hathras",
        "Jalaun",
        "Jaunpur",
        "Jhansi",
        "Kannauj",
        "Kanpur Dehat",
        "Kanpur Nagar",
        "Kasganj",
        "Kaushambi",
        "Kushinagar",
        "Lakhimpur Kheri",
        "Lalitpur",
        "Lucknow",
        "Maharajganj",
        "Mahoba",
        "Mainpuri",
        "Mathura",
        "Mau",
        "Meerut",
        "Mirzapur",
        "Moradabad",
        "Muzaffarnagar",
        "Pilibhit",
        "Pratapgarh",
        "Prayagraj",
        "Rae Bareli",
        "Rampur",
        "Saharanpur",
        "Sambhal",
        "Sant Kabir Nagar",
        "Shahjahanpur",
        "Shamli",
        "Shravasti",
        "Siddharthnagar",
        "Sitapur",
        "Sonbhadra",
        "Sultanpur",
        "Unnao",
        "Varanasi",
    ]
    configs = [
        {"label": "Category of Project", "type": "select", "options": ["-- Select --", "Irrigation", "Multipurpose"]},
        {"label": "Type of Project", "type": "select", "options": ["-- Select --", "Storage", "Diversion"]},
        {"label": "Location of Head Works", "type": "text"},
        {"label": "Date of Investement clearance by GOI", "type": "date"},
        {"label": "Date of CWC clearence", "type": "date"},
        {"label": "Date of approval of EFC", "type": "date"},
        {"label": "Districts covered", "type": "multiselect", "options": up_districts},
        {"label": "Gross Command area", "type": "text"},
        {"label": "CCA", "type": "text"},
        {"label": "Irrigation Potential in RABI", "type": "text"},
        {"label": "Irrigation Potential in KHARIF", "type": "text"},
        {"label": "Requirement of Water for project", "type": "text"},
        {"label": "Availability of Water against the requirement", "type": "text"},
        {"label": "Pre-Project Crop Pattern in RABI", "type": "text"},
        {"label": "Pre-Project Crop Pattern in KHARIF", "type": "text"},
        {"label": "Post-Project Crop Pattern in RABI", "type": "text"},
        {"label": "Post-Project Crop Pattern in KHARIF", "type": "text"},
    ]

     
    for i in range(1, 7):
        rev = _rev_label(i)
        configs.extend(
            [
                {"label": f"Date of approval revised DPR ({rev})", "type": "date"},
                {"label": f"Amount of revised DPR ({rev})", "type": "text"},
                {"label": f"Target date to complete the project ({rev})", "type": "date"},
            ]
        )
    return configs


def get_existing_dpr_fields(existing_dpr):
    existing_dpr = existing_dpr or {}
    payload_raw = existing_dpr.get("dpr_form_data")
    payload = {}
    if isinstance(payload_raw, dict):
        payload = payload_raw
    elif isinstance(payload_raw, str) and payload_raw.strip():
        try:
            parsed_payload = json.loads(payload_raw)
            if isinstance(parsed_payload, dict):
                payload = parsed_payload
        except (TypeError, ValueError):
            payload = {}

    # Backward compatibility with older DPR payload/columns.
    aliases = {
        "Category of Project": ["Category of Project", "category_of_project"],
        "Type of Project": ["Type of Project", "type_of_project"],
        "Location of Head Works": ["Location of Head Works", "location_of_head_works"],
        "Date of Investement clearance by GOI": [
            "Date of Investement clearance by GOI",
            "date_of_investement_clearance_by_goi",
        ],
        "Date of CWC clearence": ["Date of CWC clearence", "date_of_cwc_clearence"],
        "Date of approval of EFC": ["Date of approval of EFC", "date_of_approval_of_efc"],
        "Districts covered": ["Districts covered", "districts_covered"],
        "Gross Command area": ["Gross Command area", "gross_command_area"],
        "CCA": ["CCA", "cca"],
        "Irrigation Potential in RABI": ["Irrigation Potential in RABI", "irrigation_potential_in_rabi"],
        "Irrigation Potential in KHARIF": ["Irrigation Potential in KHARIF", "irrigation_potential_in_kharif"],
        "Requirement of Water for project": ["Requirement of Water for project", "requirement_of_water_for_project"],
        "Availability of Water against the requirement": [
            "Availability of Water against the requirement",
            "availability_of_water_against_the_requirement",
        ],
        "Pre-Project Crop Pattern in RABI": ["Pre-Project Crop Pattern in RABI", "pre_project_crop_pattern_in_rabi"],
        "Pre-Project Crop Pattern in KHARIF": ["Pre-Project Crop Pattern in KHARIF", "pre_project_crop_pattern_in_kharif"],
        "Post-Project Crop Pattern in RABI": ["Post-Project Crop Pattern in RABI", "post_project_crop_pattern_in_rabi"],
        "Post-Project Crop Pattern in KHARIF": ["Post-Project Crop Pattern in KHARIF", "post_project_crop_pattern_in_kharif"],
    }
    for i in range(1, 7):
        aliases[f"Date of approval revised DPR ({'1st' if i == 1 else '2nd' if i == 2 else '3rd' if i == 3 else str(i) + 'th'} revision)"] = [
            f"Date of approval revised DPR ({'1st' if i == 1 else '2nd' if i == 2 else '3rd' if i == 3 else str(i) + 'th'} revision)",
            f"date_of_approval_revised_dpr_revision_{i}",
        ]
        aliases[f"Amount of revised DPR ({'1st' if i == 1 else '2nd' if i == 2 else '3rd' if i == 3 else str(i) + 'th'} revision)"] = [
            f"Amount of revised DPR ({'1st' if i == 1 else '2nd' if i == 2 else '3rd' if i == 3 else str(i) + 'th'} revision)",
            f"amount_of_revised_dpr_revision_{i}",
        ]
        aliases[f"Target date to complete the project ({'1st' if i == 1 else '2nd' if i == 2 else '3rd' if i == 3 else str(i) + 'th'} revision)"] = [
            f"Target date to complete the project ({'1st' if i == 1 else '2nd' if i == 2 else '3rd' if i == 3 else str(i) + 'th'} revision)",
            f"target_date_to_complete_project_revision_{i}",
        ]

    resolved = {}
    for cfg in get_dpr_field_configs():
        label = cfg.get("label")
        if not label:
            continue

        value = payload.get(label)
        if value in (None, ""):
            for key_name in aliases.get(label, []):
                candidate = payload.get(key_name)
                if candidate not in (None, ""):
                    value = candidate
                    break

        if value in (None, ""):
            # Support dict-style rows where labels may have been materialized.
            candidate = existing_dpr.get(label)
            if candidate not in (None, ""):
                value = candidate

        if value in (None, ""):
            for key_name in aliases.get(label, []):
                candidate = existing_dpr.get(key_name)
                if candidate not in (None, ""):
                    value = candidate
                    break

        if value not in (None, ""):
            resolved[label] = value

    return resolved


def render_create_dpr_page(flow_data=None):
    flow_data = flow_data or {}
    project_name = (flow_data.get("project_name") or "").strip()
    safe_project = _safe_key(project_name or "project")
    render_flow_header(f"Create DPR: {project_name or 'Unknown'}", back_key=f"back_create_dpr_{safe_project}")

    if not project_name:
        st.warning("No project selected.")
        return

    existing_dpr = get_project_dpr(user_id, project_name, module="contract_management") or {}
    existing_fields = get_existing_dpr_fields(existing_dpr)

    field_configs = get_dpr_field_configs()
    for cfg in field_configs:
        label = cfg["label"]
        if cfg.get("type") == "section":
            continue
        state_key = f"dpr_form_{_safe_key(label)}_{safe_project}"
        if state_key in st.session_state:
            continue
        existing_value = existing_fields.get(label)
        if cfg["type"] == "date":
            st.session_state[state_key] = parse_date_for_input(existing_value)
        elif cfg["type"] == "select":
            options = cfg.get("options", [])
            normalized = str(existing_value or "").strip().lower()
            matched = next((opt for opt in options if str(opt).strip().lower() == normalized), None)
            st.session_state[state_key] = matched if matched else options[0]
        elif cfg["type"] == "multiselect":
            options = cfg.get("options", [])
            if isinstance(existing_value, (list, tuple, set)):
                raw_selected = [str(v).strip() for v in existing_value if str(v).strip()]
            else:
                raw_selected = [x.strip() for x in str(existing_value or "").split(",") if x.strip()]
            option_map = {str(opt).strip().lower(): opt for opt in options}
            selected = []
            for raw_item in raw_selected:
                item = option_map.get(raw_item.lower())
                if item and item not in selected:
                    selected.append(item)
            st.session_state[state_key] = selected
        else:
            st.session_state[state_key] = "" if existing_value in (None, "") else str(existing_value)

    st.markdown(
        "<div style='font-size:13px;color:#6b7280;margin-bottom:8px;'>Please complete DPR first before creating estimate.</div>",
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    form_values = {}
    for idx, cfg in enumerate(field_configs):
        label = cfg["label"]
        ftype = cfg["type"]
        if ftype == "section":
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            st.markdown(f"#### {label}")
            continue
        state_key = f"dpr_form_{_safe_key(label)}_{safe_project}"
        target_col = col1 if idx % 2 == 0 else col2
        with target_col:
            if ftype == "select":
                value = st.selectbox(label, options=cfg.get("options", []), key=state_key)
            elif ftype == "date":
                value = st.date_input(label, key=state_key)
            elif ftype == "multiselect":
                value = st.multiselect(label, options=cfg.get("options", []), key=state_key)
            else:
                value = st.text_input(label, key=state_key)
        form_values[label] = value

    existing_payload_raw = existing_dpr.get("dpr_form_data")
    existing_payload = {}
    if isinstance(existing_payload_raw, dict):
        existing_payload = existing_payload_raw
    elif isinstance(existing_payload_raw, str) and existing_payload_raw.strip():
        try:
            parsed_payload = json.loads(existing_payload_raw)
            if isinstance(parsed_payload, dict):
                existing_payload = parsed_payload
        except (TypeError, ValueError):
            existing_payload = {}

    upload_configs = [
        {"key": "upload_complete_dpr", "label": "Upload Complete DPR", "required": True},
        {"key": "investment_clearence", "label": "Investment clearence", "required": True},
        {"key": "cwc_clearence", "label": "CWC clearence", "required": True},
        {"key": "dpr_approval_by_efc", "label": "DPR Approval by EFC", "required": True},
        {"key": "survey_reports", "label": "Survey Reports", "required": True},
    ]

    st.markdown("#### DPR Documents")
    upload_inputs = {}
    for cfg in upload_configs:
        label = cfg["label"] + (" (mandatory)" if cfg["required"] else "")
        upload_inputs[cfg["key"]] = st.file_uploader(
            label,
            type=["pdf", "doc", "docx", "xlsx", "xls", "jpg", "jpeg", "png"],
            key=f"dpr_upload_{cfg['key']}_{safe_project}",
        )
        file_name_key = f"{cfg['key']}_file_name"
        existing_file_name = existing_payload.get(file_name_key)
        if cfg["key"] == "upload_complete_dpr" and not existing_file_name:
            existing_file_name = existing_dpr.get("dpr_file_name")
        if existing_file_name:
            st.caption(f"Existing: {existing_file_name}")

    if existing_dpr:
        last_file = existing_dpr.get("dpr_file_name") or "N/A"
        updated_at = fmt_dt(existing_dpr.get("updated_at"))
        st.success(f"Existing DPR found. File: `{last_file}` | Last Updated: {updated_at}")

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    if st.button("Create DPR", key=f"btn_save_dpr_{safe_project}", use_container_width=True, type="primary"):
        cleaned_values = {}
        for cfg in field_configs:
            label = cfg["label"]
            ftype = cfg["type"]
            if ftype == "section":
                continue
            value = form_values.get(label)
            is_optional = bool(cfg.get("optional"))

            if ftype == "select":
                if value in (None, "", "-- Select --"):
                    st.error(f"Please select `{label}`.")
                    return
                cleaned_values[label] = value
            elif ftype == "multiselect":
                selected_values = [str(v).strip() for v in (value or []) if str(v).strip()]
                if not selected_values and not is_optional:
                    st.error(f"Please select at least one option for `{label}`.")
                    return
                cleaned_values[label] = ", ".join(selected_values) if selected_values else None
            elif ftype == "date":
                if value in (None, "") and not is_optional:
                    st.error(f"Please select `{label}`.")
                    return
                cleaned_values[label] = normalize_date_for_storage(value) if value not in (None, "") else None
            else:
                text_value = (str(value) if value is not None else "").strip()
                if not text_value and not is_optional:
                    st.error(f"Please enter `{label}`.")
                    return
                cleaned_values[label] = text_value if text_value else None

        selected_file_name = existing_dpr.get("dpr_file_name")
        selected_file_path = existing_dpr.get("dpr_file_path")
        os.makedirs("uploads", exist_ok=True)
        for cfg in upload_configs:
            file_name_key = f"{cfg['key']}_file_name"
            file_path_key = f"{cfg['key']}_file_path"
            saved_file_name = existing_payload.get(file_name_key)
            saved_file_path = existing_payload.get(file_path_key)

            if cfg["key"] == "upload_complete_dpr":
                if not saved_file_name:
                    saved_file_name = selected_file_name
                if not saved_file_path:
                    saved_file_path = selected_file_path

            upload_obj = upload_inputs.get(cfg["key"])
            if upload_obj:
                ext = os.path.splitext(upload_obj.name)[1]
                ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                fname = f"DPR_{safe_project}_{_safe_key(cfg['key'])}_{ts}{ext}"
                saved_file_path = os.path.join("uploads", fname)
                with open(saved_file_path, "wb") as f:
                    f.write(upload_obj.getbuffer())
                saved_file_name = upload_obj.name

            if cfg["required"] and not saved_file_name:
                st.error(f"Please upload `{cfg['label']}`.")
                return

            cleaned_values[file_name_key] = saved_file_name
            cleaned_values[file_path_key] = saved_file_path

            if cfg["key"] == "upload_complete_dpr":
                selected_file_name = saved_file_name
                selected_file_path = saved_file_path

        is_saved = upsert_project_dpr(
            user_id=user_id,
            project_name=project_name,
            fields=cleaned_values,
            dpr_file_name=selected_file_name,
            dpr_file_path=selected_file_path,
            module="contract_management",
        )
        if not is_saved:
            st.error("Unable to save DPR right now. Please try again.")
            return

        st.success("DPR created successfully.")
        back_flow_page()
        st.rerun()


def render_dpr_view_page(flow_data=None):
    flow_data = flow_data or {}
    project_name = (flow_data.get("project_name") or "").strip()
    safe_project = _safe_key(project_name or "project")
    render_flow_header(f"DPR Data: {project_name or 'Unknown'}", back_key=f"back_dpr_view_{safe_project}")

    if not project_name:
        st.warning("No project selected.")
        return

    st.session_state.current_project_name = project_name
    project_dpr = get_project_dpr(user_id, project_name, module="contract_management") or {}
    if not project_dpr:
        st.info("No DPR data found for this project.")
        if st.button("Create DPR", key=f"btn_dpr_view_create_{safe_project}", use_container_width=True, type="primary"):
            open_flow_page(
                "create_dpr",
                data={"project_name": project_name, "module": "contract_management"},
                push_history=True,
            )
            st.rerun()
        return

    top1, top2 = st.columns([2, 1])
    with top1:
        file_name = project_dpr.get("dpr_file_name") or "N/A"
        updated_at = fmt_dt(project_dpr.get("updated_at"))
        st.markdown(
            f"<div style='font-size:13px;color:#6b7280;'>File: <b>{esc_html(file_name)}</b> | Last Updated: {esc_html(updated_at)}</div>",
            unsafe_allow_html=True,
        )
    with top2:
        if st.button("Update DPR Data", key=f"btn_dpr_view_update_{safe_project}", use_container_width=True, type="primary"):
            open_flow_page(
                "create_dpr",
                data={"project_name": project_name, "module": "contract_management"},
                push_history=True,
            )
            st.rerun()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown("#### DPR Form Data")
    existing_fields = get_existing_dpr_fields(project_dpr)
    for cfg in get_dpr_field_configs():
        label = cfg.get("label")
        ftype = cfg.get("type")
        if not label:
            continue
        if ftype == "section":
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            st.markdown(f"##### {label}")
            continue

        raw_val = existing_fields.get(label)
        if isinstance(raw_val, (list, tuple, set)):
            display_val = ", ".join([str(v) for v in raw_val if str(v).strip()]) or "N/A"
        else:
            display_val = str(raw_val).strip() if raw_val not in (None, "") else "N/A"

        c1, c2 = st.columns([2.8, 4.2])
        with c1:
            st.markdown(f"**{label}**")
        with c2:
            st.markdown(f"<span>{esc_html(display_val)}</span>", unsafe_allow_html=True)

    payload_raw = project_dpr.get("dpr_form_data")
    payload = {}
    if isinstance(payload_raw, dict):
        payload = payload_raw
    elif isinstance(payload_raw, str) and payload_raw.strip():
        try:
            payload = json.loads(payload_raw) or {}
        except (TypeError, ValueError):
            payload = {}

    docs = [
        ("Upload Complete DPR", "upload_complete_dpr_file_name"),
        ("Investment clearence", "investment_clearence_file_name"),
        ("CWC clearence", "cwc_clearence_file_name"),
        ("DPR Approval by EFC", "dpr_approval_by_efc_file_name"),
        ("Survey Reports", "survey_reports_file_name"),
    ]
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    st.markdown("#### DPR Documents")
    for label, key_name in docs:
        file_name = payload.get(key_name) or project_dpr.get(key_name)
        if key_name == "upload_complete_dpr_file_name" and not file_name:
            file_name = project_dpr.get("dpr_file_name")
        display_file = str(file_name).strip() if file_name not in (None, "") else "N/A"
        c1, c2 = st.columns([2.8, 4.2])
        with c1:
            st.markdown(f"**{label}**")
        with c2:
            st.markdown(f"<span>{esc_html(display_file)}</span>", unsafe_allow_html=True)


def render_create_estimate_page(flow_data=None):
    flow_data = flow_data or {}
    project_name = (flow_data.get("project_name") or "").strip()
    safe_project = _safe_key(project_name or "project")
    render_flow_header(
        f"Create Estimate: {project_name or 'Unknown'}",
        back_key=f"back_create_est_{safe_project}",
    )

    if not project_name:
        st.warning("No project selected.")
        return

    st.session_state.current_project_name = project_name

    existing_project_estimates = get_project_estimate_groups(project_name)
    is_fresh_project = len(existing_project_estimates) == 0
    project_dpr = get_project_dpr(user_id, project_name, module="contract_management")
    has_dpr = bool(project_dpr)
    if is_fresh_project and not has_dpr:
        st.warning("Please create DPR first for this project.")
        if st.button("Go To Create DPR", key=f"goto_create_dpr_{safe_project}", use_container_width=True, type="primary"):
            open_flow_page(
                "create_dpr",
                data={"project_name": project_name, "module": "contract_management"},
                push_history=True,
            )
            st.rerun()
        return

    nm_proj_key = f"header_modal_nm_proj_{safe_project}"
    est_no_key = f"header_modal_est_no_{safe_project}"
    est_yr_key = f"header_modal_est_yr_{safe_project}"
    if not st.session_state.get(nm_proj_key):
        st.session_state[nm_proj_key] = project_name

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.text_input(
        "Name of Project",
        placeholder="Enter project name",
        key=nm_proj_key,
    )

    prefill_est_no = flow_data.get("prefill_estimate_number")
    prefill_est_yr = normalize_year_option(flow_data.get("prefill_year_of_estimate"))
    if prefill_est_no and not st.session_state.get(est_no_key):
        st.session_state[est_no_key] = str(prefill_est_no)

    c1, c2 = st.columns(2)
    with c1:
        st.text_input("Estimate Number", placeholder="e.g. EST/2024/001", key=est_no_key)
    with c2:
        current_year = datetime.datetime.now().year
        year_options = [f"{y}-{str(y + 1)[2:]}" for y in range(current_year, 1999, -1)]
        if prefill_est_yr and prefill_est_yr not in year_options:
            year_options.insert(0, prefill_est_yr)
        if prefill_est_yr and not st.session_state.get(est_yr_key):
            st.session_state[est_yr_key] = prefill_est_yr
        elif st.session_state.get(est_yr_key) not in year_options:
            st.session_state[est_yr_key] = year_options[0]
        st.selectbox("Year of Estimate", options=year_options, key=est_yr_key)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    submit_col1, submit_col2 = st.columns([3.8, 1.2])
    with submit_col1:
        submit_clicked = st.button("Create Estimate ->", key=f"create_est_project_{safe_project}", use_container_width=True, type="primary")
    with submit_col2:
        if st.button("Cancel", key=f"cancel_estimate_page_{safe_project}", use_container_width=True):
            back_flow_page()
            st.rerun()

    if not submit_clicked:
        return

    est_no = (st.session_state.get(est_no_key) or "").strip()
    est_yr = st.session_state.get(est_yr_key)
    nm_proj = (st.session_state.get(nm_proj_key) or project_name).strip()

    if not est_no or not est_yr or not nm_proj:
        st.error("Please enter Name of Project, Estimate Number and Year.")
        return

    existing_ones = get_submissions_by_estimate(
        est_no,
        est_yr,
        module="contract_management",
        name_of_project=nm_proj,
    )
    if existing_ones:
        open_flow_page(
            "duplicate_submission",
            data={
                "module": "contract_management",
                "est_no": est_no,
                "est_yr": est_yr,
                "sub": existing_ones[0],
            },
            push_history=True,
        )
        st.rerun()

    clear_module_state("contract_management")
    st.session_state.initial_estimate_number = est_no
    st.session_state.initial_year_of_estimate = est_yr
    st.session_state.initial_name_of_project = nm_proj

    try:
        target_m_id = create_master_submission(
            user_id,
            "contract_management",
            modules.get("contract_management", []),
            status="DRAFT",
            estimate_number=est_no,
            year_of_estimate=est_yr,
            name_of_project=nm_proj,
        )
        st.session_state.master_id = target_m_id
        st.session_state.current_view = "contract_management"
        remember_flow_return_for_module()
        close_flow_page()
        st.rerun()
    except Exception as e:
        report_error("Error starting application.", e, "app.render_create_estimate_page")
        return


def render_project_detail_page(flow_data=None):
    flow_data = flow_data or {}
    project_name = (flow_data.get("project_name") or "").strip()
    safe_project = _safe_key(project_name or "project")
    render_flow_header(f"Project: {project_name or 'Unknown'}", back_key=f"back_project_detail_{safe_project}")

    if not project_name:
        st.warning("No project selected.")
        return
    st.session_state.current_project_name = project_name

    project_groups = get_project_estimate_groups(project_name)
    estimate_count = len(project_groups)
    st.markdown(
        f"""
        <div style="padding:10px 14px; border:1px solid #e5e8ef; border-radius:8px; background:#f8f9fc;">
            <div style="font-size:12px; color:#6b7280;">Project Summary</div>
            <div style="font-size:20px; font-weight:700; color:#1a3a6b;">{esc_html(project_name)}</div>
            <div style="font-size:13px; color:#374151; margin-top:4px;">Total Estimates: <b>{estimate_count}</b></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    st.markdown("#### Estimates in this Project")

    if not project_groups:
        st.info("No estimates created for this project yet.")
    else:
        page_key = f"project_estimates_page_{safe_project}"
        page_size_key = f"{page_key}_size"
        paged_estimates, start_idx, total_pages = paginate_list(project_groups, page_key, render_controls=False)

        h1, h2, h3, h4, h5, h6, h7 = st.columns([0.6, 2.9, 1.5, 1.4, 2.1, 1.6, 1.2])
        h1.markdown("**S.No**")
        h2.markdown("**Estimate Number**")
        h3.markdown("**Year**")
        h4.markdown("**Contracts**")
        h5.markdown("**Last Updated**")
        h6.markdown("**Status**")
        with h7:
            st.markdown('<div class="rows-per-page" style="margin-bottom:0;text-align:right;">Rows</div>', unsafe_allow_html=True)
            new_size = st.selectbox(
                "Size",
                [10, 25, 50, 100],
                index=[10, 25, 50, 100].index(st.session_state.get(page_size_key, 10)),
                key=f"size_select_{safe_project}",
                label_visibility="collapsed",
            )
            if new_size != st.session_state.get(page_size_key, 10):
                st.session_state[page_size_key] = new_size
                st.session_state[page_key] = 1
                st.rerun()

        st.markdown("<hr style='margin:4px 0; border-color:#e5e8ef;'>", unsafe_allow_html=True)

        for i, est in enumerate(paged_estimates):
            est_no = est.get("estimate_number")
            est_yr = est.get("year_of_estimate")
            status = est.get("status", "DRAFT")
            latest = est.get("latest_date")
            contract_count = int(est.get("contract_count") or 0)
            s_no = start_idx + i + 1

            r1, r2, r3, r4, r5, r6 = st.columns([0.6, 2.9, 1.5, 1.4, 2.1, 1.6])
            r1.write(str(s_no))
            display_est = str(est_no or "")
            with r2:
                est_group_href = (
                    f'./?estimate_action=open_group&est_no={quote(str(est_no))}&est_yr={quote(str(est_yr))}'
                    f'&project_name={quote(str(project_name))}'
                )
                st.markdown(
                    f'<a href="{est_group_href}" target="_self" class="dashboard-project-link">{esc_html(display_est)}</a>',
                    unsafe_allow_html=True,
                )
            with r3:
                y_val = est_yr.year if hasattr(est_yr, "year") else est_yr
                st.write(str(y_val))
            with r4:
                st.write(str(contract_count))
            r5.write(fmt_dt(latest))
            with r6:
                status_bg = "#fffbeb" if status == "DRAFT" else "#ecfdf5"
                status_text = "#92400e" if status == "DRAFT" else "#065f46"
                status_bdr = "#fcd34d" if status == "DRAFT" else "#a7f3d0"
                st.markdown(
                    f'<span style="background:{status_bg}; color:{status_text}; border:1px solid {status_bdr}; '
                    f'padding:2px 10px; border-radius:4px; font-size:11px; font-weight:700;">{status}</span>',
                    unsafe_allow_html=True,
                )
            st.markdown("<hr style='margin:6px 0; border:0; border-top:1px solid #f3f4f6;'>", unsafe_allow_html=True)

        render_pagination_footer(page_key, total_pages)

    if estimate_count == 0:
        project_dpr = get_project_dpr(user_id, project_name, module="contract_management")
        has_dpr = bool(project_dpr)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown("#### DPR")
        if has_dpr:
            d1, d2 = st.columns(2)
            with d1:
                if st.button("Update DPR", key=f"btn_manage_dpr_{safe_project}", use_container_width=True, type="primary"):
                    open_flow_page(
                        "create_dpr",
                        data={"project_name": project_name, "module": "contract_management"},
                        push_history=True,
                    )
                    st.rerun()
            with d2:
                if st.button("View DPR Data", key=f"btn_view_dpr_{safe_project}", use_container_width=True):
                    open_flow_page(
                        "dpr_view",
                        data={"project_name": project_name, "module": "contract_management"},
                        push_history=True,
                    )
                    st.rerun()
        else:
            if st.button("Create DPR", key=f"btn_manage_dpr_{safe_project}", use_container_width=True, type="primary"):
                open_flow_page(
                    "create_dpr",
                    data={"project_name": project_name, "module": "contract_management"},
                    push_history=True,
                )
                st.rerun()

        if has_dpr:
            file_name = project_dpr.get("dpr_file_name") or "N/A"
            updated_at = fmt_dt(project_dpr.get("updated_at"))
            st.markdown(
                f"<div style='font-size:12px;color:#6b7280;margin:4px 0 8px 0;'>DPR ready: <b>{esc_html(file_name)}</b> | Updated: {esc_html(updated_at)}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.info("No DPR created for this fresh project yet.")


def render_new_application_page(flow_data=None):
    flow_data = flow_data or {}
    render_flow_header("Start New Project", back_key="back_new_app_top")
    project_placeholder = "-- Select Project --"
    created_projects_key = "created_projects_store"

    module_options = list(module_display_map.keys())
    if not module_options:
        st.warning("No modules have been assigned to your account yet.")
        return

    selected_module_key = "new_app_module_select"
    prefill_module = flow_data.get("module")
    if prefill_module in module_options:
        st.session_state[selected_module_key] = prefill_module
    elif st.session_state.get(selected_module_key) not in module_options:
        st.session_state[selected_module_key] = module_options[0]

    st.markdown("Select a module below to begin a new audit application.")
    selected_m = st.selectbox(
        "Select Module",
        options=module_options,
        format_func=lambda x: module_display_map[x],
        key=selected_module_key,
    )

    if selected_m != "contract_management":
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        if st.button("Start Application ->", use_container_width=True, type="primary"):
            clear_module_state(selected_m)
            try:
                target_m_id = create_master_submission(
                    user_id,
                    selected_m,
                    modules.get(selected_m, []),
                    status="DRAFT",
                    estimate_number=None,
                    year_of_estimate=None,
                    name_of_project=None,
                )
                st.session_state.master_id = target_m_id
                st.session_state.current_view = selected_m
                remember_flow_return_for_module()
                close_flow_page()
                st.rerun()
            except Exception as e:
                report_error("Error starting application.", e, "app.render_new_application_page")
                return
        return

    prefill_project = (flow_data.get("prefill_name_of_project") or "").strip()
    merged_projects = build_contract_project_catalog(prefill_project=prefill_project)

    project_options = [
        project_placeholder,
        "Upper Ganga Canal Rehabilitation",
        "Sharda Canal Modernization",
        "Eastern Feeder Channel Restoration",
        "Bund Strengthening and Safety Upgrade",
        "Irrigation Pump Station Renewal",
    ]
    for item in merged_projects:
        pname = item.get("project_name")
        if pname and pname not in project_options:
            project_options.append(pname)

    if prefill_project:
        st.session_state["new_app_project_name"] = prefill_project
    elif st.session_state.get("new_app_project_name") not in project_options:
        st.session_state["new_app_project_name"] = project_placeholder

    st.markdown("#### Select Project")
    st.selectbox(
        "Name of Project",
        options=project_options,
        key="new_app_project_name",
        help="Select an existing project name from the list.",
    )
    if st.button("Select Project", key="btn_create_project", use_container_width=True, type="primary"):
        selected_project = (st.session_state.get("new_app_project_name") or "").strip()
        if not selected_project or selected_project == project_placeholder:
            st.error("Please select a project name first.")
            return
        current_projects = st.session_state.get(created_projects_key, [])
        exists = any((p.get("project_name") or "").strip().lower() == selected_project.lower() for p in current_projects)
        if not exists:
            current_projects.insert(0, {
                "project_name": selected_project,
                "created_at": datetime.datetime.now().isoformat(),
                "estimate_count": 0,
            })
            st.session_state[created_projects_key] = current_projects
        open_flow_page(
            "project_detail",
            data={"project_name": selected_project, "module": "contract_management"},
            push_history=True,
        )
        st.rerun()

def render_active_flow_page():
    page = st.session_state.get("flow_page")
    payload = st.session_state.get("flow_data", {})

    if not page:
        return False

    if page == "new_application":
        render_new_application_page(payload)
    elif page == "project_detail":
        render_project_detail_page(payload)
    elif page == "create_dpr":
        render_create_dpr_page(payload)
    elif page == "dpr_view":
        render_dpr_view_page(payload)
    elif page == "create_estimate":
        render_create_estimate_page(payload)
    elif page == "duplicate_submission":
        render_duplicate_submission_page(payload)
    elif page == "estimate_group":
        render_estimate_group_page(
            payload.get("est_no"),
            payload.get("est_yr"),
            user_id=payload.get("user_id"),
            module=payload.get("module"),
        )
    elif page == "submission_details":
        render_submission_details_page(payload.get("sub"))
    else:
        close_flow_page()
        st.rerun()

    return True


def is_section_complete(user_id, table, master_id=None):
    percentage, completed, total = get_user_progress(user_id, [table], master_id=master_id)
    return percentage == 100


def paginate_list(items, key_prefix, render_controls=True):
    size_key = f"{key_prefix}_size"
    if size_key not in st.session_state:
        st.session_state[size_key] = 10
    if key_prefix not in st.session_state:
        st.session_state[key_prefix] = 1
    if render_controls:
        col_size, _ = st.columns([1, 6])
        with col_size:
            st.markdown('<div class="rows-per-page">Rows per page</div>', unsafe_allow_html=True)
            new_size = st.selectbox("Rows per page", [10, 25, 50, 100],
                index=[10,25,50,100].index(st.session_state[size_key]),
                key=f"size_select_{key_prefix}", label_visibility="collapsed")
            if new_size != st.session_state[size_key]:
                st.session_state[size_key] = new_size
                st.session_state[key_prefix] = 1
                st.rerun()
    items_per_page = st.session_state[size_key]
    total_pages    = max(1, (len(items) + items_per_page - 1) // items_per_page)
    if st.session_state[key_prefix] > total_pages: st.session_state[key_prefix] = total_pages
    if st.session_state[key_prefix] < 1:           st.session_state[key_prefix] = 1
    start_idx  = (st.session_state[key_prefix] - 1) * items_per_page
    paged_items = items[start_idx : start_idx + items_per_page]
    if render_controls and total_pages > 1:
        render_pagination_footer(key_prefix, total_pages)
    return paged_items, start_idx, total_pages


def render_pagination_footer(key_prefix, total_pages):
    if total_pages <= 1:
        return
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("Previous", key=f"prev_{key_prefix}",
                     disabled=st.session_state[key_prefix] == 1, use_container_width=True):
            st.session_state[key_prefix] -= 1
            st.rerun()
    with col2:
        st.markdown(
            f"<div style='text-align:center; padding-top:10px; font-weight:600; "
            f"color:#6b7280; font-size:13px;'>Page {st.session_state[key_prefix]} of {total_pages}</div>",
            unsafe_allow_html=True
        )
    with col3:
        if st.button("Next", key=f"next_{key_prefix}",
                     disabled=st.session_state[key_prefix] >= total_pages, use_container_width=True):
            st.session_state[key_prefix] += 1
            st.rerun()
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)


def render_metric_cards(total, submitted, drafts, card_type="user"):
    param_key = "user_status_filter" if card_type == "user" else "status_filter"

    st.markdown('<div class="metric-row">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)

    cards = [
        (c1, total,     "Total Applications",  "All modules combined",       "ALL",       "metric-total"),
        (c2, submitted, "Completed Audits",     "Final submissions",          "COMPLETED", "metric-completed"),
        (c3, drafts,    "Pending Drafts",       "Work in progress",           "DRAFT",     "metric-draft"),
    ]

    for col, val, label, sub_label, filter_val, css_class in cards:
        with col:
            st.markdown(f"""
            <a href="./?{param_key}={filter_val}" target="_self" class="metric-card-link">
                <div class="minimal-card {css_class}">
                    <div class="metric-val">{val}</div>
                    <div class="metric-label-txt">{label}</div>
                    <div class="metric-sub">{sub_label}</div>
                </div>
            </a>
            """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


# =====================================================
# ================= MODULE CONFIGURATION ==============
# =====================================================
all_tables = get_all_tables()

all_modules = {}
for table in all_tables:
    if "_" in table:
        module_prefix = "_".join(table.split("_")[:2])
        all_modules.setdefault(module_prefix, []).append(table)

all_module_display_map = {m: m.replace("_", " ").title() for m in all_modules.keys()}

allowed = st.session_state.get("allowed_modules", "")
if allowed:
    allowed_list = allowed.split(",")
    modules = {k: v for k, v in all_modules.items() if k in allowed_list}
else:
    modules = {}

module_display_map = {m: m.replace("_", " ").title() for m in modules.keys()}


# =====================================================
# ================= NAVIGATION HANDLING ===============
# =====================================================
if st.query_params.get("nav") == "Main":
    st.session_state.current_view = "Main"
    st.query_params.clear()
    st.rerun()
elif st.query_params.get("nav") == "Logout":
    cookies["logged_in"] = "0"
    cookies.save()
    st.session_state.logged_in = False
    st.session_state.user_id   = None
    st.query_params.clear()
    st.rerun()
elif st.query_params.get("nav") == "NewApp":
    if not is_admin:
        open_flow_page("new_application", data={}, push_history=False)
    st.query_params.clear()
    st.rerun()
elif st.query_params.get("nav") == "CreateEstimate":
    if not is_admin:
        active_project = ""
        requested_project = st.query_params.get("project")
        if isinstance(requested_project, list):
            requested_project = requested_project[0] if requested_project else ""
        if requested_project:
            active_project = str(requested_project).strip()
        current_flow = st.session_state.get("flow_page")
        if not active_project and current_flow in ("project_detail", "create_dpr", "create_estimate", "dpr_view"):
            active_project = (st.session_state.get("flow_data", {}).get("project_name") or "").strip()
        if not active_project:
            active_project = (st.session_state.get("current_project_name") or "").strip()
        if active_project:
            st.session_state.current_project_name = active_project
            open_flow_page(
                "create_estimate",
                data={"project_name": active_project, "module": "contract_management"},
                push_history=True,
            )
    st.query_params.clear()
    st.rerun()
elif st.query_params.get("estimate_action"):
    action = st.query_params.get("estimate_action")
    if isinstance(action, list):
        action = action[0] if action else ""
    est_no = st.query_params.get("est_no")
    if isinstance(est_no, list):
        est_no = est_no[0] if est_no else ""
    est_yr = st.query_params.get("est_yr")
    if isinstance(est_yr, list):
        est_yr = est_yr[0] if est_yr else ""
    project_name = st.query_params.get("project_name")
    if isinstance(project_name, list):
        project_name = project_name[0] if project_name else ""

    if str(action or "").strip().lower() == "open_group" and est_no and est_yr:
        if not st.session_state.get("flow_page") and project_name:
            st.session_state.flow_page = "project_detail"
            st.session_state.flow_data = {
                "project_name": str(project_name).strip(),
                "module": "contract_management",
            }
            st.session_state.flow_history = []
        open_flow_page(
            "estimate_group",
            data={
                "est_no": str(est_no).strip(),
                "est_yr": str(est_yr).strip(),
                "user_id": user_id,
                "module": "contract_management",
            },
            push_history=True,
        )
    st.query_params.clear()
    st.rerun()
elif st.query_params.get("contract_action"):
    action = st.query_params.get("contract_action")
    if isinstance(action, list):
        action = action[0] if action else ""
    action_name = str(action or "").strip().lower()

    est_no = st.query_params.get("est_no")
    if isinstance(est_no, list):
        est_no = est_no[0] if est_no else ""
    est_no = str(est_no or "").strip()

    est_yr = st.query_params.get("est_yr")
    if isinstance(est_yr, list):
        est_yr = est_yr[0] if est_yr else ""
    est_yr = str(est_yr or "").strip()

    sub_id_raw = st.query_params.get("sub_id")
    if isinstance(sub_id_raw, list):
        sub_id_raw = sub_id_raw[0] if sub_id_raw else ""
    try:
        sub_id = int(str(sub_id_raw).strip()) if sub_id_raw not in (None, "") else None
    except (TypeError, ValueError):
        sub_id = None

    if action_name == "start_new" and est_no and est_yr and not is_admin:
        st.session_state.initial_estimate_number = est_no
        st.session_state.initial_year_of_estimate = est_yr
        prefill_project = ""
        submissions_for_prefill = get_submissions_by_estimate(est_no, est_yr, user_id=None, module=None)
        if submissions_for_prefill:
            for sub in submissions_for_prefill:
                if sub.get("name_of_project"):
                    prefill_project = sub.get("name_of_project")
                    break
        if prefill_project:
            st.session_state.initial_name_of_project = prefill_project

        saved_no = st.session_state.get("initial_estimate_number")
        saved_yr = st.session_state.get("initial_year_of_estimate")
        saved_nm = st.session_state.get("initial_name_of_project")
        clear_module_state("contract_management")
        st.session_state.initial_estimate_number = saved_no
        st.session_state.initial_year_of_estimate = saved_yr
        st.session_state.initial_name_of_project = saved_nm
        st.session_state.master_id = None
        st.session_state.current_view = "contract_management"
        remember_flow_return_for_module()
        close_flow_page()
    elif action_name in {"resume", "view", "upload"} and sub_id:
        sub = get_master_submission(sub_id)
        if sub:
            if action_name == "resume" and not is_admin:
                clear_module_state(sub.get("module"))
                st.session_state.master_id = sub["id"]
                st.session_state.current_view = sub.get("module")
                remember_flow_return_for_module()
                close_flow_page()
            elif action_name == "view":
                open_flow_page("submission_details", data={"sub": sub}, push_history=True)
            elif action_name == "upload":
                st.session_state.show_up_id = sub["id"]
                if est_no and est_yr:
                    open_flow_page(
                        "estimate_group",
                        data={
                            "est_no": est_no,
                            "est_yr": est_yr,
                            "user_id": user_id,
                            "module": "contract_management",
                        },
                        push_history=False,
                    )
    st.query_params.clear()
    st.rerun()
elif st.query_params.get("dash_action"):
    if not is_admin:
        action = st.query_params.get("dash_action")
        if isinstance(action, list):
            action = action[0] if action else ""
        requested_project = st.query_params.get("dash_project")
        if isinstance(requested_project, list):
            requested_project = requested_project[0] if requested_project else ""
        project_name = str(requested_project or "").strip()
        action_name = str(action or "").strip().lower()
        if project_name:
            st.session_state.current_project_name = project_name
            if action_name == "view_dpr":
                open_flow_page(
                    "dpr_view",
                    data={"project_name": project_name, "module": "contract_management"},
                    push_history=False,
                )
            elif action_name == "fill_dpr":
                open_flow_page(
                    "create_dpr",
                    data={"project_name": project_name, "module": "contract_management"},
                    push_history=False,
                )
    st.query_params.clear()
    st.rerun()
elif st.query_params.get("dash_project"):
    if not is_admin:
        requested_project = st.query_params.get("dash_project")
        if isinstance(requested_project, list):
            requested_project = requested_project[0] if requested_project else ""
        project_name = str(requested_project or "").strip()
        if project_name:
            st.session_state.current_project_name = project_name
            open_flow_page(
                "project_detail",
                data={"project_name": project_name, "module": "contract_management"},
                push_history=False,
            )
    st.query_params.clear()
    st.rerun()


# Legacy state bridge for existing sessions.
if st.session_state.get("show_new_app_modal"):
    del st.session_state["show_new_app_modal"]
    open_flow_page("new_application", data={}, push_history=False)
    st.rerun()
if st.session_state.get("active_modal_data"):
    legacy_dup = st.session_state.pop("active_modal_data")
    open_flow_page("duplicate_submission", data=legacy_dup, push_history=True)
    st.rerun()
if st.session_state.get("active_est_dlg"):
    legacy_group = st.session_state.pop("active_est_dlg")
    open_flow_page("estimate_group", data=legacy_group, push_history=False)
    st.rerun()
if st.session_state.get("trigger_new_app_from_modal"):
    del st.session_state["trigger_new_app_from_modal"]
    open_flow_page(
        "new_application",
        data={
            "module": "contract_management",
            "prefill_estimate_number": st.session_state.get("initial_estimate_number"),
            "prefill_year_of_estimate": normalize_year_option(st.session_state.get("initial_year_of_estimate")),
            "prefill_name_of_project": st.session_state.get("initial_name_of_project"),
        },
        push_history=False,
    )
    st.rerun()
if st.session_state.get("sub_to_view"):
    legacy_sub = st.session_state.pop("sub_to_view")
    st.session_state.pop("sub_view_mode", None)
    open_flow_page("submission_details", data={"sub": legacy_sub}, push_history=True)
    st.rerun()

if render_active_flow_page():
    render_footer()
    st.stop()


# =====================================================
# ================= USER SIDE =========================
# =====================================================
if not is_admin:

    current_view_key = st.session_state.current_view
    selected_module  = "Main" if current_view_key == "Main" else module_display_map.get(current_view_key, current_view_key)

    if "current_module" not in st.session_state:
        st.session_state.current_module = selected_module
    if st.session_state.current_module != selected_module:
        for key in list(st.session_state.keys()):
            if key.endswith("_initialized"):
                del st.session_state[key]
        st.session_state.current_module = selected_module

    # =========================================================
    # ==================== MAIN DASHBOARD =====================
    # =========================================================
    if selected_module == "Main":
        st.markdown('<div class="dashboard-no-padding-trigger"></div>', unsafe_allow_html=True)

        username_display = esc_html(st.session_state.username or "Officer")
        st.markdown(f"""
        <div class="welcome-hero">
            <div style="font-size:11px; font-weight:700; color:#9ca3af; letter-spacing:1.1px;
                        text-transform:uppercase; margin-bottom:8px;">
                Irrigation Department - Uttar Pradesh
            </div>
            <h1>Welcome, {username_display}</h1>
            <p>Contract Management Portal - manage your submissions from this central portal.</p>
        </div>
        """, unsafe_allow_html=True)

        draft_summaries = get_user_draft_summaries(user_id)

        if not modules:
            st.warning("**No modules have been assigned to your account yet.** Please contact your administrator.")

        show_estimate_data_on_dashboard = st.session_state.get("show_estimate_data_on_dashboard", False)
        if show_estimate_data_on_dashboard:
            # --- ACTIVITY SECTION ---
            st.markdown("""
            <div class="section-header">
                <h3>Your Activity &amp; Submissions</h3>
            </div>
            """, unsafe_allow_html=True)
    
            if "user_status_filter" not in st.session_state:
                st.session_state.user_status_filter = "ALL"
    
            raw_submissions = get_user_master_submissions(user_id, module=None)
            allowed_list    = st.session_state.get("allowed_modules","").split(",") if st.session_state.get("allowed_modules") else []
            submissions     = [s for s in raw_submissions if s.get("module") in allowed_list]
    
            draft_count     = len(draft_summaries)
            submitted_count = len(submissions)
            total_count     = submitted_count + draft_count
    
            if total_count == 0:
                st.markdown("""
                <div class="empty-state">
                    <div class="empty-icon">No Data</div>
                    <p>No applications yet.</p>
                    <small>Click "New Application" in the top navigation to get started.</small>
                </div>
                """, unsafe_allow_html=True)
            else:
                all_items = submissions + draft_summaries
                all_items.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
    
                render_metric_cards(total_count, submitted_count, draft_count,
                                    card_type="user")
    
            if submissions or draft_summaries:
                if st.session_state.user_status_filter == "COMPLETED":
                    raw_filtered = [s for s in all_items if s["status"] != "DRAFT"]
                elif st.session_state.user_status_filter == "DRAFT":
                    raw_filtered = [s for s in all_items if s["status"] == "DRAFT"]
                else:
                    raw_filtered = all_items
    
                # Group by estimate
                grouped_data = {}
                for item in raw_filtered:
                    e_no = item.get("estimate_number") or "---"
                    e_yr = item.get("year_of_estimate") or "---"
                    yr_val = getattr(e_yr, 'year', e_yr)
                    group_key = (str(e_no).strip().lower(), str(yr_val)) if e_no != "---" else (f"master_{item['id']}", None)
                    if group_key not in grouped_data:
                        grouped_data[group_key] = {
                            "estimate_number": e_no, "year_of_estimate": e_yr,
                            "latest_date": item.get("created_at"), "count": 1,
                            "module": item.get("module"), "sub": item
                        }
                    else:
                        grouped_data[group_key]["count"] += 1
                        if (item.get("created_at") or "") > (grouped_data[group_key]["latest_date"] or ""):
                            grouped_data[group_key]["latest_date"] = item.get("created_at")
    
                filtered_subs = sorted(grouped_data.values(), key=lambda x: str(x["latest_date"] or ""), reverse=True)
    
                if not filtered_subs:
                    label = st.session_state.user_status_filter.lower()
                    st.info(f"No {label} applications found." if label != "all" else "No applications found.")
                else:
                    paged_subs, start_idx, total_pages = paginate_list(filtered_subs, "dashboard_page", render_controls=False)
    
                    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    
                    # Table header
                    h1, h2, h3, h4, h5, h6 = st.columns([0.5, 3.0, 1.5, 2.3, 1.5, 1.2])
                    h1.markdown("**S.No**")
                    h2.markdown("**Estimate Number**")
                    h3.markdown("**Year**")
                    h4.markdown("**Last Updated**")
                    h5.markdown("**Applications**")
                    with h6:
                        st.markdown('<div class="rows-per-page" style="margin-bottom:0;text-align:right;">Rows</div>', unsafe_allow_html=True)
                        size_key = "dashboard_page_size"
                        new_size = st.selectbox("Size", [10,25,50,100],
                            index=[10,25,50,100].index(st.session_state.get(size_key,10)),
                            key="size_select_dashboard_inline", label_visibility="collapsed")
                        if new_size != st.session_state.get(size_key, 10):
                            st.session_state[size_key]     = new_size
                            st.session_state.dashboard_page = 1
                            st.rerun()
    
                    st.markdown("<hr style='margin:4px 0; border-color:#e5e8ef;'>", unsafe_allow_html=True)
    
                    for i, group in enumerate(paged_subs):
                        s_no      = start_idx + i + 1
                        est_no    = group["estimate_number"]
                        est_yr    = group["year_of_estimate"]
                        app_count = group["count"]
                        latest_dt = group["latest_date"]
    
                        r1, r2, r3, r4, r56 = st.columns([0.5, 3.0, 1.5, 2.3, 2.7])
                        r1.write(f"{s_no}")
                        with r2:
                            label_text = f"**{est_no}**" if (est_no and est_no != "---") else f"**{module_display_map.get(group.get('module'),'Draft')} (Draft)**"
                            if st.button(label_text, key=f"btn_grp_{i}_{est_no}", use_container_width=True):
                                open_flow_page(
                                    "estimate_group",
                                    data={
                                        "est_no": est_no,
                                        "est_yr": est_yr,
                                        "user_id": user_id,
                                        "module": group.get("module"),
                                    },
                                    push_history=False,
                                )
                                st.rerun()
                        with r3:
                            y_val = est_yr.year if hasattr(est_yr, 'year') else est_yr
                            st.write(str(y_val))
                        with r4:
                            st.write(fmt_dt(latest_dt))
                        with r56:
                            st.markdown(
                                f'<div class="apps-badge-static">{app_count} '
                                f'Application{"s" if app_count > 1 else ""}</div>',
                                unsafe_allow_html=True
                            )
                        st.markdown("<hr style='margin:6px 0; border:0; border-top:1px solid #f3f4f6;'>",
                                    unsafe_allow_html=True)
    
                    render_pagination_footer("dashboard_page", total_pages)

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        dashboard_projects = []
        if "contract_management" in modules:
            dashboard_projects = build_contract_project_catalog()
            mini_stats = get_contract_mini_dashboard_stats(dashboard_projects)

            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            selected_filter = str(st.session_state.get("mini_dashboard_filter", "DPR")).upper()
            if selected_filter not in {"DPR", "ESTIMATES", "PROJECTS", "CONTRACTS"}:
                selected_filter = "DPR"

            def _mini_card(title, value, filter_key):
                is_selected = selected_filter == filter_key
                border = "#1a3a6b" if is_selected else "#e5e8ef"
                bg = "#f8f9fc" if is_selected else "#fff"
                return (
                    f'<a href="./?mini_filter={filter_key}" target="_self" '
                    f'style="text-decoration:none; display:block;">'
                    f'<div style="padding:10px 12px;border:1px solid {border}; border-radius:8px; background:{bg};">'
                    f'<div style="font-size:11px;color:#6b7280;font-weight:700;">{esc_html(title)}</div>'
                    f'<div style="font-size:20px;color:#1a3a6b;font-weight:800;">{esc_html(value)}</div>'
                    f'</div></a>'
                )

            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.markdown(
                    _mini_card(
                        "DPR finished",
                        f'{mini_stats["dpr_completed"]}/{mini_stats["dpr_incomplete"]}',
                        "DPR",
                    ),
                    unsafe_allow_html=True,
                )
            with m2:
                st.markdown(
                    _mini_card(
                        "Estimates finished",
                        f'{mini_stats["estimates_completed"]}/{mini_stats["estimates_incomplete"]}',
                        "ESTIMATES",
                    ),
                    unsafe_allow_html=True,
                )
            with m3:
                st.markdown(
                    _mini_card(
                        "Projects",
                        f'{mini_stats["projects_completed"]}/{mini_stats["projects_incomplete"]}',
                        "PROJECTS",
                    ),
                    unsafe_allow_html=True,
                )
            with m4:
                st.markdown(
                    _mini_card(
                        "Contracts",
                        f'{mini_stats["contracts_completed"]}/{mini_stats["contracts_incomplete"]}',
                        "CONTRACTS",
                    ),
                    unsafe_allow_html=True,
                )

            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

        st.markdown("""
        <div class="section-header">
            <h3>Your Projects</h3>
        </div>
        """, unsafe_allow_html=True)

        if "contract_management" not in modules:
            st.info("Project list is available under Contract Management module.")
        else:
            filtered_dashboard_projects = list(dashboard_projects)
            selected_filter = str(st.session_state.get("mini_dashboard_filter", "DPR")).upper()
            if selected_filter not in {"DPR", "ESTIMATES", "PROJECTS", "CONTRACTS"}:
                selected_filter = "DPR"

            estimate_summary_map = {}
            for row in mini_stats.get("estimate_details") or []:
                pname_key = " ".join((row.get("Project Name") or "").split()).lower()
                if not pname_key:
                    continue
                bucket = estimate_summary_map.setdefault(pname_key, {"completed": 0, "incomplete": 0})
                if (row.get("Status") or "").lower() == "completed":
                    bucket["completed"] += 1
                else:
                    bucket["incomplete"] += 1

            contract_summary_map = {}
            for row in mini_stats.get("contract_details") or []:
                pname_key = " ".join((row.get("Project Name") or "").split()).lower()
                if not pname_key or pname_key == "-":
                    continue
                bucket = contract_summary_map.setdefault(pname_key, {"completed": 0, "incomplete": 0})
                if (row.get("Status") or "").lower() == "completed":
                    bucket["completed"] += 1
                else:
                    bucket["incomplete"] += 1

            project_status_map = {
                " ".join((r.get("Project Name") or "").split()).lower(): (r.get("Status") or "Incomplete")
                for r in (mini_stats.get("project_details") or [])
            }

            if selected_filter == "ESTIMATES":
                filtered_dashboard_projects = [
                    p for p in filtered_dashboard_projects
                    if sum(estimate_summary_map.get(" ".join((p.get("project_name") or "").split()).lower(), {}).values()) > 0
                ]
            elif selected_filter == "CONTRACTS":
                filtered_dashboard_projects = [
                    p for p in filtered_dashboard_projects
                    if sum(contract_summary_map.get(" ".join((p.get("project_name") or "").split()).lower(), {}).values()) > 0
                ]
            elif selected_filter == "PROJECTS":
                filtered_dashboard_projects.sort(
                    key=lambda p: (
                        0
                        if project_status_map.get(" ".join((p.get("project_name") or "").split()).lower()) == "Completed"
                        else 1,
                        str(p.get("project_name") or "").lower(),
                    )
                )

            filter_label = {
                "DPR": "All Projects",
                "ESTIMATES": "Projects With Estimates",
                "PROJECTS": "Project Completion View",
                "CONTRACTS": "Projects With Contracts",
            }.get(selected_filter, "All Projects")
            st.markdown(
                f"<div style='font-size:12px;color:#6b7280;margin:0 0 8px 0;'>View: <b>{esc_html(filter_label)}</b></div>",
                unsafe_allow_html=True,
            )

            if not filtered_dashboard_projects:
                if dashboard_projects:
                    st.info("No projects match the selected mini dashboard filter.")
                else:
                    st.info("No projects created yet. Use Start New Project to add your first project.")
            else:
                paged_projects, start_idx, total_pages = paginate_list(
                    filtered_dashboard_projects, "dashboard_projects_page", render_controls=False
                )

                h1, h2, h3, h4, h5 = st.columns([0.6, 3.8, 1.6, 2.0, 1.2])
                h1.markdown("**S.No**")
                h2.markdown("**Project Name**")
                if selected_filter == "CONTRACTS":
                    h3.markdown("**Contracts (C/I)**")
                    h4.markdown("**Contract Status**")
                elif selected_filter == "ESTIMATES":
                    h3.markdown("**Estimates (C/I)**")
                    h4.markdown("**Estimate Status**")
                elif selected_filter == "PROJECTS":
                    h3.markdown("**Estimates**")
                    h4.markdown("**Project Status**")
                else:
                    h3.markdown("**Estimates**")
                    h4.markdown("**DPR Status**")
                with h5:
                    st.markdown('<div class="rows-per-page" style="margin-bottom:0;text-align:right;">Rows</div>', unsafe_allow_html=True)
                    size_key = "dashboard_projects_page_size"
                    new_size = st.selectbox(
                        "Size",
                        [10, 25, 50, 100],
                        index=[10, 25, 50, 100].index(st.session_state.get(size_key, 10)),
                        key="size_select_dashboard_projects_inline",
                        label_visibility="collapsed",
                    )
                    if new_size != st.session_state.get(size_key, 10):
                        st.session_state[size_key] = new_size
                        st.session_state.dashboard_projects_page = 1
                        st.rerun()

                st.markdown("<hr style='margin:4px 0; border-color:#e5e8ef;'>", unsafe_allow_html=True)

                for i, proj in enumerate(paged_projects):
                    project_name = proj.get("project_name", "")
                    estimate_count = int(proj.get("estimate_count") or 0)
                    project_dpr = get_project_dpr(user_id, project_name, module="contract_management")
                    has_dpr = bool(project_dpr)
                    project_key = " ".join((project_name or "").split()).lower()
                    est_counts = estimate_summary_map.get(project_key, {"completed": 0, "incomplete": 0})
                    contract_counts = contract_summary_map.get(project_key, {"completed": 0, "incomplete": 0})
                    project_status = project_status_map.get(project_key, "Incomplete")
                    s_no = start_idx + i + 1

                    r1, r2, r3, r4 = st.columns([0.6, 3.8, 1.6, 2.0])
                    r1.write(str(s_no))
                    with r2:
                        project_href = f'./?dash_project={quote(str(project_name))}'
                        st.markdown(
                            f'<a href="{project_href}" target="_self" class="dashboard-project-link">{esc_html(project_name)}</a>',
                            unsafe_allow_html=True,
                        )
                    if selected_filter == "CONTRACTS":
                        r3.write(f'{contract_counts["completed"]}/{contract_counts["incomplete"]}')
                    elif selected_filter == "ESTIMATES":
                        r3.write(f'{est_counts["completed"]}/{est_counts["incomplete"]}')
                    else:
                        r3.write(str(estimate_count))

                    if selected_filter == "PROJECTS":
                        with r4:
                            if project_status == "Completed":
                                st.markdown(
                                    '<span style="background:#ecfdf5; color:#065f46; border:1px solid #a7f3d0; '
                                    'padding:2px 10px; border-radius:4px; font-size:11px; font-weight:700;">Completed</span>',
                                    unsafe_allow_html=True,
                                )
                            else:
                                st.markdown(
                                    '<span style="background:#fffbeb; color:#92400e; border:1px solid #fcd34d; '
                                    'padding:2px 10px; border-radius:4px; font-size:11px; font-weight:700;">Incomplete</span>',
                                    unsafe_allow_html=True,
                                )
                    elif selected_filter == "CONTRACTS":
                        with r4:
                            if contract_counts["incomplete"] == 0 and (contract_counts["completed"] > 0):
                                st.markdown(
                                    '<span style="background:#ecfdf5; color:#065f46; border:1px solid #a7f3d0; '
                                    'padding:2px 10px; border-radius:4px; font-size:11px; font-weight:700;">Completed</span>',
                                    unsafe_allow_html=True,
                                )
                            else:
                                st.markdown(
                                    '<span style="background:#fffbeb; color:#92400e; border:1px solid #fcd34d; '
                                    'padding:2px 10px; border-radius:4px; font-size:11px; font-weight:700;">Incomplete</span>',
                                    unsafe_allow_html=True,
                                )
                    elif selected_filter == "ESTIMATES":
                        with r4:
                            if est_counts["incomplete"] == 0 and (est_counts["completed"] > 0):
                                st.markdown(
                                    '<span style="background:#ecfdf5; color:#065f46; border:1px solid #a7f3d0; '
                                    'padding:2px 10px; border-radius:4px; font-size:11px; font-weight:700;">Completed</span>',
                                    unsafe_allow_html=True,
                                )
                            else:
                                st.markdown(
                                    '<span style="background:#fffbeb; color:#92400e; border:1px solid #fcd34d; '
                                    'padding:2px 10px; border-radius:4px; font-size:11px; font-weight:700;">Incomplete</span>',
                                    unsafe_allow_html=True,
                                )
                    elif has_dpr:
                        with r4:
                            dpr_status_col, dpr_action_col = st.columns([1.0, 1.35])
                            with dpr_status_col:
                                st.markdown(
                                    '<span style="background:#ecfdf5; color:#065f46; border:1px solid #a7f3d0; '
                                    'padding:2px 8px; border-radius:4px; font-size:10.5px; font-weight:700;">Available</span>',
                                    unsafe_allow_html=True,
                                )
                            with dpr_action_col:
                                view_dpr_href = f'./?dash_action=view_dpr&dash_project={quote(str(project_name))}'
                                st.markdown(
                                    f'<a href="{view_dpr_href}" target="_self" class="dashboard-project-link">View DPR</a>',
                                    unsafe_allow_html=True,
                                )
                    else:
                        with r4:
                            dpr_status_col, dpr_action_col = st.columns([1.0, 1.35])
                            with dpr_status_col:
                                st.markdown(
                                    '<span style="background:#fffbeb; color:#92400e; border:1px solid #fcd34d; '
                                    'padding:2px 8px; border-radius:4px; font-size:10.5px; font-weight:700;">Pending</span>',
                                    unsafe_allow_html=True,
                                )
                            with dpr_action_col:
                                fill_dpr_href = f'./?dash_action=fill_dpr&dash_project={quote(str(project_name))}'
                                st.markdown(
                                    f'<a href="{fill_dpr_href}" target="_self" class="dashboard-project-link">Fill DPR</a>',
                                    unsafe_allow_html=True,
                                )

                    st.markdown("<hr style='margin:6px 0; border:0; border-top:1px solid #f3f4f6;'>", unsafe_allow_html=True)

                render_pagination_footer("dashboard_projects_page", total_pages)

        render_footer()
        st.stop()

    # =========================================================
    # ================== MODULE FORM VIEW =====================
    # =========================================================

    CUSTOM_TABLE_ORDER = {
        "contract_management": [
            "contract_management_admin_financial_sanction",
            "contract_management_technical_sanction",
            "contract_management_tender_award_contract",
            "contract_management_contract_master",
            "contract_management_payments_recoveries",
            "contract_management_budget_summary",
        ]
    }

    module_name = current_view_key
    if module_name in CUSTOM_TABLE_ORDER:
        ordered = [t for t in CUSTOM_TABLE_ORDER[module_name] if t in modules.get(module_name, [])]
        others  = sorted([t for t in modules.get(module_name, []) if t not in CUSTOM_TABLE_ORDER[module_name]])
        tables  = ordered + others
    else:
        tables = sorted(modules.get(module_name, []))

    prefix = module_name + "_"

    can_edit = can_user_edit(st.session_state.master_id) if st.session_state.master_id else True

    percentage, completed, total = get_user_progress(user_id, tables, master_id=st.session_state.master_id)

    back_col, _ = st.columns([1.3, 6])
    with back_col:
        if st.button("<- Back", key=f"back_module_{module_name}", use_container_width=True):
            if restore_module_return_flow():
                st.rerun()
            st.session_state.current_view = "Main"
            st.rerun()

    # --- Module header ---
    st.markdown(f"""
    <div style="margin-bottom:20px;">
        <div style="font-size:11px; font-weight:700; color:#9ca3af; letter-spacing:1px;
                    text-transform:uppercase; margin-bottom:6px;">
            Module
        </div>
        <h2 style="margin:0; font-size:22px; font-weight:800; color:#1a3a6b;">{selected_module}</h2>
        <p style="margin:4px 0 0; color:#6b7280; font-size:13.5px;">
            Fill in all sections below to complete your audit application.
        </p>
    </div>
    """, unsafe_allow_html=True)

    prog_color = "#dc2626" if percentage < 40 else ("#d97706" if percentage < 75 else "#059669")

    st.markdown(f"""
    <div class="progress-wrapper">
        <div class="progress-label">Application Progress</div>
        <div class="progress-pct">{percentage:.0f}% Complete</div>
        <div class="custom-progress">
            <div class="custom-progress-fill" style="width:{percentage}%; background:{prog_color};"></div>
        </div>
        <div style="margin-top:8px; font-size:12px; color:#9ca3af;">
            {completed} of {total} sections filled in
        </div>
    </div>
    """, unsafe_allow_html=True)

    if percentage == 100:
        st.markdown("""
        <div class="completion-banner">
            <h3>All Sections Complete!</h3>
            <p>Scroll down to review and submit your complete application.</p>
        </div>
        """, unsafe_allow_html=True)

    # --- Tabs ---
    tab_labels = []
    for table in tables:
        section_name = table.replace(prefix, "").replace("_", " ").title()
        is_complete  = is_section_complete(user_id, table, master_id=st.session_state.master_id)
        tab_labels.append(f"🟢 {section_name}" if is_complete else f"🟡 {section_name}")

    tabs = st.tabs(tab_labels)

    first_table      = tables[0]
    first_table_draft = get_user_draft(first_table, user_id, master_id=st.session_state.master_id)

    estimate_number = name_of_project = year_of_estimate = None

    if first_table_draft:
        estimate_number  = first_table_draft.get("estimate_number")
        year_of_estimate = first_table_draft.get("year_of_estimate")
        name_of_project  = first_table_draft.get("name_of_project")
    elif st.session_state.get("master_id"):
        master_rec = get_master_submission(st.session_state.master_id)
        if master_rec:
            estimate_number  = master_rec.get("estimate_number")
            year_of_estimate = master_rec.get("year_of_estimate")
            name_of_project  = master_rec.get("name_of_project")
            if not name_of_project:
                alt_subs = get_submissions_by_estimate(estimate_number, year_of_estimate)
                for alt_s in alt_subs:
                    if alt_s.get("name_of_project"):
                        name_of_project = alt_s.get("name_of_project")
                        break

    if not estimate_number:
        estimate_number  = st.session_state.get("initial_estimate_number")
    if not year_of_estimate:
        year_of_estimate = st.session_state.get("initial_year_of_estimate")
    if not name_of_project:
        name_of_project  = st.session_state.get("initial_name_of_project")

    for i, table in enumerate(tables):
        with tabs[i]:
            is_master_form = (table == first_table)
            columns        = get_table_columns(table, is_admin=False)

            if table != first_table and not first_table_draft:
                st.markdown("""
                <div class="section-helper">
                    <b>Please complete the first section first.</b><br>
                    You must save the first section before proceeding.
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="section-helper">
                    <b>How to fill this section:</b> Fill all fields below then click
                    <b>Save Section</b> at the bottom. You can edit any time before submitting.
                </div>
                """, unsafe_allow_html=True)

            # Initialize session state once
            if f"{table}_initialized" not in st.session_state:
                draft = get_user_draft(table, user_id, master_id=st.session_state.master_id)
                for col_info in columns:
                    col   = col_info["column_name"]
                    dtype = col_info["data_type"]
                    key   = f"{table}_{col}"
                    use_date_picker = is_date_picker_field(col, dtype)
                    if draft and col in draft and draft[col] is not None:
                        val = draft[col]
                        if use_date_picker:
                            val = parse_date_for_input(val)
                        elif dtype in ("integer","bigint","smallint"):
                            try: val = int(val)
                            except (TypeError, ValueError): val = 0
                        elif dtype in ("numeric","double precision","real"):
                            try: val = float(val)
                            except (TypeError, ValueError): val = 0.0
                        elif dtype == "date":
                            if isinstance(val, datetime.datetime): val = val.date()
                            elif isinstance(val, str):
                                try: val = datetime.date.fromisoformat(val[:10])
                                except (TypeError, ValueError): val = None
                            if col == "year_of_estimate" and val:
                                val = val.year if hasattr(val,'year') else val
                        else:
                            val = str(val)
                        if col == "year_of_estimate" and "-" in str(val) and len(str(val)) > 7:
                            try:
                                y   = int(str(val).split("-")[0])
                                val = f"{y}-{str(y+1)[2:]}"
                            except (TypeError, ValueError):
                                pass
                        st.session_state[key] = val
                    else:
                        if use_date_picker:
                            st.session_state.setdefault(key, None)
                        elif dtype in ("integer","bigint","smallint"):
                            st.session_state.setdefault(key, 0)
                        elif dtype in ("numeric","double precision","real"):
                            st.session_state.setdefault(key, 0.0)
                        elif dtype == "date":
                            st.session_state.setdefault(key, None)
                        else:
                            st.session_state.setdefault(key, "")
                        if is_master_form and not draft:
                            if col == "estimate_number" and estimate_number:
                                st.session_state[key] = str(estimate_number)
                            elif col == "year_of_estimate" and year_of_estimate:
                                st.session_state[key] = year_of_estimate
                            elif col == "name_of_project" and name_of_project:
                                st.session_state[key] = str(name_of_project)
                st.session_state[f"{table}_initialized"] = True

            form_data    = {}
            filled_fields = 0

            # ---- FIRST TAB: inside st.form ----
            if table == first_table:
                with st.form(f"form_{table}"):
                    col1, col2 = st.columns(2)
                    filled_fields = 0
                    for index, col_info in enumerate(columns):
                        col   = col_info["column_name"]
                        if col in ["estimate_number","year_of_estimate","name_of_project"] and module_name != "contract_management":
                            continue
                        dtype = col_info["data_type"]
                        key   = f"{table}_{col}"
                        use_date_picker = is_date_picker_field(col, dtype)
                        target_col = col1 if index % 2 == 0 else col2
                        with target_col:
                            label = col.replace("_"," ").title()
                            if any(w in col.lower() for w in money_keywords):
                                label = f"{label} (INR)"
                            is_disabled = (module_name == "contract_management" and
                                           col in ["estimate_number","year_of_estimate","name_of_project"])
                            if dtype in ("integer","bigint","smallint"):
                                value = st.number_input(label, step=1, key=key, disabled=is_disabled)
                            elif dtype in ("numeric","double precision","real"):
                                value = st.number_input(label, key=key, disabled=is_disabled)
                            elif use_date_picker:
                                value = st.date_input(label, key=key, disabled=is_disabled)
                            elif dtype == "date":
                                if col == "year_of_estimate":
                                    cy = datetime.datetime.now().year
                                    yo = [f"{y}-{str(y+1)[2:]}" for y in range(cy,1999,-1)]
                                    value = st.selectbox(label, options=yo, key=key, disabled=is_disabled)
                                else:
                                    value = st.date_input(label, key=key, disabled=is_disabled)
                            elif dtype in ("boolean","bool"):
                                bool_options = ["","Yes","No"]
                                curr_val = st.session_state.get(key)
                                idx = 0
                                if curr_val is True  or str(curr_val).lower()=="true":  idx = 1
                                if curr_val is False or str(curr_val).lower()=="false": idx = 2
                                sel = st.selectbox(label, options=bool_options, index=idx,
                                                   key=f"{key}_select", disabled=is_disabled)
                                value = True if sel=="Yes" else (False if sel=="No" else None)
                            else:
                                value = st.text_input(label, key=key, disabled=is_disabled)
                        form_data[col] = value
                        if col not in ["estimate_number","year_of_estimate","name_of_project"] \
                                and value not in ("",None,0,0.0):
                            filled_fields += 1

                    submitted = st.form_submit_button("Save Section", use_container_width=True, type="primary")

                if submitted:
                    for col_info in columns:
                        if col_info["is_nullable"] == "NO":
                            col_name = col_info["column_name"]
                            val      = form_data.get(col_name)
                            if val in (None,"",0,0.0):
                                st.error(f"{col_name.replace('_',' ').title()} is required.")
                                st.stop()
                    if filled_fields == 0:
                        st.warning("Please fill in at least one field before saving.")
                        st.stop()
                    if module_name == "contract_management":
                        for req_col in ["estimate_number","year_of_estimate","name_of_project"]:
                            if req_col in form_data and form_data.get(req_col) in (None,"",0,0.0):
                                st.error(f"{req_col.replace('_',' ').title()} is required.")
                                st.stop()

                    form_data = serialize_date_fields_as_text(form_data, columns)

                    target_master_id = st.session_state.master_id
                    if target_master_id is None:
                        try:
                            target_master_id = create_master_submission(
                                user_id, module_name, tables, status='DRAFT',
                                estimate_number=estimate_number,
                                year_of_estimate=year_of_estimate)
                        except ValueError as ve:
                            st.error(f"**Duplicate Application Found:** {str(ve)}")
                            st.stop()
                        except Exception as e:
                            report_error("Failed to create application.", e, "app.save_first_section.create")
                            st.stop()

                    try:
                        save_draft_record(table, form_data, user_id, master_id=target_master_id)
                        if table == tables[0]:
                            update_master_submission(target_master_id,
                                estimate_number=form_data.get("estimate_number"),
                                year_of_estimate=form_data.get("year_of_estimate"),
                                name_of_project=form_data.get("name_of_project"))
                        st.session_state.master_id = target_master_id
                        st.success("Section saved successfully!")
                        st.toast("Application saved to drafts.")
                        st.rerun()
                    except Exception as e:
                        report_error("Failed to save section.", e, "app.save_first_section")
                        st.stop()

            # ---- OTHER TABS ----
            else:
                col1, col2 = st.columns(2)
                for index, col_info in enumerate(columns):
                    col   = col_info["column_name"]
                    dtype = col_info["data_type"]
                    key   = f"{table}_{col}"
                    use_date_picker = is_date_picker_field(col, dtype)
                    target_col = col1 if index % 2 == 0 else col2
                    with target_col:
                        label = col.replace("_"," ").title()
                        if any(w in col.lower() for w in money_keywords):
                            label = f"{label} (INR)"
                        if col in ["estimate_number","year_of_estimate","name_of_project"]:
                            value = (estimate_number if col=="estimate_number"
                                     else (name_of_project if col=="name_of_project"
                                           else year_of_estimate))
                            display_key = f"display_{table}_{col}"
                            st.session_state[display_key] = str(value) if value is not None else ""
                            st.text_input(label, disabled=True, key=display_key)
                            form_data[col] = value
                            continue
                        if dtype in ("integer","bigint","smallint"):
                            value = st.number_input(label, step=1, key=key)
                        elif dtype in ("numeric","double precision","real"):
                            value = st.number_input(label, key=key)
                        elif use_date_picker:
                            value = st.date_input(label, key=key)
                        elif dtype == "date":
                            if col == "year_of_estimate":
                                cy = datetime.datetime.now().year
                                yo = list(range(cy, 1999, -1))
                                value = st.selectbox(label, options=yo, key=key)
                            else:
                                value = st.date_input(label, key=key)
                        elif dtype in ("boolean","bool"):
                            bool_options = ["","Yes","No"]
                            curr_val = st.session_state.get(key)
                            idx = 0
                            if curr_val is True  or str(curr_val).lower()=="true":  idx = 1
                            if curr_val is False or str(curr_val).lower()=="false": idx = 2
                            sel = st.selectbox(label, options=bool_options, index=idx, key=f"{key}_select")
                            value = True if sel=="Yes" else (False if sel=="No" else None)
                        else:
                            value = st.text_input(label, key=key)

                    form_data[col] = value
                    if col == "year_of_estimate" and isinstance(value, int):
                        form_data[col] = datetime.date(value, 1, 1)
                    if col not in ["estimate_number","year_of_estimate"] and value not in ("",None,0,0.0):
                        filled_fields += 1

                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

                if st.button("Save Section", key=f"save_{table}", use_container_width=True, type="primary"):
                    if not first_table_draft:
                        st.warning("Please complete the first section before saving this one.")
                        st.stop()
                    if not can_edit:
                        st.warning("This application has been submitted and cannot be edited.")
                    elif filled_fields == 0:
                        st.warning("Please fill in at least one field before saving.")
                    else:
                        table_col_names = [c["column_name"] for c in columns]
                        if "estimate_number"  in table_col_names: form_data["estimate_number"]  = estimate_number
                        if "year_of_estimate" in table_col_names: form_data["year_of_estimate"] = year_of_estimate
                        if "name_of_project"  in table_col_names: form_data["name_of_project"]  = name_of_project

                        form_data = serialize_date_fields_as_text(form_data, columns)

                        target_master_id = st.session_state.master_id
                        if target_master_id is None:
                            try:
                                target_master_id = create_master_submission(
                                    user_id, module_name, tables, status='DRAFT',
                                    estimate_number=estimate_number,
                                    year_of_estimate=year_of_estimate)
                            except Exception as e:
                                err = str(e).lower()
                                if "unique_estimate" in err or "duplicate key" in err:
                                    st.error(f"An application with Estimate **{estimate_number}** already exists.")
                                else:
                                    report_error("Failed to create application.", e, "app.save_other_section.create")
                                st.stop()

                        try:
                            save_draft_record(table, form_data, user_id, master_id=target_master_id)
                            if table == tables[0]:
                                update_master_submission(target_master_id,
                                    estimate_number=form_data.get("estimate_number"),
                                    year_of_estimate=form_data.get("year_of_estimate"),
                                    name_of_project=form_data.get("name_of_project"))
                            st.session_state.master_id = target_master_id
                            st.success("Section saved successfully!")
                            st.toast("Application saved to drafts.")
                            st.rerun()
                        except Exception as e:
                            report_error("Failed to save section.", e, "app.save_other_section")
                            st.stop()

    # =========================================================
    # ================== FINAL SUBMIT =========================
    # =========================================================
    master_id_active = st.session_state.get("master_id")
    incomplete_sections = []
    if master_id_active:
        incomplete_sections = get_incomplete_forms(user_id, tables, master_id=master_id_active)
    else:
        incomplete_sections = tables

    if master_id_active:
        st.markdown("""
        <div class="submit-cta">
            <h3> Ready to Submit Your Application?</h3>
            <p>Once all sections are complete, submit your full application for review.</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    if incomplete_sections:
        st.error("**The following sections still need to be completed before submission:**")
        for idx, sec in enumerate(incomplete_sections, 1):
            clean_name = sec.replace(prefix,"").replace("_"," ").title()
            st.markdown(f"&nbsp;&nbsp;&nbsp;**{idx}.** {clean_name}")
    else:
        st.markdown("""
        <div class="submit-cta" style="background:#fffbeb; border-top-color:#d97706;">
            <h3 style="color:#92400e;">Required Attachments</h3>
            <p>Upload the mandatory documents below to enable final submission.</p>
        </div>
        """, unsafe_allow_html=True)

        col_u1, col_u2 = st.columns(2)
        m_id        = st.session_state.master_id
        master_info = get_master_submission(m_id)
        existing_est = master_info.get("estimate_attachment")
        existing_sar = master_info.get("sar_attachment")

        def clean(s): return "".join([c if c.isalnum() or c in ('-','_') else '_' for c in str(s)])

        with col_u1:
            if existing_est:
                st.success(f"Estimate Uploaded: `{os.path.basename(existing_est)}`")
            est_file = st.file_uploader("Upload Estimate",
                type=['pdf','docx','xlsx','jpg','png'], key="uploader_estimate")
            if est_file:
                fid = f"{est_file.name}_{est_file.size}"
                if st.session_state.get("last_est_id") != fid:
                    full_data = get_full_submission_data(m_id)
                    sub_data  = full_data.get(tables[0] if tables else None)
                    if sub_data is not None and not sub_data.empty:
                        tr = sub_data.iloc[0]
                        en = clean(tr.get("estimate_number",  master_info.get("estimate_number","NA")))
                        pn = clean(tr.get("name_of_project",  master_info.get("name_of_project","NA")))
                        ey = clean(tr.get("year_of_estimate", master_info.get("year_of_estimate","NA")))
                    else:
                        en = clean(master_info.get("estimate_number","NA"))
                        pn = clean(master_info.get("name_of_project","NA"))
                        ey = clean(master_info.get("year_of_estimate","NA"))
                    ext   = os.path.splitext(est_file.name)[1]
                    spath = os.path.join("uploads", f"Estimate_{en}_{pn}_{ey}{ext}")
                    with open(spath,"wb") as f: f.write(est_file.getbuffer())
                    update_master_attachments(m_id, estimate_path=spath)
                    st.session_state["last_est_id"] = fid
                    st.rerun()

        with col_u2:
            if existing_sar:
                st.success(f"SAR Uploaded: `{os.path.basename(existing_sar)}`")
            sar_file = st.file_uploader("Upload SAR",
                type=['pdf','docx','xlsx','jpg','png'], key="uploader_sar")
            if sar_file:
                fid = f"{sar_file.name}_{sar_file.size}"
                if st.session_state.get("last_sar_id") != fid:
                    full_data = get_full_submission_data(m_id)
                    sub_data  = full_data.get(tables[0] if tables else None)
                    if sub_data is not None and not sub_data.empty:
                        tr = sub_data.iloc[0]
                        en = clean(tr.get("estimate_number",  master_info.get("estimate_number","NA")))
                        pn = clean(tr.get("name_of_project",  master_info.get("name_of_project","NA")))
                        ey = clean(tr.get("year_of_estimate", master_info.get("year_of_estimate","NA")))
                    else:
                        en = clean(master_info.get("estimate_number","NA"))
                        pn = clean(master_info.get("name_of_project","NA"))
                        ey = clean(master_info.get("year_of_estimate","NA"))
                    ext   = os.path.splitext(sar_file.name)[1]
                    spath = os.path.join("uploads", f"SAR_{en}_{pn}_{ey}{ext}")
                    with open(spath,"wb") as f: f.write(sar_file.getbuffer())
                    update_master_attachments(m_id, sar_path=spath)
                    st.session_state["last_sar_id"] = fid
                    st.rerun()

        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        if st.button(" Submit My Complete Application", use_container_width=True, type="primary"):
            success = update_master_status(st.session_state.master_id, 'COMPLETED')
            if success:
                set_drafts_to_final(st.session_state.master_id, tables)
                st.balloons()
                st.success("Application Submitted Successfully!")
                st.session_state.master_id    = None
                st.session_state.current_view = "Main"
                st.rerun()


# =====================================================
# ================= ADMIN SIDE ========================
# =====================================================
if is_admin:

    if "status_filter" not in st.session_state:
        st.session_state.status_filter = "ALL"

    st.markdown("""
    <div class="hero-banner">
        <h1>Admin Review Panel</h1>
        <p>Review submitted applications, manage user accounts, and export audit reports.</p>
    </div>
    """, unsafe_allow_html=True)

    tab_review, tab_users, tab_manage_users = st.tabs([
        "Review Applications", "Create User", "Manage Users"
    ])

    # ---- CREATE USER ----
    with tab_users:
        st.markdown("### Create New User")
        st.markdown("Create a new applicant account. Usernames must be unique.")
        with st.form("create_user_form", clear_on_submit=True):
            new_username = st.text_input("Username")
            new_password = st.text_input("Password", type="password")
            new_role     = st.selectbox("Role", options=["operator","admin"],
                format_func=lambda x: "Administrator" if x=="admin" else "Operator")
            selected_mods = st.multiselect("Allowed Modules",
                options=list(all_modules.keys()),
                format_func=lambda x: all_module_display_map.get(x,x))
            submit_user = st.form_submit_button("Create User", type="primary")
            if submit_user:
                if not new_username.strip() or not new_password.strip():
                    st.error("Username and Password cannot be empty.")
                else:
                    modules_str = ",".join(selected_mods)
                    success, msg = create_user(new_username.strip(), new_password.strip(),
                                               role=new_role, allowed_modules=modules_str)
                    if success: st.success(f"{msg}")
                    else:       st.error(f"{msg}")

    # ---- MANAGE USERS ----
    with tab_manage_users:
        st.markdown("### Manage Existing Users")
        st.markdown("View all users and update their access and module permissions.")

        raw_users_df = get_all_users_admin()
        if not raw_users_df.empty:
            users_list  = raw_users_df.to_dict('records')
            paged_users, start_idx, total_pages = paginate_list(users_list, "manage_users_page", render_controls=False)

            c1, c2, c3, c4, c5, c6 = st.columns([0.5, 2, 1.5, 1.5, 3.5, 1.5])
            c1.markdown("**S.No**"); c2.markdown("**Username**"); c3.markdown("**Role**")
            c4.markdown("**Status**"); c5.markdown("**Allowed Modules**"); c6.markdown("**Action**")
            st.markdown("<hr style='margin:0; padding:0;'>", unsafe_allow_html=True)

            def update_user_per_callback(uid, session_key):
                if (st.session_state.get('logging_out') or
                        not st.session_state.get('logged_in') or
                        st.session_state.get('role') != 'admin'):
                    return
                new_mods = st.session_state.get(session_key, [])
                update_user_modules(uid, new_mods)
                st.toast(f"Permissions updated for user ID: {uid}")

            for i, row_usr in enumerate(paged_users):
                uid         = row_usr['id']
                uname       = row_usr['username']
                urole       = row_usr['role']
                is_active   = row_usr.get('is_active', True)
                allowed_str = row_usr.get('allowed_modules','')
                safe_uname = esc_html(uname)
                current_allowed = allowed_str.split(',') if allowed_str else []
                s_no = start_idx + i + 1

                cc1, cc2, cc3, cc4, cc5, cc6 = st.columns([0.5, 2, 1.5, 1.5, 3.5, 1.5])
                with cc1:
                    st.markdown(f"<div style='padding-top:10px;'>{s_no}</div>", unsafe_allow_html=True)
                with cc2:
                    st.markdown(f"<div style='padding-top:10px;'><b>{safe_uname}</b></div>", unsafe_allow_html=True)
                with cc3:
                    st.markdown(f"<div style='padding-top:10px;'>{'Administrator' if urole=='admin' else 'Operator'}</div>",
                                unsafe_allow_html=True)
                with cc4:
                    if is_active:
                        st.markdown("<div style='padding-top:10px;color:#059669;font-weight:700;'>Active</div>",
                                    unsafe_allow_html=True)
                    else:
                        st.markdown("<div style='padding-top:10px;color:#dc2626;font-weight:700;'>Revoked</div>",
                                    unsafe_allow_html=True)
                with cc5:
                    if urole != 'admin':
                        st.multiselect("Modules",
                            options=list(all_modules.keys()),
                            default=[m for m in current_allowed if m in all_modules],
                            format_func=lambda x: all_module_display_map.get(x,x),
                            key=f"mods_inline_{uid}",
                            label_visibility="collapsed",
                            on_change=update_user_per_callback,
                            args=(uid, f"mods_inline_{uid}"))
                    else:
                        st.markdown("<div style='padding-top:10px;color:#9ca3af;font-style:italic;'>Full Access</div>",
                                    unsafe_allow_html=True)
                with cc6:
                    if st.session_state.user_id == uid:
                        st.button("Self", disabled=True, key=f"btn_{uid}", use_container_width=True)
                    elif urole == 'admin':
                        st.button("Admin", disabled=True, key=f"btn_admin_{uid}", use_container_width=True)
                    else:
                        btn_label = "Revoke" if is_active else "Grant"
                        btn_type  = "secondary" if is_active else "primary"
                        if st.button(btn_label, key=f"btn_toggle_{uid}", type=btn_type, use_container_width=True):
                            toggle_user_status(uid, is_active)
                            st.rerun()
                st.markdown("<hr style='margin:0; padding:0;'>", unsafe_allow_html=True)

            render_pagination_footer("manage_users_page", total_pages)

    # ---- REVIEW APPLICATIONS ----
    with tab_review:
        all_users_df = get_all_users_admin()
        users_df     = all_users_df[all_users_df["role"] != "admin"]

        if users_df.empty:
            st.markdown("""
            <div class="empty-state">
                <div class="empty-icon">Users</div>
                <p>No applicant accounts found.</p>
                <small>Create a user account in the 'Create User' tab first.</small>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("#### Select an Applicant to Review")
            applicant_options = ["--- Select Applicant ---", "All Users"] + list(users_df["username"])
            selected_user = st.selectbox("Applicant", applicant_options,
                label_visibility="collapsed",
                help="Choose 'All Users' to see every submission, or pick a specific applicant")

            if selected_user != "--- Select Applicant ---":
                if "prev_selected_user" not in st.session_state:
                    st.session_state.prev_selected_user = selected_user
                if st.session_state.prev_selected_user != selected_user:
                    st.session_state.admin_review_page  = 1
                    st.session_state.prev_selected_user = selected_user

                is_all_users = (selected_user == "All Users")

                if not is_all_users:
                    user_row         = users_df[users_df["username"]==selected_user].iloc[0]
                    selected_user_id = int(user_row["id"])

                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

                if is_all_users:
                    all_masters = []
                    all_drafts  = []
                    agg_pending = agg_drafts = 0
                    for _, u_row in users_df.iterrows():
                        uid   = int(u_row["id"])
                        uname = u_row["username"]
                        u_submitted, u_drafts = get_user_master_status_counts(uid, all_modules)
                        agg_pending += u_submitted
                        agg_drafts  += u_drafts
                        u_masters = get_user_master_submissions_admin(uid)
                        all_masters.extend(u_masters)
                        u_draft_sums = get_user_draft_summaries(uid)
                        for d in u_draft_sums: d["created_by_user"] = uname
                        all_drafts.extend(u_draft_sums)

                    total       = agg_pending + agg_drafts
                    submitted   = agg_pending
                    submissions = all_masters + all_drafts
                    submissions.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)

                    st.markdown("#### Submission Overview - All Users")
                    if total == 0:
                        st.markdown("""<div class="empty-state"><div class="empty-icon">Search</div>
                            <p>No applications found.</p></div>""", unsafe_allow_html=True)
                    else:
                        render_metric_cards(total, submitted, agg_drafts,
                                            card_type="admin")
                else:
                    submitted, drafts = get_user_master_status_counts(selected_user_id, all_modules)
                    total = submitted + drafts
                    selected_user_safe = esc_html(selected_user)
                    st.markdown(f"#### Submission Overview - {selected_user_safe}")
                    if total == 0:
                        st.markdown(f"""<div class="empty-state"><div class="empty-icon">Search</div>
                            <p>No activity found for <b>{selected_user_safe}</b>.</p></div>""",
                            unsafe_allow_html=True)
                    else:
                        render_metric_cards(total, submitted, drafts,
                                            card_type="admin")
                    masters       = get_user_master_submissions_admin(selected_user_id)
                    draft_summaries = get_user_draft_summaries(selected_user_id)
                    for d in draft_summaries: d["created_by_user"] = selected_user
                    submissions   = masters + draft_summaries

                st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

                if submissions:
                    if st.session_state.status_filter == "COMPLETED":
                        filtered_subs = [s for s in submissions if s["status"] != "DRAFT"]
                    elif st.session_state.status_filter == "DRAFT":
                        filtered_subs = [s for s in submissions if s["status"] == "DRAFT"]
                    else:
                        filtered_subs = submissions

                    if not filtered_subs:
                        st.info("No items match the selected filter.")
                    else:
                        # Group by estimate
                        admin_groups = {}
                        for item in filtered_subs:
                            e_no   = item.get("estimate_number") or "---"
                            e_yr   = item.get("year_of_estimate") or "---"
                            status = item.get("status","DRAFT")
                            yr_val = getattr(e_yr,'year', e_yr)
                            g_key  = (str(e_no).strip().lower(), str(yr_val))
                            if g_key not in admin_groups:
                                admin_groups[g_key] = {
                                    "estimate_number": e_no, "year_of_estimate": e_yr,
                                    "latest_date": item.get("created_at"),
                                    "total_count": 1,
                                    "draft_count": 1 if status=="DRAFT" else 0,
                                }
                            else:
                                admin_groups[g_key]["total_count"] += 1
                                if status=="DRAFT": admin_groups[g_key]["draft_count"] += 1
                                if (item.get("created_at") or "") > (admin_groups[g_key]["latest_date"] or ""):
                                    admin_groups[g_key]["latest_date"] = item.get("created_at")

                        display_list = sorted(admin_groups.values(),
                                              key=lambda x: str(x["latest_date"] or ""), reverse=True)

                        st.markdown("#### Activity List")
                        paged_subs, start_idx, total_pages = paginate_list(
                            display_list, "admin_review_page", render_controls=False)

                        st.markdown('<div class="estimate-link-list">', unsafe_allow_html=True)
                        st.markdown("""
                        <div class="activity-header">
                            <div style="display:flex; align-items:center;">
                                <div style="flex:0.5;">S.No</div>
                                <div style="flex:2.5; padding-left:16px;">Estimate Number</div>
                                <div style="flex:2; text-align:center;">Total</div>
                                <div style="flex:2; text-align:center;">Drafted</div>
                                <div style="flex:2; text-align:center;">Completed</div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        for i, group in enumerate(paged_subs):
                            s_no        = start_idx + i + 1
                            est_no      = group["estimate_number"]
                            est_yr      = group["year_of_estimate"]
                            total_c     = group["total_count"]
                            draft_c     = group["draft_count"]
                            completed_c = total_c - draft_c

                            st.markdown('<div class="activity-card">', unsafe_allow_html=True)
                            r1, r2, r3, r4, r5 = st.columns([0.5, 2.5, 2, 2, 2])
                            with r1:
                                st.markdown(f"<div style='padding-top:8px; font-weight:700; color:#9ca3af;'>#{s_no}</div>",
                                            unsafe_allow_html=True)
                            with r2:
                                if est_no and est_no != "---":
                                    if st.button(f"**{est_no}**", key=f"adv_btn_{i}_{est_no}", use_container_width=True):
                                        open_flow_page(
                                            "estimate_group",
                                            data={"est_no": est_no, "est_yr": est_yr},
                                            push_history=False,
                                        )
                                        st.rerun()
                                else:
                                    st.markdown("<div style='padding-top:8px; color:#9ca3af;'>-</div>",
                                                unsafe_allow_html=True)
                            with r3:
                                st.markdown(f"<div style='text-align:center;padding-top:4px;'>"
                                            f"<span class='activity-badge badge-total-count'>{total_c}</span></div>",
                                            unsafe_allow_html=True)
                            with r4:
                                st.markdown(f"<div style='text-align:center;padding-top:4px;'>"
                                            f"<span class='activity-badge badge-draft-count'>{draft_c}</span></div>",
                                            unsafe_allow_html=True)
                            with r5:
                                st.markdown(f"<div style='text-align:center;padding-top:4px;'>"
                                            f"<span class='activity-badge badge-comp-count'>{completed_c}</span></div>",
                                            unsafe_allow_html=True)
                            st.markdown("</div>", unsafe_allow_html=True)

                        st.markdown('</div>', unsafe_allow_html=True)
                        render_pagination_footer("admin_review_page", total_pages)

                elif st.session_state.status_filter != "ALL":
                    st.markdown("""<div class="empty-state"><div class="empty-icon">Search</div>
                        <small>Try a different filter or applicant.</small></div>""",
                        unsafe_allow_html=True)

render_footer()
