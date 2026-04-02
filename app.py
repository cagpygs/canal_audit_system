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
_base_dir = os.path.dirname(os.path.abspath(__file__))
_logo_path = os.path.join(_base_dir, "logo.png")
if os.path.exists(_logo_path):
    with open(_logo_path, "rb") as _f:
        _logo_b64 = base64.b64encode(_f.read()).decode()
    LOGO_IMG = f'<img src="data:image/png;base64,{_logo_b64}" style="width:120px;height:120px;object-fit:contain;">'
    LOGO_SMALL = f'<img src="data:image/png;base64,{_logo_b64}" style="width:50px;height:50px;object-fit:contain;vertical-align:middle;">'
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

# ========== STYLE LOADING ==========
def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name, encoding='utf-8') as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

load_css('style.css')


def render_footer():
    """Renders the common footer."""
    st.markdown("""
    <div class="footer-container">
        <div class="footer-brand">Comptroller and Auditor General of India</div>
        <div class="footer-subtitle">Irrigation Department - Canal Audit & Management System</div>
        <div class="footer-links">
            <a href="#">Privacy Policy</a>
            <a href="#">Terms of Service</a>
            <a href="#">Technical Support</a>
            <a href="#">Contact Us</a>
        </div>
        <div class="footer-bottom">
            © 2024 CAG India. All Rights Reserved. | Developed by DAC-Cell-Latief.
        </div>
    </div>
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

# Helper function for navigation
def go_home():
    st.session_state.current_view = "Main"
    st.session_state.master_id = None
    st.session_state.show_draft_prompt = None
    st.rerun()


# ================= LOGIN PAGE =================

if not st.session_state.logged_in or not st.session_state.user_id:

    # Center the form using columns
    _, col, _ = st.columns([1, 1.4, 1])

    with col:
        st.markdown(f"""
        <div class="login-container">
            <div class="login-logo">{LOGO_IMG}</div>
            <div class="login-title">Audit Management System</div>
            <div class="login-subtitle">Comptroller &amp; Auditor General of India</div>
        </div>
        """, unsafe_allow_html=True)
        
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
# We use a placeholder for the background styling and a container for the items
st.markdown('<div id="sticky-header"></div>', unsafe_allow_html=True)

# Container for the premium header
st.markdown(f'<div id="sticky-header-container"><div class="nav-brand">{LOGO_SMALL if "LOGO_SMALL" in locals() else "🏛️"}<h2>Audit Management</h2>{"" if is_admin else f"""<div class="nav-links"><a href="./?nav=Main" target="_self" class="nav-item">Dashboard</a><a href="./?nav=NewApp" target="_self" class="nav-item">Start New Application</a></div>"""}</div><div class="nav-right"><a href="./?nav=Logout" target="_self" class="nav-item" style="color:#ef4444; margin-right:15px; background:rgba(239,68,68,0.1);">🚪 Logout</a><div class="user-profile"><div class="avatar">{st.session_state.username[0].upper() if st.session_state.get("username") else "U"}</div><div class="user-info"><div class="user-name">{st.session_state.get("username", "User")}</div><div class="user-role">{st.session_state.role.replace("_", " ").title() if st.session_state.get("role") else "Member"}</div></div></div></div></div>', unsafe_allow_html=True)




def clear_module_state(m_key=None):
    """Clears stale session state flags and draft metadata to ensure a fresh form start."""
    # 1. Clear ALL section initialization flags and display buffers
    for key in list(st.session_state.keys()):
        if "_initialized" in key or "display_" in key:
            del st.session_state[key]
            
    # 2. Clear the specific initial preliminary values
    if "initial_estimate_number" in st.session_state:
        del st.session_state["initial_estimate_number"]
    if "initial_year_of_estimate" in st.session_state:
        del st.session_state["initial_year_of_estimate"]
    if "initial_name_of_project" in st.session_state:
        del st.session_state["initial_name_of_project"]
    
    # 3. If a module key is provided, also delete unattached DB drafts and clear its specific table entries
    if m_key:
        m_tables = all_modules.get(m_key, [])
        user_id = st.session_state.get("user_id")
        delete_unattached_drafts(user_id, m_tables)
        # Clear specific table data to avoid ghost inputs
        for table in m_tables:
            for key in list(st.session_state.keys()):
                if key.startswith(f"{table}_"):
                    del st.session_state[key]



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


@st.dialog("📋 Submission Details", width="large", dismissible=False)
def show_submission_details(sub, mode="user"):
    """
    Shows full submission data in a centered modal.
    mode: "user" (Dashboard) or "admin" (Review Panel)
    """
    module_key = sub.get("module") or ""
    module_label = module_key.replace("_", " ").title()
    status = sub["status"]
    is_synthetic_draft = str(sub.get("id", "")).startswith("draft_")
    
    # ---- Status Summary ----
    created_at = sub.get("created_at", "")
    created_by_user = sub.get("created_by_user") or "Unknown"

    if status == "DRAFT":
        status_color = "#64748b"
        status_text = "Work In Progress (Draft)"
    else:
        status_color = "#10b981"
        status_text = "Completed"

    if module_key == "contract_management":
        est_no = sub.get("estimate_number") or "---"
        est_yr = sub.get("year_of_estimate") or "---"
        y_val = est_yr.year if hasattr(est_yr, 'year') else est_yr
        display_key = f"{est_no} ({y_val})" if est_no != "---" else "---"
        est_html = f'<div style="font-size:13px; font-weight:600; color:#334155; margin-bottom:6px;">🔹 Estimate Key: {display_key}</div>'
    else:
        est_html = ""

    st.markdown(f"""
    <div style="padding:15px; border-radius:12px; background:#f8fafc; margin-bottom:20px; border-left:5px solid {status_color};">
        <div style="display:flex; justify-content:space-between; align-items:start;">
            <div>
                <div style="font-weight:700; font-size:14px; color:#1e3a5f; margin-bottom:4px;">{module_label}</div>
                {est_html}
                <div style="font-size:12px; color:#64748b; margin-bottom:2px;"><b>{"Submitted By" if status != "DRAFT" else "Created By"}:</b> {created_by_user}</div>
                <div style="font-size:12px; color:#64748b;"><b>{"Submitted on" if status != "DRAFT" else "Last Updated"}:</b> {fmt_dt(created_at)}</div>
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
        st.info("💡 This is a **Draft** module. It has not been submitted yet.")
        return

    # Add PDF download for both users and admins if Submitted
    if status != "DRAFT":
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        pdf = export_master_submission_pdf(sub["id"])
        st.download_button(
            "📥 Download PDF Record",
            pdf,
            file_name=f"submission_{sub['id']}.pdf",
            mime="application/pdf",
            key=f"dlg_pdf_{sub['id']}",
            use_container_width=True,
            type="primary"
        )
    
    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    if st.button("✖️ Close", key=f"close_sub_details_{sub.get('id', 'def')}", use_container_width=True):
        st.rerun()

@st.dialog("📂 Applications for Estimate", width="large", dismissible=False)
def show_estimate_group_dialog(est_no, est_yr, user_id=None, module=None):

    """
    Shows all master_submission records for a specific estimate number and year.
    """
    y_val = est_yr
    st.markdown(f"#### 📜 Grouped by Estimate: **{est_no}** ({y_val})")
    
    is_admin_user = st.session_state.get("role") == "admin"

    # --- ACTION BUTTONS AT TOP ---
    if not is_admin_user:
        cols = st.columns([1, 1, 1])
        with cols[0]:
            if st.button("➕ Start New Application for this Estimate Number", key=f"btn_new_app_grp_{est_no}", use_container_width=True, type="primary"):
                st.session_state.trigger_new_app_from_modal = True
                st.session_state.initial_estimate_number = est_no
                st.session_state.initial_year_of_estimate = est_yr
                # Check if available in group submissions
                submissions = get_submissions_by_estimate(est_no, est_yr, user_id=None, module=None)
                if submissions:
                    try:
                        s_data = get_full_submission_data(submissions[0]['id'])
                        first_table = list(s_data.keys())[0] if s_data else None
                        if first_table and 'name_of_project' in s_data[first_table].columns:
                            st.session_state.initial_name_of_project = s_data[first_table].iloc[0]['name_of_project']
                    except Exception:
                        pass
                st.rerun()
        st.markdown("<div style='height:15px'></div>", unsafe_allow_html=True)
    
    st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)
    
    submissions = get_submissions_by_estimate(est_no, est_yr, user_id=user_id, module=module)

    
    if not submissions:
        st.info("No applications found for this estimate.")
    
    else:
        # Header for the applications list
        h1, h2, h3, h4, r_spacer, h6 = st.columns([0.8, 1.8, 1.2, 1.2, 1.0, 1.2])
        h1.markdown("**S.No**")
        h2.markdown("**User**")
        h3.markdown("**Date**")
        h4.markdown("**Status**")
        h6.markdown("**Action**")
        st.markdown("<hr style='margin:0; margin-bottom:10px;'>", unsafe_allow_html=True)

        for i, s in enumerate(submissions, 1):
            r1, r2, r3, r4, r_spacer2, r6 = st.columns([0.8, 1.8, 1.2, 1.2, 1.0, 1.2])
            status = s.get("status", "DRAFT")
            status_color = "#3b82f6" if status == "DRAFT" else "#10b981"
            
            with r1:
                st.write(f"**{i}**")
            with r2:
                st.write(s.get("created_by_user", "Unknown"))
            with r3:
                st.write(fmt_dt(s.get("created_at")))
            with r4:
                st.markdown(f'<span style="background:{status_color}22; color:{status_color}; padding:2px 8px; border-radius:12px; font-size:11px; font-weight:600;">{status}</span>', unsafe_allow_html=True)
                
            with r6:
                if status == "DRAFT" and not is_admin_user:
                    if st.button("📝 Resume", key=f"btn_group_res_{s['id']}", use_container_width=True):
                        clear_module_state(s.get("module"))
                        st.session_state.master_id = s["id"]
                        st.session_state.current_view = s.get("module")
                        st.rerun()

                else:
                    # View button for completed or drafts (if admin)
                    if st.button("🔍 View", key=f"btn_group_view_{s['id']}", use_container_width=True):
                        clear_module_state(s.get("module"))
                        st.session_state.sub_to_view = s
                        st.session_state.sub_view_mode = "admin" if is_admin_user else "user"
                        st.rerun()



    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    if st.button("✖️ Close", key=f"close_est_group_{est_no}", use_container_width=True):
        st.rerun()

