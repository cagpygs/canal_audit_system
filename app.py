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
    get_user_by_id,
    get_user_draft,
    get_user_draft_summaries,
    get_user_master_status_counts,
    get_user_master_submissions,
    get_user_master_submissions_admin,
    get_user_progress,
    save_draft_record,
    set_drafts_to_final,
    toggle_user_status,
    update_master_attachments,
    update_master_status,
    update_master_submission,
    update_user_modules,
)
from streamlit_cookies_manager.encrypted_cookie_manager import EncryptedCookieManager
import datetime
import base64
import html
import os
import streamlit as st

from error_utils import log_exception, report_error

st.set_page_config(
    page_title="CAG Audit Management System",
    page_icon="🏛️",
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
    LOGO_IMG   = "🏛️"
    LOGO_SMALL = "🏛️"


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
                Irrigation Audit Wing &nbsp;·&nbsp; Uttar Pradesh &nbsp;·&nbsp; Secure Government Portal
            </div>
        </div>
        <div>
            <div class="cag-footer-right-slogan">SATYAMEVA JAYATE</div>
            <div class="cag-footer-right-sub">Developed by DAC Cell · Latief</div>
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
                st.error("❌ Your permission has been revoked. You have been logged out.")
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

# =====================================================
# ================= TOP NAVIGATION BAR ================
# =====================================================
st.markdown(f"""
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
    <div class="nav-links-left">
        <a href="./?nav=Main" target="_self"
           class="nav-item-minimal">
           Dashboard
        </a>
        <a href="./?nav=NewApp" target="_self" class="nav-item-minimal">Create New Estimate</a>
    </div>
    <div class="nav-right-actions">
        <span style="font-size:11px; color:rgba(255,255,255,0.45); letter-spacing:0.3px;">
            {role_label}
        </span>
        <a href="./?nav=Logout" target="_self" class="logout-link">Sign Out</a>
        <div class="user-pill">
            <div class="avatar-mini">
                {st.session_state.username[0].upper() if st.session_state.get("username") else "U"}
            </div>
            <div style="font-size:13px; font-weight:600; color:#fff;">
                {st.session_state.get("username", "User")}
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)


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
        return "—"
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return "—"
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


@st.dialog("📋 Submission Details", width="large", dismissible=False)
def show_submission_details(sub):
    module_key   = sub.get("module") or ""
    module_label = module_key.replace("_", " ").title()
    module_label_safe = esc_html(module_label)
    status       = sub["status"]
    is_synthetic_draft = str(sub.get("id", "")).startswith("draft_")

    created_at       = sub.get("created_at", "")
    created_by_user  = sub.get("created_by_user") or "Unknown"
    created_by_user_safe = esc_html(created_by_user)
    created_at_safe = esc_html(fmt_dt(created_at))

    if status == "DRAFT":
        status_color = "#d97706"
    else:
        status_color = "#059669"

    if module_key == "contract_management":
        est_no  = sub.get("estimate_number") or "---"
        est_yr  = sub.get("year_of_estimate") or "---"
        y_val   = est_yr.year if hasattr(est_yr, 'year') else est_yr
        display_key = f"{est_no} ({y_val})" if est_no != "---" else "---"
        est_html = (f'<div style="font-size:12px; font-weight:600; color:#374151; margin-bottom:4px;">'
                    f'Estimate: {esc_html(display_key)}</div>')
    else:
        est_html = ""

    st.markdown(f"""
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
    """, unsafe_allow_html=True)

    if is_synthetic_draft:
        uid          = sub.get("user_id")
        module_tables = all_modules.get(module_key, [])
        full_data    = get_full_draft_data(uid, module_tables)
    else:
        full_data = get_full_submission_data(sub["id"])

    if not full_data:
        st.info("No data entries found yet for this draft.")

    for section_name, df_section in full_data.items():
        clean_name = (section_name.replace(module_key + "_", "").replace("_", " ").title())
        st.markdown(f"#### 📄 {clean_name}")
        st.dataframe(df_section, use_container_width=True)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    est_path = sub.get("estimate_attachment")
    sar_path = sub.get("sar_attachment")
    if est_path or sar_path:
        st.markdown("#### 📂 Attached Documents")
        col_at1, col_at2 = st.columns(2)
        if est_path and os.path.exists(est_path):
            with col_at1:
                with open(est_path, "rb") as f:
                    st.download_button("📑 Download Estimate", data=f,
                        file_name=os.path.basename(est_path), key=f"dl_est_{sub['id']}",
                        use_container_width=True)
        if sar_path and os.path.exists(sar_path):
            with col_at2:
                with open(sar_path, "rb") as f:
                    st.download_button("📑 Download SAR", data=f,
                        file_name=os.path.basename(sar_path), key=f"dl_sar_{sub['id']}",
                        use_container_width=True)

    st.markdown("---")

    if is_synthetic_draft:
        st.info("💡 This is a **Draft** module. It has not been submitted yet.")
        return

    if status != "DRAFT":
        pdf = export_master_submission_pdf(sub["id"])
        st.download_button("📥 Download PDF Record", pdf,
            file_name=f"submission_{sub['id']}.pdf", mime="application/pdf",
            key=f"dlg_pdf_{sub['id']}", use_container_width=True, type="primary")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    if st.button("✖️ Close", key=f"close_sub_details_{sub.get('id','def')}", use_container_width=True):
        for k in ["sub_to_view", "sub_view_mode"]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()


@st.dialog("📂 Applications for Estimate", width="large", dismissible=False)
def show_estimate_group_dialog(est_no, est_yr, user_id=None, module=None):
    y_val = est_yr
    st.markdown(f"#### Grouped by Estimate: **{est_no}** ({y_val})")

    is_admin_user = st.session_state.get("role") == "admin"

    if not is_admin_user:
        if st.button("➕ Start New Application for this Estimate", key=f"btn_new_app_grp_{est_no}",
                     use_container_width=True, type="primary"):
            st.session_state.trigger_new_app_from_modal = True
            st.session_state.initial_estimate_number    = est_no
            st.session_state.initial_year_of_estimate   = est_yr
            submissions = get_submissions_by_estimate(est_no, est_yr, user_id=None, module=None)
            if submissions:
                for sub in submissions:
                    if sub.get('name_of_project'):
                        st.session_state.initial_name_of_project = sub.get('name_of_project')
                        break
            if "active_est_dlg" in st.session_state:
                del st.session_state.active_est_dlg
            st.rerun()
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

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
            status       = s.get("status", "DRAFT")
            status_bg    = "#fffbeb" if status == "DRAFT" else "#ecfdf5"
            status_text_c= "#92400e" if status == "DRAFT" else "#065f46"
            status_bdr   = "#fcd34d" if status == "DRAFT" else "#a7f3d0"

            with r1:  st.write(f"**{i}**")
            with r_id: st.code(f"{s['id']}")
            with r2:  st.write(s.get("created_by_user", "Unknown"))
            with r3:  st.write(fmt_dt(s.get("created_at")))
            with r4:
                st.markdown(
                    f'<span style="background:{status_bg}; color:{status_text_c}; '
                    f'border:1px solid {status_bdr}; padding:2px 10px; border-radius:4px; '
                    f'font-size:11px; font-weight:700;">{status}</span>',
                    unsafe_allow_html=True
                )
                if status == "COMPLETED":
                    cnt = sum([
                        1 if (s.get("estimate_attachment") or "").strip() else 0,
                        1 if (s.get("sar_attachment") or "").strip() else 0,
                    ])
                    if cnt == 0:
                        st.markdown("<div style='margin-top:4px;font-size:11px;font-weight:600;color:#dc2626;'>❌ Missing Files</div>", unsafe_allow_html=True)
                    elif cnt == 1:
                        st.markdown("<div style='margin-top:4px;font-size:11px;font-weight:600;color:#d97706;'>⚠️ 1/2 Uploaded</div>", unsafe_allow_html=True)
                    else:
                        st.markdown("<div style='margin-top:4px;font-size:11px;font-weight:600;color:#059669;'>✅ Both Uploaded</div>", unsafe_allow_html=True)

            with r6:
                if status == "DRAFT" and not is_admin_user:
                    if st.button("📝 Resume", key=f"btn_group_res_{s['id']}", use_container_width=True):
                        clear_module_state(s.get("module"))
                        st.session_state.master_id    = s["id"]
                        st.session_state.current_view = s.get("module")
                        if "active_est_dlg" in st.session_state:
                            del st.session_state.active_est_dlg
                        st.rerun()
                else:
                    v1, v2 = st.columns(2)
                    with v1:
                        if st.button("🔍 View", key=f"btn_group_view_{s['id']}", use_container_width=True):
                            st.session_state.sub_to_view  = s
                            st.session_state.sub_view_mode = "admin" if is_admin_user else "user"
                            st.rerun()
                    with v2:
                        if status == "COMPLETED":
                            if st.button("📤 Upload", key=f"btn_group_up_{s['id']}", use_container_width=True):
                                st.session_state.show_up_id = s['id']
                                st.rerun()

            st.markdown("<hr style='margin:8px 0; border:0; border-top:1px solid #f3f4f6;'>",
                        unsafe_allow_html=True)

        # Inline uploader
        if st.session_state.get("show_up_id"):
            up_id  = st.session_state.show_up_id
            st.markdown("---")
            st.markdown(f"#### 📤 Upload Documents for ID: `{up_id}`")
            m_info   = get_master_submission(up_id)
            f_data   = get_full_submission_data(up_id)
            m_key    = m_info.get("module")
            m_tables = all_modules.get(m_key, [])
            first_t  = m_tables[0] if m_tables else None
            sub_d    = f_data.get(first_t)

            def clean_n(s): return "".join([c if c.isalnum() or c in ('-','_') else '_' for c in str(s)])
            if sub_d is not None and not sub_d.empty:
                t_row = sub_d.iloc[0]
                e_no  = clean_n(t_row.get("estimate_number", m_info.get("estimate_number","NA")))
                p_nm  = clean_n(t_row.get("name_of_project", m_info.get("name_of_project","NA")))
                e_yr  = clean_n(t_row.get("year_of_estimate", m_info.get("year_of_estimate","NA")))
            else:
                e_no = clean_n(m_info.get("estimate_number","NA"))
                p_nm = clean_n(m_info.get("name_of_project","NA"))
                e_yr = clean_n(m_info.get("year_of_estimate","NA"))

            c1, c2 = st.columns(2)
            with c1:
                curr_est = m_info.get("estimate_attachment")
                if curr_est and os.path.exists(curr_est):
                    st.success(f"✅ Estimate on record: `{os.path.basename(curr_est)}`")
                est_f = st.file_uploader("📑 Upload / Replace Estimate",
                    type=['pdf','docx','xlsx','jpg','png'], key=f"dlg_up_est_{up_id}")
                if est_f:
                    fid = f"{est_f.name}_{est_f.size}"
                    if st.session_state.get(f"last_up_est_{up_id}") != fid:
                        ext   = os.path.splitext(est_f.name)[1]
                        spath = os.path.join("uploads", f"Estimate_{e_no}_{p_nm}_{e_yr}{ext}")
                        with open(spath, "wb") as f: f.write(est_f.getbuffer())
                        update_master_attachments(up_id, estimate_path=spath)
                        st.session_state[f"last_up_est_{up_id}"] = fid
                        st.success("Estimate uploaded successfully!")
                        st.rerun()
            with c2:
                curr_sar = m_info.get("sar_attachment")
                if curr_sar and os.path.exists(curr_sar):
                    st.success(f"✅ SAR on record: `{os.path.basename(curr_sar)}`")
                sar_f = st.file_uploader("📑 Upload / Replace SAR",
                    type=['pdf','docx','xlsx','jpg','png'], key=f"dlg_up_sar_{up_id}")
                if sar_f:
                    fid = f"{sar_f.name}_{sar_f.size}"
                    if st.session_state.get(f"last_up_sar_{up_id}") != fid:
                        ext   = os.path.splitext(sar_f.name)[1]
                        spath = os.path.join("uploads", f"SAR_{e_no}_{p_nm}_{e_yr}{ext}")
                        with open(spath, "wb") as f: f.write(sar_f.getbuffer())
                        update_master_attachments(up_id, sar_path=spath)
                        st.session_state[f"last_up_sar_{up_id}"] = fid
                        st.success("SAR uploaded successfully!")
                        st.rerun()
            if st.button("Close Upload Panel", key="close_dlg_up"):
                del st.session_state.show_up_id
                st.rerun()

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    if st.button("✖️ Close", key=f"close_est_group_{est_no}", use_container_width=True):
        if "active_est_dlg" in st.session_state:
            del st.session_state.active_est_dlg
        st.rerun()


@st.dialog("📋 Application Already Exists", width="medium", dismissible=False)
def show_duplicate_submission_modal():
    data = st.session_state.get("active_modal_data")
    if not data:
        st.rerun()
        return
    m_key  = data["module"]
    est_no = data["est_no"]
    est_yr = data["est_yr"]
    sub    = data["sub"]
    status = sub["status"]
    yr_val = getattr(est_yr, 'year', est_yr)
    st.markdown(f"An application for **{est_no}** ({yr_val}) already exists.")
    if status == "DRAFT":
        st.warning("⚠️ **Existing draft found with same Estimate Number and Year.**")
        if st.button("📝 Resume Existing Draft", type="primary", use_container_width=True):
            clear_module_state(m_key)
            st.session_state.master_id    = sub["id"]
            st.session_state.current_view = m_key
            del st.session_state["active_modal_data"]
            st.rerun()
    else:
        st.error("🚫 **Submission Already Completed.** This estimate cannot be modified or duplicated.")
    if st.button("✖️ Close", use_container_width=True):
        del st.session_state["active_modal_data"]
        st.rerun()


@st.dialog("🚀 Start New Estimate", width="medium", dismissible=False)
def show_new_application_dialog():
    st.markdown("Select a module below to begin a new audit application.")
    selected_m = st.selectbox(
        "Select Module",
        options=list(module_display_map.keys()),
        format_func=lambda x: module_display_map[x],
        key="header_modal_sel_key"
    )
    if selected_m == "contract_management":
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.text_input("Name of Project", placeholder="Enter project name", key="header_modal_nm_proj")
        ce1, ce2 = st.columns(2)
        with ce1:
            st.text_input("Estimate Number", placeholder="e.g. EST/2024/001", key="header_modal_est_no")
        with ce2:
            current_year = datetime.datetime.now().year
            year_options = [f"{y}-{str(y+1)[2:]}" for y in range(current_year, 1999, -1)]
            st.selectbox("Year of Estimate", options=year_options, key="header_modal_est_yr")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    if st.button("Create Estimate →", use_container_width=True, type="primary"):
        if selected_m == "contract_management":
            est_no  = st.session_state.get("header_modal_est_no", "").strip()
            est_yr  = st.session_state.get("header_modal_est_yr")
            nm_proj = st.session_state.get("header_modal_nm_proj", "").strip()
            if not est_no or not est_yr or not nm_proj:
                st.error("⚠️ Please enter Name of Project, Estimate Number and Year.")
                return
            existing_ones = get_submissions_by_estimate(est_no, est_yr, module=selected_m, name_of_project=nm_proj)
            if existing_ones:
                st.session_state.active_modal_data = {
                    "module": selected_m, "est_no": est_no,
                    "est_yr": est_yr, "sub": existing_ones[0]
                }
                st.rerun()

        clear_module_state(selected_m)
        initial_est_no = initial_est_yr = initial_nm_proj = None
        if selected_m == "contract_management":
            initial_est_no  = est_no
            initial_est_yr  = est_yr
            initial_nm_proj = nm_proj
            st.session_state.initial_estimate_number  = est_no
            st.session_state.initial_year_of_estimate = est_yr
            st.session_state.initial_name_of_project  = nm_proj
        try:
            target_m_id = create_master_submission(
                user_id, selected_m, modules.get(selected_m, []),
                status='DRAFT',
                estimate_number=initial_est_no,
                year_of_estimate=initial_est_yr,
                name_of_project=initial_nm_proj
            )
            st.session_state.master_id    = target_m_id
            st.session_state.current_view = selected_m
            st.rerun()
        except Exception as e:
            report_error("❌ Error starting application.", e, "app.show_new_application_dialog")
            return

    if st.button("✖️ Close", use_container_width=True):
        st.rerun()


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
        if st.button("⬅️ Previous", key=f"prev_{key_prefix}",
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
        if st.button("Next ➡️", key=f"next_{key_prefix}",
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
    st.session_state.show_new_app_modal = True
    st.query_params.clear()
    st.rerun()


# =====================================================
# ================= USER SIDE =========================
# =====================================================
if not is_admin:

    # --- DIALOG DISPATCH ---
    if st.session_state.get("show_new_app_modal"):
        del st.session_state["show_new_app_modal"]
        show_new_application_dialog()

    elif st.session_state.get("sub_to_view"):
        sub_to_view = st.session_state.pop("sub_to_view")
        st.session_state.pop("sub_view_mode", "user")
        show_submission_details(sub_to_view)

    elif st.session_state.get("active_modal_data"):
        show_duplicate_submission_modal()

    elif st.session_state.get("active_est_dlg"):
        dlg = st.session_state.active_est_dlg
        show_estimate_group_dialog(dlg['est_no'], dlg['est_yr'],
                                   user_id=dlg.get('user_id'), module=dlg.get('module'))

    current_view_key = st.session_state.current_view
    selected_module  = "Main" if current_view_key == "Main" else module_display_map.get(current_view_key, current_view_key)

    if "current_module" not in st.session_state:
        st.session_state.current_module = selected_module
    if st.session_state.current_module != selected_module:
        for key in list(st.session_state.keys()):
            if key.endswith("_initialized"):
                del st.session_state[key]
        st.session_state.current_module = selected_module

    # Trigger new app from group modal
    if st.session_state.get("trigger_new_app_from_modal"):
        del st.session_state["trigger_new_app_from_modal"]
        saved_no = st.session_state.get("initial_estimate_number")
        saved_yr = st.session_state.get("initial_year_of_estimate")
        saved_nm = st.session_state.get("initial_name_of_project")
        clear_module_state("contract_management")
        st.session_state.initial_estimate_number  = saved_no
        st.session_state.initial_year_of_estimate = saved_yr
        st.session_state.initial_name_of_project  = saved_nm
        st.session_state.master_id    = None
        st.session_state.current_view = "contract_management"
        st.rerun()

    # =========================================================
    # ==================== MAIN DASHBOARD =====================
    # =========================================================
    if selected_module == "Main":

        username_display = esc_html(st.session_state.username or "Officer")
        st.markdown(f"""
        <div class="welcome-hero">
            <div style="font-size:11px; font-weight:700; color:#9ca3af; letter-spacing:1.1px;
                        text-transform:uppercase; margin-bottom:8px;">
                Irrigation Department · Uttar Pradesh
            </div>
            <h1>Welcome, {username_display}</h1>
            <p>Contract Management Portal — manage your submissions from this central portal.</p>
        </div>
        """, unsafe_allow_html=True)

        draft_summaries = get_user_draft_summaries(user_id)

        if not modules:
            st.warning("⚠️ **No modules have been assigned to your account yet.** Please contact your administrator.")

        # --- ACTIVITY SECTION ---
        st.markdown("""
        <div class="section-header">
            <h3>📋 Your Activity &amp; Submissions</h3>
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
                <div class="empty-icon">📂</div>
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
                            st.session_state.active_est_dlg = {
                                'est_no': est_no, 'est_yr': est_yr,
                                'user_id': user_id, 'module': group.get("module")
                            }
                            st.rerun()
                    with r3:
                        y_val = est_yr.year if hasattr(est_yr, 'year') else est_yr
                        st.write(str(y_val))
                    with r4:
                        st.write(fmt_dt(latest_dt))
                    with r56:
                        st.markdown(
                            f'<div class="apps-badge-static">📁 {app_count} '
                            f'Application{"s" if app_count > 1 else ""}</div>',
                            unsafe_allow_html=True
                        )
                    st.markdown("<hr style='margin:6px 0; border:0; border-top:1px solid #f3f4f6;'>",
                                unsafe_allow_html=True)

                render_pagination_footer("dashboard_page", total_pages)

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
            <h3>🎉 All Sections Complete!</h3>
            <p>Scroll down to review and submit your complete application.</p>
        </div>
        """, unsafe_allow_html=True)

    # --- Tabs ---
    tab_labels = []
    for table in tables:
        section_name = table.replace(prefix, "").replace("_", " ").title()
        is_complete  = is_section_complete(user_id, table, master_id=st.session_state.master_id)
        tab_labels.append(f"✅ {section_name}" if is_complete else f"⬜ {section_name}")

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
                    📌 <b>Please complete the first section first.</b><br>
                    You must save the first section before proceeding.
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="section-helper">
                    ✏️ <b>How to fill this section:</b> Fill all fields below then click
                    <b>💾 Save Section</b> at the bottom. You can edit any time before submitting.
                </div>
                """, unsafe_allow_html=True)

            # Initialize session state once
            if f"{table}_initialized" not in st.session_state:
                draft = get_user_draft(table, user_id, master_id=st.session_state.master_id)
                for col_info in columns:
                    col   = col_info["column_name"]
                    dtype = col_info["data_type"]
                    key   = f"{table}_{col}"
                    if draft and col in draft and draft[col] is not None:
                        val = draft[col]
                        if dtype in ("integer","bigint","smallint"):
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
                        if dtype in ("integer","bigint","smallint"):
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
                        target_col = col1 if index % 2 == 0 else col2
                        with target_col:
                            label = col.replace("_"," ").title()
                            if any(w in col.lower() for w in money_keywords):
                                label = f"{label} (₹)"
                            is_disabled = (module_name == "contract_management" and
                                           col in ["estimate_number","year_of_estimate","name_of_project"])
                            if dtype in ("integer","bigint","smallint"):
                                value = st.number_input(label, step=1, key=key, disabled=is_disabled)
                            elif dtype in ("numeric","double precision","real"):
                                value = st.number_input(label, key=key, disabled=is_disabled)
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

                    submitted = st.form_submit_button("💾 Save Section", use_container_width=True, type="primary")

                if submitted:
                    for col_info in columns:
                        if col_info["is_nullable"] == "NO":
                            col_name = col_info["column_name"]
                            val      = form_data.get(col_name)
                            if val in (None,"",0,0.0):
                                st.error(f"⚠️ {col_name.replace('_',' ').title()} is required.")
                                st.stop()
                    if filled_fields == 0:
                        st.warning("⚠️ Please fill in at least one field before saving.")
                        st.stop()
                    if module_name == "contract_management":
                        for req_col in ["estimate_number","year_of_estimate","name_of_project"]:
                            if req_col in form_data and form_data.get(req_col) in (None,"",0,0.0):
                                st.error(f"⚠️ {req_col.replace('_',' ').title()} is required.")
                                st.stop()

                    target_master_id = st.session_state.master_id
                    if target_master_id is None:
                        try:
                            target_master_id = create_master_submission(
                                user_id, module_name, tables, status='DRAFT',
                                estimate_number=estimate_number,
                                year_of_estimate=year_of_estimate)
                        except ValueError as ve:
                            st.error(f"🚫 **Duplicate Application Found:** {str(ve)}")
                            st.stop()
                        except Exception as e:
                            report_error("❌ Failed to create application.", e, "app.save_first_section.create")
                            st.stop()

                    try:
                        save_draft_record(table, form_data, user_id, master_id=target_master_id)
                        if table == tables[0]:
                            update_master_submission(target_master_id,
                                estimate_number=form_data.get("estimate_number"),
                                year_of_estimate=form_data.get("year_of_estimate"),
                                name_of_project=form_data.get("name_of_project"))
                        st.session_state.master_id = target_master_id
                        st.success("✅ Section saved successfully!")
                        st.toast("📝 Application saved to drafts.")
                        st.rerun()
                    except Exception as e:
                        report_error("❌ Failed to save section.", e, "app.save_first_section")
                        st.stop()

            # ---- OTHER TABS ----
            else:
                col1, col2 = st.columns(2)
                for index, col_info in enumerate(columns):
                    col   = col_info["column_name"]
                    dtype = col_info["data_type"]
                    key   = f"{table}_{col}"
                    target_col = col1 if index % 2 == 0 else col2
                    with target_col:
                        label = col.replace("_"," ").title()
                        if any(w in col.lower() for w in money_keywords):
                            label = f"{label} (₹)"
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
                        if "estimate_number"  in table_col_names: form_data["estimate_number"]  = estimate_number
                        if "year_of_estimate" in table_col_names: form_data["year_of_estimate"] = year_of_estimate
                        if "name_of_project"  in table_col_names: form_data["name_of_project"]  = name_of_project

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
                                    st.error(f"⚠️ An application with Estimate **{estimate_number}** already exists.")
                                else:
                                    report_error("❌ Failed to create application.", e, "app.save_other_section.create")
                                st.stop()

                        try:
                            save_draft_record(table, form_data, user_id, master_id=target_master_id)
                            if table == tables[0]:
                                update_master_submission(target_master_id,
                                    estimate_number=form_data.get("estimate_number"),
                                    year_of_estimate=form_data.get("year_of_estimate"),
                                    name_of_project=form_data.get("name_of_project"))
                            st.session_state.master_id = target_master_id
                            st.success("✅ Section saved successfully!")
                            st.toast("📝 Application saved to drafts.")
                            st.rerun()
                        except Exception as e:
                            report_error("❌ Failed to save section.", e, "app.save_other_section")
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
            <h3>🚀 Ready to Submit Your Application?</h3>
            <p>Once all sections are complete, submit your full application for review.</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    if incomplete_sections:
        st.error("⚠️ **The following sections still need to be completed before submission:**")
        for idx, sec in enumerate(incomplete_sections, 1):
            clean_name = sec.replace(prefix,"").replace("_"," ").title()
            st.markdown(f"&nbsp;&nbsp;&nbsp;**{idx}.** {clean_name}")
    else:
        st.markdown("""
        <div class="submit-cta" style="background:#fffbeb; border-top-color:#d97706;">
            <h3 style="color:#92400e;">📁 Required Attachments</h3>
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
                st.success(f"✅ Estimate Uploaded: `{os.path.basename(existing_est)}`")
            est_file = st.file_uploader("📑 Upload Estimate",
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
                st.success(f"✅ SAR Uploaded: `{os.path.basename(existing_sar)}`")
            sar_file = st.file_uploader("📑 Upload SAR",
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
        if st.button("🚀 Submit My Complete Application", use_container_width=True, type="primary"):
            success = update_master_status(st.session_state.master_id, 'COMPLETED')
            if success:
                set_drafts_to_final(st.session_state.master_id, tables)
                st.balloons()
                st.success("🎉 Application Submitted Successfully!")
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
        <h1>🛡️ Admin Review Panel</h1>
        <p>Review submitted applications, manage user accounts, and export audit reports.</p>
    </div>
    """, unsafe_allow_html=True)

    tab_review, tab_users, tab_manage_users = st.tabs([
        "📋 Review Applications", "➕ Create User", "👥 Manage Users"
    ])

    # ---- CREATE USER ----
    with tab_users:
        st.markdown("### ➕ Create New User")
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
                    st.error("⚠️ Username and Password cannot be empty.")
                else:
                    modules_str = ",".join(selected_mods)
                    success, msg = create_user(new_username.strip(), new_password.strip(),
                                               role=new_role, allowed_modules=modules_str)
                    if success: st.success(f"✅ {msg}")
                    else:       st.error(f"❌ {msg}")

    # ---- MANAGE USERS ----
    with tab_manage_users:
        st.markdown("### 👥 Manage Existing Users")
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
                st.toast(f"✅ Permissions updated for user ID: {uid}")

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
                        st.markdown("<div style='padding-top:10px;color:#059669;font-weight:700;'>✅ Active</div>",
                                    unsafe_allow_html=True)
                    else:
                        st.markdown("<div style='padding-top:10px;color:#dc2626;font-weight:700;'>❌ Revoked</div>",
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

        # Dialog dispatch (admin side)
        if st.session_state.get("sub_to_view"):
            sub_to_view = st.session_state.pop("sub_to_view")
            st.session_state.pop("sub_view_mode", "admin")
            show_submission_details(sub_to_view)
        elif st.session_state.get("active_est_dlg"):
            dlg = st.session_state.active_est_dlg
            show_estimate_group_dialog(dlg['est_no'], dlg['est_yr'],
                                       user_id=dlg.get('user_id'), module=dlg.get('module'))

        if users_df.empty:
            st.markdown("""
            <div class="empty-state">
                <div class="empty-icon">👥</div>
                <p>No applicant accounts found.</p>
                <small>Create a user account in the 'Create User' tab first.</small>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("#### 👤 Select an Applicant to Review")
            applicant_options = ["--- Select Applicant ---", "🌐 All Users"] + list(users_df["username"])
            selected_user = st.selectbox("Applicant", applicant_options,
                label_visibility="collapsed",
                help="Choose 'All Users' to see every submission, or pick a specific applicant")

            if selected_user != "--- Select Applicant ---":
                if "prev_selected_user" not in st.session_state:
                    st.session_state.prev_selected_user = selected_user
                if st.session_state.prev_selected_user != selected_user:
                    st.session_state.admin_review_page  = 1
                    st.session_state.prev_selected_user = selected_user

                is_all_users = (selected_user == "🌐 All Users")

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

                    st.markdown("#### 📊 Submission Overview — All Users")
                    if total == 0:
                        st.markdown("""<div class="empty-state"><div class="empty-icon">🔍</div>
                            <p>No applications found.</p></div>""", unsafe_allow_html=True)
                    else:
                        render_metric_cards(total, submitted, agg_drafts,
                                            card_type="admin")
                else:
                    submitted, drafts = get_user_master_status_counts(selected_user_id, all_modules)
                    total = submitted + drafts
                    selected_user_safe = esc_html(selected_user)
                    st.markdown(f"#### 📊 Submission Overview — {selected_user_safe}")
                    if total == 0:
                        st.markdown(f"""<div class="empty-state"><div class="empty-icon">🔍</div>
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

                        st.markdown("#### 📋 Activity List")
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
                                        show_estimate_group_dialog(est_no, est_yr)
                                else:
                                    st.markdown("<div style='padding-top:8px; color:#9ca3af;'>—</div>",
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
                    st.markdown("""<div class="empty-state"><div class="empty-icon">🔍</div>
                        <small>Try a different filter or applicant.</small></div>""",
                        unsafe_allow_html=True)

render_footer()
