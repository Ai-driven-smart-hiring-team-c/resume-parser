"""
settings.py
One place that reads configuration, in this order:
  1. real environment variables (your laptop: $env:DB_PASSWORD=..., Docker, etc.)
  2. Streamlit secrets (Streamlit Community Cloud: the "Secrets" box)
  3. the default given by the caller

bootstrap() copies Streamlit secrets into os.environ so every module can simply
use os.environ / get_setting. app.py calls it before anything imports db.py.
"""

import os


def get_setting(name, default=None):
    value = os.environ.get(name)
    if value not in (None, ""):
        return value
    try:
        import streamlit as st
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:          # no secrets file locally, or not running inside Streamlit
        pass
    return default


def bootstrap():
    """Make top-level Streamlit secrets visible as environment variables (never
    overrides a variable that is already set)."""
    try:
        import streamlit as st
        for key in list(st.secrets.keys()):
            value = st.secrets[key]
            if isinstance(value, (str, int, float, bool)) and key not in os.environ:
                os.environ[key] = str(value)
    except Exception:
        pass