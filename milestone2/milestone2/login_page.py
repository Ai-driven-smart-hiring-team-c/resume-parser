"""
login_page.py
Unified authentication for ALL THREE roles (admin, recruiter, candidate) on
one screen -- no separate app/port needed. A toggle at the top switches
between "Recruiter / Admin" and "Candidate" login+signup forms. Each uses
its own database table (recruiters vs candidate_accounts) and its own
remember-me token/query-param ("rt" vs "ct"), so the two account systems
never collide.

Usage in app.py -- call this near the very top, right after init_db():

    from login_page import (
        is_recruiter_authenticated, is_candidate_authenticated,
        render_unified_login_page, render_logout_button,
        render_candidate_logout_button, is_admin,
    )

    if not is_recruiter_authenticated() and not is_candidate_authenticated():
        render_unified_login_page()
        st.stop()

    if is_candidate_authenticated():
        # render the candidate-only view, then st.stop()
        ...
    else:
        # existing recruiter/admin sidebar + pages
        ...
"""

import re
from datetime import datetime, timedelta

import streamlit as st

from db import (
    insert_recruiter, get_recruiter_by_email,
    save_remember_token, get_recruiter_by_token, delete_remember_token,
    insert_candidate_account, get_candidate_account_by_email,
    save_candidate_remember_token, get_candidate_account_by_token, delete_candidate_remember_token,
)
from auth import hash_password, verify_password, generate_remember_token, hash_token

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
REMEMBER_DAYS = 30


# ============================================================
# Query-param helpers (works across Streamlit versions old & new)
# ============================================================

def _get_query_param(key):
    try:
        return st.query_params.get(key)
    except Exception:
        values = st.experimental_get_query_params().get(key)
        return values[0] if values else None


def _set_query_param(key, value):
    try:
        st.query_params[key] = value
    except Exception:
        params = st.experimental_get_query_params()
        params[key] = value
        st.experimental_set_query_params(**params)


def _clear_query_param(key):
    try:
        if key in st.query_params:
            del st.query_params[key]
    except Exception:
        params = st.experimental_get_query_params()
        params.pop(key, None)
        st.experimental_set_query_params(**params)


# ============================================================
# Auth state -- RECRUITER / ADMIN
# ============================================================

def _try_auto_login_recruiter():
    if st.session_state.get("recruiter"):
        return
    token = _get_query_param("rt")
    if not token:
        return
    recruiter = get_recruiter_by_token(hash_token(token))
    if recruiter:
        st.session_state["recruiter"] = recruiter


def is_recruiter_authenticated() -> bool:
    _try_auto_login_recruiter()
    return bool(st.session_state.get("recruiter"))


# kept for backward compatibility with any old imports
is_authenticated = is_recruiter_authenticated


def is_admin() -> bool:
    recruiter = st.session_state.get("recruiter")
    return bool(recruiter and recruiter.get("role") == "admin")


def logout():
    token = _get_query_param("rt")
    if token:
        delete_remember_token(hash_token(token))
    _clear_query_param("rt")
    st.session_state.pop("recruiter", None)
    st.rerun()


