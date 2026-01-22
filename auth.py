import streamlit as st
import hashlib
from modules.gsheet_connector import GSheetConnector

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_user(username, password):
    """Verify user from GSheet"""
    gs = GSheetConnector(st.secrets["SHEET_ID"])
    users_df = gs.get_sheet_data("users")
    
    if username in users_df['username'].values:
        user_row = users_df[users_df['username'] == username].iloc[0]
        hashed_input = hash_password(password)
        
        if user_row['password_hash'] == hashed_input:
            return True, user_row['role']
    
    return False, None

def show_login_page():
    st.title("🔐 S&OP Forecast Dashboard Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            authenticated, role = verify_user(username, password)
            if authenticated:
                st.session_state.authenticated = True
                st.session_state.username = username
                st.session_state.role = role
                st.rerun()
            else:
                st.error("Invalid username or password")
