import streamlit as st
import pandas as pd
import numpy as np
import gspread
import plotly.graph_objects as go
import plotly.express as px
from google.oauth2.service_account import Credentials
import json
from datetime import datetime
import time
import re
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode, JsCode
from streamlit_extras.metric_cards import style_metric_cards
from streamlit_extras.stylable_container import stylable_container
from streamlit_extras.toggle_switch import st_toggle_switch
from streamlit_autorefresh import st_autorefresh

# ============================================================================
# PAGE CONFIG - MODERN
# ============================================================================
st.set_page_config(
    page_title="ERHA S&OP 3-Month Consensus Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        'Get Help': 'https://www.erhagroup.com',
        'Report a bug': None,
        'About': "ERHA S&OP Dashboard v2.0"
    }
)

# ============================================================================
# MODERN CSS & THEME
# ============================================================================
st.markdown("""
<style>
    /* Modern Gradient Theme */
    :root {
        --primary: #3B82F6;
        --primary-dark: #1E3A8A;
        --secondary: #10B981;
        --danger: #EF4444;
        --warning: #F59E0B;
        --light: #F9FAFB;
        --dark: #1F2937;
        --border: #E5E7EB;
        --shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
    }
    
    /* Modern Header */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        color: white;
        box-shadow: var(--shadow);
    }
    
    .main-title {
        font-size: 2.8rem;
        font-weight: 800;
        margin: 0;
        background: linear-gradient(90deg, #FFFFFF 0%, #E5E7EB 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -0.5px;
    }
    
    .sub-title {
        font-size: 1.1rem;
        opacity: 0.9;
        margin-top: 0.5rem;
        font-weight: 400;
    }
    
    /* Modern Cards */
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid var(--border);
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        transition: all 0.3s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow);
    }
    
    /* Modern Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent;
        padding: 0;
        border-bottom: 2px solid var(--border);
    }
    
    .stTabs [data-baseweb="tab"] {
        padding: 12px 24px;
        border: none;
        border-bottom: 3px solid transparent;
        background: transparent;
        font-weight: 600;
        color: var(--dark);
        opacity: 0.7;
        transition: all 0.2s ease;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        opacity: 1;
        color: var(--primary);
    }
    
    .stTabs [aria-selected="true"] {
        background: transparent !important;
        color: var(--primary) !important;
        opacity: 1 !important;
        border-bottom: 3px solid var(--primary) !important;
    }
    
    /* Modern Filter Bar */
    .filter-bar {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid var(--border);
        margin-bottom: 2rem;
        display: flex;
        gap: 1rem;
        align-items: center;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    
    /* Badge Styles */
    .badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        margin: 0 4px;
    }
    
    .badge-primary { background: #DBEAFE; color: #1E40AF; }
    .badge-success { background: #D1FAE5; color: #065F46; }
    .badge-warning { background: #FEF3C7; color: #92400E; }
    .badge-danger { background: #FEE2E2; color: #991B1B; }
    
    /* Loading Animation */
    .loading-pulse {
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0% { opacity: 0.6; }
        50% { opacity: 1; }
        100% { opacity: 0.6; }
    }
    
    /* Responsive */
    @media (max-width: 768px) {
        .main-title { font-size: 2rem; }
        .filter-bar { flex-direction: column; }
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# AUTO-REFRESH (setiap 5 menit)
# ============================================================================
# Uncomment untuk auto-refresh
# st_autorefresh(interval=5 * 60 * 1000, key="data_refresh")

# ============================================================================
# GSHEET CONNECTOR CLASS (YOUR CODE)
# ============================================================================
class GSheetConnector:
    def __init__(self):
        self.sheet_id = st.secrets["gsheets"]["sheet_id"]
        self.service_account_info = json.loads(st.secrets["gsheets"]["service_account_info"])
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
        
        # Identify month columns (Feb-26, Mar-26, etc.)
        month_columns = [col for col in df.columns if '-' in str(col) and len(str(col)) >= 6]
        
        # Keep only relevant columns
        keep_columns = ['sku_code', 'Product_Name', 'Brand_Group', 'Brand', 'SKU_Tier'] + month_columns
        keep_columns = [col for col in keep_columns if col in df.columns]
        
        return df[keep_columns]

# ============================================================================
# DATA LOADER DENGAN GSHEETCONNECTOR ASLI
# ============================================================================
@st.cache_data(ttl=300, show_spinner=False)
def load_all_data():
    """Load and process all required data dari Google Sheets"""
    
    # Buat loading state
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        # Step 1: Connect to Google Sheets
        status_text.text("🔄 Connecting to Google Sheets...")
        progress_bar.progress(10)
        
        # Gunakan GSheetConnector Anda
        gs = GSheetConnector()
        
        # Step 2: Load sales history
        status_text.text("📥 Loading sales history...")
        progress_bar.progress(30)
        sales_df = gs.get_sheet_data("sales_history")
        
        if sales_df.empty:
            st.error("❌ No sales history data found")
            return pd.DataFrame()
        
        # Step 3: Load ROFO current
        status_text.text("📊 Loading ROFO forecast...")
        progress_bar.progress(50)
        rofo_df = gs.get_sheet_data("rofo_current")
        
        if rofo_df.empty:
            st.error("❌ No ROFO forecast data found")
            return pd.DataFrame()
        
        # Step 4: Load stock data
        status_text.text("📦 Loading stock data...")
        progress_bar.progress(70)
        stock_df = gs.get_sheet_data("stock_onhand")
        
        # Step 5: Process data sesuai kebutuhan
        status_text.text("⚙️ Processing data...")
        progress_bar.progress(90)
        
        # ===== PROSES DATA (sama seperti script asli Anda) =====
        
        # 1. Get last 3 months sales (Oct, Nov, Dec 2025)
        sales_months = ['Oct-25', 'Nov-25', 'Dec-25']
        available_sales_months = [m for m in sales_months if m in sales_df.columns]
        
        if len(available_sales_months) < 3:
            st.warning(f"⚠️ Only {len(available_sales_months)} of last 3 months available")
        
        # Calculate L3M Average
        sales_df['L3M_Avg'] = sales_df[available_sales_months].mean(axis=1).round(0)
        
        # 2. Get ROFO months
        adjustment_months = ['Feb-26', 'Mar-26', 'Apr-26']
        projection_months = ['May-26', 'Jun-26', 'Jul-26', 'Aug-26', 'Sep-26', 
                            'Oct-26', 'Nov-26', 'Dec-26', 'Jan-27']
        
        all_rofo_months = adjustment_months + projection_months
        available_rofo_months = [m for m in all_rofo_months if m in rofo_df.columns]
        
        # 3. Merge data
        sales_cols = ['sku_code', 'Product_Name', 'Brand_Group', 'Brand', 'SKU_Tier', 'L3M_Avg']
        sales_cols += available_sales_months
        sales_essential = sales_df[sales_cols].copy()
        
        rofo_cols = ['sku_code', 'Product_Name', 'Brand_Group', 'Brand', 'SKU_Tier']
        # Cari kolom floor_price jika ada
        if 'floor_price' in rofo_df.columns:
            rofo_cols.append('floor_price')
        rofo_cols += [m for m in available_rofo_months if m in rofo_df.columns]
        rofo_essential = rofo_df[rofo_cols].copy()
        
        merged_df = pd.merge(
            sales_essential,
            rofo_essential,
            on=['sku_code', 'Product_Name', 'Brand_Group', 'Brand', 'SKU_Tier'],
            how='inner',
            suffixes=('_sales', '_rofo')
        )
        
        # 4. Merge with stock
        if not stock_df.empty and 'sku_code' in stock_df.columns:
            if 'Stock_Qty' in stock_df.columns:
                merged_df = pd.merge(
                    merged_df,
                    stock_df[['sku_code', 'Stock_Qty']],
                    on='sku_code',
                    how='left'
                )
            else:
                # Cari kolom stock dengan nama lain
                stock_cols = [col for col in stock_df.columns if 'stock' in col.lower() or 'qty' in col.lower()]
                if stock_cols:
                    merged_df = pd.merge(
                        merged_df,
                        stock_df[['sku_code'] + stock_cols[:1]],
                        on='sku_code',
                        how='left'
                    )
                    merged_df.rename(columns={stock_cols[0]: 'Stock_Qty'}, inplace=True)
                else:
                    merged_df['Stock_Qty'] = 0
        else:
            merged_df['Stock_Qty'] = 0
        
        merged_df['Stock_Qty'] = merged_df['Stock_Qty'].fillna(0)
        
        # 5. Calculate Month Cover
        merged_df['Month_Cover'] = (merged_df['Stock_Qty'] / merged_df['L3M_Avg'].replace(0, 1)).round(1)
        merged_df['Month_Cover'] = merged_df['Month_Cover'].replace([np.inf, -np.inf], 0)
        
        # 6. Add consensus columns
        for month in adjustment_months:
            if month in merged_df.columns:
                merged_df[f'Cons_{month}'] = merged_df[month]
        
        status_text.text("✅ Data loaded successfully!")
        progress_bar.progress(100)
        time.sleep(0.5)  # Biar loading terlihat
        status_text.empty()
        progress_bar.empty()
        
        # Simpan informasi bulan ke session state
        st.session_state.adjustment_months = [m for m in adjustment_months if m in available_rofo_months]
        st.session_state.projection_months = [m for m in projection_months if m in available_rofo_months]
        
        return merged_df
        
    except Exception as e:
        status_text.empty()
        progress_bar.empty()
        st.error(f"❌ Error loading data: {str(e)}")
        st.info("⚠️ Using demo data for now. Check your Google Sheets connection.")
        
        # Fallback ke data dummy
        return create_demo_data()

def create_demo_data():
    """Create demo data if Google Sheets fails"""
    st.warning("⚠️ Using demo data. Real data will be loaded when Google Sheets connection is fixed.")
    
    np.random.seed(42)
    
    brands = ['Acneact', 'Age Corrector', 'Truwhite', 'ER Hair', 'His Erha', 'Perfect Shield', 'Skinsitive']
    skus = [f'ERH{str(i).zfill(3)}' for i in range(1, 101)]
    
    data = {
        'sku_code': skus,
        'Product_Name': [f'Product {i}' for i in range(1, 101)],
        'Brand': np.random.choice(brands, 100),
        'Brand_Group': ['Skincare', 'Haircare', 'Bodycare'] * 33 + ['Skincare'],
        'SKU_Tier': np.random.choice(['A', 'B', 'C'], 100, p=[0.2, 0.3, 0.5]),
        'Oct-25': np.random.randint(100, 1000, 100),
        'Nov-25': np.random.randint(100, 1000, 100),
        'Dec-25': np.random.randint(100, 1000, 100),
        'Feb-26': np.random.randint(50, 1500, 100),
        'Mar-26': np.random.randint(50, 1500, 100),
        'Apr-26': np.random.randint(50, 1500, 100),
        'floor_price': np.random.randint(50000, 500000, 100),
        'Stock_Qty': np.random.randint(0, 5000, 100)
    }
    
    df = pd.DataFrame(data)
    
    # Calculate metrics
    df['L3M_Avg'] = df[['Oct-25', 'Nov-25', 'Dec-25']].mean(axis=1).round(0)
    df['Month_Cover'] = (df['Stock_Qty'] / df['L3M_Avg'].replace(0, 1)).round(1)
    df['Month_Cover'] = df['Month_Cover'].replace([np.inf, -np.inf], 0)
    
    # Add consensus columns
    for month in ['Feb-26', 'Mar-26', 'Apr-26']:
        df[f'Cons_{month}'] = df[month]
    
    # Simpan ke session state
    st.session_state.adjustment_months = ['Feb-26', 'Mar-26', 'Apr-26']
    st.session_state.projection_months = []
    st.session_state.has_floor_price = True
    
    return df

# ============================================================================
# MODERN HEADER
# ============================================================================
with st.container():
    st.markdown("""
    <div class="main-header">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h1 class="main-title">📊 ERHA S&OP Dashboard</h1>
                <p class="sub-title">3-Month Consensus | Real-time Collaboration | AI-Powered Insights</p>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 0.9rem; opacity: 0.8;">Meeting Status</div>
                <div style="display: flex; align-items: center; gap: 8px; margin-top: 4px;">
                    <div style="width: 8px; height: 8px; background: #10B981; border-radius: 50%;"></div>
                    <span style="font-weight: 600;">Live</span>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ============================================================================
# MEETING INFO BAR - MODERN
# ============================================================================
with stylable_container(
    key="meeting_bar",
    css_styles="""
    {
        background: white;
        padding: 1rem 1.5rem;
        border-radius: 12px;
        border: 1px solid #E5E7EB;
        margin-bottom: 1.5rem;
    }
    """
):
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    with col1:
        meeting_date = st.date_input("📅 Meeting Date", value=datetime.now().date(), key="meeting_date")
    with col2:
        st.selectbox("👥 Participants", ["All Teams", "Supply Chain", "Marketing", "Finance"], key="participants")
    with col3:
        st.selectbox("📁 Version", ["v2.0 - Current", "v1.0 - Previous"], key="version")
    with col4:
        st_toggle_switch("🔔 Notifications", key="notifications")

# ============================================================================
# LOAD DATA DENGAN LOADING ANIMATION
# ============================================================================
with st.spinner('🔄 Loading latest data from Google Sheets...'):
    all_df = load_all_data()

# Initialize session state for months if not exists
if 'adjustment_months' not in st.session_state:
    st.session_state.adjustment_months = ['Feb-26', 'Mar-26', 'Apr-26']
if 'projection_months' not in st.session_state:
    st.session_state.projection_months = []
if 'has_floor_price' not in st.session_state:
    st.session_state.has_floor_price = 'floor_price' in all_df.columns

# ============================================================================
# QUICK METRICS OVERVIEW - MODERN
# ============================================================================
st.markdown("### 📊 Quick Overview")
metrics_cols = st.columns(5)

with metrics_cols[0]:
    with stylable_container(
        key="metric1",
        css_styles="""
        {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 1.5rem;
            border-radius: 12px;
            color: white;
        }
        """
    ):
        st.metric("Total SKUs", f"{len(all_df):,}", "SKUs")
        style_metric_cards()

with metrics_cols[1]:
    with stylable_container(
        key="metric2",
        css_styles="""
        {
            background: linear-gradient(135deg, #10B981 0%, #059669 100%);
            padding: 1.5rem;
            border-radius: 12px;
            color: white;
        }
        """
    ):
        if 'L3M_Avg' in all_df.columns:
            total_sales = all_df['L3M_Avg'].sum() * 3
        else:
            total_sales = all_df[['Oct-25', 'Nov-25', 'Dec-25']].sum().sum() if all([col in all_df.columns for col in ['Oct-25', 'Nov-25', 'Dec-25']]) else 0
        st.metric("Total Sales L3M", f"{total_sales:,.0f}", "units")
        style_metric_cards()

with metrics_cols[2]:
    with stylable_container(
        key="metric3",
        css_styles="""
        {
            background: linear-gradient(135deg, #F59E0B 0%, #D97706 100%);
            padding: 1.5rem;
            border-radius: 12px;
            color: white;
        }
        """
    ):
        avg_cover = all_df['Month_Cover'].mean() if 'Month_Cover' in all_df.columns else 0
        st.metric("Avg Month Cover", f"{avg_cover:.1f}", "months")
        style_metric_cards()

with metrics_cols[3]:
    with stylable_container(
        key="metric4",
        css_styles="""
        {
            background: linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%);
            padding: 1.5rem;
            border-radius: 12px;
            color: white;
        }
        """
    ):
        if 'Month_Cover' in all_df.columns:
            high_cover = len(all_df[all_df['Month_Cover'] > 1.5])
        else:
            high_cover = 0
        st.metric("High Cover SKUs", f"{high_cover:,}", f"{high_cover/len(all_df)*100:.0f}%" if len(all_df) > 0 else "0%")
        style_metric_cards()

with metrics_cols[4]:
    with stylable_container(
        key="metric5",
        css_styles="""
        {
            background: linear-gradient(135deg, #8B5CF6 0%, #7C3AED 100%);
            padding: 1.5rem;
            border-radius: 12px;
            color: white;
        }
        """
    ):
        forecast_total = 0
        for month in st.session_state.adjustment_months:
            if month in all_df.columns:
                forecast_total += all_df[month].sum()
        growth = ((forecast_total - total_sales) / total_sales * 100) if total_sales > 0 else 0
        st.metric("3M Forecast", f"{forecast_total:,.0f}", f"{growth:+.1f}%")
        style_metric_cards()

# ============================================================================
# MODERN FILTER BAR
# ============================================================================
with st.container():
    st.markdown("### 🔍 Filter Data")
    
    with stylable_container(
        key="filter_container",
        css_styles="""
        {
            background: white;
            padding: 1.5rem;
            border-radius: 12px;
            border: 1px solid #E5E7EB;
            margin-bottom: 1.5rem;
        }
        """
    ):
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            brand_groups = ["ALL"]
            if 'Brand_Group' in all_df.columns:
                brand_groups += sorted(all_df['Brand_Group'].dropna().unique().tolist())
            selected_brand_group = st.selectbox(
                "Brand Group",
                brand_groups,
                key="filter_brand_group"
            )
        
        with col2:
            brands = ["ALL"]
            if 'Brand' in all_df.columns:
                brands += sorted(all_df['Brand'].dropna().unique().tolist())
            selected_brand = st.selectbox(
                "Brand",
                brands,
                key="filter_brand"
            )
        
        with col3:
            sku_tiers = ["ALL"]
            if 'SKU_Tier' in all_df.columns:
                sku_tiers += sorted(all_df['SKU_Tier'].dropna().unique().tolist())
            selected_tier = st.selectbox(
                "SKU Tier",
                sku_tiers,
                key="filter_tier"
            )
        
        with col4:
            month_cover_filter = st.selectbox(
                "Month Cover",
                ["ALL", "< 1.5 months", "1.5 - 3 months", "> 3 months"],
                key="filter_month_cover"
            )
        
        with col5:
            st.markdown("&nbsp;")
            col5a, col5b = st.columns(2)
            with col5a:
                if st.button("🔄 Refresh", use_container_width=True):
                    st.cache_data.clear()
                    st.rerun()
            with col5b:
                if st.button("📊 Reset Filters", type="secondary", use_container_width=True):
                    for key in ["filter_brand_group", "filter_brand", "filter_tier", "filter_month_cover"]:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.rerun()

# ============================================================================
# TAB INTERFACE - MODERN
# ============================================================================
tab1, tab2, tab3 = st.tabs(["📝 Input & Adjustment", "📊 Analytics Dashboard", "🎯 Focus Areas"])

# ============================================================================
# TAB 1: INPUT TABLE DENGAN DATA EDITOR (STABLE VERSION)
# ============================================================================
with tab1:
    st.markdown("### 🎯 3-Month Forecast Adjustment")
    
    # Filter data untuk tab 1
    filtered_df = all_df.copy()
    if selected_brand_group != "ALL" and 'Brand_Group' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['Brand_Group'] == selected_brand_group]
    if selected_brand != "ALL" and 'Brand' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['Brand'] == selected_brand]
    if selected_tier != "ALL" and 'SKU_Tier' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['SKU_Tier'] == selected_tier]
    
    # Apply month cover filter
    if month_cover_filter != "ALL" and 'Month_Cover' in filtered_df.columns:
        if month_cover_filter == "< 1.5 months":
            filtered_df = filtered_df[filtered_df['Month_Cover'] < 1.5]
        elif month_cover_filter == "1.5 - 3 months":
            filtered_df = filtered_df[(filtered_df['Month_Cover'] >= 1.5) & (filtered_df['Month_Cover'] <= 3)]
        elif month_cover_filter == "> 3 months":
            filtered_df = filtered_df[filtered_df['Month_Cover'] > 3]
    
    # Prepare display dataframe
    display_columns = ['sku_code', 'Product_Name', 'Brand', 'SKU_Tier']
    
    # Add sales months if available
    sales_cols = [col for col in ['Oct-25', 'Nov-25', 'Dec-25'] if col in filtered_df.columns]
    display_columns += sales_cols
    
    # Add calculated columns
    calc_cols = [col for col in ['L3M_Avg', 'Stock_Qty', 'Month_Cover'] if col in filtered_df.columns]
    display_columns += calc_cols
    
    # Add forecast months
    forecast_cols = []
    for month in st.session_state.adjustment_months:
        if month in filtered_df.columns:
            forecast_cols.append(month)
    display_columns += forecast_cols
    
    # Add percentage columns
    for month in forecast_cols:
        if 'L3M_Avg' in filtered_df.columns:
            filtered_df[f'{month}_%'] = (filtered_df[month] / filtered_df['L3M_Avg'].replace(0, 1) * 100).round(1)
            display_columns.append(f'{month}_%')
    
    # Add consensus columns
    consensus_cols = []
    for month in st.session_state.adjustment_months:
        cons_col = f'Cons_{month}'
        if cons_col in filtered_df.columns:
            consensus_cols.append(cons_col)
        else:
            # Initialize consensus columns
            if month in filtered_df.columns:
                filtered_df[cons_col] = filtered_df[month]
                consensus_cols.append(cons_col)
    
    display_columns += consensus_cols
    
    # Create display dataframe
    display_df = filtered_df[display_columns].copy()
    
    # Add row numbers
    display_df.insert(0, 'No.', range(1, len(display_df) + 1))
    
    # Display info
    st.info(f"📋 Showing **{len(display_df)}** SKUs out of **{len(all_df)}** total")
    
    # Color legend
    st.markdown("""
    <div style="display: flex; gap: 1rem; margin: 1rem 0; padding: 0.75rem; background: #F9FAFB; border-radius: 8px; align-items: center;">
        <div style="font-size: 0.85rem; font-weight: 500; color: #6B7280;">Color Legend:</div>
        <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
            <div style="background-color: #FCE7F3; color: #BE185D; padding: 4px 12px; border-radius: 4px; font-size: 0.8rem; font-weight: 600;">
                Month Cover > 1.5
            </div>
            <div style="background-color: #FFEDD5; color: #9A3412; padding: 4px 12px; border-radius: 4px; font-size: 0.8rem; font-weight: 600;">
                Growth < 90%
            </div>
            <div style="background-color: #FEE2E2; color: #991B1B; padding: 4px 12px; border-radius: 4px; font-size: 0.8rem; font-weight: 600;">
                Growth > 130%
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Display the dataframe with conditional formatting
    st.markdown("#### 📋 Current Forecast (Read-only View)")
    
    # Limit rows untuk performance
    display_limit = 100
    if len(display_df) > display_limit:
        st.warning(f"Showing first {display_limit} of {len(display_df)} rows. Use filters to narrow down.")
        display_sample = display_df.head(display_limit)
    else:
        display_sample = display_df
    
    # Fungsi untuk apply styling
    def style_dataframe(df):
        # Convert to HTML dengan styling
        html = '<table class="dataframe" style="width:100%; border-collapse: collapse;"><thead><tr>'
        
        # Header
        for col in df.columns:
            html += f'<th style="background-color: #F3F4F6; padding: 12px; border-bottom: 2px solid #D1D5DB; text-align: left;">{col}</th>'
        html += '</tr></thead><tbody>'
        
        # Rows dengan conditional formatting
        for idx, row in df.iterrows():
            html += '<tr>'
            
            for col_idx, col_name in enumerate(df.columns):
                value = row[col_name]
                cell_style = 'padding: 10px 12px; border-bottom: 1px solid #E5E7EB;'
                
                # Apply conditional formatting
                if col_name == 'Month_Cover' and isinstance(value, (int, float)):
                    if value > 1.5:
                        cell_style += 'background-color: #FCE7F3 !important; color: #BE185D !important; font-weight: 600; border-left: 3px solid #BE185D !important;'
                
                elif '_%' in col_name and isinstance(value, (int, float)):
                    if value < 90:
                        cell_style += 'background-color: #FFEDD5 !important; color: #9A3412 !important; font-weight: 600; border-left: 3px solid #9A3412 !important;'
                    elif value > 130:
                        cell_style += 'background-color: #FEE2E2 !important; color: #991B1B !important; font-weight: 600; border-left: 3px solid #991B1B !important;'
                
                elif col_name == 'Brand' and isinstance(value, str):
                    brand_lower = value.lower().replace(' ', '-').replace('_', '-')
                    cell_style += f'background-color: var(--brand-{brand_lower}, #FFFFFF) !important;'
                
                html += f'<td style="{cell_style}">{value}</td>'
            
            html += '</tr>'
        
        html += '</tbody></table>'
        return html
    
    # Display styled table
    st.markdown(style_dataframe(display_sample), unsafe_allow_html=True)
    
    # =================================================================
    # EDITABLE CONSENSUS SECTION
    # =================================================================
    st.markdown("---")
    st.markdown("### ✏️ Edit Consensus Values")
    
    # Create editable dataframe hanya untuk consensus columns
    editable_cols = ['No.', 'sku_code', 'Product_Name', 'Brand', 'SKU_Tier']
    
    if 'L3M_Avg' in display_df.columns:
        editable_cols.append('L3M_Avg')
    
    # Add consensus columns
    for month in st.session_state.adjustment_months:
        cons_col = f'Cons_{month}'
        if cons_col in display_df.columns:
            editable_cols.append(cons_col)
    
    # Create editable dataframe
    editable_df = display_df[editable_cols].copy()
    
    # Column config untuk editor
    column_config = {}
    
    # Read-only columns
    for col in ['No.', 'sku_code', 'Product_Name', 'Brand', 'SKU_Tier', 'L3M_Avg']:
        if col in editable_df.columns:
            column_config[col] = st.column_config.Column(
                col.replace('_', ' '),
                disabled=True
            )
    
    # Editable consensus columns
    for month in st.session_state.adjustment_months:
        cons_col = f'Cons_{month}'
        if cons_col in editable_df.columns:
            column_config[cons_col] = st.column_config.NumberColumn(
                f"Cons {month}",
                min_value=0,
                step=1,
                format="%d",
                help=f"Final consensus for {month}"
            )
    
    # Display data editor untuk consensus values
    st.markdown("**Edit the Consensus columns below:**")
    edited_consensus = st.data_editor(
        editable_df,
        column_config=column_config,
        use_container_width=True,
        height=400,
        key="consensus_editor",
        num_rows="fixed"
    )
    
    # Save button section
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if st.button("💾 Save Consensus", type="primary", use_container_width=True, key="save_consensus"):
            with st.spinner("Saving consensus values..."):
                # Store in session state
                st.session_state.consensus_data = edited_consensus.copy()
                
                # Calculate changes
                changes_summary = []
                for month in st.session_state.adjustment_months:
                    cons_col = f'Cons_{month}'
                    if cons_col in edited_consensus.columns:
                        original_val = display_df[cons_col].sum()
                        new_val = edited_consensus[cons_col].sum()
                        change = new_val - original_val
                        change_pct = (change / original_val * 100) if original_val != 0 else 0
                        changes_summary.append({
                            'month': month,
                            'original': original_val,
                            'new': new_val,
                            'change': change,
                            'change_pct': change_pct
                        })
                
                st.session_state.changes_summary = changes_summary
                st.success("✅ Consensus values saved!")
                
                # Show changes
                st.info("**Summary of Changes:**")
                for change in changes_summary:
                    st.write(f"- **{change['month']}:** {change['change']:+,.0f} units ({change['change_pct']:+.1f}%)")
    
    with col2:
        if st.button("📊 Preview Changes", use_container_width=True, key="preview_changes"):
            if 'consensus_data' in st.session_state:
                st.info("**Latest Consensus Values:**")
                st.dataframe(st.session_state.consensus_data, use_container_width=True)
            else:
                st.warning("No consensus data saved yet.")
    
    with col3:
        if st.button("🔄 Reset All", use_container_width=True, key="reset_consensus"):
            if 'consensus_data' in st.session_state:
                del st.session_state.consensus_data
            if 'changes_summary' in st.session_state:
                del st.session_state.changes_summary
            st.rerun()

# ============================================================================
# TAB 2: ANALYTICS DASHBOARD
# ============================================================================
with tab2:
    st.markdown("### 📈 Consensus Results & Projections")
    
    # Use edited consensus data if available
    results_df = all_df.copy()
    
    if 'consensus_data' in st.session_state:
        consensus_df = st.session_state.consensus_data.copy()
        
        # Map consensus values back to full dataset
        for month in st.session_state.adjustment_months:
            cons_col = f'Cons_{month}'
            if cons_col in consensus_df.columns:
                # Create mapping dari sku_code ke consensus value
                consensus_map = dict(zip(consensus_df['sku_code'], consensus_df[cons_col]))
                results_df[cons_col] = results_df['sku_code'].map(consensus_map).fillna(results_df[month])
    else:
        # Initialize consensus columns as same as ROFO
        for month in st.session_state.adjustment_months:
            cons_col = f'Cons_{month}'
            if month in results_df.columns:
                results_df[cons_col] = results_df[month]
    
    # Summary untuk Tab 2
    st.markdown("#### 📊 Overall Summary")
    metric_cols2 = st.columns(4)
    
    with metric_cols2[0]:
        total_all_skus = len(results_df)
        st.metric("Total SKUs", f"{total_all_skus:,}")
    
    with metric_cols2[1]:
        if 'L3M_Avg' in results_df.columns:
            total_all_l3m = results_df['L3M_Avg'].sum()
        else:
            total_all_l3m = 0
        st.metric("Total L3M Sales", f"{total_all_l3m:,.0f}")
    
    with metric_cols2[2]:
        if 'Stock_Qty' in results_df.columns:
            total_all_stock = results_df['Stock_Qty'].sum()
        else:
            total_all_stock = 0
        st.metric("Total Stock", f"{total_all_stock:,}")
    
    with metric_cols2[3]:
        if st.session_state.adjustment_months:
            month = st.session_state.adjustment_months[0]
            cons_col = f'Cons_{month}'
            if cons_col in results_df.columns:
                total_consensus = results_df[cons_col].sum()
                total_baseline = results_df['L3M_Avg'].sum() if 'L3M_Avg' in results_df.columns else 0
                total_growth = ((total_consensus - total_baseline) / total_baseline * 100).round(1) if total_baseline > 0 else 0
                st.metric(f"Total {month} Growth", f"{total_growth:+.1f}%")
            else:
                st.metric(f"Total {month}", "N/A")
    
    # Show changes summary jika ada
    if 'changes_summary' in st.session_state:
        st.markdown("---")
        st.markdown("#### 📝 Consensus Changes Summary")
        
        changes_df = pd.DataFrame(st.session_state.changes_summary)
        
        # Format untuk display
        display_changes = changes_df.copy()
        display_changes['Original'] = display_changes['original'].apply(lambda x: f"{x:,.0f}")
        display_changes['New'] = display_changes['new'].apply(lambda x: f"{x:,.0f}")
        display_changes['Change'] = display_changes['change'].apply(lambda x: f"{x:+,.0f}")
        display_changes['Change %'] = display_changes['change_pct'].apply(lambda x: f"{x:+.1f}%")
        
        # Display
        st.dataframe(display_changes[['month', 'Original', 'New', 'Change', 'Change %']].rename(
            columns={'month': 'Month'}
        ), use_container_width=True, hide_index=True)
    
    # =================================================================
    # MONTHLY SUMMARY TABLE
    # =================================================================
    st.markdown("---")
    st.markdown("#### 📈 Monthly Volume Summary")
    
    # Prepare monthly summary data
    summary_data = []
    
    # Include semua bulan: adjustment + projection
    all_display_months = [f'Cons_{m}' for m in st.session_state.adjustment_months] + st.session_state.projection_months
    all_display_months = [m for m in all_display_months if m in results_df.columns]
    
    for month in all_display_months:
        month_name = month.replace('Cons_', '')
        total_qty = results_df[month].sum()
        
        # Calculate growth vs L3M untuk consensus months
        growth_pct = None
        if month.startswith('Cons_') and 'L3M_Avg' in results_df.columns:
            growth_pct = ((results_df[month].sum() - results_df['L3M_Avg'].sum()) / 
                         results_df['L3M_Avg'].sum() * 100).round(1)
        
        summary_data.append({
            'Month': month_name,
            'Total Volume': total_qty,
            'Growth vs L3M': growth_pct
        })
    
    if summary_data:
        summary_df = pd.DataFrame(summary_data)
        
        # Format untuk display
        display_summary = summary_df.copy()
        display_summary['Total Volume'] = display_summary['Total Volume'].apply(lambda x: f"{x:,.0f}")
        display_summary['Growth vs L3M'] = display_summary['Growth vs L3M'].apply(
            lambda x: f"{x:+.1f}%" if pd.notnull(x) else "N/A"
        )
        
        # Display summary table
        col1, col2 = st.columns([3, 2])
        
        with col1:
            st.dataframe(display_summary, use_container_width=True, hide_index=True)
        
        with col2:
            # Key metrics card
            st.markdown("#### 🎯 Key Metrics")
            
            # Calculate averages
            growth_values = summary_df['Growth vs L3M'].dropna()
            if not growth_values.empty:
                avg_growth = growth_values.mean()
                st.metric("Avg Growth vs L3M", f"{avg_growth:+.1f}%")
            
            # Stock metrics
            if 'Month_Cover' in results_df.columns:
                high_cover_count = len(results_df[results_df['Month_Cover'] > 1.5])
                st.metric("SKUs with Month Cover > 1.5", f"{high_cover_count:,}")
                
                avg_month_cover_all = results_df['Month_Cover'].mean()
                st.metric("Overall Avg Month Cover", f"{avg_month_cover_all:.1f}")
            
            if st.session_state.has_floor_price and 'floor_price' in results_df.columns:
                # Hitung total value dari 3 bulan adjustment
                adjustment_value = 0
                for month in st.session_state.adjustment_months:
                    cons_col = f'Cons_{month}'
                    if cons_col in results_df.columns:
                        month_value = (results_df[cons_col] * results_df['floor_price']).sum()
                        adjustment_value += month_value
                
                st.metric("Total 3-Month Value", f"Rp {adjustment_value:,.0f}")
    
    # =================================================================
    # VISUAL ANALYTICS
    # =================================================================
    st.markdown("---")
    st.markdown("### 📊 Visual Analytics")
    
    # Chart 1: Monthly Volume Trend
    if 'summary_data' in locals() and summary_data:
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            st.markdown("#### 📈 Monthly Volume Trend")
            
            # Buat DataFrame untuk chart
            chart_data = []
            
            for row in summary_data:
                month_name = row['Month']
                total_volume = row['Total Volume']
                
                # Determine type
                if month_name in [m.replace('Cons_', '') for m in st.session_state.adjustment_months]:
                    chart_type = 'Adjusted'
                elif month_name in st.session_state.projection_months:
                    chart_type = 'Projected'
                else:
                    chart_type = 'Other'
                
                chart_data.append({
                    'Month': month_name,
                    'Volume': total_volume,
                    'Type': chart_type
                })
            
            chart_df = pd.DataFrame(chart_data)
            
            if not chart_df.empty:
                fig = px.line(
                    chart_df,
                    x='Month',
                    y='Volume',
                    color='Type',
                    markers=True,
                    line_shape='spline',
                    title="Monthly Forecast Volume Trend",
                    template='plotly_white'
                )
                
                fig.update_layout(
                    height=400,
                    hovermode='x unified',
                    plot_bgcolor='white',
                    yaxis=dict(
                        title="Volume (units)", 
                        gridcolor='#E5E7EB',
                        tickformat=',.0f'
                    ),
                    xaxis=dict(
                        title="Month", 
                        tickangle=45, 
                        gridcolor='#E5E7EB',
                        type='category'
                    )
                )
                
                # Format hover
                fig.update_traces(
                    hovertemplate='<b>%{x}</b><br>Volume: %{y:,.0f} units<br>Type: %{data.name}'
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No chart data available")
        
        with chart_col2:
            st.markdown("#### 📊 Brand Contribution")
            
            # Calculate brand totals untuk adjusted months
            if 'Brand' in results_df.columns:
                brand_data = []
                for brand in results_df['Brand'].dropna().unique():
                    brand_qty = 0
                    for month in st.session_state.adjustment_months:
                        cons_col = f'Cons_{month}'
                        if cons_col in results_df.columns:
                            brand_mask = results_df['Brand'] == brand
                            brand_qty += results_df.loc[brand_mask, cons_col].sum()
                    
                    if brand_qty > 0:  # Hanya tampilkan brand dengan volume > 0
                        brand_data.append({
                            'Brand': brand,
                            'Total Volume': brand_qty
                        })
                
                if brand_data:
                    brand_df = pd.DataFrame(brand_data)
                    brand_df = brand_df.sort_values('Total Volume', ascending=True)
                    
                    # Limit to top 10 jika terlalu banyak
                    if len(brand_df) > 10:
                        brand_df = brand_df.tail(10)
                    
                    fig = px.bar(
                        brand_df,
                        y='Brand',
                        x='Total Volume',
                        orientation='h',
                        title="Brand Contribution to Adjusted Forecast",
                        color='Total Volume',
                        color_continuous_scale='Viridis'
                    )
                    
                    fig.update_layout(
                        height=400,
                        showlegend=False,
                        plot_bgcolor='white',
                        xaxis=dict(
                            title="Total Volume (units)", 
                            gridcolor='#E5E7EB',
                            tickformat=',.0f'
                        )
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No brand contribution data available")
            else:
                st.info("Brand column not found in data")
    
    # =================================================================
    # DETAILED DATA TABLE
    # =================================================================
    st.markdown("---")
    st.markdown("#### 📋 Detailed Consensus Data")
    
    # Prepare detailed view
    detailed_cols = ['sku_code', 'Product_Name', 'Brand', 'SKU_Tier']
    
    if 'L3M_Avg' in results_df.columns:
        detailed_cols.append('L3M_Avg')
    if 'Month_Cover' in results_df.columns:
        detailed_cols.append('Month_Cover')
    
    # Add consensus columns
    for month in st.session_state.adjustment_months:
        cons_col = f'Cons_{month}'
        if cons_col in results_df.columns:
            detailed_cols.append(cons_col)
    
    # Add growth % columns
    for month in st.session_state.adjustment_months:
        cons_col = f'Cons_{month}'
        if cons_col in results_df.columns and 'L3M_Avg' in results_df.columns:
            growth_col = f'Cons_{month}_Growth'
            results_df[growth_col] = (results_df[cons_col] / results_df['L3M_Avg'].replace(0, 1) * 100).round(1)
            detailed_cols.append(growth_col)
    
    if detailed_cols:
        detailed_df = results_df[detailed_cols].copy()
        
        # Add row numbers
        detailed_df.insert(0, 'No.', range(1, len(detailed_df) + 1))
        
        # Limit display
        if len(detailed_df) > 50:
            st.info(f"Showing first 50 of {len(detailed_df)} SKUs. Use filters in Tab 1 for specific views.")
            st.dataframe(detailed_df.head(50), use_container_width=True, hide_index=True)
        else:
            st.dataframe(detailed_df, use_container_width=True, hide_index=True)
        
        # Export button
        if st.button("📥 Export Full Consensus Data", key="export_tab2"):
            csv = detailed_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="⬇️ Download CSV",
                data=csv,
                file_name=f"full_consensus_data_{meeting_date}.csv",
                mime="text/csv",
                key="download_tab2"
            )

# ============================================================================
# TAB 3: FOCUS AREAS & ALERTS
# ============================================================================
with tab3:
    st.markdown("### 🎯 Focus Areas & Action Items")
    
    # Generate alerts
    alerts_data = {}
    
    if 'Month_Cover' in all_df.columns:
        high_cover_skus = all_df[all_df['Month_Cover'] > 1.5].sort_values('Month_Cover', ascending=False)
        alerts_data['high_cover'] = {
            'count': len(high_cover_skus),
            'data': high_cover_skus,
            'title': '⚠️ High Month Cover',
            'subtitle': 'Month Cover > 1.5',
            'color': '#EF4444'
        }
    
    if 'L3M_Avg' in all_df.columns and 'Feb-26' in all_df.columns:
        low_growth_mask = (all_df['Feb-26'] / all_df['L3M_Avg'].replace(0, 1) * 100) < 90
        low_growth_skus = all_df[low_growth_mask].sort_values('L3M_Avg')
        alerts_data['low_growth'] = {
            'count': len(low_growth_skus),
            'data': low_growth_skus,
            'title': '📉 Low Growth SKUs',
            'subtitle': '<90% growth',
            'color': '#F59E0B'
        }
        
        high_growth_mask = (all_df['Feb-26'] / all_df['L3M_Avg'].replace(0, 1) * 100) > 130
        high_growth_skus = all_df[high_growth_mask].sort_values('Feb-26', ascending=False)
        alerts_data['high_growth'] = {
            'count': len(high_growth_skus),
            'data': high_growth_skus,
            'title': '📈 High Growth SKUs',
            'subtitle': '>130% growth',
            'color': '#10B981'
        }
    
    if 'Stock_Qty' in all_df.columns and 'L3M_Avg' in all_df.columns:
        low_stock_skus = all_df[all_df['Stock_Qty'] < all_df['L3M_Avg']].sort_values('Stock_Qty')
        alerts_data['low_stock'] = {
            'count': len(low_stock_skus),
            'data': low_stock_skus,
            'title': '📦 Low Stock SKUs',
            'subtitle': '<1 month cover',
            'color': '#8B5CF6'
        }
    
    # Display alerts in grid
    if alerts_data:
        # Row 1
        cols = st.columns(2)
        alert_keys = list(alerts_data.keys())
        
        for i, alert_key in enumerate(alert_keys[:2]):
            with cols[i]:
                alert = alerts_data[alert_key]
                with stylable_container(
                    key=f"alert_{alert_key}",
                    css_styles=f"""
                    {{
                        background: white;
                        padding: 1.5rem;
                        border-radius: 12px;
                        border-left: 6px solid {alert['color']};
                        margin-bottom: 1rem;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                    }}
                    """
                ):
                    st.markdown(f"#### {alert['title']}")
                    st.metric("SKUs", f"{alert['count']:,}", alert['subtitle'])
                    
                    if alert['count'] > 0:
                        with st.expander("View SKUs"):
                            if 'sku_code' in alert['data'].columns:
                                display_cols = ['sku_code', 'Product_Name', 'Brand']
                                if 'Month_Cover' in alert['data'].columns:
                                    display_cols.append('Month_Cover')
                                if 'L3M_Avg' in alert['data'].columns and 'Feb-26' in alert['data'].columns:
                                    display_cols.extend(['L3M_Avg', 'Feb-26'])
                                if 'Stock_Qty' in alert['data'].columns:
                                    display_cols.append('Stock_Qty')
                                
                                st.dataframe(alert['data'][display_cols].head(10))
        
        # Row 2
        if len(alert_keys) > 2:
            cols2 = st.columns(2)
            for i, alert_key in enumerate(alert_keys[2:4]):
                with cols2[i]:
                    alert = alerts_data[alert_key]
                    with stylable_container(
                        key=f"alert_{alert_key}_2",
                        css_styles=f"""
                        {{
                            background: white;
                            padding: 1.5rem;
                            border-radius: 12px;
                            border-left: 6px solid {alert['color']};
                            margin-bottom: 1rem;
                            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                        }}
                        """
                    ):
                        st.markdown(f"#### {alert['title']}")
                        st.metric("SKUs", f"{alert['count']:,}", alert['subtitle'])
                        
                        if alert['count'] > 0:
                            with st.expander("View SKUs"):
                                if 'sku_code' in alert['data'].columns:
                                    display_cols = ['sku_code', 'Product_Name', 'Brand']
                                    if 'Month_Cover' in alert['data'].columns:
                                        display_cols.append('Month_Cover')
                                    if 'L3M_Avg' in alert['data'].columns and 'Feb-26' in alert['data'].columns:
                                        display_cols.extend(['L3M_Avg', 'Feb-26'])
                                    if 'Stock_Qty' in alert['data'].columns:
                                        display_cols.append('Stock_Qty')
                                    
                                    st.dataframe(alert['data'][display_cols].head(10))
    else:
        st.info("No alert data available. Check if required columns exist in your data.")

# ============================================================================
# SIDEBAR CONFIGURATION
# ============================================================================
with st.sidebar:
    st.markdown("### ⚙️ Dashboard Settings")
    
    # Auto-refresh toggle
    auto_refresh = st.checkbox("🔄 Auto-refresh data", value=False)
    if auto_refresh:
        refresh_interval = st.slider("Refresh interval (minutes)", 1, 30, 5)
    
    # Theme selector
    theme = st.selectbox("🎨 Theme", ["Light", "Dark", "Auto"])
    
    # Data range
    st.markdown("---")
    st.markdown("### 📅 Data Range")
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("From", value=datetime(2025, 10, 1).date())
    with col2:
        end_date = st.date_input("To", value=datetime(2026, 4, 30).date())
    
    # Export options
    st.markdown("---")
    st.markdown("### 📤 Export Data")
    
    export_format = st.radio("Format", ["CSV", "Excel", "PDF"])
    
    if st.button("📥 Generate Export", use_container_width=True):
        st.success(f"Exporting data as {export_format}...")
    
    # Debug info
    st.markdown("---")
    with st.expander("🔧 Debug Info"):
        st.write(f"Data shape: {all_df.shape}")
        st.write(f"Columns: {list(all_df.columns)}")
        st.write(f"Adjustment months: {st.session_state.adjustment_months}")
        st.write(f"Has floor price: {st.session_state.has_floor_price}")

# ============================================================================
# MODERN FOOTER
# ============================================================================
st.markdown("---")
footer_cols = st.columns([2, 1, 1])

with footer_cols[0]:
    st.markdown(f"""
    <div style="color: #6B7280; font-size: 0.9rem;">
        <p>📊 <strong>ERHA S&OP Dashboard v2.0</strong></p>
        <p>For internal use only. Data loaded from Google Sheets.</p>
    </div>
    """, unsafe_allow_html=True)

with footer_cols[1]:
    st.markdown(f"""
    <div style="color: #6B7280; font-size: 0.9rem; text-align: center;">
        <p><strong>Meeting</strong></p>
        <p>{meeting_date}</p>
    </div>
    """, unsafe_allow_html=True)

with footer_cols[2]:
    st.markdown(f"""
    <div style="color: #6B7280; font-size: 0.9rem; text-align: center;">
        <p><strong>Last Updated</strong></p>
        <p>{datetime.now().strftime('%H:%M:%S')}</p>
    </div>
    """, unsafe_allow_html=True)

# ============================================================================
# DEPLOYMENT INSTRUCTIONS
# ============================================================================
with st.expander("🚀 Deployment Instructions", expanded=False):
    st.markdown("""
    ### **Deploy to Streamlit Cloud**
    
    1. **Push to GitHub:**
    ```bash
    git add .
    git commit -m "Add modern S&OP dashboard"
    git push origin main
    ```
    
    2. **Go to [share.streamlit.io](https://share.streamlit.io)**
    3. **Click "New app"** → Select repository
    4. **Set main file to:** `app.py`
    5. **Add secrets:** (in Streamlit Cloud dashboard)
    ```toml
    [gsheets]
    sheet_id = "your-sheet-id"
    service_account_info = '{"type": "service_account", ...}'
    ```
    
    ### **Requirements File**
    Create `requirements.txt`:
    ```txt
    streamlit>=1.28.0
    pandas>=2.0.0
    numpy>=1.24.0
    plotly>=5.17.0
    gspread>=5.11.0
    google-auth>=2.23.0
    streamlit-aggrid>=0.3.4
    streamlit-extras>=0.4.0
    streamlit-autorefresh>=0.1.4
    ```
    
    ### **Alternative Hosting:**
    - **Hugging Face Spaces:** Free, public only
    - **Render:** Free tier available
    - **Railway:** $5/month starter
    - **AWS EC2:** ~$10/month
    """)
