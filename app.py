from auth import login
from crud import *
from crud import update_user_modules
from streamlit_cookies_manager.encrypted_cookie_manager import EncryptedCookieManager
import datetime
import base64
import os
from streamlit_option_menu import option_menu
import streamlit as st
import streamlit.components.v1 as components



# Load CAG logo as base64 for HTML embedding
_logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
if os.path.exists(_logo_path):
    with open(_logo_path, "rb") as _f:
        _logo_b64 = base64.b64encode(_f.read()).decode()
    LOGO_IMG = f'<img src="data:image/png;base64,{_logo_b64}" style="width:200px;height:200px;object-fit:contain;">'
    LOGO_SMALL = f'<img src="data:image/png;base64,{_logo_b64}" style="width:150px;height:150px;object-fit:contain;vertical-align:middle;">'
else:
    LOGO_IMG = "🏛️"
    LOGO_SMALL = "🏛️"

cookies = EncryptedCookieManager(
    prefix="canal_app",
    password="super-secret-password",
)

if not cookies.ready():
    st.stop()

# 🔹 Money field detection
money_keywords = ["expenditure", "amount", "cost", "payment", "value", "budget"]

st.set_page_config(
    page_title="Audit Management System",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ========== HIDDEN DEVELOPER INFO ==========
st.markdown("""
<div id="dev-info"
     style="display:none;position:absolute;width:0;height:0;overflow:hidden;"
     data-developer="Latief"
     data-contact="+91-8951352811"
     data-system="Audit Management System"
     data-built-for="CAG India"
     aria-hidden="true">
</div>
""", unsafe_allow_html=True)

# ========== MASTER CSS ==========
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    font-size: 15px;
}

/* ---- Background ---- */
.stApp {
    background-color: #f8fafc;
    background-image: radial-gradient(circle at 50% 0%, #e0e7ff 0%, transparent 40%),
                      radial-gradient(circle at 100% 100%, #dbeafe 0%, transparent 40%);
    background-attachment: fixed;
}

.block-container {
    padding-top: 1.5rem;
    padding-bottom: 3rem;
    max-width: 1200px;
}

/* ---- Top Header Bar ---- */
.top-header {
    background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%);
    color: white;
    padding: 16px 24px;
    border-radius: 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 24px;
    box-shadow: 0 4px 20px rgba(37,99,235,0.25);
}
.top-header h1 {
    margin: 0;
    font-size: 22px;
    font-weight: 700;
    color: white;
    letter-spacing: -0.3px;
}
.top-header .subtitle {
    font-size: 13px;
    opacity: 0.75;
    margin-top: 2px;
}
.user-pill {
    background: rgba(255,255,255,0.15);
    border-radius: 30px;
    padding: 6px 16px;
    font-size: 14px;
    font-weight: 600;
    display: inline-block;
}

/* ---- Login Page ---- */
.login-container {
    max-width: 420px;
    margin: 60px auto 0 auto;
    text-align: center;
}
.login-logo {
    font-size: 64px;
    margin-bottom: 8px;
}
.login-title {
    font-size: 28px;
    font-weight: 800;
    color: #1e3a5f;
    margin-bottom: 4px;
}
.login-subtitle {
    font-size: 15px;
    color: #64748b;
    margin-bottom: 32px;
}
.login-card {
    background: rgba(255, 255, 255, 0.85);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    padding: 36px 32px;
    border-radius: 20px;
    box-shadow: 0 10px 40px rgba(0,0,0,0.08);
    border: 1px solid rgba(255, 255, 255, 0.5);
    text-align: left;
}

/* ---- Cards ---- */
.card {
    background: rgba(255, 255, 255, 0.85);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    padding: 24px;
    border-radius: 16px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.05);
    border: 1px solid rgba(255, 255, 255, 0.5);
    margin-bottom: 20px;
}