@st.dialog("📋 Application Already Exists", width="medium", dismissible=False)
def show_duplicate_submission_modal():
    """Shows a modal when a user tries to start an estimate that already has a submission."""
    data = st.session_state.get("active_modal_data")
    if not data:
        st.rerun()
        return

    m_key = data["module"]
    est_no = data["est_no"]
    est_yr = data["est_yr"]
    sub = data["sub"]
    status = sub["status"]
    
    yr_val = getattr(est_yr, 'year', est_yr)
    st.markdown(f"An application for **{est_no}** ({yr_val}) already exists.")
    
    if status == "DRAFT":
        st.warning("⚠️ **Existing Application with same Estimate Number and Year Found**")
    else:
        st.error("🚫 **Submission Already Completed**\nThis estimate has already been submitted and cannot be modified or duplicated.")
        if st.button("🔍 View Submission Details", type="primary", use_container_width=True):
            show_submission_details(sub, mode="user")
            # We don't clear modal data here so the details show behind it, 
            # or we clear and let details render?
            # Actually show_submission_details is also a dialog. 
            # Streamlit doesn't support nested dialogs well.
            # So let's just show a close button.
            
    if st.button("✖️ Close", use_container_width=True):
        del st.session_state["active_modal_data"]
        st.rerun()

@st.dialog("🚀 Start New Application", width="medium", dismissible=False)
def show_new_application_dialog():
    """Shows a modal to start a new application from the header."""
    st.markdown("Select a module below to start a new application.")
    
    # Use a unique key for modal selection to avoid conflicts with dashboard
    selected_m = st.selectbox(
        "Select Module", 
        options=list(module_display_map.keys()), 
        format_func=lambda x: module_display_map[x],
        key="header_modal_sel_key"
    )
    
    # Show estimate inputs if Contract Management is selected
    if selected_m == "contract_management":
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        st.text_input("Name of Project", placeholder="Enter Name of Project", key="header_modal_nm_proj")
        ce1, ce2 = st.columns(2)
        with ce1:
            st.text_input("Estimate Number", placeholder="Enter Estimate Number", key="header_modal_est_no")
        with ce2:
            current_year = datetime.datetime.now().year
            year_options = [f"{y}-{str(y+1)[2:]}" for y in range(current_year, 1999, -1)]
            st.selectbox("Year of Estimate", options=year_options, key="header_modal_est_yr")

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    
    if st.button("Start Application →", use_container_width=True, type="primary"):
        # Logic to handle starting the application
        if selected_m == "contract_management":
             est_no = st.session_state.get("header_modal_est_no", "").strip()
             est_yr = st.session_state.get("header_modal_est_yr")
             nm_proj = st.session_state.get("header_modal_nm_proj", "").strip()
             if not est_no or not est_yr or not nm_proj:
                 st.error("⚠️ Please enter Name of Project, Estimate Number and Year.")
                 return
             
             # Check for existing drafts (must match Project + Est No + Year)
             existing_ones = get_submissions_by_estimate(est_no, est_yr, module=selected_m, name_of_project=nm_proj)

             if existing_ones:
                 st.session_state.active_modal_data = {
                     "module": selected_m,
                     "est_no": est_no,
                     "est_yr": est_yr,
                     "sub": existing_ones[0]
                 }
                 st.rerun()

        # If starting fresh, clear stale state first to reset initialization flags
        clear_module_state(selected_m)
        
        # Then set the NEW initial values
        initial_est_no = None
        initial_est_yr = None
        initial_nm_proj = None
        if selected_m == "contract_management":
             initial_est_no = est_no
             initial_est_yr = est_yr
             initial_nm_proj = nm_proj
             st.session_state.initial_estimate_number = est_no
             st.session_state.initial_year_of_estimate = est_yr
             st.session_state.initial_name_of_project = nm_proj
        
        # --- CREATE MASTER RECORD IMMEDIATELY ---
        try:
             target_m_id = create_master_submission(
                 user_id, selected_m, modules.get(selected_m, []), 
                 status='DRAFT',
                 estimate_number=initial_est_no,
                 year_of_estimate=initial_est_yr,
                 name_of_project=initial_nm_proj
             )
             st.session_state.master_id = target_m_id
             st.session_state.current_view = selected_m
             st.rerun()
        except Exception as e:
             st.error(f"❌ Error starting application: {e}")
             return

    if st.button("✖️ Close", use_container_width=True):
        st.rerun()


