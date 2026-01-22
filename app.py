import streamlit as st
import pandas as pd
import hashlib
import gspread
import plotly.graph_objects as go
from google.oauth2.service_account import Credentials
import json
from datetime import datetime

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================
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
    .stButton button {
        width: 100%;
    }
    .stDataFrame {
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'username' not in st.session_state:
    st.session_state.username = None
if 'role' not in st.session_state:
    st.session_state.role = None

# ============================================================================
# GSHEET CONNECTOR CLASS
# ============================================================================
class GSheetConnector:
    def __init__(self):
        try:
            self.sheet_id = st.secrets["gsheets"]["sheet_id"]
            self.service_account_info = json.loads(st.secrets["gsheets"]["service_account_info"])
        except:
            st.error("GSheet credentials not found in secrets.")
            raise
        
        self.client = None
        self.connect()
    
    def connect(self):
        """Connect to Google Sheets API"""
        try:
            scope = ['https://www.googleapis.com/auth/spreadsheets']
            creds = Credentials.from_service_account_info(
                self.service_account_info, scopes=scope)
            self.client = gspread.authorize(creds)
            self.sheet = self.client.open_by_key(self.sheet_id)
        except Exception as e:
            st.error(f"Failed to connect to Google Sheets: {str(e)}")
            raise
    
    def get_sheet_data(self, sheet_name):
        """Read sheet as DataFrame"""
        try:
            worksheet = self.sheet.worksheet(sheet_name)
            data = worksheet.get_all_records()
            return pd.DataFrame(data)
        except Exception as e:
            st.error(f"Error reading sheet {sheet_name}: {str(e)}")
            return pd.DataFrame()
    
    def update_sheet(self, sheet_name, df):
        """Update sheet with DataFrame"""
        try:
            worksheet = self.sheet.worksheet(sheet_name)
            worksheet.clear()
            
            # Convert DataFrame to list of lists
            data = [df.columns.values.tolist()] + df.values.tolist()
            worksheet.update(data, value_input_option='USER_ENTERED')
            return True
        except Exception as e:
            st.error(f"Error updating sheet {sheet_name}: {str(e)}")
            return False
    
    def append_to_sheet(self, sheet_name, data_dict):
        """Append single row to sheet"""
        try:
            worksheet = self.sheet.worksheet(sheet_name)
            worksheet.append_row(list(data_dict.values()))
            return True
        except Exception as e:
            st.error(f"Error appending to sheet {sheet_name}: {str(e)}")
            return False
    
    def get_rofo_current(self):
        """Get ROFO current data with proper column handling"""
        df = self.get_sheet_data("rofo_current")
        
        if df.empty:
            return df
        
        # Identify month columns (Feb-26, Mar-26, etc.)
        month_columns = [col for col in df.columns if '-' in str(col) and len(str(col)) >= 6]
        
        # Keep only relevant columns
        keep_columns = ['sku_code', 'Product_Name', 'Brand_Group', 'Brand', 'SKU_Tier'] + month_columns
        keep_columns = [col for col in keep_columns if col in df.columns]
        
        return df[keep_columns]

# ============================================================================
# AUTHENTICATION FUNCTIONS
# ============================================================================
def hash_password(password):
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_user(username, password):
    """Verify user from GSheet"""
    try:
        gs = GSheetConnector()
        users_df = gs.get_sheet_data("users")
        
        if users_df.empty or 'username' not in users_df.columns:
            st.error("Users database not found or empty.")
            return False, None
        
        if username in users_df['username'].values:
            user_row = users_df[users_df['username'] == username].iloc[0]
            hashed_input = hash_password(password)
            
            if str(user_row['password_hash']).strip() == hashed_input:
                return True, user_row['role']
        
        return False, None
    except Exception as e:
        st.error(f"Authentication error: {str(e)}")
        return False, None

def show_login_page():
    """Display login page"""
    st.title("🔐 S&OP Forecast Dashboard Login")
    st.markdown("---")
    
    with st.form("login_form"):
        st.subheader("Please Login")
        username = st.text_input("Username", placeholder="Enter your username", key="login_username")
        password = st.text_input("Password", type="password", placeholder="Enter your password", key="login_password")
        submit = st.form_submit_button("🚀 Login", use_container_width=True, key="login_submit")
        
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
    st.caption("**Login Credentials (Password: 'password' for all):**")
    st.caption("- Channel/Sales: `channel_sales`")
    st.caption("- ERHA SKINCARE GROUP 1: `brand_group1`")
    st.caption("- ERHA SKINCARE GROUP 2: `brand_group2`")
    st.caption("- Admin/Demand Planner: `demand_planner`")

# ============================================================================
# CHANNEL/SALES PAGE
# ============================================================================
def show_channel_page(username):
    """Channel/Sales input page - Includes ALL SKUs including ERHA OTHERS"""
    st.title("📊 Channel/Sales Forecast Input")
    st.markdown("---")
    
    # Initialize connector
    gs = GSheetConnector()
    
    # Load data
    with st.spinner("Loading all SKU data..."):
        rofo_df = gs.get_rofo_current()
        
        if rofo_df.empty:
            st.error("No ROFO data available.")
            return
        
        # Merge dengan stock data
        stock_df = gs.get_sheet_data("stock_onhand")
        if not stock_df.empty and 'sku_code' in stock_df.columns:
            merged_df = pd.merge(
                rofo_df, 
                stock_df[['sku_code', 'Stock_Qty']], 
                on='sku_code', 
                how='left'
            )
            merged_df['Stock_Qty'] = merged_df['Stock_Qty'].fillna(0)
        else:
            merged_df = rofo_df.copy()
            merged_df['Stock_Qty'] = 0
    
    # Identify month columns
    month_columns = [col for col in merged_df.columns if '-' in str(col) and len(str(col)) >= 6]
    
    # Create input form
    st.subheader("📝 Forecast Adjustment Input")
    st.caption(f"Logged in as: **{username}** | Role: **Channel/Sales**")
    
    with st.form("channel_input_form"):
        # Display metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total SKUs", len(merged_df))
        with col2:
            total_stock = merged_df['Stock_Qty'].sum()
            st.metric("Total Stock", f"{total_stock:,.0f}")
        with col3:
            st.metric("Monthly Periods", len(month_columns))
        
        st.markdown("---")
        
        # Create editable dataframe
        edited_df = merged_df.copy()
        
        # Add input columns for each month
        for month in month_columns:
            edited_df[f"{month}_input"] = edited_df[month]
        
        # Display columns for editing
        display_columns = ['sku_code', 'Product_Name', 'Brand_Group', 'Brand', 'SKU_Tier', 'Stock_Qty']
        for month in month_columns:
            display_columns.extend([month, f"{month}_input"])
        
        # Create column configuration
        column_config = {}
        
        # Fixed columns
        column_config['sku_code'] = st.column_config.TextColumn("SKU Code", disabled=True)
        column_config['Product_Name'] = st.column_config.TextColumn("Product Name", disabled=True)
        column_config['Brand_Group'] = st.column_config.TextColumn("Brand Group", disabled=True)
        column_config['Brand'] = st.column_config.TextColumn("Brand", disabled=True)
        column_config['SKU_Tier'] = st.column_config.TextColumn("SKU Tier", disabled=True)
        column_config['Stock_Qty'] = st.column_config.NumberColumn("Stock Qty", disabled=True, format="%d")
        
        # Month columns
        for month in month_columns:
            column_config[month] = st.column_config.NumberColumn(
                f"Baseline {month}",
                disabled=True,
                format="%d"
            )
            column_config[f"{month}_input"] = st.column_config.NumberColumn(
                f"Your Input {month}",
                min_value=0,
                step=1,
                format="%d"
            )
        
        # Display data editor
        st.write("### Adjust Forecast Quantities (±40% limit)")
        edited_data = st.data_editor(
            edited_df[display_columns],
            column_config=column_config,
            use_container_width=True,
            height=400,
            num_rows="fixed",
            key="channel_editor"
        )
        
        # Notes field
        notes = st.text_area(
            "Notes / Justification for adjustments",
            placeholder="Explain significant changes...",
            key="channel_notes"
        )
        
        # Submit button
        submit = st.form_submit_button(
            "💾 Save to Channel Input",
            use_container_width=True,
            key="channel_submit"
        )
        
        if submit:
            # Validate adjustments (±40%)
            validation_errors = []
            
            for month in month_columns:
                input_col = f"{month}_input"
                baseline_col = month
                
                for idx, row in edited_data.iterrows():
                    baseline = row[baseline_col]
                    new_value = row[input_col]
                    
                    if pd.isna(baseline) or pd.isna(new_value):
                        continue
                    
                    try:
                        baseline = float(baseline)
                        new_value = float(new_value)
                    except:
                        continue
                    
                    max_change = baseline * 0.4
                    min_allowed = max(0, baseline - max_change)
                    max_allowed = baseline + max_change
                    
                    if new_value < min_allowed or new_value > max_allowed:
                        validation_errors.append({
                            'sku': row['sku_code'],
                            'brand_group': row.get('Brand_Group', 'N/A'),
                            'month': month,
                            'baseline': baseline,
                            'input': new_value,
                            'min_allowed': min_allowed,
                            'max_allowed': max_allowed
                        })
            
            # Show validation errors if any
            if validation_errors:
                st.error(f"❌ {len(validation_errors)} adjustments exceed ±40% limit")
                for error in validation_errors[:3]:
                    st.error(
                        f"**{error['sku']} - {error['month']}:** "
                        f"Input {error['input']:.0f} vs Baseline {error['baseline']:.0f}"
                    )
                if len(validation_errors) > 3:
                    st.error(f"... and {len(validation_errors) - 3} more errors")
            
            else:
                # Prepare data for saving
                save_df = edited_data.copy()
                
                # Keep only necessary columns
                save_columns = ['sku_code', 'Product_Name', 'Brand_Group', 'Brand', 'SKU_Tier']
                
                # Replace baseline with input values
                for month in month_columns:
                    save_df[month] = save_df[f"{month}_input"]
                    save_columns.append(month)
                
                # Add metadata
                save_df['notes'] = notes
                save_df['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                save_df['submitted_by'] = username
                
                # Select final columns
                final_columns = save_columns + ['notes', 'last_updated', 'submitted_by']
                save_df = save_df[final_columns]
                
                # Save to GSheet
                with st.spinner("Saving to Google Sheets..."):
                    success = gs.update_sheet("channel_input", save_df)
                    
                    if success:
                        # Log submission
                        log_entry = {
                            'submission_id': f"CH_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                            'username': username,
                            'role': 'channel',
                            'submission_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'status': 'submitted'
                        }
                        gs.append_to_sheet("input_log", log_entry)
                        
                        st.success("✅ Channel input saved successfully!")
                        st.balloons()
                    else:
                        st.error("❌ Failed to save data. Please try again.")

# ============================================================================
# BRAND PAGE
# ============================================================================
def show_brand_page(username, user_role):
    """Brand input page for both brand groups"""
    
    # Configuration for brand groups
    BRAND_CONFIG = {
        'brand1': {
            'name': 'ERHA SKINCARE GROUP 1',
            'brand_groups': ['ACNEACT', 'AGE CORRECTOR', 'TRUWHITE'],
            'sheet_name': 'brand1_input',
            'log_prefix': 'B1_',
            'icon': '🏷️'
        },
        'brand2': {
            'name': 'ERHA SKINCARE GROUP 2', 
            'brand_groups': ['ERHAIR', 'HISERHA', 'PERFECT SHIELD', 'SKINSITIVE'],
            'sheet_name': 'brand2_input',
            'log_prefix': 'B2_',
            'icon': '🏷️'
        }
    }
    
    # Get configuration for this user role
    config = BRAND_CONFIG.get(user_role)
    if not config:
        st.error("Invalid brand configuration.")
        return
    
    # Set page title and icon
    st.title(f"{config['icon']} {config['name']} Forecast Input")
    st.markdown("---")
    
    # Initialize connector
    gs = GSheetConnector()
    
    # Load data - Filter by brand group
    with st.spinner(f"Loading data for {config['name']}..."):
        rofo_df = gs.get_rofo_current()
        
        if rofo_df.empty:
            st.error("No ROFO data available.")
            return
        
        # FILTER: Only show SKUs for this brand group
        if 'Brand_Group' in rofo_df.columns:
            filtered_df = rofo_df[rofo_df['Brand_Group'].isin(config['brand_groups'])]
            
            if filtered_df.empty:
                st.warning(f"No SKUs found for {config['name']}.")
                return
        else:
            st.error("Brand_Group column not found in ROFO data")
            return
        
        # Merge with stock data
        stock_df = gs.get_sheet_data("stock_onhand")
        if not stock_df.empty and 'sku_code' in stock_df.columns:
            merged_df = pd.merge(
                filtered_df,
                stock_df[['sku_code', 'Stock_Qty']],
                on='sku_code',
                how='left'
            )
            merged_df['Stock_Qty'] = merged_df['Stock_Qty'].fillna(0)
        else:
            merged_df = filtered_df.copy()
            merged_df['Stock_Qty'] = 0
    
    # Identify month columns
    month_columns = [col for col in merged_df.columns if '-' in str(col) and len(str(col)) >= 6]
    
    # Create input form
    st.subheader("📝 Forecast Adjustment Input")
    st.caption(f"Logged in as: **{username}** | Role: **{config['name']}**")
    
    with st.form(f"{user_role}_input_form"):
        # Display metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(f"{config['name']} SKUs", len(merged_df))
        with col2:
            total_stock = merged_df['Stock_Qty'].sum()
            st.metric("Total Stock", f"{total_stock:,.0f}")
        with col3:
            st.metric("Monthly Periods", len(month_columns))
        
        st.markdown("---")
        
        # Create editable dataframe
        edited_df = merged_df.copy()
        
        # Add input columns for each month
        for month in month_columns:
            edited_df[f"{month}_input"] = edited_df[month]
        
        # Display columns for editing
        display_columns = ['sku_code', 'Product_Name', 'Brand', 'SKU_Tier', 'Stock_Qty']
        for month in month_columns:
            display_columns.extend([month, f"{month}_input"])
        
        # Create column configuration
        column_config = {}
        
        # Fixed columns
        column_config['sku_code'] = st.column_config.TextColumn("SKU Code", disabled=True)
        column_config['Product_Name'] = st.column_config.TextColumn("Product Name", disabled=True)
        column_config['Brand'] = st.column_config.TextColumn("Brand", disabled=True)
        column_config['SKU_Tier'] = st.column_config.TextColumn("SKU Tier", disabled=True)
        column_config['Stock_Qty'] = st.column_config.NumberColumn("Stock Qty", disabled=True, format="%d")
        
        # Month columns
        for month in month_columns:
            column_config[month] = st.column_config.NumberColumn(
                f"Baseline {month}",
                disabled=True,
                format="%d"
            )
            column_config[f"{month}_input"] = st.column_config.NumberColumn(
                f"Your Input {month}",
                min_value=0,
                step=1,
                format="%d"
            )
        
        # Display data editor
        st.write("### Adjust Forecast Quantities (±40% limit)")
        edited_data = st.data_editor(
            edited_df[display_columns],
            column_config=column_config,
            use_container_width=True,
            height=400,
            num_rows="fixed",
            key=f"{user_role}_editor"
        )
        
        # Campaign fields
        campaign_name = st.text_input(
            "Campaign Name (if applicable)",
            placeholder=f"e.g., {config['name']} Q2 Promotion",
            key=f"{user_role}_campaign"
        )
        
        notes = st.text_area(
            "Adjustment Notes",
            placeholder="Explain your forecast adjustments...",
            key=f"{user_role}_notes"
        )
        
        # Submit button
        submit = st.form_submit_button(
            f"💾 Save to {config['name']} Input",
            use_container_width=True,
            key=f"{user_role}_submit"
        )
        
        if submit:
            # Validate adjustments (±40%)
            validation_errors = []
            
            for month in month_columns:
                input_col = f"{month}_input"
                baseline_col = month
                
                for idx, row in edited_data.iterrows():
                    baseline = row[baseline_col]
                    new_value = row[input_col]
                    
                    if pd.isna(baseline) or pd.isna(new_value):
                        continue
                    
                    try:
                        baseline = float(baseline)
                        new_value = float(new_value)
                    except:
                        continue
                    
                    max_change = baseline * 0.4
                    min_allowed = max(0, baseline - max_change)
                    max_allowed = baseline + max_change
                    
                    if new_value < min_allowed or new_value > max_allowed:
                        validation_errors.append({
                            'sku': row['sku_code'],
                            'brand': row['Brand'],
                            'month': month,
                            'baseline': baseline,
                            'input': new_value,
                            'min_allowed': min_allowed,
                            'max_allowed': max_allowed
                        })
            
            if validation_errors:
                st.error(f"❌ {len(validation_errors)} adjustments exceed ±40% limit")
                for error in validation_errors[:3]:
                    st.error(
                        f"**{error['sku']} - {error['month']}:** "
                        f"Input {error['input']:.0f} vs Baseline {error['baseline']:.0f}"
                    )
                if len(validation_errors) > 3:
                    st.error(f"... and {len(validation_errors) - 3} more errors")
            
            else:
                # Prepare data for saving
                save_df = edited_data.copy()
                
                # Keep only necessary columns
                save_columns = ['sku_code', 'Product_Name', 'Brand_Group', 'Brand', 'SKU_Tier']
                
                # Replace baseline with input values
                for month in month_columns:
                    save_df[month] = save_df[f"{month}_input"]
                    save_columns.append(month)
                
                # Add metadata
                save_df['campaign_name'] = campaign_name
                save_df['notes'] = notes
                save_df['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                save_df['submitted_by'] = username
                
                # Select final columns
                final_columns = save_columns + ['campaign_name', 'notes', 'last_updated', 'submitted_by']
                save_df = save_df[final_columns]
                
                # Save to GSheet
                with st.spinner(f"Saving to {config['name']}..."):
                    success = gs.update_sheet(config['sheet_name'], save_df)
                    
                    if success:
                        # Log submission
                        log_entry = {
                            'submission_id': f"{config['log_prefix']}{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                            'username': username,
                            'role': user_role,
                            'submission_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'status': 'submitted'
                        }
                        gs.append_to_sheet("input_log", log_entry)
                        
                        st.success(f"✅ {config['name']} input saved successfully!")
                        st.balloons()
                    else:
                        st.error("❌ Failed to save data. Please try again.")

# ============================================================================
# ADMIN PAGE
# ============================================================================
def show_admin_page(username):
    """Admin/Demand Planner dashboard"""
    st.title("👨‍💼 Admin - Demand Planner Dashboard")
    st.markdown("---")
    
    # Initialize connector
    gs = GSheetConnector()
    
    # Sidebar controls
    with st.sidebar:
        st.header("Admin Controls")
        
        if st.button("🔄 Refresh All Data", use_container_width=True, key="admin_refresh"):
            st.rerun()
        
        st.markdown("---")
        st.subheader("Consensus Management")
        
        if st.button("✅ Finalize Consensus", type="primary", use_container_width=True, key="admin_finalize"):
            st.info("Consensus finalization feature coming soon...")
        
        st.markdown("---")
        st.subheader("Export Options")
        
        if st.button("📊 Export to Excel", use_container_width=True, key="admin_export"):
            st.info("Export feature coming soon...")
        
        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True, key="admin_logout"):
            st.session_state.authenticated = False
            st.session_state.username = None
            st.session_state.role = None
            st.rerun()
    
    # Load all data
    with st.spinner("Loading all data..."):
        rofo_df = gs.get_rofo_current()
        channel_df = gs.get_sheet_data("channel_input")
        brand1_df = gs.get_sheet_data("brand1_input")
        brand2_df = gs.get_sheet_data("brand2_input")
        stock_df = gs.get_sheet_data("stock_onhand")
        log_df = gs.get_sheet_data("input_log")
    
    # Tab layout
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Overview", 
        "🔍 Comparison", 
        "📊 Stock Simulation", 
        "📋 Submission Status"
    ])
    
    with tab1:
        st.subheader("S&OP Forecast Overview")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_skus = len(rofo_df) if not rofo_df.empty else 0
            st.metric("Total SKUs", total_skus)
        
        with col2:
            submitted = len(log_df[log_df['status'] == 'submitted']) if not log_df.empty else 0
            st.metric("Submissions Received", submitted)
        
        with col3:
            total_stock = stock_df['Stock_Qty'].sum() if not stock_df.empty else 0
            st.metric("Total Stock", f"{total_stock:,.0f}")
        
        with col4:
            total_users = 4
            active_users = len(log_df['username'].unique()) if not log_df.empty else 0
            st.metric("Active Users", f"{active_users}/{total_users}")
        
        # Recent activity
        st.markdown("---")
        st.subheader("Recent Activity")
        
        if not log_df.empty:
            recent_logs = log_df.sort_values('submission_date', ascending=False).head(10)
            for _, log in recent_logs.iterrows():
                st.write(f"**{log['username']}** ({log['role']}) submitted at {log['submission_date']}")
        else:
            st.info("No submissions yet.")
    
    with tab2:
        st.subheader("Forecast Comparison")
        
        if not rofo_df.empty:
            month_columns = [col for col in rofo_df.columns if '-' in str(col) and len(str(col)) >= 6]
            
            if month_columns:
                sample_month = month_columns[0]
                
                comparison_data = []
                
                # Get values from each source (first 10 SKUs)
                for idx, sku_row in rofo_df.head(10).iterrows():
                    sku_code = sku_row['sku_code']
                    
                    # Get channel input
                    channel_val = None
                    if not channel_df.empty and 'sku_code' in channel_df.columns:
                        channel_row = channel_df[channel_df['sku_code'] == sku_code]
                        if not channel_row.empty and sample_month in channel_row.columns:
                            channel_val = channel_row.iloc[0][sample_month]
                    
                    # Get brand1 input
                    brand1_val = None
                    if not brand1_df.empty and 'sku_code' in brand1_df.columns:
                        brand1_row = brand1_df[brand1_df['sku_code'] == sku_code]
                        if not brand1_row.empty and sample_month in brand1_row.columns:
                            brand1_val = brand1_row.iloc[0][sample_month]
                    
                    # Get brand2 input
                    brand2_val = None
                    if not brand2_df.empty and 'sku_code' in brand2_df.columns:
                        brand2_row = brand2_df[brand2_df['sku_code'] == sku_code]
                        if not brand2_row.empty and sample_month in brand2_row.columns:
                            brand2_val = brand2_row.iloc[0][sample_month]
                    
                    comparison_data.append({
                        'SKU': sku_code,
                        'Product': sku_row.get('Product_Name', ''),
                        'Brand Group': sku_row.get('Brand_Group', ''),
                        'Baseline': sku_row[sample_month],
                        'Channel': channel_val,
                        'Brand Group 1': brand1_val,
                        'Brand Group 2': brand2_val
                    })
                
                comp_df = pd.DataFrame(comparison_data)
                st.dataframe(comp_df, use_container_width=True)
    
    with tab3:
        st.subheader("Stock Projection Simulation")
        
        if not rofo_df.empty and not stock_df.empty:
            month_columns = [col for col in rofo_df.columns if '-' in str(col) and len(str(col)) >= 6]
            
            if month_columns:
                # Calculate total forecast per month
                total_forecast = []
                for month in month_columns:
                    if month in rofo_df.columns:
                        total_forecast.append({
                            'Month': month,
                            'Total Forecast': rofo_df[month].sum()
                        })
                
                forecast_df = pd.DataFrame(total_forecast)
                
                # Display forecast chart
                st.write("### Total Monthly Forecast")
                st.bar_chart(forecast_df.set_index('Month'))
                
                # Stock coverage calculation
                total_stock = stock_df['Stock_Qty'].sum()
                avg_monthly_forecast = rofo_df[month_columns].sum().mean()
                
                if avg_monthly_forecast > 0:
                    months_coverage = total_stock / avg_monthly_forecast
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Total Stock", f"{total_stock:,.0f}")
                    with col2:
                        st.metric("Months of Coverage", f"{months_coverage:.1f}")
        
        else:
            st.info("Data not available for stock simulation.")
    
    with tab4:
        st.subheader("Submission Status")
        
        if not log_df.empty:
            st.dataframe(log_df, use_container_width=True)
        else:
            st.info("No submissions yet.")

# ============================================================================
# MAIN APP LOGIC
# ============================================================================
def main():
    if not st.session_state.authenticated:
        show_login_page()
    else:
        # Show current user info in sidebar
        with st.sidebar:
            st.write(f"Logged in as: **{st.session_state.username}**")
            st.write(f"Role: **{st.session_state.role}**")
            
            if st.button("🚪 Logout", use_container_width=True, key="main_logout"):
                st.session_state.authenticated = False
                st.session_state.username = None
                st.session_state.role = None
                st.rerun()
        
        # Route based on role
        user_role = st.session_state.role
        
        if user_role == 'channel':
            show_channel_page(st.session_state.username)
        
        elif user_role in ['brand1', 'brand2']:
            show_brand_page(st.session_state.username, user_role)
        
        elif user_role == 'admin':
            show_admin_page(st.session_state.username)
        
        else:
            st.error("Invalid user role. Please contact administrator.")

# ============================================================================
# RUN THE APP
# ============================================================================
if __name__ == "__main__":
    main()