def render_logout_button():
    """Call inside the sidebar (recruiter/admin view) to show who's logged
    in + a logout button."""
    recruiter = st.session_state.get("recruiter")
    if not recruiter:
        return
    role_label = "Admin" if recruiter.get("role") == "admin" else "Recruiter"
    st.markdown(
        f"""
        <div style="
            display:flex;align-items:center;gap:10px;
            background:#eef2ff;border-radius:10px;padding:10px 14px;margin-bottom:10px;
        ">
            <div style="
                width:36px;height:36px;border-radius:50%;
                background:linear-gradient(135deg,#2563eb,#4f46e5);
                color:white;display:flex;align-items:center;justify-content:center;
                font-weight:700;font-size:14px;flex-shrink:0;
            ">{recruiter['name'][:1].upper()}</div>
            <div style="overflow:hidden;">
                <div style="font-weight:600;color:#101828;font-size:13px;">{recruiter['name']} &middot; <span style="color:#4f46e5;">{role_label}</span></div>
                <div style="color:#667085;font-size:11px;white-space:nowrap;text-overflow:ellipsis;overflow:hidden;">{recruiter['email']}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("🚪 Log Out", use_container_width=True, key="recruiter_logout_btn"):
        logout()


# ============================================================
# Auth state -- CANDIDATE
# ============================================================

def _try_auto_login_candidate():
    if st.session_state.get("candidate"):
        return
    token = _get_query_param("ct")
    if not token:
        return
    candidate = get_candidate_account_by_token(hash_token(token))
    if candidate:
        st.session_state["candidate"] = candidate


def is_candidate_authenticated() -> bool:
    _try_auto_login_candidate()
    return bool(st.session_state.get("candidate"))


def logout_candidate():
    token = _get_query_param("ct")
    if token:
        delete_candidate_remember_token(hash_token(token))
    _clear_query_param("ct")
    st.session_state.pop("candidate", None)
    st.rerun()


def render_candidate_logout_button():
    """Call inside the sidebar (candidate view) to show who's logged in +
    a logout button."""
    candidate = st.session_state.get("candidate")
    if not candidate:
        return
    st.markdown(
        f"""
        <div style="
            display:flex;align-items:center;gap:10px;
            background:#eef2ff;border-radius:10px;padding:10px 14px;margin-bottom:10px;
        ">
            <div style="
                width:36px;height:36px;border-radius:50%;
                background:linear-gradient(135deg,#2563eb,#4f46e5);
                color:white;display:flex;align-items:center;justify-content:center;
                font-weight:700;font-size:14px;flex-shrink:0;
            ">{candidate['name'][:1].upper()}</div>
            <div style="overflow:hidden;">
                <div style="font-weight:600;color:#101828;font-size:13px;">{candidate['name']} &middot; <span style="color:#4f46e5;">Candidate</span></div>
                <div style="color:#667085;font-size:11px;white-space:nowrap;text-overflow:ellipsis;overflow:hidden;">{candidate['email']}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("🚪 Log Out", use_container_width=True, key="candidate_logout_btn"):
        logout_candidate()


# ============================================================
# Unified login / signup screen
# ============================================================

def _inject_css():
    # shared palette / fonts, then the login-only bits on top
    from ui_theme import inject_theme
    inject_theme()
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none; }
        .login-logo {
            position: relative; width: 58px; height: 58px; border-radius: 15px;
            background: var(--cobalt); margin: 10px auto 18px auto;
        }
        .login-logo::before, .login-logo::after {
            content: ""; position: absolute; top: 17px; width: 24px; height: 24px;
            border-radius: 50%; border: 3.5px solid #fff;
        }
        .login-logo::before { left: 9px; }
        .login-logo::after { left: 24px; border-color: #7FE6D2; }
        .login-title {
            text-align: center; font-family: var(--display); font-size: 32px; font-weight: 800;
            color: var(--ink); margin-bottom: 6px; letter-spacing: -0.02em;
        }
        .login-subtitle {
            text-align: center; color: var(--muted); font-size: 14.5px; margin-bottom: 22px;
        }
        div[data-testid="stForm"] { border: none; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_recruiter_forms():
    tab_login, tab_signup = st.tabs(["🔑  Log In", "✨  Sign Up"])

    # -------------------- LOG IN --------------------
    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="you@company.com")
            password = st.text_input("Password", type="password", placeholder="••••••••")
            remember = st.checkbox("Remember me on this device", value=True)
            submitted = st.form_submit_button("Log In", type="primary", use_container_width=True)

        if submitted:
            clean_email = (email or "").strip().lower()
            if not clean_email or not password:
                st.error("Please enter both email and password.")
            else:
                recruiter = get_recruiter_by_email(clean_email)
                if recruiter and verify_password(
                    password, recruiter["password_salt"], recruiter["password_hash"]
                ):
                    st.session_state["recruiter"] = recruiter
                    if remember:
                        token = generate_remember_token()
                        expires_at = datetime.now() + timedelta(days=REMEMBER_DAYS)
                        save_remember_token(recruiter["id"], hash_token(token), expires_at)
                        _set_query_param("rt", token)
                    st.rerun()
                else:
                    st.error("Incorrect email or password.")

    # -------------------- SIGN UP --------------------
    with tab_signup:
        with st.form("signup_form"):
            name = st.text_input("Full Name", placeholder="Jane Doe")
            signup_email = st.text_input("Work Email", placeholder="you@company.com")
            signup_password = st.text_input(
                "Password", type="password", placeholder="At least 6 characters"
            )
            confirm_password = st.text_input("Confirm Password", type="password")
            signup_submitted = st.form_submit_button(
                "Create Account", type="primary", use_container_width=True
            )

        if signup_submitted:
            clean_name = (name or "").strip()
            clean_email = (signup_email or "").strip().lower()

            if not clean_name or not clean_email or not signup_password:
                st.error("Please fill in all fields.")
            elif not EMAIL_RE.match(clean_email):
                st.error("Please enter a valid email address.")
            elif len(signup_password) < 6:
                st.error("Password must be at least 6 characters.")
            elif signup_password != confirm_password:
                st.error("Passwords don't match.")
            elif get_recruiter_by_email(clean_email):
                st.error("An account with this email already exists — try Log In instead.")
            else:
                salt, pwd_hash = hash_password(signup_password)
                recruiter_id = insert_recruiter(
                    clean_name, clean_email, salt, pwd_hash, role="recruiter"
                )
                if recruiter_id:
                    st.success("Account created! Switch to the Log In tab to sign in.")
                else:
                    st.error("Something went wrong creating your account — please try again.")


def _render_candidate_forms():
    tab_login, tab_signup = st.tabs(["🔑  Log In", "✨  Sign Up"])

    # -------------------- LOG IN --------------------
    with tab_login:
        with st.form("candidate_login_form"):
            email = st.text_input("Email", placeholder="you@example.com", key="cand_login_email")
            password = st.text_input("Password", type="password", key="cand_login_pw")
            remember = st.checkbox("Remember me on this device", value=True, key="cand_login_remember")
            submitted = st.form_submit_button("Log In", type="primary", use_container_width=True)

        if submitted:
            clean_email = (email or "").strip().lower()
            if not clean_email or not password:
                st.error("Please enter both email and password.")
            else:
                candidate = get_candidate_account_by_email(clean_email)
                if candidate and verify_password(
                    password, candidate["password_salt"], candidate["password_hash"]
                ):
                    st.session_state["candidate"] = candidate
                    if remember:
                        token = generate_remember_token()
                        expires_at = datetime.now() + timedelta(days=REMEMBER_DAYS)
                        save_candidate_remember_token(candidate["id"], hash_token(token), expires_at)
                        _set_query_param("ct", token)
                    st.rerun()
                else:
                    st.error("Incorrect email or password.")

    # -------------------- SIGN UP --------------------
    with tab_signup:
        with st.form("candidate_signup_form"):
            name = st.text_input("Full Name", placeholder="Jane Doe", key="cand_signup_name")
            signup_email = st.text_input("Email", placeholder="you@example.com", key="cand_signup_email")
            signup_password = st.text_input(
                "Password", type="password", placeholder="At least 6 characters", key="cand_signup_pw"
            )
            confirm_password = st.text_input("Confirm Password", type="password", key="cand_signup_confirm")
            signup_submitted = st.form_submit_button(
                "Create Account", type="primary", use_container_width=True
            )

        if signup_submitted:
            clean_name = (name or "").strip()
            clean_email = (signup_email or "").strip().lower()

            if not clean_name or not clean_email or not signup_password:
                st.error("Please fill in all fields.")
            elif not EMAIL_RE.match(clean_email):
                st.error("Please enter a valid email address.")
            elif len(signup_password) < 6:
                st.error("Password must be at least 6 characters.")
            elif signup_password != confirm_password:
                st.error("Passwords don't match.")
            elif get_candidate_account_by_email(clean_email):
                st.error("An account with this email already exists — try Log In instead.")
            else:
                salt, pwd_hash = hash_password(signup_password)
                new_id = insert_candidate_account(clean_name, clean_email, salt, pwd_hash)
                if new_id:
                    st.success("Account created! Switch to the Log In tab to sign in.")
                else:
                    st.error("Something went wrong — please try again.")


def render_unified_login_page():
    _inject_css()

    left, center, right = st.columns([1, 1.3, 1])

    with center:
        st.markdown('<div class="login-logo">💼</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-title">Recruitment Copilot</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="login-subtitle">Recruiters, admins and candidates sign in here</div>',
            unsafe_allow_html=True,
        )

        role_choice = st.radio(
            "I am logging in as a:",
            ["Recruiter / Admin", "Candidate"],
            horizontal=True,
            label_visibility="collapsed",
        )

        with st.container(border=True):
            if role_choice == "Recruiter / Admin":
                _render_recruiter_forms()
            else:
                _render_candidate_forms()

        st.markdown(
            "<p style='text-align:center;color:#98a2b3;font-size:12px;margin-top:16px;'>"
            "Your password is never stored in plain text.</p>",
            unsafe_allow_html=True,
        )


# Backward-compatible alias for any old imports
render_login_page = render_unified_login_page