/* ---- Status Metric Cards ---- */
.metric-card {
    background: rgba(255, 255, 255, 0.85);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border-radius: 16px;
    padding: 20px 16px;
    text-align: center;
    box-shadow: 0 4px 16px rgba(0,0,0,0.06);
    border: 1px solid rgba(255, 255, 255, 0.6);
    cursor: pointer;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    border-top: 4px solid #e2e8f0;
}
.metric-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.12);
}
.metric-card .metric-number {
    font-size: 36px;
    font-weight: 800;
    line-height: 1.1;
}
.metric-card .metric-label {
    font-size: 13px;
    font-weight: 600;
    color: #64748b;
    margin-top: 4px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.metric-card.total  { border-top-color: #3b82f6; }
.metric-card.approved { border-top-color: #10b981; }
.metric-card.pending  { border-top-color: #f59e0b; }
.metric-card.rejected { border-top-color: #ef4444; }
.metric-card.total   .metric-number { color: #3b82f6; }
.metric-card.approved .metric-number { color: #10b981; }
.metric-card.pending  .metric-number { color: #f59e0b; }
.metric-card.rejected .metric-number { color: #ef4444; }
.metric-card.active {
    transform: translateY(-3px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.15);
}

/* ---- Progress Bar ---- */
.progress-wrapper {
    background: white;
    border-radius: 16px;
    padding: 20px 24px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    margin-bottom: 20px;
}
.progress-label {
    font-size: 14px;
    font-weight: 600;
    color: #475569;
    margin-bottom: 8px;
}
.progress-pct {
    font-size: 28px;
    font-weight: 800;
    color: #1e3a5f;
    margin-bottom: 8px;
}
.custom-progress {
    background: #e2e8f0;
    border-radius: 10px;
    height: 14px;
    width: 100%;
}
.custom-progress-fill {
    height: 100%;
    border-radius: 10px;
    text-align: right;
    padding-right: 8px;
    font-size: 10px;
    font-weight: 700;
    color: white;
    line-height: 14px;
    transition: width 0.5s ease;
}

/* ---- Submission Cards ---- */
.submission-card {
    background: white;
    padding: 18px 20px;
    border-radius: 14px;
    margin-bottom: 12px;
    border-left: 6px solid #e2e8f0;
    box-shadow: 0 2px 10px rgba(0,0,0,0.06);
}
.submission-card.approved { border-left-color: #10b981; }
.submission-card.rejected { border-left-color: #ef4444; }
.submission-card.pending  { border-left-color: #f59e0b; }

/* ---- Status Badge ---- */
.badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.4px;
}
.badge-approved { background: #ecfdf5; color: #065f46; }
.badge-rejected { background: #fef2f2; color: #991b1b; }
.badge-pending  { background: #fffbeb; color: #92400e; }

/* ---- Timeline ---- */
.timeline-card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 16px;
}
.timeline-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
    font-size: 14px;
}
.timeline-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
}

/* ---- Submit CTA ---- */
.submit-cta {
    background: linear-gradient(135deg, #1e3a5f, #2563eb);
    color: white;
    padding: 28px 32px;
    border-radius: 18px;
    text-align: center;
    margin-top: 24px;
    box-shadow: 0 6px 24px rgba(37,99,235,0.25);
}
.submit-cta h3 {
    color: white;
    font-size: 20px;
    margin-bottom: 8px;
    font-weight: 700;
}
.submit-cta p {
    opacity: 0.82;
    font-size: 14px;
    margin-bottom: 0;
}

/* ---- Section helper ---- */
.section-helper {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 10px;
    padding: 12px 16px;
    font-size: 13px;
    color: #1e40af;
    margin-bottom: 16px;
}

/* ---- Admin Panel ---- */
.admin-banner {
    background: linear-gradient(135deg, #0f172a, #1e3a5f);
    color: white;
    padding: 20px 28px;
    border-radius: 16px;
    margin-bottom: 24px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.15);
}
.admin-banner h2 { color: white; font-size: 20px; margin: 0 0 4px 0; font-weight: 700; }
.admin-banner p  { color: rgba(255,255,255,0.65); font-size: 13px; margin: 0; }

/* ---- Buttons ---- */
.stButton > button {
    border-radius: 10px;
    font-weight: 600;
    font-size: 14px;
    height: 44px;
    border: none;
    font-family: 'Inter', sans-serif;
    transition: all 0.2s ease;
}
.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 16px rgba(0,0,0,0.12);
}

/* ---- Tabs ---- */
button[data-baseweb="tab"] {
    font-size: 14px;
    font-weight: 600;
    padding: 10px 18px;
    font-family: 'Inter', sans-serif;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: #2563eb;
    border-bottom: 3px solid #2563eb;
}

/* ---- Sidebar ---- */
[data-testid="stSidebar"] {
    background: white !important;
}
.sidebar-section-title {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #94a3b8;
    margin: 16px 0 8px 0;
}
.sidebar-info-card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 14px 16px;
    font-size: 13px;
    line-height: 1.8;
    color: #334155;
}
.sidebar-tip {
    background: #eff6ff;
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 12px;
    color: #1d4ed8;
    margin-top: 12px;
    line-height: 1.5;
}

/* ---- Expander ---- */
.streamlit-expanderHeader {
    font-size: 15px;
    font-weight: 600;
}

/* ---- Inputs ---- */
.stTextInput input, .stNumberInput input, .stSelectbox [data-baseweb="select"] {
    border-radius: 8px;
    font-size: 14px;
    transition: all 0.2s ease;
}
.stTextInput input:focus, .stNumberInput input:focus, .stSelectbox [data-baseweb="select"]:focus-within {
    border-color: #3b82f6 !important;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.3) !important;
}

/* ---- Approve / Reject ---- */
.approve-btn > button {
    background: #10b981 !important;
    color: white !important;
}
.reject-btn > button {
    background: #ef4444 !important;
    color: white !important;
}

/* ---- Empty state ---- */
.empty-state {
    text-align: center;
    padding: 48px 24px;
    color: #94a3b8;
}
.empty-state .empty-icon { font-size: 52px; margin-bottom: 12px; }
.empty-state p { font-size: 16px; font-weight: 500; }
.empty-state small { font-size: 13px; }

/* ---- Completion banner ---- */
.completion-banner {
    background: linear-gradient(135deg, #ecfdf5, #d1fae5);
    border: 2px solid #10b981;
    border-radius: 14px;
    padding: 20px 24px;
    text-align: center;
    margin: 16px 0;
}
.completion-banner h3 { color: #065f46; margin: 0 0 4px 0; font-size: 18px; }
.completion-banner p  { color: #047857; margin: 0; font-size: 14px; }
</style>
""", unsafe_allow_html=True)


# ================= SESSION STATE =================

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

# --- Live Permission Sync ---
if st.session_state.get("logged_in") and st.session_state.get("user_id"):
    try:
        current_user_info = get_user_by_id(st.session_state.user_id)
        if current_user_info:
            # Check if account was revoked
            if current_user_info.get("is_active") is False:
                # Force logout
                cookies["logged_in"] = "0"
                cookies["user_id"] = ""
                cookies.save()
                st.session_state.logged_in = False
                st.session_state.user_id = None
                st.session_state.username = None
                st.session_state.role = None
                st.session_state.allowed_modules = ""
                st.error("❌ Your permission has been revoked. You have been logged out.")
                st.rerun()
            
            # Sync role and permissions only if they changed
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
            # User no longer exists in DB
            cookies["logged_in"] = "0"
            cookies.save()
            st.session_state.logged_in = False
            st.session_state.user_id = None
            st.rerun()
    except Exception as e:
        # Prevent sync errors from breaking the app
        pass


# ================= LOGIN PAGE =================

if not st.session_state.logged_in or not st.session_state.user_id:

    st.markdown(f"""
    <div class="login-container">
        <div class="login-logo">{LOGO_IMG}</div>
        <div class="login-title">Login</div>
        <div class="login-subtitle">Comptroller &amp; Auditor General of India</div>
    </div>
    """, unsafe_allow_html=True)

    # Center the form using columns
    _, col, _ = st.columns([1, 1.4, 1])

    with col:
        with st.container():
           
            st.markdown("#### 🔐 Sign In")
            u = st.text_input("Username", placeholder="Enter your username", label_visibility="visible")
            p = st.text_input("Password", type="password", placeholder="Enter your password")

            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

            if st.button("Sign In →", use_container_width=True, type="primary"):
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
                            st.error("❌ Your permission has been revoked. Please contact Administrator.")
                        else:
                            st.error("❌ Incorrect username or password. Please try again.")

            st.markdown("</div>", unsafe_allow_html=True)
            # Reset logout flag once login page is safely shown
            st.session_state.logging_out = False

    st.markdown("""
    <div style="text-align:center; margin-top:28px; color:#94a3b8; font-size:13px;">
        Having trouble signing in? Contact your system administrator.
    </div>
    """, unsafe_allow_html=True)

    st.stop()


if "master_id" not in st.session_state:
    st.session_state.master_id = None

# ================= USER INFO =================

user_id = st.session_state.get("user_id")
is_admin = st.session_state.role == "admin"
role_label = "Administrator" if is_admin else "Field Officer"

# ================= TOP NAVIGATION BAR =================

col_title, col_user, col_logout = st.columns([6, 3, 1])

with col_title:
    st.markdown(f"""
    <div class="top-header">
        <div style="display:flex;align-items:center;gap:14px;">
            {LOGO_SMALL}
            <div>
                <h1 style="margin:0;">Audit Management System</h1>
                <div class="subtitle">Application Management Portal</div>
            </div>
        </div>
        <div class="user-pill">
            👤 {st.session_state.username} &nbsp;-&nbsp; {role_label}
        </div>
    </div>
    """, unsafe_allow_html=True)

# Logout in its own column (right side)
with col_logout:
    st.markdown("<div style='margin-top:6px'></div>", unsafe_allow_html=True)
    if st.button("🚪 Logout", help="Sign out of your account"):
        cookies["logged_in"] = "0"
        cookies["user_id"] = ""
        cookies["username"] = ""
        cookies["role"] = ""
        cookies["allowed_modules"] = ""
        cookies.save()

        # Targeted reset instead of clear() which breaks CookieManager internals
        st.session_state.logging_out = True
        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.session_state.username = None
        st.session_state.role = None
        st.session_state.allowed_modules = ""
        
        st.rerun()


# =====================================================
# ================= HELPER FUNCTIONS =================
# =====================================================

def fmt_dt(value):
    """Format a datetime or string timestamp into 12-hour AM/PM display."""
    if not value:
        return "—"
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return "—"
        try:
            value = datetime.datetime.fromisoformat(value)
        except Exception:
            return value[:16]
    if isinstance(value, datetime.datetime):
        return value.strftime("%d %b %Y, %I:%M %p")
    if isinstance(value, datetime.date):
        return value.strftime("%d %b %Y")
    return str(value)[:16]


@st.dialog("📋 Submission Details", width="large")
def show_submission_details(sub, mode="user"):
    """
    Shows full submission data in a centered modal.
    mode: "user" (Dashboard) or "admin" (Review Panel)
    """
    module_key = sub.get("module") or ""
    module_label = module_key.replace("_", " ").title()
    status = sub["status"]
    is_synthetic_draft = str(sub.get("id", "")).startswith("draft_")
    
    # ---- Status Summary Timeline ----
    created_at = sub.get("created_at", "")
    approved_at = sub.get("approved_at", "")
    rejected_at = sub.get("rejected_at", "")
    reason = sub.get("rejection_reason", "")

    status_color = "#3b82f6" 
    status_text = "Awaiting Review"
    if status == "APPROVED":
        status_color = "#10b981"
        status_text = f"Approved on {fmt_dt(approved_at)}"
    elif status == "REJECTED":
        status_color = "#ef4444"
        status_text = f"Rejected on {fmt_dt(rejected_at)}"
    elif status == "DRAFT":
        status_color = "#64748b"
        status_text = "Work In Progress (Draft)"

    created_by_user = sub.get("created_by_user") or "Unknown"
    
    st.markdown(f"""
    <div style="padding:15px; border-radius:12px; background:#f8fafc; margin-bottom:20px; border-left:5px solid {status_color};">
        <div style="display:flex; justify-content:space-between; align-items:start;">
            <div>
                <div style="font-weight:700; font-size:14px; color:#1e3a5f; margin-bottom:4px;">{module_label}</div>
                <div style="font-size:12px; color:#64748b; margin-bottom:2px;"><b>{"Submitted By" if status != "DRAFT" else "Created By"}:</b> {created_by_user}</div>
                <div style="font-size:12px; color:#64748b;"><b>{"Submitted on" if status != "DRAFT" else "Last Updated"}:</b> {fmt_dt(created_at)}</div>
            </div>
            <div style="text-align:right;">
                <div style="font-size:13px; color:{status_color}; font-weight:700; text-transform:uppercase; letter-spacing:0.5px;">{status_text}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ---- Data Sections ----
    if is_synthetic_draft:
        # For drafts, we need to fetch by user and module prefix
        user_id = sub.get("user_id")
        module_tables = all_modules.get(module_key, [])
        full_data = get_full_draft_data(user_id, module_tables)
    else:
        full_data = get_full_submission_data(sub["id"])
    
    if not full_data:
        st.info("No data entries found yet for this draft.")
    
    for section_name, df_section in full_data.items():
        clean_name = (
            section_name.replace(module_key + "_", "")
            .replace("_", " ")
            .title()
        )
        st.markdown(f"#### 📄 {clean_name}")
        st.dataframe(df_section, use_container_width=True)
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    st.markdown("---")

    # ---- Actions based on mode ----
    if is_synthetic_draft:
        st.info("💡 This is a **Draft** module. It has not been submitted yet and cannot be reviewed.")
        return

    if mode == "user":
        if status == "REJECTED":
            if reason:
                st.error(f"**Rejection Reason:** {reason}")
            
            sub_module_display = module_display_map.get(module_key, "")
            if sub_module_display:
                confirm_key = f"confirm_resubmit_{sub['id']}"
                module_tables = sorted(modules.get(module_key, []))
                has_draft = False
                if module_tables:
                    has_draft = get_user_draft(module_tables[0], st.session_state.user_id) is not None

                if not st.session_state.get(confirm_key):
                    if st.button("✏️ Edit & Resubmit", key=f"dlg_resub_{sub['id']}", use_container_width=True, type="primary"):
                        if has_draft:
                            st.session_state[confirm_key] = True
                            st.rerun()
                        else:
                            st.session_state.resubmit_master_id = sub["id"]
                            st.session_state.resubmit_module = module_key
                            st.session_state.nav_to_module = sub_module_display
                            for k in list(st.session_state.keys()):
                                if k.endswith("_initialized"): del st.session_state[k]
                            st.rerun()
                else:
                    st.warning("⚠️ **Active draft found.** Proceed items will erase current draft.")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        if st.button("📝 Keep Draft", key=f"dlg_keep_{sub['id']}", use_container_width=True):
                            st.session_state[confirm_key] = False
                            st.session_state.nav_to_module = sub_module_display
                            st.rerun()
                    with c2:
                        if st.button("🗑️ Discard & Edit", key=f"dlg_disc_{sub['id']}", use_container_width=True, type="primary"):
                            delete_draft_by_user(int(st.session_state.user_id), module_tables)
                            st.session_state[confirm_key] = False
                            st.session_state.resubmit_master_id = sub["id"]
                            st.session_state.resubmit_module = module_key
                            st.session_state.nav_to_module = sub_module_display
                            for k in list(st.session_state.keys()):
                                if k.endswith("_initialized"): del st.session_state[k]
                            st.rerun()
                    with c3:
                        if st.button("✖ Cancel", key=f"dlg_can_{sub['id']}", use_container_width=True):
                            st.session_state[confirm_key] = False
                            st.rerun()
        
        # Add PDF download for users if Approved or Rejected
        if status in ["APPROVED", "REJECTED"]:
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            pdf = export_master_submission_pdf(sub["id"])
            st.download_button(
                "📥 Download PDF Record",
                pdf,
                file_name=f"submission_{sub['id']}.pdf",
                mime="application/pdf",
                key=f"dlg_user_pdf_{sub['id']}",
                use_container_width=True,
                type="primary" if status == "APPROVED" else "secondary"
            )

    elif mode == "admin":
        st.markdown("### ⚖️ Review Decision")
        col_approve, col_reject, col_download = st.columns([1, 2, 1])

        with col_approve:
            if st.button("✅ Approve", key=f"dlg_app_{sub['id']}", use_container_width=True):
                approve_master_submission(sub["id"])
                st.success("Approved.")
                st.rerun()

        with col_reject:
            reason_input = st.text_input("Rejection Reason", key=f"dlg_reason_{sub['id']}", placeholder="Reason...")
            if st.button("❌ Reject", key=f"dlg_rej_{sub['id']}", use_container_width=True):
                if not reason_input.strip():
                    st.error("Enter reason.")
                else:
                    reject_master_submission(sub["id"], reason_input)
                    st.success("Rejected.")
                    st.rerun()

        with col_download:
            pdf = export_master_submission_pdf(sub["id"])
            st.download_button(
                "📥 PDF",
                pdf,
                file_name=f"submission_{sub['id']}.pdf",
                mime="application/pdf",
                key=f"dlg_pdf_{sub['id']}",
                use_container_width=True,
            )

def is_section_complete(user_id, table):
    percentage, completed, total = get_user_progress(user_id, [table])
    return percentage == 100

def paginate_list(items, key_prefix, render_controls=True):
    """
    Slices a list based on current session state page and renders pagination controls.
    Includes a selector for items per page.
    Returns (paged_items, start_idx, total_pages)
    """
    size_key = f"{key_prefix}_size"
    if size_key not in st.session_state:
        st.session_state[size_key] = 10
    
    if key_prefix not in st.session_state:
        st.session_state[key_prefix] = 1

    # Row count selector (Always at top)
    col_size, _ = st.columns([2, 5])
    with col_size:
        new_size = st.selectbox(
            "Rows per page:", 
            [10, 25, 50, 100], 
            index=[10, 25, 50, 100].index(st.session_state[size_key]),
            key=f"size_select_{key_prefix}"
        )
        if new_size != st.session_state[size_key]:
            st.session_state[size_key] = new_size
            st.session_state[key_prefix] = 1 # Reset to page 1 on size change
            st.rerun()

    items_per_page = st.session_state[size_key]
    total_pages = max(1, (len(items) + items_per_page - 1) // items_per_page)
    
    # Boundary check
    if st.session_state[key_prefix] > total_pages:
        st.session_state[key_prefix] = total_pages
    if st.session_state[key_prefix] < 1:
        st.session_state[key_prefix] = 1
        
    start_idx = (st.session_state[key_prefix] - 1) * items_per_page
    end_idx = start_idx + items_per_page
    
    # Slice items
    paged_items = items[start_idx:end_idx]
    
    # Render controls if requested and more than 1 page
    if render_controls and total_pages > 1:
        render_pagination_footer(key_prefix, total_pages)
        
    return paged_items, start_idx, total_pages

def render_pagination_footer(key_prefix, total_pages):
    """Renders the Previous/Page Info/Next buttons at the bottom."""
    if total_pages <= 1:
        return
        
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("⬅️ Previous", key=f"prev_{key_prefix}", disabled=st.session_state[key_prefix] == 1, use_container_width=True):
            st.session_state[key_prefix] -= 1
            st.rerun()
    with col2:
        st.markdown(f"<div style='text-align:center; padding-top:10px; font-weight:600; color:#64748b; font-size:14px;'>Page {st.session_state[key_prefix]} of {total_pages}</div>", unsafe_allow_html=True)
    with col3:
        if st.button("Next ➡️", key=f"next_{key_prefix}", disabled=st.session_state[key_prefix] >= total_pages, use_container_width=True):
            st.session_state[key_prefix] += 1
            st.rerun()
    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)


def render_metric_cards(total, approved, pending, rejected, current_filter, card_type="user", drafts=None):
    """Render status metric cards as clickable buttons."""
    prefix = f"{card_type}_"
    num_cols = 5 if drafts is not None else 4
    cols = st.columns(num_cols)

    with cols[0]:
        st.markdown(f"""
        <div class="metric-card" style="background: white; border: 1px solid #e2e8f0; {'border: 2px solid #3b82f6;' if current_filter == 'ALL' else ''}">
            <div class="metric-number" style="color: #475569;">{total}</div>
            <div class="metric-label">📋 Total</div>
        </div>""", unsafe_allow_html=True)
        if st.button("Select All", key=f"{prefix}btn_all", use_container_width=True):
            if card_type == "user":
                st.session_state.user_status_filter = "ALL"
                st.session_state.dashboard_page = 1
            else:
                st.session_state.status_filter = "ALL"
                st.session_state.admin_review_page = 1
            st.rerun()

    with cols[1]:
        st.markdown(f"""
        <div class="metric-card approved {'active' if current_filter == 'APPROVED' else ''}">
            <div class="metric-number">{approved}</div>
            <div class="metric-label">✅ Approved</div>
        </div>""", unsafe_allow_html=True)
        if st.button("Select Approved", key=f"{prefix}btn_approved", use_container_width=True):
            if card_type == "user":
                st.session_state.user_status_filter = "APPROVED"
                st.session_state.dashboard_page = 1
            else:
                st.session_state.status_filter = "APPROVED"
                st.session_state.admin_review_page = 1
            st.rerun()

    with cols[2]:
        st.markdown(f"""
        <div class="metric-card pending {'active' if current_filter == 'PENDING' else ''}">
            <div class="metric-number">{pending}</div>
            <div class="metric-label">🕐 Pending</div>
        </div>""", unsafe_allow_html=True)
        if st.button("Select Pending", key=f"{prefix}btn_pending", use_container_width=True):
            if card_type == "user":
                st.session_state.user_status_filter = "PENDING"
                st.session_state.dashboard_page = 1
            else:
                st.session_state.status_filter = "PENDING"
                st.session_state.admin_review_page = 1
            st.rerun()

    with cols[3]:
        st.markdown(f"""
        <div class="metric-card rejected {'active' if current_filter == 'REJECTED' else ''}">
            <div class="metric-number">{rejected}</div>
            <div class="metric-label">❌ Rejected</div>
        </div>""", unsafe_allow_html=True)
        if st.button("Select Rejected", key=f"{prefix}btn_rejected", use_container_width=True):
            if card_type == "user":
                st.session_state.user_status_filter = "REJECTED"
                st.session_state.dashboard_page = 1
            else:
                st.session_state.status_filter = "REJECTED"
                st.session_state.admin_review_page = 1
            st.rerun()

    if drafts is not None:
        with cols[4]:
            st.markdown(f"""
            <div class="metric-card" style="background: white; border: 1px solid #e2e8f0; {'border: 2px solid #3b82f6;' if current_filter == 'DRAFT' else ''}">
                <div class="metric-number" style="color: #64748b;">{drafts}</div>
                <div class="metric-label">📝 Drafts</div>
            </div>""", unsafe_allow_html=True)
            if st.button("Select Drafts", key=f"{prefix}btn_drafts", use_container_width=True):
                st.session_state.status_filter = "DRAFT"
                st.session_state.admin_review_page = 1
                st.rerun()


# ================= MODULE CONFIGURATION =================

all_tables = get_all_tables()

# Extract module prefixes dynamically
all_modules = {}
for table in all_tables:
    if "_" in table:
        module_prefix = "_".join(table.split("_")[:2])
        all_modules.setdefault(module_prefix, []).append(table)

all_module_display_map = {m: m.replace("_", " ").title() for m in all_modules.keys()}

# =====================================================
# ================= USER SIDE =========================
# =====================================================

if not is_admin:

    # Filter modules based on permissions
    allowed = st.session_state.get("allowed_modules", "")
    if allowed:
        allowed_list = allowed.split(",")
        modules = {k: v for k, v in all_modules.items() if k in allowed_list}
    else:
        # If no modules assigned, show nothing in sidebar except dashboard
        modules = {}

    module_display_map = {m: m.replace("_", " ").title() for m in modules.keys()}
    sidebar_options = ["📄 Dashboard"] + list(module_display_map.values())

    # ---- Sidebar ----
    with st.sidebar:
        st.markdown('<div class="sidebar-section-title">Navigation</div>', unsafe_allow_html=True)

        # Default icons for option menu
        icons = ["grid"] + ["clipboard-data"] * len(module_display_map)
        
        # Navigation index handling
        nav_target = st.session_state.get("nav_to_module")
        default_idx = 0
        manual_idx = None
        
        if nav_target and nav_target in sidebar_options:
            default_idx = sidebar_options.index(nav_target)
            manual_idx = default_idx
            st.session_state.nav_to_module = None  # consume it

        selected_module = option_menu(
            menu_title=None,
            options=sidebar_options,
            icons=icons,
            default_index=default_idx,
            styles={
                "container": {"padding": "0!important", "background-color": "transparent", "border": "none"},
                "icon": {"color": "#64748b", "font-size": "16px"},
                "nav-link": {"font-size": "14px", "text-align": "left", "margin": "0px", "--hover-color": "#f1f5f9"},
                "nav-link-selected": {"background-color": "#eff6ff", "color": "#1d4ed8", "font-weight": "600"}
            },
            key="sidebar_nav_option",
            manual_select=manual_idx
        )
        st.markdown("---")

        st.markdown(f"""
        <div class="sidebar-info-card">
            👤 <b>User:</b> {st.session_state.username}<br>
            🔑 <b>Role:</b> {role_label}<br>
            📅 <b>Today:</b> {datetime.date.today().strftime("%d %b %Y")}
        </div>
        <div class="sidebar-tip">
            💡 <b>Tip:</b> Select a module from above to start filling in your application forms.
        </div>
        """, unsafe_allow_html=True)

    # Reset form initialization when module changes
    if "current_module" not in st.session_state:
        st.session_state.current_module = selected_module

    if st.session_state.current_module != selected_module:
        for key in list(st.session_state.keys()):
            if key.endswith("_initialized"):
                del st.session_state[key]
        st.session_state.current_module = selected_module

    # ---------- DASHBOARD PAGE ----------

    if selected_module == "📄 Dashboard":

        st.markdown(f"## 👋 Hello, {st.session_state.username}!")

        st.markdown("""
        Welcome to the **Audit Management System Portal**. This platform is designed to streamline your 
        application submission process, track the status of your submitted records, and manage your 
         requirements efficiently.
        """)
        st.markdown("---")
        
        # --- Start New Application Section ---
        st.markdown("### 🚀 Start New Application")
        
        if not modules:
            st.warning("⚠️ **No modules have been assigned to your account yet.**\n\nPlease contact your administrator to grant access to specific modules.")
        else:
            st.markdown("Select a module below to start a new application.")
            
            # Display modules in a select box
            mod_names = list(module_display_map.values())
            c_sel, c_btn = st.columns([5, 1])
            with c_sel:
                selected_new_mod = st.selectbox("Select Module", mod_names, label_visibility="collapsed")
            with c_btn:
                if st.button("Start →", use_container_width=True, type="primary"):
                    if selected_new_mod:
                        st.session_state.nav_to_module = selected_new_mod
                        st.rerun()
            
        st.markdown("---")

        if "user_status_filter" not in st.session_state:
            st.session_state.user_status_filter = "ALL"

        st.markdown("### 📋 Your Submitted Applications")
        st.markdown("Here you can view all the applications you have submitted and their current status.")
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        raw_submissions = get_user_master_submissions(user_id, module=None)
        
        # Filter submissions by current module permissions
        allowed_list = st.session_state.get("allowed_modules", "").split(",") if st.session_state.get("allowed_modules") else []
        submissions = [s for s in raw_submissions if s.get("module") in allowed_list]

        approved_count = sum(1 for s in submissions if s["status"] == "APPROVED")
        rejected_count = sum(1 for s in submissions if s["status"] == "REJECTED")
        pending_count  = sum(1 for s in submissions if s["status"] == "PENDING")
        total_count    = approved_count + rejected_count + pending_count

        if total_count == 0:
            st.markdown(f"""
            <div class="empty-state">
                <div class="empty-icon">📂</div>
                <p>You have not submitted any applications yet.</p>
                <small>Select a module from the sidebar to get started.</small>
            </div>
            """, unsafe_allow_html=True)
        else:
            render_metric_cards(
                total_count, approved_count, pending_count, rejected_count,
                st.session_state.user_status_filter, card_type="user"
            )

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

        if submissions:
            if st.session_state.user_status_filter != "ALL":
                filtered_subs = [s for s in submissions if s["status"] == st.session_state.user_status_filter]
            else:
                filtered_subs = submissions
            
            # Show simple message if no filtered results
            if not filtered_subs:
                msg = f"No {st.session_state.user_status_filter.lower()} applications found." if st.session_state.user_status_filter != "ALL" else "No applications found."
                st.info(msg)
            else:
                paged_subs, start_idx, total_pages = paginate_list(filtered_subs, "dashboard_page", render_controls=False)
                
                # Tabular Header
                h1, h2, h3, h4, h5 = st.columns([0.5, 2.5, 2, 1.5, 1.5])
                h1.markdown("**S.No**")
                h2.markdown("**Module Name**")
                h3.markdown("**Submitted Date**")
                h4.markdown("**Status**")
                h5.markdown("**Action**")
                st.markdown("<hr style='margin:0; margin-bottom:10px;'>", unsafe_allow_html=True)

                for i, sub in enumerate(paged_subs):
                    s_no = start_idx + i + 1
                    module_label = (sub.get("module") or "").replace("_", " ").title()
                    status = sub["status"]

                    if status == "APPROVED":
                        badge_html = '<span class="badge badge-approved" style="padding:2px 8px; font-size:11px;">✅ Approved</span>'
                    elif status == "REJECTED":
                        badge_html = '<span class="badge badge-rejected" style="padding:2px 8px; font-size:11px;">❌ Rejected</span>'
                    else:
                        badge_html = '<span class="badge badge-pending" style="padding:2px 8px; font-size:11px;">🕐 Pending</span>'

                    submitted_date = fmt_dt(sub.get("created_at", ""))
                    
                    r1, r2, r3, r4, r5 = st.columns([0.5, 2.5, 2, 1.5, 1.5])
                    r1.write(f"{s_no}")
                    r2.write(module_label)
                    r3.write(submitted_date)
                    r4.markdown(badge_html, unsafe_allow_html=True)
                    
                    with r5:
                        if st.button("🔍 View", key=f"btn_view_{sub['id']}", use_container_width=True):
                            show_submission_details(sub, mode="user")
                
                # Navigation at bottom
                render_pagination_footer("dashboard_page", total_pages)

        st.stop()

    # ---- Module Form Area ----

    module_name = [k for k, v in module_display_map.items() if v == selected_module][0]
    tables = sorted(modules[module_name])
    prefix = module_name + "_"

    if st.session_state.master_id:
        can_edit = can_user_edit(st.session_state.master_id)
    else:
        can_edit = True

    # ---- Pre-fill from rejected submission if Edit & Resubmit was clicked ----
    resubmit_mid = st.session_state.get("resubmit_master_id")
    resubmit_mod = st.session_state.get("resubmit_module")
    rejected_prefill = {}  # {table: {col: value}}
    rejected_reason  = ""

    if resubmit_mid and resubmit_mod == module_name:
        can_edit = True
        raw = get_full_submission_data(resubmit_mid)
        for tbl, df in raw.items():
            if not df.empty:
                rejected_prefill[tbl] = df.iloc[0].to_dict()

        # Fetch rejection reason from master_submission
        all_subs = get_user_master_submissions(user_id, module=module_name)
        for s in all_subs:
            if s["id"] == resubmit_mid:
                rejected_reason = s.get("rejection_reason", "")
                break

        # Seed session state with pre-filled values right now, before tabs render
        for table in tables:
            tdata = rejected_prefill.get(table, {})
            if tdata:
                cols = get_table_columns(table, is_admin=False)
                for col_info in cols:
                    col  = col_info["column_name"]
                    dtype = col_info["data_type"]
                    raw_val = tdata.get(col)
                    if raw_val is None:
                        continue
                    key = f"{table}_{col}"

                    if dtype in ("integer", "bigint", "smallint"):
                        try: st.session_state[key] = int(raw_val)
                        except: st.session_state[key] = 0
                    elif dtype in ("numeric", "double precision", "real"):
                        try: st.session_state[key] = float(raw_val)
                        except: st.session_state[key] = 0.0
                    elif dtype == "date":
                        import datetime
                        if isinstance(raw_val, datetime.datetime):
                            st.session_state[key] = raw_val.date()
                        elif isinstance(raw_val, datetime.date):
                            st.session_state[key] = raw_val
                        elif isinstance(raw_val, str):
                            try: st.session_state[key] = datetime.date.fromisoformat(raw_val[:10])
                            except: st.session_state[key] = None
                        else:
                            st.session_state[key] = None
                    else:
                        st.session_state[key] = str(raw_val) if raw_val is not None else ""

                st.session_state[f"{table}_initialized"] = True  # mark as done


        # Consume the trigger so it doesn't fire again
        st.session_state.resubmit_master_id = None
        st.session_state.resubmit_module = None

    # ---- Page Header ----
    st.markdown(f"## 📊 {selected_module}")

    # ---- Rejection banner (shown right after navigating via Resubmit) ----
    if rejected_reason:
        st.markdown(f"""
<div style="background:#fef2f2;border:2px solid #ef4444;border-radius:14px;padding:18px 22px;margin-bottom:16px;">
<div style="font-weight:700;font-size:16px;color:#991b1b;margin-bottom:6px;">✏️ Edit &amp; Resubmit Your Application</div>
<div style="font-size:14px;color:#7f1d1d;margin-bottom:10px;"><b>Rejection Reason:</b> {rejected_reason}</div>
<div style="font-size:13px;color:#b91c1c;">Your previous answers are pre-filled below. Make your corrections, save each section, then click <b>🚀 Submit</b>.</div>
</div>
""", unsafe_allow_html=True)
    # ---- Progress Section ----
    percentage, completed, total = get_user_progress(user_id, tables)

    # Update sidebar quick info
    with st.sidebar:
        st.markdown(f"""
        <div style="margin-top:12px">
        <div class="sidebar-section-title">Application Progress</div>
        <div class="sidebar-info-card">
            📋 <b>Sections:</b> {total}<br>
            ✅ <b>Completed:</b> {completed}<br>
            📊 <b>Progress:</b> {percentage:.0f}%
        </div>
        </div>
        """, unsafe_allow_html=True)

    if percentage < 40:
        prog_color = "#ef4444"
    elif percentage < 75:
        prog_color = "#f59e0b"
    else:
        prog_color = "#10b981"

    st.markdown(f"""
    <div class="progress-wrapper">
        <div class="progress-label">Your Application Progress</div>
        <div class="progress-pct">{percentage:.0f}% Complete</div>
        <div class="custom-progress">
            <div class="custom-progress-fill" style="width:{percentage}%; background-color:{prog_color};">
            </div>
        </div>
        <div style="margin-top:8px; font-size:13px; color:#64748b;">
            {completed} of {total} sections filled in
        </div>
    </div>
    """, unsafe_allow_html=True)

    if percentage == 100:
        st.markdown("""
        <div class="completion-banner">
            <h3>🎉 All Sections Complete!</h3>
            <p>Scroll down to submit your complete application.</p>
        </div>
        """, unsafe_allow_html=True)

    # ---- Tabs ----
    tab_labels = []
    for table in tables:
        section_name = table.replace(prefix, "").replace("_", " ").title()
        is_complete = is_section_complete(user_id, table)
        label = f"✅ {section_name}" if is_complete else f"⬜ {section_name}"
        tab_labels.append(label)

    tabs = st.tabs(tab_labels)

    # Read estimate fields from first tab draft
    first_table = tables[0]
    first_table_draft = get_user_draft(first_table, user_id)

    estimate_number = None
    year_of_estimate = None
    if first_table_draft:
        estimate_number = first_table_draft.get("estimate_number")
        year_of_estimate = first_table_draft.get("year_of_estimate")

    for i, table in enumerate(tables):

        with tabs[i]:

            is_master_form = table == first_table
            columns = get_table_columns(table, is_admin=False)

            if table != first_table and not first_table_draft:
                st.markdown("""
                <div class="section-helper">
                    📌 <b>Please complete the first section first.</b><br>
                    You must fill in and save the first section before you can proceed with this one.
                </div>
                """, unsafe_allow_html=True)

            else:
                st.markdown("""
                <div class="section-helper">
                    ✏️ <b>How to fill this section:</b> Fill in all the fields below, then click
                    <b>💾 Save Section</b> at the bottom. You can come back and edit any time before submitting.
                </div>
                """, unsafe_allow_html=True)

            # Load draft into session state only once
            if f"{table}_initialized" not in st.session_state:
                draft = get_user_draft(table, user_id)

                for col_info in columns:
                    col = col_info["column_name"]
                    dtype = col_info["data_type"]
                    key = f"{table}_{col}"

                    if draft and col in draft and draft[col] is not None:
                        val = draft[col]
                        if dtype in ("integer", "bigint", "smallint"):
                            try: val = int(val)
                            except: val = 0
                        elif dtype in ("numeric", "double precision", "real"):
                            try: val = float(val)
                            except: val = 0.0
                        elif dtype == "date":
                            # Always store as datetime.date so widget never conflicts
                            if isinstance(val, datetime.datetime):
                                val = val.date()
                            elif isinstance(val, str):
                                try: val = datetime.date.fromisoformat(val[:10])
                                except: val = None
                        else:
                            val = str(val)
                        st.session_state[key] = val
                    else:
                        if dtype in ("integer", "bigint", "smallint"):
                            st.session_state.setdefault(key, 0)
                        elif dtype in ("numeric", "double precision", "real"):
                            st.session_state.setdefault(key, 0.0)
                        elif dtype == "date":
                            st.session_state.setdefault(key, None)
                        else:
                            st.session_state.setdefault(key, "")

                st.session_state[f"{table}_initialized"] = True

            form_data = {}
            filled_fields = 0

            # ---- FIRST TAB: use st.form ----
            if table == first_table:

                with st.form(f"form_{table}"):
                    col1, col2 = st.columns(2)
                    filled_fields = 0

                    for index, col_info in enumerate(columns):
                        col = col_info["column_name"]
                        dtype = col_info["data_type"]
                        key = f"{table}_{col}"

                        target_col = col1 if index % 2 == 0 else col2

                        with target_col:
                            label = col.replace("_", " ").title()
                            if any(word in col.lower() for word in money_keywords):
                                label = f"{label} (₹)"

                            if dtype in ("integer", "bigint", "smallint"):
                                value = st.number_input(label, step=1, key=key)

                            elif dtype in ("numeric", "double precision", "real"):
                                value = st.number_input(label, key=key)

                            elif dtype == "date":
                                value = st.date_input(label, key=key)

                            elif dtype == "boolean" or dtype == "bool":
                                bool_options = ["", "Yes", "No"]
                                idx = 0
                                curr_val = st.session_state.get(key)
                                if curr_val is True or str(curr_val).lower() == "true":
                                    idx = 1
                                elif curr_val is False or str(curr_val).lower() == "false":
                                    idx = 2
                                selection = st.selectbox(label, options=bool_options, index=idx, key=f"{key}_select")
                                if selection == "Yes":
                                    value = True
                                elif selection == "No":
                                    value = False
                                else:
                                    value = None
                            else:
                                value = st.text_input(label, key=key)

                        form_data[col] = value
                        if value not in ("", None, 0, 0.0):
                            filled_fields += 1

                    submitted = st.form_submit_button("💾 Save Section", use_container_width=True, type="primary")


                if submitted:
                    # Generic mandatory field validation based on is_nullable
                    for col_info in columns:
                        if col_info["is_nullable"] == "NO":
                            col_name = col_info["column_name"]
                            val = form_data.get(col_name)
                            if val in (None, "", 0, 0.0):
                                display_name = col_name.replace("_", " ").title()
                                st.error(f"⚠️ {display_name} is required. Please fill it in before saving.")
                                st.stop()

                    if filled_fields == 0:
                        st.warning("⚠️ Please fill in at least one field before saving.")
                        st.stop()

                    # Explicit UI level validation for Estimate fields (Contract Management only)
                    if module_name == "contract_management":
                        for req_col in ["estimate_number", "year_of_estimate"]:
                            if req_col in form_data:
                                val = form_data.get(req_col)
                                if val in (None, "", 0, 0.0):
                                    disp = req_col.replace("_", " ").title()
                                    st.error(f"⚠️ {disp} is required. Please fill it in before saving.")
                                    st.stop()

                    save_draft_record(table, form_data, user_id)
                    st.success("✅ Section saved successfully!")
                    st.rerun()

            # ---- OTHER TABS ----
            else:
                col1, col2 = st.columns(2)

                for index, col_info in enumerate(columns):
                    col = col_info["column_name"]
                    dtype = col_info["data_type"]
                    key = f"{table}_{col}"

                    target_col = col1 if index % 2 == 0 else col2

                    with target_col:
                        label = col.replace("_", " ").title()
                        if any(word in col.lower() for word in money_keywords):
                            label = f"{label} (₹)"

                        # Locked estimate fields — force session_state so widget always
                        # shows the live value even without a manual page reload
                        if col in ["estimate_number", "year_of_estimate"]:
                            value = estimate_number if col == "estimate_number" else year_of_estimate
                            display_key = f"display_{table}_{col}"
                            # Always overwrite so rerun after first-tab save reflects immediately
                            st.session_state[display_key] = "" if value is None else str(value)
                            st.text_input(
                                label,
                                disabled=True,
                                key=display_key,
                            )
                            form_data[col] = value
                            continue

                        # Widgets now rely purely on session state for their value
                        if dtype in ("integer", "bigint", "smallint"):
                            value = st.number_input(label, step=1, key=key)

                        elif dtype in ("numeric", "double precision", "real"):
                            value = st.number_input(label, key=key)

                        elif dtype == "date":
                            value = st.date_input(label, key=key)

                        elif dtype == "boolean" or dtype == "bool":
                            # Use a selectbox for boolean fields to ensure valid input
                            bool_options = ["", "Yes", "No"]
                            # Pre-select based on session state if it exists
                            idx = 0
                            curr_val = st.session_state.get(key)
                            if curr_val is True or str(curr_val).lower() == "true":
                                idx = 1
                            elif curr_val is False or str(curr_val).lower() == "false":
                                idx = 2
                            
                            selection = st.selectbox(label, options=bool_options, index=idx, key=f"{key}_select")
                            
                            if selection == "Yes":
                                value = True
                            elif selection == "No":
                                value = False
                            else:
                                value = None
                        else:
                            value = st.text_input(label, key=key)

                    form_data[col] = value
                    # Count filled fields based on the value from the widget (which is also in session_state)
                    if value not in ("", None, 0, 0.0):
                        filled_fields += 1

                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

                if st.button("💾 Save Section", key=f"save_{table}", use_container_width=True, type="primary"):

                    if not first_table_draft:
                        st.warning("⚠️ Please complete the first section before saving this one.")
                        st.stop()

                    if not can_edit:
                        st.warning("🔒 This application has been submitted and cannot be edited unless it is rejected.")

                    elif filled_fields == 0:
                        st.warning("⚠️ Please fill in at least one field before saving.")

                    else:
                        table_col_names = [c["column_name"] for c in columns]
                        if "estimate_number" in table_col_names:
                            form_data["estimate_number"] = estimate_number
                        if "year_of_estimate" in table_col_names:
                            form_data["year_of_estimate"] = year_of_estimate
                        save_draft_record(table, form_data, user_id)
                        st.success("✅ Section saved successfully!")
                        st.rerun()

    # ---------- FINAL SUBMIT ----------

    incomplete_sections = get_incomplete_forms(user_id, tables)

    st.markdown("""
    <div class="submit-cta">
        <h3>🚀 Ready to Submit Your Application?</h3>
        <p>Once all sections are complete, click the button below to submit your full application for review.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    if incomplete_sections:
        st.error("⚠️ **The following sections still need to be completed before you can submit:**")
        for i, sec in enumerate(incomplete_sections, 1):
            clean_name = sec.replace(prefix, "").replace("_", " ").title()
            st.markdown(f"&nbsp;&nbsp;&nbsp;**{i}.** {clean_name}")
    else:
        if st.button("🚀 Submit My Complete Application", use_container_width=True, type="primary"):
            create_master_submission(user_id, module_name, tables)
            current_master_id = st.session_state.master_id
            delete_user_drafts(current_master_id, tables)
            st.session_state.master_id = None

            for table in tables:
                for key in list(st.session_state.keys()):
                    if key.startswith(f"{table}_"):
                        del st.session_state[key]

            st.toast("🎉 Application submitted successfully! You'll be notified once it's reviewed.")
            import time
            time.sleep(5)
            st.rerun()


# =====================================================
# ================= ADMIN SIDE ========================
# =====================================================

if is_admin:

    if "status_filter" not in st.session_state:
        st.session_state.status_filter = "ALL"

    st.markdown("""
    <div class="admin-banner">
        <h2>🛡️ Admin Review Panel</h2>
        <p>Review submitted applications, manage users, and download PDF reports.</p>
    </div>
    """, unsafe_allow_html=True)

    tab_review, tab_users, tab_manage_users = st.tabs(["📋 Review Applications", "➕ Create User", "👥 Manage Users"])

    with tab_users:
        st.markdown("### ➕ Create New User")
        st.markdown("Create a new applicant account. Usernames must be unique.")
        
        with st.form("create_user_form", clear_on_submit=True):
            new_username = st.text_input("Username")
            new_password = st.text_input("Password", type="password")
            new_role = st.selectbox("Role", options=["operator", "admin"], format_func=lambda x: "Administrator" if x == "admin" else "Operator")
            
            # Module selection
            selected_mods = st.multiselect(
                "Allowed Modules",
                options=list(all_modules.keys()),
                format_func=lambda x: all_module_display_map.get(x, x)
            )
            
            submit_user = st.form_submit_button("Create User", type="primary")
            
            if submit_user:
                if not new_username.strip() or not new_password.strip():
                    st.error("⚠️ Username and Password cannot be empty.")
                else:
                    modules_str = ",".join(selected_mods)
                    success, msg = create_user(new_username.strip(), new_password.strip(), role=new_role, allowed_modules=modules_str)
                    if success:
                        st.success(f"✅ {msg}")
                    else:
                        st.error(f"❌ {msg}")

    with tab_manage_users:
        st.markdown("### 👥 Manage Existing Users")
        st.markdown("View all users and toggle their access status.")
        
        raw_users_df = get_all_users_admin()
        
        if not raw_users_df.empty:
            # Paginate the users (controls at bottom)
            users_list = raw_users_df.to_dict('records')
            paged_users, start_idx, total_pages = paginate_list(users_list, "manage_users_page", render_controls=False)
            
            c1, c2, c3, c4, c5, c6 = st.columns([0.5, 2, 1.5, 1.5, 3.5, 1.5])
            c1.markdown("**S.No**")
            c2.markdown("**Username**")
            c3.markdown("**Role**")
            c4.markdown("**Status**")
            c5.markdown("**Allowed Modules**")
            c6.markdown("**Action**")
            st.markdown("<hr style='margin: 0; padding: 0;'>", unsafe_allow_html=True)
            
            def update_user_per_callback(uid, session_key):
                # Guard: skip if we're in the middle of a logout or role changed
                if st.session_state.get('logging_out') or not st.session_state.get('logged_in') or st.session_state.get('role') != 'admin':
                    return
                
                new_mods = st.session_state.get(session_key, [])
                update_user_modules(uid, new_mods)
                st.toast(f"✅ Permissions updated for user ID: {uid}")

            for i, row_usr in enumerate(paged_users):
                uid = row_usr['id']
                uname = row_usr['username']
                urole = row_usr['role']
                is_active = row_usr.get('is_active', True)
                allowed_str = row_usr.get('allowed_modules', '')
                current_allowed = allowed_str.split(',') if allowed_str else []
                s_no = start_idx + i + 1
                
                cc1, cc2, cc3, cc4, cc5, cc6 = st.columns([0.5, 2, 1.5, 1.5, 3.5, 1.5])
                with cc1:
                    st.markdown(f"<div style='padding-top:10px;'>{s_no}</div>", unsafe_allow_html=True)
                with cc2:
                    st.markdown(f"<div style='padding-top:10px;'><b>{uname}</b></div>", unsafe_allow_html=True)
                with cc3:
                    st.markdown(f"<div style='padding-top:10px;'>{'Administrator' if urole == 'admin' else 'Operator'}</div>", unsafe_allow_html=True)
                with cc4:
                    if is_active:
                        st.markdown("<div style='padding-top:10px;color:#10b981;font-weight:600;'>✅ Active</div>", unsafe_allow_html=True)
                    else:
                        st.markdown("<div style='padding-top:10px;color:#ef4444;font-weight:600;'>❌ Revoked</div>", unsafe_allow_html=True)
                with cc5:
                    if urole != 'admin':
                        st.multiselect(
                            "Modules",
                            options=list(all_modules.keys()),
                            default=[m for m in current_allowed if m in all_modules],
                            format_func=lambda x: all_module_display_map.get(x, x),
                            key=f"mods_inline_{uid}",
                            label_visibility="collapsed",
                            on_change=update_user_per_callback,
                            args=(uid, f"mods_inline_{uid}")
                        )
                    else:
                        st.markdown("<div style='padding-top:10px;color:#64748b;font-style:italic;'>Full Access</div>", unsafe_allow_html=True)
                with cc6:
                    if st.session_state.user_id == uid:
                        st.button("Self", disabled=True, key=f"btn_{uid}", use_container_width=True)
                    elif urole == 'admin':
                        st.button("Admin", disabled=True, key=f"btn_admin_{uid}", use_container_width=True)
                    else:
                        btn_label = "Revoke" if is_active else "Grant"
                        btn_type = "secondary" if is_active else "primary"
                        if st.button(btn_label, key=f"btn_toggle_{uid}", type=btn_type, use_container_width=True):
                            toggle_user_status(uid, is_active)
                            st.rerun()
                st.markdown("<hr style='margin: 0; padding: 0;'>", unsafe_allow_html=True)
            
            # Show pagination controls at the bottom
            render_pagination_footer("manage_users_page", total_pages)

    with tab_review:
        # ---- User Selector ----
        all_users_df = get_all_users_admin()
        # Filter for non-admins (applicants)
        users_df = all_users_df[all_users_df["role"] != "admin"]

        if users_df.empty:
            st.markdown("""
            <div class="empty-state">
                <div class="empty-icon">👥</div>
                <p>No applicant accounts found.</p>
                <small>Create a user account first in the 'Create User' tab.</small>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("#### 👤 Select an Applicant to Review")
            applicant_options = ["--- Select Applicant ---"] + list(users_df["username"])
            selected_user = st.selectbox(
                "Applicant",
                applicant_options,
                label_visibility="collapsed",
                help="Choose the user whose applications you want to review"
            )

            if selected_user != "--- Select Applicant ---":
                # Reset page if user changed
                if "prev_selected_user" not in st.session_state:
                    st.session_state.prev_selected_user = selected_user
                if st.session_state.prev_selected_user != selected_user:
                    st.session_state.admin_review_page = 1
                    st.session_state.prev_selected_user = selected_user

                user_row = users_df[users_df["username"] == selected_user].iloc[0]
                selected_user_id = int(user_row["id"])

                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

                # ---- Status Counts ----
                approved, rejected, pending, drafts = get_user_master_status_counts(selected_user_id, all_modules)
                total = approved + rejected + pending + drafts

                st.markdown("#### 📊 Submission Overview")
                
                if total == 0:
                    st.markdown(f"""
                    <div class="empty-state">
                        <div class="empty-icon">🔍</div>
                        <p>No activity found for <b>{selected_user}</b>.</p>
                        <small>This user has no submissions or drafts currently.</small>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    render_metric_cards(total, approved, pending, rejected, st.session_state.status_filter, card_type="admin", drafts=drafts)

                st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

                # ---- Submission List ----
                masters = get_user_master_submissions_admin(selected_user_id)
                draft_summaries = get_user_draft_summaries(selected_user_id, all_modules)
                
                # Attach creator name to drafts
                for d in draft_summaries:
                    d["created_by_user"] = selected_user

                submissions = masters + draft_summaries

                if submissions:
                    if st.session_state.status_filter != "ALL":
                        filtered_subs = [s for s in submissions if s["status"] == st.session_state.status_filter]
                    else:
                        filtered_subs = submissions
                    
                    if not filtered_subs:
                        st.info(f"No {st.session_state.status_filter.lower()} items found." if st.session_state.status_filter != "ALL" else "No items found.")
                    else:
                        st.markdown("#### 📋 Activity List")
                        paged_subs, start_idx, total_pages = paginate_list(filtered_subs, "admin_review_page", render_controls=False)

                        # Tabular Header
                        h1, h2, h3, h4, h5 = st.columns([0.5, 2.5, 2, 1.5, 1.5])
                        h1.markdown("**S.No**")
                        h2.markdown("**Module Name**")
                        h3.markdown("**Submitted Date**")
                        h4.markdown("**Status**")
                        h5.markdown("**Action**")
                        st.markdown("<hr style='margin:0; margin-bottom:10px;'>", unsafe_allow_html=True)

                        for i, sub in enumerate(paged_subs):
                            s_no = start_idx + i + 1
                            module_name = sub.get("module")
                            module_label = (module_name or "Unknown").replace("_", " ").title()
                            status = sub["status"]

                            if status == "APPROVED":
                                badge_html = '<span class="badge badge-approved" style="padding:2px 8px; font-size:11px;">✅ Approved</span>'
                            elif status == "REJECTED":
                                badge_html = '<span class="badge badge-rejected" style="padding:2px 8px; font-size:11px;">❌ Rejected</span>'
                            elif status == "DRAFT":
                                badge_html = '<span class="badge" style="padding:2px 8px; font-size:11px; background:#f1f5f9; color:#64748b; border:1px solid #e2e8f0;">📝 Draft</span>'
                            else:
                                badge_html = '<span class="badge badge-pending" style="padding:2px 8px; font-size:11px;">🕐 Pending</span>'

                            # ---- Timeline Card ----
                            created_at  = sub.get("created_at", "")
                            approved_at = sub.get("approved_at", "")
                            rejected_at = sub.get("rejected_at", "")
                            reason      = sub.get("rejection_reason", "")

                            # Build extra rows for timeline
                            if status == "APPROVED" and approved_at:
                                extra_rows = f'<div class="timeline-row"><div class="timeline-dot" style="background:#10b981"></div><span><b>Approved:</b> {fmt_dt(approved_at)}</span></div>'
                            elif status == "REJECTED":
                                extra_rows = ""
                                if rejected_at:
                                    extra_rows += f'<div class="timeline-row"><div class="timeline-dot" style="background:#ef4444"></div><span><b>Rejected:</b> {fmt_dt(rejected_at)}</span></div>'
                                if reason:
                                    extra_rows += f'<div class="timeline-row"><div class="timeline-dot" style="background:#f97316"></div><span><b>Reason:</b> {reason}</span></div>'
                            else:
                                extra_rows = '<div class="timeline-row"><div class="timeline-dot" style="background:#f59e0b"></div><span><b>Status:</b> Awaiting review</span></div>'

                            submitted_str = fmt_dt(created_at)

                            r1, r2, r3, r4, r5 = st.columns([0.5, 2.5, 2, 1.5, 1.5])
                            r1.write(f"{s_no}")
                            r2.write(module_label)
                            r3.write(submitted_str)
                            r4.markdown(badge_html, unsafe_allow_html=True)
                            
                            with r5:
                                btn_label = "🔍 View" if status == "DRAFT" else "🔍 Review"
                                if st.button(btn_label, key=f"btn_rev_{sub['id']}", use_container_width=True):
                                    show_submission_details(sub, mode="admin")
                        
                        # Navigation at bottom
                        render_pagination_footer("admin_review_page", total_pages)

                elif st.session_state.status_filter != "ALL":
                    st.markdown("""
                    <div class="empty-state">
                        <div class="empty-icon">🔍</div>
                        <small>Try selecting a different filter or applicant.</small>
                    </div>
                    """, unsafe_allow_html=True)