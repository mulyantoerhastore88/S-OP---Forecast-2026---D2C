import streamlit as st
import pandas as pd
from modules.auth import authenticate_user
from modules.gsheet_connector import GSheetConnector

# Page config
st.set_page_config(page_title="S&OP Forecast Dashboard", layout="wide")

# Authentication
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    from modules.auth import show_login_page
    show_login_page()
else:
    # Load user role from session
    user_role = st.session_state.role
    username = st.session_state.username
    
    # Route based on role
    if user_role == 'channel':
        from modules.channel_view import show_channel_page
        show_channel_page(username)
    elif user_role == 'brand1':
        from modules.brand1_view import show_brand1_page
        show_brand1_page(username)
    elif user_role == 'brand2':
        from modules.brand2_view import show_brand2_page
        show_brand2_page(username)
    elif user_role == 'admin':
        from modules.admin_view import show_admin_page
        show_admin_page(username)
