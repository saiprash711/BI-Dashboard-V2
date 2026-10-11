"""
Access control for the Conversion Analytics dashboard.

Scope of the guarantee
----------------------
Streamlit executes the whole script server-side and only ships rendered output
to the browser, so gating ``main()`` behind :func:`require_login` genuinely
withholds the data — this is not a cosmetic overlay. What it does *not* do is
protect the workbook sitting next to ``app.py``: anyone with filesystem access
to that folder still has the data. Treat this as "who may look at the
dashboard", not as a substitute for host-level access control.

Credentials
-----------
Only PBKDF2-HMAC-SHA256 digests are stored, never a password. The encoding is

    pbkdf2_sha256$<iterations>$<base64 salt>$<base64 digest>

The built-in accounts in :data:`_BUILTIN_USERS` are starter credentials and
should be replaced. Two ways to do that, in precedence order:

1. ``.streamlit/secrets.toml`` — overrides everything below and keeps digests
   out of source control::

       [auth.users.admin]
       hash = "pbkdf2_sha256$240000$...$..."
       name = "Priya Raman"
       role = "Administrator"

2. Edit :data:`_BUILTIN_USERS` directly.

Generate a digest for either route with::

    python auth.py hash
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta

import streamlit as st

import theme as T

# ─────────────────────────────────────────────────────────────────────────────
# POLICY
# ─────────────────────────────────────────────────────────────────────────────
ITERATIONS = 240_000        # PBKDF2 rounds for newly generated digests
MAX_ATTEMPTS = 5            # failures tolerated before a cool-down
LOCKOUT_SECONDS = 60        # length of that cool-down
SESSION_HOURS = 12          # a signed-in session expires after this long

_ALGO = "pbkdf2_sha256"

# Verified when an unknown username is submitted, so a missing account costs the
# same time as a wrong password and cannot be distinguished by response latency.
_DECOY = ("pbkdf2_sha256$240000$c2FsdHNhbHRzYWx0c2FsdA==$"
          "3F0nGRHqTVdrH0kmiOEnfmS7Jt3wYBQ0YZBEEMSN0iM=")

# ─────────────────────────────────────────────────────────────────────────────
# BUILT-IN ACCOUNTS  (starter credentials — rotate before sharing the app)
#
#   admin    · TVS@dmin2026
#   analyst  · Analyst@2026
#   viewer   · Viewer@2026
# ─────────────────────────────────────────────────────────────────────────────
_BUILTIN_USERS: dict[str, dict[str, str]] = {
    "admin": {
        "hash": "pbkdf2_sha256$240000$T9sloh6rZi/Vn7+I5/BcrQ=="
                "$zUqY9dbywU1t3Re990DH28g5sJ5spfX1aKqUAXqwzwg=",
        "name": "Dashboard Administrator",
        "role": "Administrator",
    },
    "analyst": {
        "hash": "pbkdf2_sha256$240000$ci9elJBqXITknzMGBr+Bhg=="
                "$08hoH8KAIzlwKpeJKoD8SA5AIlfgE9t0u9S0ejYtq/8=",
        "name": "Conversion Analyst",
        "role": "Analyst",
    },
    "viewer": {
        "hash": "pbkdf2_sha256$240000$MRXYYER2bjoBGuYQqWZKMQ=="
                "$zdBAWGe1nBdbNmXOs/tsdX9ea/Qz5wF1QiIOb+pruuA=",
        "name": "Business Viewer",
        "role": "Viewer",
    },
}


# ═════════════════════════════════════════════════════════════════════════════
# HASHING
# ═════════════════════════════════════════════════════════════════════════════
def hash_password(password: str, iterations: int = ITERATIONS) -> str:
    """Return a self-describing PBKDF2 digest for ``password``."""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return (f"{_ALGO}${iterations}${base64.b64encode(salt).decode()}"
            f"${base64.b64encode(dk).decode()}")


def verify_password(password: str, encoded: str) -> bool:
    """
    Constant-time check of ``password`` against an encoded digest.

    A malformed digest fails closed rather than raising, so one bad entry in the
    user store cannot take the sign-in screen down.
    """
    try:
        algo, iters, salt_b64, digest_b64 = encoded.split("$")
        if algo != _ALGO:
            return False
        expected = base64.b64decode(digest_b64)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                 base64.b64decode(salt_b64), int(iters))
    except Exception:
        return False
    return hmac.compare_digest(dk, expected)


# ═════════════════════════════════════════════════════════════════════════════
# USER STORE
# ═════════════════════════════════════════════════════════════════════════════
def _users() -> dict[str, dict[str, str]]:
    """
    Active account map, secrets taking precedence over the built-ins.

    ``st.secrets`` raises when no secrets file exists, which is the normal case
    for a local run, so absence is treated as "no override".
    """
    try:
        block = st.secrets["auth"]["users"]
    except Exception:
        return _BUILTIN_USERS

    out: dict[str, dict[str, str]] = {}
    for username, spec in dict(block).items():
        spec = dict(spec) if hasattr(spec, "keys") else {"hash": str(spec)}
        if not spec.get("hash"):
            continue
        out[str(username).strip().lower()] = {
            "hash": spec["hash"],
            "name": spec.get("name", str(username).title()),
            "role": spec.get("role", "User"),
        }
    return out or _BUILTIN_USERS


def _initials(name: str) -> str:
    parts = [p for p in name.replace("-", " ").split() if p]
    if not parts:
        return "··"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


# ═════════════════════════════════════════════════════════════════════════════
# SESSION
# ═════════════════════════════════════════════════════════════════════════════
def _init_state() -> None:
    st.session_state.setdefault("auth_user", None)
    st.session_state.setdefault("auth_since", None)
    st.session_state.setdefault("auth_fails", 0)
    st.session_state.setdefault("auth_locked_until", None)
    st.session_state.setdefault("auth_error", "")


def current_user() -> dict | None:
    """The signed-in user record, or ``None``."""
    return st.session_state.get("auth_user")


def is_authenticated() -> bool:
    """
    True when a live session exists.

    Also enforces the session lifetime: an expired session is cleared here so
    every entry point inherits the check.
    """
    _init_state()
    user = st.session_state.auth_user
    if not user:
        return False
    since = st.session_state.auth_since
    if since and datetime.now() - since > timedelta(hours=SESSION_HOURS):
        _clear_session()
        st.session_state.auth_error = ("Your session expired after "
                                       f"{SESSION_HOURS} hours. Please sign in again.")
        return False
    return True


def _clear_session() -> None:
    st.session_state.auth_user = None
    st.session_state.auth_since = None


def _lock_remaining() -> int:
    until = st.session_state.get("auth_locked_until")
    if not until:
        return 0
    left = (until - datetime.now()).total_seconds()
    if left <= 0:
        st.session_state.auth_locked_until = None
        st.session_state.auth_fails = 0
        return 0
    return int(left) + 1


def _attempt(username: str, password: str) -> bool:
    """Validate one submission and update the failure counters."""
    users = _users()
    key = (username or "").strip().lower()
    record = users.get(key)

    ok = verify_password(password or "", record["hash"] if record else _DECOY)

    if not ok or record is None:
        st.session_state.auth_fails += 1
        left = MAX_ATTEMPTS - st.session_state.auth_fails
        if left <= 0:
            st.session_state.auth_locked_until = (
                datetime.now() + timedelta(seconds=LOCKOUT_SECONDS))
            st.session_state.auth_error = (
                f"Too many failed attempts. Sign-in is paused for "
                f"{LOCKOUT_SECONDS} seconds.")
        else:
            st.session_state.auth_error = (
                f"Those credentials were not recognised. "
                f"{left} attempt{'s' if left != 1 else ''} remaining.")
        return False

    st.session_state.auth_user = {
        "username": key,
        "name": record.get("name", key.title()),
        "role": record.get("role", "User"),
        "initials": _initials(record.get("name", key)),
        "token": secrets.token_hex(16),
    }
    st.session_state.auth_since = datetime.now()
    st.session_state.auth_fails = 0
    st.session_state.auth_locked_until = None
    st.session_state.auth_error = ""
    return True


def logout() -> None:
    """
    End the session and drop everything derived from it.

    Filter selections, the assistant's conversation and any uploaded workbook are
    wiped as well, so the next person to sign in on this browser starts from a
    clean dashboard rather than inheriting the previous user's view.
    """
    _clear_session()
    for key in [k for k in list(st.session_state.keys())
                if k.startswith(("f_", "qa_", "lg_", "kb_"))]:
        del st.session_state[key]
    st.session_state.uploaded = None
    st.session_state.uploaded_name = ""
    st.session_state.auth_error = ""
    st.session_state.auth_fails = 0
    st.session_state.auth_locked_until = None


# ═════════════════════════════════════════════════════════════════════════════
# SIGN-IN SCREEN
# ═════════════════════════════════════════════════════════════════════════════
_FEATURES = (
    ("◈", "Executive overview",
     "GMV, commission revenue and take rate with period-on-period movement"),
    ("⬢", "Marketplace depth",
     "Seller and buyer concentration, repeat behaviour and vehicle mix"),
    ("◉", "Governed numbers",
     "Quality scoring, validation rules and one canonical metric definition"),
)


def _brand_panel() -> str:
    feats = "".join(
        f'<div class="lg-feat"><div class="i">{ico}</div>'
        f'<div><strong>{title}</strong><em>{desc}</em></div></div>'
        for ico, title, desc in _FEATURES)
    return (
        '<div class="lg-brand">'
        '<div class="lg-logo"><div class="m">◈</div>'
        '<div><b>Conversion Analytics</b><span>TVS Certified</span></div></div>'
        '<h1>Every conversion,<br>one source of truth.</h1>'
        '<p class="lead">Transaction-level intelligence on used-car conversions — '
        'where revenue is created, which relationships carry it, and where the '
        'yield is strongest.</p>'
        f'<div class="lg-feats">{feats}</div>'
        '<div class="lg-trust">'
        '<div><b>4</b><span>Analysis modules</span></div>'
        '<div><b>40+</b><span>Tracked metrics</span></div>'
        '<div><b>SSOT</b><span>Governed source</span></div>'
        '</div></div>')


def login_screen() -> None:
    """
    Draw the sign-in view.

    Rendered as the entire page: the accompanying stylesheet hides the sidebar
    and centres the container, so nothing from the dashboard shell shows through.
    """
    _init_state()
    st.html(T.login_stylesheet())
    st.html('<div class="lg-aurora"><i></i><i></i><i></i></div><div class="lg-grid"></div>')

    left, right = st.columns([1.08, .92], gap="large", vertical_alignment="center")

    with left:
        st.markdown(_brand_panel(), unsafe_allow_html=True)

    with right:
        with st.container(key="login_card"):
            st.markdown(
                '<div class="lg-head"><div class="k">Secure access</div>'
                '<h2>Sign in to continue</h2>'
                '<p>Use the credentials issued for this dashboard. '
                'Access is limited to authorised TVS Certified users.</p></div>',
                unsafe_allow_html=True)

            locked = _lock_remaining()
            if locked:
                st.markdown(
                    f'<div class="lg-alert warn"><span class="g">◷</span>'
                    f'<div><b>Sign-in paused.</b> Too many failed attempts — '
                    f'try again in {locked} second{"s" if locked != 1 else ""}.</div></div>',
                    unsafe_allow_html=True)
            elif st.session_state.auth_error:
                st.markdown(
                    f'<div class="lg-alert"><span class="g">✕</span>'
                    f'<div>{st.session_state.auth_error}</div></div>',
                    unsafe_allow_html=True)

            # A form batches both fields into one submission, so Enter in either
            # field signs in and a single rerun handles the whole attempt.
            with st.form("login_form", border=False, clear_on_submit=False):
                username = st.text_input("Username", key="lg_user",
                                         placeholder="your.username",
                                         autocomplete="username")
                password = st.text_input("Password", key="lg_pass", type="password",
                                         placeholder="Enter your password",
                                         autocomplete="current-password")
                submitted = st.form_submit_button(
                    "Sign in  →", width="stretch", disabled=bool(locked),
                    type="secondary")

            if submitted and not locked:
                if username and password:
                    _attempt(username, password)
                else:
                    st.session_state.auth_error = "Enter both a username and a password."
                # Either way the run ends here: a success swaps in the dashboard,
                # a failure repaints this screen with the message above.
                st.rerun()

            st.markdown(
                '<div class="lg-hint">Trouble signing in?</div>'
                '<div class="lg-note">Contact the analytics team to have your '
                'access reset.</div>',
                unsafe_allow_html=True)

    st.markdown(
        '<div class="lg-foot">Authorised use only. Activity is tied to your '
        'browser session.<span class="sep">·</span>'
        f'Conversion Analytics {datetime.now():%Y}'
        '<span class="sep">·</span>TVS Certified</div>',
        unsafe_allow_html=True)


def require_login() -> bool:
    """
    Gate the application.

    Returns True when the caller may render the dashboard; otherwise draws the
    sign-in screen and returns False.
    """
    if is_authenticated():
        # The submitted password lingers in state until the widget disappears;
        # this run is the first where it can safely be dropped.
        for key in ("lg_user", "lg_pass"):
            st.session_state.pop(key, None)
        return True
    login_screen()
    return False


# ═════════════════════════════════════════════════════════════════════════════
# SIDEBAR ACCOUNT BLOCK
# ═════════════════════════════════════════════════════════════════════════════
def sidebar_account() -> None:
    """Signed-in identity plus the sign-out control. Call inside the sidebar."""
    user = current_user()
    if not user:
        return

    st.markdown(
        f'<div class="sb-user"><div class="sb-av">{user["initials"]}</div>'
        f'<div class="who"><b>{user["name"]}</b><span>{user["role"]}</span></div></div>',
        unsafe_allow_html=True)

    since = st.session_state.get("auth_since")
    if since:
        st.markdown(
            f'<div class="sb-stat"><span>Signed in</span>'
            f'<b>{since:%d %b · %H:%M}</b></div>',
            unsafe_allow_html=True)

    if st.button("⏻  Sign out", key="logout_btn", width="stretch",
                 help="End this session and return to the sign-in screen"):
        logout()
        st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# CLI — python auth.py hash
# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import getpass
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "hash":
        pw = getpass.getpass("New password: ")
        if pw != getpass.getpass("Confirm password: "):
            sys.exit("Passwords did not match.")
        if len(pw) < 8:
            sys.exit("Use at least 8 characters.")
        print("\n" + hash_password(pw) + "\n")
        print("Paste this as the 'hash' value in _BUILTIN_USERS or secrets.toml.")
    else:
        print(__doc__)
        print("Usage: python auth.py hash")
