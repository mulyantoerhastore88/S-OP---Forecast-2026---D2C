import streamlit as st
import hashlib
import pandas as pd
from datetime import datetime

# Try different import styles for Streamlit Cloud
try:
    # For Streamlit Cloud
    from gsheet_connector import GSheetConnector
except ImportError:
    # For local development
    from .gsheet_connector import GSheetConnector

def hash_password(password):
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_user(username, password):
    """Verify user from GSheet"""
    try:
        gs = GSheetConnector()
        users_df = gs.get_sheet_data("users")
        
        if users_df.empty or 'username' not in users_df.columns:
            st.error("Users database not found or empty")
            return False, None
        
        if username in users_df['username'].values:
            user_row = users_df[users_df['username'] == username].iloc[0]
            hashed_input = hash_password(password)
            
            if user_row['password_hash'] == hashed_input:
                return True, user_row['role']
        
        return False, None
    except Exception as e:
        st.error(f"Authentication error: {str(e)}")
        return False, None

def show_login_page():
    st.title("🔐 S&OP Forecast Dashboard Login")
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        with st.form("login_form"):
            st.subheader("Please Login")
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submit = st.form_submit_button("🚀 Login", use_container_width=True)
            
            if submit:
                if not username or not password:
                    st.error("Please enter both username and password")
                else:
                    with st.spinner("Authenticating..."):
                        authenticated, role = verify_user(username, password)
                        if authenticated:
                            st.session_state.authenticated = True
                            st.session_state.username = username
                            st.session_state.role = role
                            st.success(f"Welcome, {username}!")
                            st.rerun()
                        else:
                            st.error("Invalid username or password")
        
        st.markdown("---")
        st.caption("**Demo Users:**")
        st.caption("- Channel/Sales: `channel_sales` / `channel2026`")
        st.caption("- Brand Group 1: `brand_group1` / `group12026`")
        st.caption("- Brand Group 2: `brand_group2` / `group22026`")
        st.caption("- Admin: `demand_planner` / `planner2026`")
