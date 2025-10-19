"""
User authentication module using streamlit-authenticator
"""

import yaml
from yaml.loader import SafeLoader
import streamlit as st
import streamlit_authenticator as stauth
from pathlib import Path


def get_config_path():
    """Get the path to the authentication configuration file"""
    return Path(__file__).parent.parent / "auth_config.yaml"


def load_config():
    """Load authentication configuration from YAML file"""
    config_path = get_config_path()
    with open(config_path) as file:
        config = yaml.load(file, Loader=SafeLoader)
    return config


def save_config(config):
    """Save authentication configuration to YAML file"""
    config_path = get_config_path()
    with open(config_path, "w") as file:
        yaml.dump(config, file, default_flow_style=False, allow_unicode=True)


def get_authenticator():
    """Get or create the authenticator instance"""
    if "authenticator" not in st.session_state:
        config = load_config()
        st.session_state.config = config
        st.session_state.authenticator = stauth.Authenticate(
            config["credentials"],
            config["cookie"]["name"],
            config["cookie"]["key"],
            config["cookie"]["expiry_days"],
        )
    return st.session_state.authenticator


def require_authentication():
    """
    Require user authentication to access the page.
    Returns True if authenticated, False otherwise.
    """
    authenticator = get_authenticator()

    # Check authentication status first
    if st.session_state.get("authentication_status"):
        return True

    # If not authenticated, show branded login page
    st.markdown(
        """
        <style>
        .login-container {
            max-width: 400px;
            margin: 0 auto;
            padding: 2rem;
        }
        .brand-title {
            text-align: center;
            font-size: 3rem;
            font-weight: bold;
            margin-bottom: 0.5rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .brand-subtitle {
            text-align: center;
            font-size: 1.2rem;
            color: #666;
            margin-bottom: 2rem;
        }
        .welcome-text {
            text-align: center;
            font-size: 1rem;
            color: #888;
            margin-bottom: 2rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Create centered layout
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown('<div class="login-container">', unsafe_allow_html=True)

        # Brand header
        st.markdown("# 📚")
        st.markdown('<div class="brand-title">MarkDoc</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="brand-subtitle">AI-Powered Document Crawling Engine</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="welcome-text">Please sign in to continue</div>',
            unsafe_allow_html=True,
        )

        st.divider()

        # Render login widget
        try:
            authenticator.login()
        except Exception as e:
            st.error(e)

        st.markdown("</div>", unsafe_allow_html=True)

    # Check authentication status after login attempt
    if st.session_state.get("authentication_status") is False:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.error("Username/password is incorrect")
        st.stop()
    elif st.session_state.get("authentication_status") is None:
        st.stop()

    return False


def render_logout_button():
    """Render logout button in sidebar for authenticated users"""
    if st.session_state.get("authentication_status"):
        authenticator = get_authenticator()
        with st.sidebar:
            st.divider()
            st.caption(f"Logged in as: **{st.session_state.get('name')}**")
            authenticator.logout("Logout", "sidebar")
