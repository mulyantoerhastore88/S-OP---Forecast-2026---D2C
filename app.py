import streamlit as st

# Page configuration
st.set_page_config(
    page_title="S&OP Forecast Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1E3A8A;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #4B5563;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stButton button {
        width: 100%;
    }
    .stDataFrame {
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'username' not in st.session_state:
    st.session_state.username = None
if 'role' not in st.session_state:
    st.session_state.role = None

# Main app logic
def main():
    if not st.session_state.authenticated:
        from modules.auth import show_login_page
        show_login_page()
    else:
        # Show logout button in sidebar
        with st.sidebar:
            st.write(f"Logged in as: **{st.session_state.username}**")
            st.write(f"Role: **{st.session_state.role}**")
            
            if st.button("🚪 Logout", use_container_width=True):
                st.session_state.authenticated = False
                st.session_state.username = None
                st.session_state.role = None
                st.rerun()
        
        # Route based on role
        user_role = st.session_state.role
        
        if user_role == 'channel':
            from modules.channel_view import show_channel_page
            show_channel_page(st.session_state.username)
        
        elif user_role == 'brand1':
            from modules.brand1_view import show_brand1_page
            show_brand1_page(st.session_state.username)
        
        elif user_role == 'brand2':
            from modules.brand2_view import show_brand2_page
            show_brand2_page(st.session_state.username)
        
        elif user_role == 'admin':
            from modules.admin_view import show_admin_page
            show_admin_page(st.session_state.username)
        
        else:
            st.error("Invalid user role. Please contact administrator.")

if __name__ == "__main__":
    main()
