import logging
import os

import streamlit as st


LOGGER = logging.getLogger("canal_audit_system")
if not LOGGER.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    LOGGER.addHandler(handler)
LOGGER.setLevel(logging.INFO)


def _debug_mode_enabled():
    debug_flag = os.getenv("APP_DEBUG", "").strip().lower()
    return debug_flag in {"1", "true", "yes", "on"}


def report_error(user_message, exc=None, context=""):
    if exc is not None:
        if context:
            LOGGER.exception("%s: %s", context, exc)
        else:
            LOGGER.exception("Unhandled exception: %s", exc)

    if exc is not None and _debug_mode_enabled():
        st.error(f"{user_message} ({exc})")
    else:
        st.error(user_message)


def log_exception(context, exc):
    if context:
        LOGGER.exception("%s: %s", context, exc)
    else:
        LOGGER.exception("Unhandled exception: %s", exc)