def is_section_complete(user_id, table, master_id=None):
    percentage, completed, total = get_user_progress(user_id, [table], master_id=master_id)
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


def render_metric_cards(total, submitted, drafts, current_filter, card_type="user"):
    """Render status metric cards as clickable buttons."""
    prefix = f"{card_type}_"
    num_cols = 3
    cols = st.columns(num_cols)

    with cols[0]:
        st.markdown(f"""
        <div class="metric-card total {'active' if current_filter == 'ALL' else ''}">
            <div class="metric-number">{total}</div>
            <div class="metric-label">Total Applications</div>
        </div>""", unsafe_allow_html=True)
        if st.button("All", key=f"{prefix}btn_all", use_container_width=True):
            if card_type == "user":
                st.session_state.user_status_filter = "ALL"
                st.session_state.dashboard_page = 1
            else:
                st.session_state.status_filter = "ALL"
                st.session_state.admin_review_page = 1
            st.rerun()

    with cols[1]:
        st.markdown(f"""
        <div class="metric-card pending {'active' if current_filter == 'COMPLETED' else ''}">
            <div class="metric-number">{submitted}</div>
            <div class="metric-label">Completed Audits</div>
        </div>""", unsafe_allow_html=True)
        if st.button("Completed", key=f"{prefix}btn_submitted", use_container_width=True):
            if card_type == "user":
                st.session_state.user_status_filter = "COMPLETED"
                st.session_state.dashboard_page = 1
            else:
                st.session_state.status_filter = "COMPLETED"
                st.session_state.admin_review_page = 1
            st.rerun()

    with cols[2]:
        st.markdown(f"""
        <div class="metric-card draft {'active' if current_filter == 'DRAFT' else ''}">
            <div class="metric-number">{drafts}</div>
            <div class="metric-label">Draft Applications</div>
        </div>""", unsafe_allow_html=True)
        if st.button("Drafts", key=f"{prefix}btn_drafts", use_container_width=True):
            if card_type == "user":
                st.session_state.user_status_filter = "DRAFT"
                st.session_state.dashboard_page = 1
            else:
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

# --- Global Module & Permissions Config ---
allowed = st.session_state.get("allowed_modules", "")
if allowed:
    allowed_list = allowed.split(",")
    modules = {k: v for k, v in all_modules.items() if k in allowed_list}
else:
    # If no modules assigned, show nothing in sidebar except dashboard
    modules = {}

module_display_map = {m: m.replace("_", " ").title() for m in modules.keys()}


# ================= NAVIGATION HANDLING =================
# --- Unified Link Handler for HTML elements (Header Links) ---
if st.query_params.get("nav") == "Main":
    st.session_state.current_view = "Main"
    st.query_params.clear()
    st.rerun()
elif st.query_params.get("nav") == "Logout":
    cookies["logged_in"] = "0"
    cookies.save()
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.query_params.clear()
    st.rerun()
elif st.query_params.get("nav") == "NewApp":
    st.session_state.show_new_app_modal = True
    st.query_params.clear()
    st.rerun()

# =====================================================
# ================= USER SIDE =========================
# =====================================================

if not is_admin:
    # --- TRIGGER NEW APP MODAL ---
    if st.session_state.get("show_new_app_modal"):
        del st.session_state["show_new_app_modal"]
        if 'show_new_application_dialog' in locals() or 'show_new_application_dialog' in globals():
            show_new_application_dialog()

    if "current_view" not in st.session_state:
        st.session_state.current_view = "Main"
    
    current_view_key = st.session_state.current_view

    # Map current view key to a display name for selected_module if it's a module
    if current_view_key == "Main":
        selected_module = "Main"
    else:
        selected_module = module_display_map.get(current_view_key, current_view_key)

    # Reset form initialization when module changes
    if "current_module" not in st.session_state:
        st.session_state.current_module = selected_module
    
    if st.session_state.current_module != selected_module:
        for key in list(st.session_state.keys()):
            if key.endswith("_initialized"):
                del st.session_state[key]
        st.session_state.current_module = selected_module

    # ---------- GLOBAL MODAL TRIGGERS ----------
    # --- TRIGGER SUBMISSION DETAILS FROM MODAL ---
    if st.session_state.get("sub_to_view"):
        sub_to_view = st.session_state.get("sub_to_view")
        mode = st.session_state.get("sub_view_mode", "user")
        del st.session_state["sub_to_view"]
        if "sub_view_mode" in st.session_state:
            del st.session_state["sub_view_mode"]
        show_submission_details(sub_to_view, mode=mode)

    # --- MODAL PROMPT TRIGGER ---
    if st.session_state.get("active_modal_data"):
        show_duplicate_submission_modal()

    # --- TRIGGER NEW APP FROM MODAL ---
    if st.session_state.get("trigger_new_app_from_modal"):
        del st.session_state["trigger_new_app_from_modal"]
        # Save values before clearing
        saved_no = st.session_state.get("initial_estimate_number")
        saved_yr = st.session_state.get("initial_year_of_estimate")
        saved_nm = st.session_state.get("initial_name_of_project")
        clear_module_state("contract_management")
        # Restore values
        st.session_state.initial_estimate_number = saved_no
        st.session_state.initial_year_of_estimate = saved_yr
        st.session_state.initial_name_of_project = saved_nm

        st.session_state.master_id = None
        st.session_state.current_view = "contract_management"
        st.rerun()

    # ---------- MAIN PAGE ----------


    if selected_module == "Main":

        st.markdown(f"""<div class="hero-banner">
            <h1>👋 Welcome Back, {st.session_state.username}!</h1>
            <p>Access your modules and manage your submissions from this central portal.</p>
        </div>""", unsafe_allow_html=True)

        # Fetch data early for use in forms/logic
        draft_summaries = get_user_draft_summaries(user_id, all_modules)

        # --- Dashboard Content (Start New Application section removed - now in header) ---
        
        if not modules:
            st.warning("⚠️ **No modules have been assigned to your account yet.** Please contact your administrator to grant access.")

            def handle_start_click():
                sel_m_key = st.session_state.get("new_app_sel_key")
                curr_uid = st.session_state.get("user_id")
                
                if sel_m_key:
                    # Check for existing drafts generally (other modules)
                    existing_drafts = [d for d in draft_summaries if d.get("module") == sel_m_key]
                    
                    if sel_m_key == "contract_management":
                        est_no = st.session_state.get("new_app_est_no", "").strip()
                        est_yr = st.session_state.get("new_app_est_yr")
                        if not est_no or not est_yr:
                            st.error("⚠️ Please enter Estimate Number and Year before starting.")
                            return
                        
                        # Only block/warn if there is an existing DRAFT for this estimate.
                        # Multiple completed ones are now allowed.
                        # Convert year integer to date for DB compatibility
                        est_yr_date = datetime.date(est_yr, 1, 1) if isinstance(est_yr, int) else est_yr
                        existing_ones = get_submissions_by_estimate(est_no, est_yr_date, module=sel_m_key)

                        if existing_ones:
                            st.session_state.active_modal_data = {
                                "module": sel_m_key,
                                "est_no": est_no,
                                "est_yr": est_yr,
                                "sub": existing_ones[0]
                            }
                            return

                    
                    elif existing_drafts:
                        # For other modules, show the standard draft prompt (Now as a modal too)
                        st.session_state.active_modal_data = {
                            "module": sel_m_key,
                            "est_no": None,
                            "est_yr": None,
                            "sub": existing_drafts[0]
                        }
                        return
                    
                    # If no duplicates/drafts, start fresh
                    clear_module_state(sel_m_key)
                    if sel_m_key == "contract_management":
                        st.session_state.initial_estimate_number = st.session_state.get("new_app_est_no")
                        st.session_state.initial_year_of_estimate = st.session_state.get("new_app_est_yr")
                    
                    st.session_state.master_id = None
                    st.session_state.current_view = sel_m_key
            
            # --- Module Selection & Estimate Inputs ---
            if not is_admin:
                c_sel, c_btn = st.columns([5, 1])
                with c_sel:
                    selected_m = st.selectbox(
                        "Select Module", 
                        options=list(module_display_map.keys()), 
                        format_func=lambda x: module_display_map[x],
                        key="new_app_sel_key",
                        label_visibility="collapsed"
                    )
                
                # Show estimate inputs if Contract Management is selected
                if selected_m == "contract_management":
                    # Sanitize new_app_est_yr to be an integer (year)
                    if "new_app_est_yr" in st.session_state and not isinstance(st.session_state.new_app_est_yr, int):
                        del st.session_state.new_app_est_yr
                    if "new_app_est_yr" not in st.session_state:
                        st.session_state.new_app_est_yr = datetime.datetime.now().year

                    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
                    ce1, ce2 = st.columns(2)
                    with ce1:
                        st.text_input("Estimate Number", placeholder="Enter Estimate Number", key="new_app_est_no")
                    with ce2:
                        current_year = datetime.datetime.now().year
                        year_options = list(range(current_year, 1999, -1)) # Show most recent first
                        st.selectbox("Year of Estimate", options=year_options, key="new_app_est_yr")

                with c_btn:
                    st.button("Start →", key="start_new_app_btn", use_container_width=True, type="primary", on_click=handle_start_click)

                
                

        st.markdown('<div class="section-header"><h3>📋 Your Activity & Submissions</h3></div>', unsafe_allow_html=True)

        if "user_status_filter" not in st.session_state:
            st.session_state.user_status_filter = "ALL"

        # st.markdown("<div style='height:2px'></div>", unsafe_allow_html=True)

        raw_submissions = get_user_master_submissions(user_id, module=None)
        
        # Filter submissions by current module permissions
        allowed_list = st.session_state.get("allowed_modules", "").split(",") if st.session_state.get("allowed_modules") else []
        submissions = [s for s in raw_submissions if s.get("module") in allowed_list]

        # Get draft count for user
        draft_count = len(draft_summaries)
        
        submitted_count = len(submissions)
        total_count = submitted_count + draft_count

        if total_count == 0:
            st.markdown(f"""
            <div class="empty-state">
                <div class="empty-icon">📂</div>
                <p>You have not created any applications yet.</p>
                <small>Select a module from the grid above to get started.</small>
            </div>
            """, unsafe_allow_html=True)
        else:
            # Combine submissions and drafts for unified view if filter is ALL
            all_items = submissions + draft_summaries
            all_items.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)

            render_metric_cards(
                total_count, submitted_count, draft_count,
                st.session_state.user_status_filter, card_type="user"
            )

        # st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        if submissions or draft_summaries:
            if st.session_state.user_status_filter == "COMPLETED":
                raw_filtered = [s for s in all_items if s["status"] != "DRAFT"]
            elif st.session_state.user_status_filter == "DRAFT":
                raw_filtered = [s for s in all_items if s["status"] == "DRAFT"]
            else:
                raw_filtered = all_items
            
            # --- Grouping Logic ---
            grouped_data = {}
            for item in raw_filtered:
                e_no = item.get("estimate_number") or "---"
                e_yr = item.get("year_of_estimate") or "---"
                
                # Group by estimate if present, otherwise group by master_id
                if e_no != "---":
                    # Case-insensitive grouping by estimate and just the year
                    # Use est_yr.year if it's a date, otherwise just take what's there
                    yr_val = getattr(e_yr, 'year', e_yr)
                    group_key = (str(e_no).strip().lower(), str(yr_val))
                else:
                    group_key = (f"master_{item['id']}", None)
                
                if group_key not in grouped_data:
                    grouped_data[group_key] = {
                        "estimate_number": e_no,
                        "year_of_estimate": e_yr,
                        "latest_date": item.get("created_at"),
                        "count": 1,
                        "module": item.get("module"),
                        "sub": item
                    }
                else:
                    grouped_data[group_key]["count"] += 1
                    if (item.get("created_at") or "") > (grouped_data[group_key]["latest_date"] or ""):
                        grouped_data[group_key]["latest_date"] = item.get("created_at")
            
            filtered_subs = sorted(grouped_data.values(), key=lambda x: str(x["latest_date"] or ""), reverse=True)
            
            # Show simple message if no filtered results
            if not filtered_subs:
                msg = f"No {st.session_state.user_status_filter.lower()} applications found." if st.session_state.user_status_filter != "ALL" else "No applications found."
                st.info(msg)
            else:
                paged_subs, start_idx, total_pages = paginate_list(filtered_subs, "dashboard_page", render_controls=False)
                
                # Tabular Header
                h1, h2, h3, h4, h5 = st.columns([0.5, 3.0, 1.5, 2.5, 2.5])
                h1.markdown("**S.No**")
                h2.markdown("**Estimate Number**")
                h3.markdown("**Year**")
                h4.markdown("**Date**")
                h5.markdown("**No. of Applications**")
                st.markdown("<hr style='margin:0; margin-bottom:10px;'>", unsafe_allow_html=True)

                for i, group in enumerate(paged_subs):
                    s_no = start_idx + i + 1
                    est_no = group["estimate_number"]
                    est_yr = group["year_of_estimate"]
                    app_count = group["count"]
                    latest_date = group["latest_date"]
                    
                    r1, r2, r3, r4, r5 = st.columns([0.5, 3.0, 1.5, 2.5, 2.5])
                    r1.write(f"{s_no}")
                    
                    with r2:
                        if est_no and est_no != "---":
                            if st.button(f"**{est_no}**", key=f"btn_grp_{i}_{est_no}", use_container_width=True):
                                show_estimate_group_dialog(est_no, est_yr, user_id=user_id, module=group.get("module"))

                        else:
                            # If no estimate, show module name and link to dialog specifically for this item
                            mod_name = module_display_map.get(group.get("module"), "Draft")
                            if st.button(f"**{mod_name} (Draft)**", key=f"btn_grp_{i}_{est_no}", use_container_width=True):
                                show_estimate_group_dialog(est_no, est_yr, user_id=user_id, module=group.get("module"))

                    
                    with r3:
                        y_val = est_yr.year if hasattr(est_yr, 'year') else est_yr
                        st.write(str(y_val))
                    with r4:
                        st.write(fmt_dt(latest_date))
                    with r5:
                        st.markdown(f"""
                        <div style="background:#f1f5f9; border-radius:30px; padding:4px 12px; display:inline-block; font-weight:700; color:#1e3a5f; font-size:13px;">
                            👥 {app_count} Application{'s' if app_count > 1 else ''}
                        </div>
                        """, unsafe_allow_html=True)

                # st.markdown('</div>', unsafe_allow_html=True)
                
                # Navigation at bottom
                render_pagination_footer("dashboard_page", total_pages)

        render_footer()
        st.stop()

    # ---- Module Form Area ----

    CUSTOM_TABLE_ORDER = {
        "contract_management": [
            "contract_management_admin_financial_sanction",
            "contract_management_technical_sanction",
            "contract_management_tender_award_contract",
            "contract_management_contract_master",
            "contract_management_payments_recoveries",
            "contract_management_budget_summary"
        ]
    }

    module_name = current_view_key
    if module_name in CUSTOM_TABLE_ORDER:
        ordered = [t for t in CUSTOM_TABLE_ORDER[module_name] if t in modules.get(module_name, [])]
        others = sorted([t for t in modules.get(module_name, []) if t not in CUSTOM_TABLE_ORDER[module_name]])
        tables = ordered + others
    else:
        tables = sorted(modules.get(module_name, []))
    prefix = module_name + "_"

    if st.session_state.master_id:
        can_edit = can_user_edit(st.session_state.master_id)
    else:
        can_edit = True

    # ---- Progress Section ----
    percentage, completed, total = get_user_progress(user_id, tables, master_id=st.session_state.master_id)


    # ---- Module Header & Breadcrumbs ----
    st.markdown(f"""
    <div style="margin-bottom:20px;">
        <h2 style="margin:0; color:#1e293b;">{selected_module}</h2>
        <p style="margin:0; color:#64748b; font-size:15px;">Fill in all the sections below to complete your audit application.</p>
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
        is_complete = is_section_complete(user_id, table, master_id=st.session_state.master_id)
        label = f"✅ {section_name}" if is_complete else f"⬜ {section_name}"
        tab_labels.append(label)

    tabs = st.tabs(tab_labels)

    # Read estimate fields from first tab draft
    first_table = tables[0]
    first_table_draft = get_user_draft(first_table, user_id, master_id=st.session_state.master_id)

    estimate_number = None
    year_of_estimate = None
    name_of_project = None
    if first_table_draft:
        estimate_number = first_table_draft.get("estimate_number")
        year_of_estimate = first_table_draft.get("year_of_estimate")
        name_of_project = first_table_draft.get("name_of_project")
    elif module_name == "contract_management":
        # Check for initial values from Main page
        estimate_number = st.session_state.get("initial_estimate_number")
        year_of_estimate = st.session_state.get("initial_year_of_estimate")
        name_of_project = st.session_state.get("initial_name_of_project")

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
                draft = get_user_draft(table, user_id, master_id=st.session_state.master_id)

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
                            
                            # Extract year if it's for year_of_estimate selectbox
                            if col == "year_of_estimate" and val:
                                val = val.year if hasattr(val, 'year') else val
                        else:
                            val = str(val)
                        # Handle year conversion if still in date format (e.g. 2026-01-01)
                        if col == "year_of_estimate" and "-" in str(val) and len(str(val)) > 7:
                            try: 
                                y = int(str(val).split("-")[0])
                                val = f"{y}-{str(y+1)[2:]}"
                            except: pass
                        st.session_state[key] = val
                    else:
                        # Fallback for new applications (no draft yet)
                        if dtype in ("integer", "bigint", "smallint"):
                            st.session_state.setdefault(key, 0)
                        elif dtype in ("numeric", "double precision", "real"):
                            st.session_state.setdefault(key, 0.0)
                        elif dtype == "date":
                            st.session_state.setdefault(key, None)
                        else:
                            st.session_state.setdefault(key, "")
                        
                        # High-priority pre-fill for Master Estimate fields (Tab 1 fresh start)
                        if is_master_form and not draft:
                            if col == "estimate_number" and st.session_state.get("initial_estimate_number"):
                                st.session_state[key] = str(st.session_state.initial_estimate_number)
                            elif col == "year_of_estimate" and st.session_state.get("initial_year_of_estimate"):
                                val = st.session_state.initial_year_of_estimate
                                # Convert to string for text fields, keep as int for selectbox/number fields
                                if dtype in ("integer", "bigint", "smallint", "date"):
                                    st.session_state[key] = val
                                else:
                                    st.session_state[key] = str(val)
                            elif col == "name_of_project" and st.session_state.get("initial_name_of_project"):
                                st.session_state[key] = str(st.session_state.initial_name_of_project)

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
                        
                        # Skip Estimate fields for non-contract modules
                        if col in ["estimate_number", "year_of_estimate", "name_of_project"] and module_name != "contract_management":
                            continue
                            
                        dtype = col_info["data_type"]
                        key = f"{table}_{col}"

                        target_col = col1 if index % 2 == 0 else col2

                        with target_col:
                            label = col.replace("_", " ").title()
                            if any(word in col.lower() for word in money_keywords):
                                label = f"{label} (₹)"

                            # Disable estimate fields for contract_management
                            is_disabled = (module_name == "contract_management" and col in ["estimate_number", "year_of_estimate", "name_of_project"])

                            if dtype in ("integer", "bigint", "smallint"):
                                value = st.number_input(label, step=1, key=key, disabled=is_disabled)

                            elif dtype in ("numeric", "double precision", "real"):
                                value = st.number_input(label, key=key, disabled=is_disabled)

                            elif dtype == "date":
                                if col == "year_of_estimate":
                                    current_year = datetime.datetime.now().year
                                    year_options = [f"{y}-{str(y+1)[2:]}" for y in range(current_year, 1999, -1)]
                                    value = st.selectbox(label, options=year_options, key=key, disabled=is_disabled)
                                else:
                                    value = st.date_input(label, key=key, disabled=is_disabled)

                            elif dtype == "boolean" or dtype == "bool":
                                bool_options = ["", "Yes", "No"]
                                idx = 0
                                curr_val = st.session_state.get(key)
                                if curr_val is True or str(curr_val).lower() == "true":
                                    idx = 1
                                elif curr_val is False or str(curr_val).lower() == "false":
                                    idx = 2
                                selection = st.selectbox(label, options=bool_options, index=idx, key=f"{key}_select", disabled=is_disabled)
                                if selection == "Yes":
                                    value = True
                                elif selection == "No":
                                    value = False
                                else:
                                    value = None
                            else:
                                value = st.text_input(label, key=key, disabled=is_disabled)

                        form_data[col] = value
                        # year_of_estimate is now a string financial year, no conversion needed
                        form_data[col] = value
                        if col not in ["estimate_number", "year_of_estimate", "name_of_project"] and value not in ("", None, 0, 0.0):
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
                        for req_col in ["estimate_number", "year_of_estimate", "name_of_project"]:
                            if req_col in form_data:
                                val = form_data.get(req_col)
                                if val in (None, "", 0, 0.0):
                                    disp = req_col.replace("_", " ").title()
                                    st.error(f"⚠️ {disp} is required. Please fill it in before saving.")
                                    st.stop()

                    # Atomic master creation and save
                    target_master_id = st.session_state.master_id
                    is_new_app = (target_master_id is None)

                    if is_new_app:
                        try:
                            target_master_id = create_master_submission(
                                user_id, module_name, tables, 
                                status='DRAFT',
                                estimate_number=estimate_number,
                                year_of_estimate=year_of_estimate
                            )
                        except ValueError as ve:
                            st.error(f"🚫 **Duplicate Application Found**\n{str(ve)}")
                            st.stop()
                        except Exception as e:
                            st.error(f"❌ Failed to create application: {e}")
                            st.stop()
                    
                    try:

                        save_draft_record(table, form_data, user_id, master_id=target_master_id)
                        st.session_state.master_id = target_master_id
                        st.success("✅ Section saved successfully!")
                        st.toast("📝 Application saved to drafts.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Failed to save section: {e}")
                        st.stop()

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
                        if col in ["estimate_number", "year_of_estimate", "name_of_project"]:
                            value = estimate_number if col == "estimate_number" else (name_of_project if col == "name_of_project" else year_of_estimate)
                            display_key = f"display_{table}_{col}"
                            
                            if value is None:
                                disp_val = ""
                            else:
                                disp_val = str(value)

                            # Always overwrite so rerun after first-tab save reflects immediately
                            st.session_state[display_key] = disp_val

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
                            if col == "year_of_estimate":
                                current_year = datetime.datetime.now().year
                                year_options = list(range(current_year, 1999, -1))
                                value = st.selectbox(label, options=year_options, key=key)
                            else:
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
                    # Convert year selectbox integer back to date for DB
                    if col == "year_of_estimate" and isinstance(value, int):
                        form_data[col] = datetime.date(value, 1, 1)

                    # Count filled fields excluding auto-filled estimate fields
                    if col not in ["estimate_number", "year_of_estimate"] and value not in ("", None, 0, 0.0):
                        filled_fields += 1

                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

                if st.button("💾 Save Section", key=f"save_{table}", use_container_width=True, type="primary"):

                    if not first_table_draft:
                        st.warning("⚠️ Please complete the first section before saving this one.")
                        st.stop()

                    if not can_edit:
                        st.warning("🔒 This application has been submitted and cannot be edited.")

                    elif filled_fields == 0:
                        st.warning("⚠️ Please fill in at least one field before saving.")

                    else:
                        table_col_names = [c["column_name"] for c in columns]
                        if "estimate_number" in table_col_names:
                            form_data["estimate_number"] = estimate_number
                        if "year_of_estimate" in table_col_names:
                            form_data["year_of_estimate"] = year_of_estimate
                        if "name_of_project" in table_col_names:
                            form_data["name_of_project"] = name_of_project
                        # Atomic master creation and save
                        target_master_id = st.session_state.master_id
                        is_new_app = (target_master_id is None)

                        if is_new_app:
                            try:
                                target_master_id = create_master_submission(
                                    user_id, module_name, tables, 
                                    status='DRAFT',
                                    estimate_number=estimate_number,
                                    year_of_estimate=year_of_estimate
                                )
                            except Exception as e:
                                err_str = str(e).lower()
                                if "unique_estimate" in err_str or "duplicate key" in err_str:
                                    st.error(f"⚠️ An application with Estimate No: **{estimate_number}** and Year: **{year_of_estimate}** already exists for this module. Please use a unique combination.")
                                else:
                                    st.error(f"❌ Failed to create application: {e}")
                                st.stop()
                        
                        try:
                            save_draft_record(table, form_data, user_id, master_id=target_master_id)
                            st.session_state.master_id = target_master_id
                            st.success("✅ Section saved successfully!")
                            st.toast("📝 Application saved to drafts.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Failed to save section: {e}")
                            st.stop()

    # ---------- FINAL SUBMIT ----------

    incomplete_sections = get_incomplete_forms(user_id, tables, master_id=st.session_state.master_id)

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
            # Simply update status from DRAFT to COMPLETED
            success = update_master_status(st.session_state.master_id, 'COMPLETED')
            if success:
                # Mark all associated draft rows as non-draft
                set_drafts_to_final(st.session_state.master_id, tables)
                st.balloons()
                st.success("🎉 Application submitted successfully!")
                st.session_state.master_id = None
                st.session_state.current_view = "Main"
                st.rerun()
            else:
                st.error("Failed to submit. Please try again.")


# =====================================================
# ================= ADMIN SIDE ========================
# =====================================================

if is_admin:

    if "status_filter" not in st.session_state:
        st.session_state.status_filter = "ALL"

    # --- TRIGGER SUBMISSION DETAILS FROM MODAL ---
    if st.session_state.get("sub_to_view"):
        sub_to_view = st.session_state.get("sub_to_view")
        mode = st.session_state.get("sub_view_mode", "admin")
        del st.session_state["sub_to_view"]
        if "sub_view_mode" in st.session_state:
            del st.session_state["sub_view_mode"]
        show_submission_details(sub_to_view, mode=mode)

    st.markdown(f"""<div class="hero-banner" style="background: linear-gradient(135deg, #4338ca, #312e81); margin-top: 0px;"><h1>🛡️ Admin Review Panel</h1><p style="margin:0;">Review submitted applications, manage accounts, and export reports.</p></div>""", unsafe_allow_html=True)

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
            applicant_options = ["--- Select Applicant ---", "🌐 All Users"] + list(users_df["username"])
            selected_user = st.selectbox(
                "Applicant",
                applicant_options,
                label_visibility="collapsed",
                help="Choose 'All Users' to see every submission, or pick a specific applicant"
            )

            if selected_user != "--- Select Applicant ---":
                # Reset page if user changed
                if "prev_selected_user" not in st.session_state:
                    st.session_state.prev_selected_user = selected_user
                if st.session_state.prev_selected_user != selected_user:
                    st.session_state.admin_review_page = 1
                    st.session_state.prev_selected_user = selected_user

                is_all_users = (selected_user == "🌐 All Users")

                if not is_all_users:
                    user_row = users_df[users_df["username"] == selected_user].iloc[0]
                    selected_user_id = int(user_row["id"])

                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

                # ---- Status Counts & Submissions ----
                if is_all_users:
                    # Aggregate submissions from all non-admin users
                    all_masters = []
                    all_drafts = []
                    agg_pending = agg_drafts = 0

                    for _, u_row in users_df.iterrows():
                        uid = int(u_row["id"])
                        uname = u_row["username"]
                        u_submitted, u_drafts = get_user_master_status_counts(uid, all_modules)
                        agg_pending  += u_submitted
                        agg_drafts   += u_drafts

                        u_masters = get_user_master_submissions_admin(uid)
                        all_masters.extend(u_masters)

                        u_draft_sums = get_user_draft_summaries(uid, all_modules)
                        for d in u_draft_sums:
                            d["created_by_user"] = uname
                        all_drafts.extend(u_draft_sums)

                    total = agg_pending + agg_drafts
                    submitted = agg_pending
                    
                    submissions = all_masters + all_drafts
                    submissions.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
                    
                    st.markdown("#### 📊 Submission Overview Of – All Users")
                    if total == 0:
                        st.markdown("""
                        <div class="empty-state">
                            <div class="empty-icon">🔍</div>
                            <p>No applications found across all users.</p>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        render_metric_cards(total, submitted, agg_drafts,
                                            st.session_state.status_filter, card_type="admin")

                else:
                    # Single user
                    submitted, drafts = get_user_master_status_counts(selected_user_id, all_modules)
                    total = submitted + drafts

                    st.markdown(f"#### 📊 Submission Overview Of – {selected_user}")
                    if total == 0:
                        st.markdown(f"""
                        <div class="empty-state">
                            <div class="empty-icon">🔍</div>
                            <p>No activity found for <b>{selected_user}</b>.</p>
                            <small>This user has no submissions or drafts currently.</small>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        render_metric_cards(total, submitted, drafts,
                                            st.session_state.status_filter, card_type="admin")

                    masters = get_user_master_submissions_admin(selected_user_id)
                    draft_summaries = get_user_draft_summaries(selected_user_id, all_modules)
                    for d in draft_summaries:
                        d["created_by_user"] = selected_user
                    submissions = masters + draft_summaries

                st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

                # ---- Submission List ----
                if submissions:
                    if st.session_state.status_filter == "COMPLETED":
                        filtered_subs = [s for s in submissions if s["status"] != "DRAFT"]
                    elif st.session_state.status_filter == "DRAFT":
                        filtered_subs = [s for s in submissions if s["status"] == "DRAFT"]
                    else:
                        filtered_subs = submissions
                    
                    if not filtered_subs:
                        st.info(f"No {st.session_state.status_filter.lower()} items found." if st.session_state.status_filter != "ALL" else "No items found.")
                    else:
                        # --- Group by Estimate for Simplified View ---
                        admin_groups = {}
                        for item in filtered_subs:
                            e_no = item.get("estimate_number") or "---"
                            e_yr = item.get("year_of_estimate") or "---"
                            status = item.get("status", "DRAFT")
                            yr_val = getattr(e_yr, 'year', e_yr)
                            g_key = (str(e_no).strip().lower(), str(yr_val))
                            
                            if g_key not in admin_groups:
                                admin_groups[g_key] = {
                                    "estimate_number": e_no,
                                    "year_of_estimate": e_yr,
                                    "latest_date": item.get("created_at"),
                                    "total_count": 1,
                                    "draft_count": 1 if status == "DRAFT" else 0
                                }
                            else:
                                admin_groups[g_key]["total_count"] += 1
                                if status == "DRAFT":
                                    admin_groups[g_key]["draft_count"] += 1
                                if (item.get("created_at") or "") > (admin_groups[g_key]["latest_date"] or ""):
                                    admin_groups[g_key]["latest_date"] = item.get("created_at")
                                    
                        display_list = sorted(admin_groups.values(), key=lambda x: str(x["latest_date"] or ""), reverse=True)
                        
                        st.markdown("#### 📋 Activity List")
                        paged_subs, start_idx, total_pages = paginate_list(display_list, "admin_review_page", render_controls=False)

                        st.markdown('<div class="estimate-link-list">', unsafe_allow_html=True)
                        # Enhanced Header: Style with CSS classes
                        st.markdown("""
                        <div class="activity-header">
                            <div style="display: flex; align-items: center; gap: 0;">
                                <div style="flex: 0.5;"><span>S.No</span></div>
                                <div style="flex: 2.5; padding-left: 20px;"><span>Estimate Number</span></div>
                                <div style="flex: 2.0; text-align: center;"><span>Total Applications</span></div>
                                <div style="flex: 2.0; text-align: center;"><span>Drafted</span></div>
                                <div style="flex: 2.0; text-align: center;"><span>Completed</span></div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        for i, group in enumerate(paged_subs):
                            s_no = start_idx + i + 1
                            est_no = group["estimate_number"]
                            est_yr = group["year_of_estimate"]
                            total_c = group["total_count"]
                            draft_c = group["draft_count"]
                            completed_c = total_c - draft_c
                            
                            # Row Card Start
                            st.markdown(f'<div class="activity-card">', unsafe_allow_html=True)
                            
                            r1, r2, r3, r4, r5 = st.columns([0.5, 2.5, 2.0, 2.0, 2.0])
                            
                            with r1:
                                st.markdown(f"<div style='padding-top:8px; font-weight:700; color:#64748b;'>#{s_no}</div>", unsafe_allow_html=True)
                            
                            with r2:
                                if est_no and est_no != "---":
                                    if st.button(f"**{est_no}**", key=f"adv_btn_est_grp_{i}_{est_no}", use_container_width=True):
                                        show_estimate_group_dialog(est_no, est_yr)
                                else:
                                    st.markdown("<div style='padding-top:8px; color:#94a3b8;'>---</div>", unsafe_allow_html=True)
                            
                            with r3:
                                st.markdown(f"""
                                <div style='text-align:center; padding-top:4px;'>
                                    <span class="activity-badge badge-total-count">{total_c}</span>
                                </div>
                                """, unsafe_allow_html=True)
                            
                            with r4:
                                st.markdown(f"""
                                <div style='text-align:center; padding-top:4px;'>
                                    <span class="activity-badge badge-draft-count">{draft_c}</span>
                                </div>
                                """, unsafe_allow_html=True)
                                
                            with r5:
                                st.markdown(f"""
                                <div style='text-align:center; padding-top:4px;'>
                                    <span class="activity-badge badge-comp-count">{completed_c}</span>
                                </div>
                                """, unsafe_allow_html=True)
                            
                            st.markdown("</div>", unsafe_allow_html=True) # Row Card End
                        
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                        # Navigation at bottom
                        render_pagination_footer("admin_review_page", total_pages)

                elif st.session_state.status_filter != "ALL":
                    st.markdown("""
                    <div class="empty-state">
                        <div class="empty-icon">🔍</div>
                        <small>Try selecting a different filter or applicant.</small>
                    </div>
                    """, unsafe_allow_html=True)

render_footer()
