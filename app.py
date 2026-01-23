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
    
    /* Table Container dengan Frozen Header */
    .table-container {
        max-height: 500px;
        overflow-y: auto;
        overflow-x: auto;
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        margin: 15px 0;
        position: relative;
    }
    
    /* Fixed Header */
    .sticky-header {
        position: sticky;
        top: 0;
        z-index: 100;
        background-color: #1E3A8A !important;
    }
    
    .sticky-header th {
        position: sticky;
        top: 0;
        background-color: #1E3A8A !important;
        color: white !important;
        font-weight: 600;
        padding: 12px 8px !important;
        border-bottom: 2px solid #D1D5DB;
    }
    
    /* Table styling */
    .forecast-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.85em;
    }
    
    .forecast-table th, .forecast-table td {
        padding: 8px;
        text-align: left;
        border-bottom: 1px solid #E5E7EB;
        white-space: nowrap;
    }
    
    .forecast-table th {
        background-color: #1E3A8A;
        color: white;
        font-weight: 600;
    }
    
    .forecast-table tr:hover {
        background-color: #F3F4F6;
    }
    
    /* Conditional Formatting */
    .month-cover-high {
        background-color: #FCE7F3 !important;
        color: #BE185D !important;
        font-weight: 600 !important;
        border-left: 3px solid #BE185D !important;
    }
    
    .growth-low {
        background-color: #FFEDD5 !important;
        color: #9A3412 !important;
        font-weight: 600 !important;
        border-left: 3px solid #9A3412 !important;
    }
    
    .growth-high {
        background-color: #FEE2E2 !important;
        color: #991B1B !important;
        font-weight: 600 !important;
        border-left: 3px solid #991B1B !important;
    }
    
    /* Brand Colors */
    .brand-acneact { background-color: #E0F2FE !important; }
    .brand-age-corrector { background-color: #F0F9FF !important; }
    .brand-truwhite { background-color: #F0FDF4 !important; }
    .brand-erhair { background-color: #FEF3C7 !important; }
    .brand-hiserha { background-color: #FEF7CD !important; }
    .brand-perfect-shield { background-color: #FCE7F3 !important; }
    .brand-skinsitive { background-color: #F3E8FF !important; }
    
    /* Percentage styling */
    .percentage-cell {
        text-align: right !important;
        font-weight: 500 !important;
    }
    
    /* Consensus cell styling (editable) */
    .consensus-cell {
        background-color: #F0F9FF !important;
        border: 1px solid #3B82F6 !important;
        font-weight: 600 !important;
    }
    
    .consensus-cell:hover {
        background-color: #DBEAFE !important;
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
    
    /* Color Legend Styling */
    .color-legend {
        display: flex;
        gap: 1rem;
        margin: 1rem 0;
        padding: 0.75rem;
        background: #F9FAFB;
        border-radius: 8px;
        align-items: center;
        flex-wrap: wrap;
    }
    
    .legend-item {
        display: flex;
        align-items: center;
        gap: 4px;
    }
    
    .color-box {
        width: 16px;
        height: 16px;
        border-radius: 3px;
    }
    
    .legend-text {
        font-size: 0.8rem;
        font-weight: 500;
        color: #4B5563;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# AUTO-REFRESH (setiap 5 menit)
# ============================================================================
# Uncomment untuk auto-refresh
# st_autorefresh(interval=5 * 60 * 1000, key="data_refresh")

# ============================================================================
# GSHEET CONNECTOR CLASS
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

# ============================================================================
# DATA LOADER DENGAN GSHEETCONNECTOR
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
        
        # Gunakan GSheetConnector
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
        
        # Step 5: Process data
        status_text.text("⚙️ Processing data...")
        progress_bar.progress(90)
        
        # ===== PROSES DATA =====
        
        # 1. Get last 3 months sales (Oct, Nov, Dec 2025)
        sales_months = ['Oct-25', 'Nov-25', 'Dec-25']
        available_sales_months = [m for m in sales_months if m in sales_df.columns]
        
        if len(available_sales_months) < 3:
            st.warning(f"⚠️ Only {len(available_sales_months)} of last 3 months available")
        
        # Calculate L3M Average
        sales_df['L3M_Avg'] = sales_df[available_sales_months].mean(axis=1).round(0)
        
        # 2. Get ROFO months
        adjustment_months = ['Feb-26', 'Mar-26', 'Apr-26']
        all_rofo_months = adjustment_months
        available_rofo_months = [m for m in all_rofo_months if m in rofo_df.columns]
        
        # 3. Merge data
        sales_cols = ['sku_code', 'Product_Name', 'Brand_Group', 'Brand', 'SKU_Tier', 'L3M_Avg']
        sales_cols += available_sales_months
        sales_essential = sales_df[sales_cols].copy()
        
        rofo_cols = ['sku_code', 'Product_Name', 'Brand_Group', 'Brand', 'SKU_Tier']
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
        time.sleep(0.5)
        status_text.empty()
        progress_bar.empty()
        
        # Simpan informasi bulan ke session state
        st.session_state.adjustment_months = [m for m in adjustment_months if m in available_rofo_months]
        
        return merged_df
        
    except Exception as e:
        status_text.empty()
        progress_bar.empty()
        st.error(f"❌ Error loading data: {str(e)}")
        st.info("⚠️ Using demo data for now.")
        
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
    
    return df

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def calculate_percentage_columns(df):
    """Calculate percentage columns vs L3M Avg"""
    df_calc = df.copy()
    
    for month in st.session_state.adjustment_months:
        if month in df_calc.columns and 'L3M_Avg' in df_calc.columns:
            pct_col = f'{month}_%'
            # Calculate percentage
            df_calc[pct_col] = (df_calc[month] / df_calc['L3M_Avg'].replace(0, np.nan) * 100).round(1)
            # Replace inf and nan
            df_calc[pct_col] = df_calc[pct_col].replace([np.inf, -np.inf], 0).fillna(100)
    
    return df_calc

def create_html_table_with_frozen_header(df):
    """Create HTML table with frozen header and conditional formatting"""
    
    html = """
    <div class="table-container">
        <table class="forecast-table">
            <thead class="sticky-header">
                <tr>
    """
    
    # Header row
    for col in df.columns:
        display_name = col.replace('_', ' ').replace('-', ' ').replace('Cons ', 'Consensus ')
        html += f'<th>{display_name}</th>'
    
    html += '</tr></thead><tbody>'
    
    # Data rows dengan conditional formatting
    for idx, row in df.iterrows():
        html += '<tr>'
        
        for col in df.columns:
            value = row[col]
            cell_class = ''
            display_value = value
            
            # Format persentase
            if '_%' in col and isinstance(value, (int, float)):
                display_value = f"{value:.1f}%"
                cell_class += 'percentage-cell '
                
                # Conditional formatting untuk persentase
                if value < 90:
                    cell_class += 'growth-low '
                elif value > 130:
                    cell_class += 'growth-high '
            
            # Conditional formatting untuk Month_Cover
            elif col == 'Month_Cover' and isinstance(value, (int, float)):
                if value > 1.5:
                    cell_class += 'month-cover-high '
            
            # Brand coloring
            elif col == 'Brand' and isinstance(value, str):
                brand_lower = value.lower().replace(' ', '-').replace('_', '-')
                cell_class += f'brand-{brand_lower} '
            
            # Consensus cells styling
            elif col.startswith('Cons_'):
                cell_class += 'consensus-cell '
            
            html += f'<td class="{cell_class.strip()}">{display_value}</td>'
        
        html += '</tr>'
    
    html += '</tbody></table></div>'
    
    return html

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
# MEETING INFO BAR
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
# LOAD DATA
# ============================================================================
with st.spinner('🔄 Loading latest data from Google Sheets...'):
    all_df = load_all_data()

# Initialize session state for months if not exists
if 'adjustment_months' not in st.session_state:
    st.session_state.adjustment_months = ['Feb-26', 'Mar-26', 'Apr-26']

# ============================================================================
# QUICK METRICS OVERVIEW
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
# FILTER BAR
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
# TAB INTERFACE
# ============================================================================
tab1, tab2, tab3 = st.tabs(["📝 Input & Adjustment", "📊 Analytics Dashboard", "🎯 Focus Areas"])

# ============================================================================
# TAB 1: INPUT & ADJUSTMENT (WITH EDITABLE TABLE)
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
    
    # Display info
    st.info(f"📋 Showing **{len(filtered_df)}** SKUs out of **{len(all_df)}** total")
    
    # =================================================================
    # COLOR LEGEND
    # =================================================================
    st.markdown("""
    <div class="color-legend">
        <div class="legend-item">
            <div class="color-box" style="background-color: #FCE7F3; border-left: 3px solid #BE185D;"></div>
            <span class="legend-text">Month Cover > 1.5</span>
        </div>
        <div class="legend-item">
            <div class="color-box" style="background-color: #FFEDD5; border-left: 3px solid #9A3412;"></div>
            <span class="legend-text">Growth < 90%</span>
        </div>
        <div class="legend-item">
            <div class="color-box" style="background-color: #FEE2E2; border-left: 3px solid #991B1B;"></div>
            <span class="legend-text">Growth > 130%</span>
        </div>
        <div class="legend-item">
            <div class="color-box" style="background-color: #E0F2FE;"></div>
            <span class="legend-text">Acneact</span>
        </div>
        <div class="legend-item">
            <div class="color-box" style="background-color: #F0F9FF;"></div>
            <span class="legend-text">Age Corrector</span>
        </div>
        <div class="legend-item">
            <div class="color-box" style="background-color: #F0FDF4;"></div>
            <span class="legend-text">Truwhite</span>
        </div>
        <div class="legend-item">
            <div class="color-box" style="background-color: #FEF3C7;"></div>
            <span class="legend-text">ER Hair</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # =================================================================
    # STEP 1: DISPLAY TABLE DENGAN FROZEN HEADER
    # =================================================================
    st.markdown("#### 📋 Forecast Table (Read-only View)")
    st.markdown("*Scroll to see all data - Headers stay fixed at top*")
    
    # Prepare display dataframe dengan semua kolom yang diperlukan
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
    
    # Create display dataframe
    display_df = filtered_df[display_columns].copy()
    
    # Calculate percentage columns
    display_df = calculate_percentage_columns(display_df)
    
    # Add percentage columns to display
    for month in st.session_state.adjustment_months:
        pct_col = f'{month}_%'
        if pct_col in display_df.columns:
            display_columns.append(pct_col)
    
    # Add consensus columns
    consensus_cols = []
    for month in st.session_state.adjustment_months:
        cons_col = f'Cons_{month}'
        if cons_col in filtered_df.columns:
            display_df[cons_col] = filtered_df[cons_col]
            consensus_cols.append(cons_col)
        else:
            # Initialize consensus columns
            if month in filtered_df.columns:
                display_df[cons_col] = filtered_df[month]
                consensus_cols.append(cons_col)
    
    display_columns += consensus_cols
    
    # Reorder columns untuk display yang lebih baik
    final_display_cols = ['sku_code', 'Product_Name', 'Brand', 'SKU_Tier']
    final_display_cols += sales_cols
    final_display_cols += calc_cols
    final_display_cols += forecast_cols
    
    # Add percentage columns setelah forecast columns
    pct_cols_list = []
    for month in st.session_state.adjustment_months:
        pct_col = f'{month}_%'
        if pct_col in display_df.columns:
            pct_cols_list.append(pct_col)
    final_display_cols += pct_cols_list
    
    # Add consensus columns di akhir
    final_display_cols += consensus_cols
    
    display_df = display_df[final_display_cols]
    
    # Add row numbers
    display_df.insert(0, 'No.', range(1, len(display_df) + 1))
    
    # Display table dengan frozen header
    html_table = create_html_table_with_frozen_header(display_df)
    st.markdown(html_table, unsafe_allow_html=True)
    
    # =================================================================
    # STEP 2: EDITABLE CONSENSUS SECTION
    # =================================================================
    st.markdown("---")
    st.markdown("### ✏️ Edit Consensus Values")
    st.markdown("*Double-click cells below to edit consensus values*")
    
    # Prepare dataframe untuk editing consensus saja
    edit_consensus_df = display_df[['No.', 'sku_code', 'Product_Name', 'Brand', 'SKU_Tier', 'L3M_Avg']].copy()
    
    # Tambahkan consensus columns
    for month in st.session_state.adjustment_months:
        cons_col = f'Cons_{month}'
        if cons_col in display_df.columns:
            edit_consensus_df[cons_col] = display_df[cons_col]
    
    # Column configuration
    column_config = {
        'No.': st.column_config.Column("No.", disabled=True),
        'sku_code': st.column_config.TextColumn("SKU Code", disabled=True),
        'Product_Name': st.column_config.TextColumn("Product Name", disabled=True),
        'Brand': st.column_config.TextColumn("Brand", disabled=True),
        'SKU_Tier': st.column_config.TextColumn("SKU Tier", disabled=True),
        'L3M_Avg': st.column_config.NumberColumn("L3M Avg", format="%d", disabled=True),
    }
    
    # Add consensus columns config
    for month in st.session_state.adjustment_months:
        cons_col = f'Cons_{month}'
        if cons_col in edit_consensus_df.columns:
            column_config[cons_col] = st.column_config.NumberColumn(
                f"Consensus {month}",
                min_value=0,
                step=1,
                format="%d",
                help=f"Edit consensus value for {month}"
            )
    
    # Display data editor
    edited_df = st.data_editor(
        edit_consensus_df,
        column_config=column_config,
        use_container_width=True,
        height=400,
        key="consensus_editor_final",
        num_rows="fixed"
    )
    
    # =================================================================
    # STEP 3: SAVE & ACTIONS
    # =================================================================
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("💾 Save Consensus Values", type="primary", use_container_width=True):
            # Simpan ke session state
            st.session_state.edited_consensus = edited_df.copy()
            
            # Hitung perubahan
            changes = []
            for month in st.session_state.adjustment_months:
                cons_col = f'Cons_{month}'
                if cons_col in edited_df.columns:
                    original_total = display_df[cons_col].sum()
                    new_total = edited_df[cons_col].sum()
                    change = new_total - original_total
                    change_pct = (change / original_total * 100) if original_total > 0 else 0
                    
                    changes.append({
                        'Month': month,
                        'Original': f"{original_total:,.0f}",
                        'New': f"{new_total:,.0f}",
                        'Change': f"{change:+,.0f}",
                        'Change %': f"{change_pct:+.1f}%"
                    })
            
            st.session_state.consensus_changes = changes
            st.success("✅ Consensus values saved!")
            
            # Tampilkan summary
            if changes:
                with st.expander("📊 View Changes Summary", expanded=True):
                    changes_df = pd.DataFrame(changes)
                    st.dataframe(changes_df, use_container_width=True, hide_index=True)
                    
                    # Total changes
                    total_change = sum([c['Change'] for c in changes])
                    st.metric("Total Change", f"{total_change:+,.0f} units")
    
    with col2:
        if st.button("📊 Compare with Original", use_container_width=True):
            if 'consensus_changes' in st.session_state:
                changes_df = pd.DataFrame(st.session_state.consensus_changes)
                
                # Create comparison chart
                fig = px.bar(
                    changes_df,
                    x='Month',
                    y='Change',
                    title="Changes vs Original Forecast",
                    color='Change',
                    color_continuous_scale='RdYlGn',
                    text='Change'
                )
                
                fig.update_layout(
                    height=300,
                    showlegend=False,
                    yaxis_title="Change (units)"
                )
                
                fig.update_traces(texttemplate='%{text:+,}', textposition='outside')
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("No changes saved yet. Save consensus values first.")
    
    with col3:
        if st.button("🔄 Reset to Original", type="secondary", use_container_width=True):
            if 'edited_consensus' in st.session_state:
                del st.session_state.edited_consensus
            if 'consensus_changes' in st.session_state:
                del st.session_state.consensus_changes
            st.rerun()
    
    # =================================================================
    # STEP 4: DOWNLOAD OPTIONS
    # =================================================================
    st.markdown("---")
    st.markdown("### 📤 Export Options")
    
    col_d1, col_d2, col_d3 = st.columns(3)
    
    with col_d1:
        if st.button("⬇️ Download Current View", use_container_width=True):
            csv = display_df.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"forecast_view_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
    
    with col_d2:
        if st.button("⬇️ Download Consensus Only", use_container_width=True):
            if 'edited_consensus' in st.session_state:
                csv = st.session_state.edited_consensus.to_csv(index=False)
                st.download_button(
                    label="📥 Download CSV",
                    data=csv,
                    file_name=f"consensus_values_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                csv = edited_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download CSV",
                    data=csv,
                    file_name=f"consensus_values_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
    
    with col_d3:
        if st.button("⬇️ Download Full Data", use_container_width=True):
            csv = all_df.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"full_data_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )

# ============================================================================
# TAB 2: ANALYTICS DASHBOARD
# ============================================================================
with tab2:
    st.markdown("### 📈 Consensus Results & Projections")
    
    # Gunakan edited consensus data jika ada
    results_df = all_df.copy()
    
    if 'edited_consensus' in st.session_state:
        consensus_df = st.session_state.edited_consensus.copy()
        
        # Map consensus values back ke full dataset
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
    if 'consensus_changes' in st.session_state:
        st.markdown("---")
        st.markdown("#### 📝 Consensus Changes Summary")
        
        changes_df = pd.DataFrame(st.session_state.consensus_changes)
        
        # Format untuk display
        display_changes = changes_df.copy()
        display_changes['Original'] = display_changes['Original']
        display_changes['New'] = display_changes['New']
        display_changes['Change'] = display_changes['Change']
        display_changes['Change %'] = display_changes['Change %']
        
        # Display
        st.dataframe(display_changes[['Month', 'Original', 'New', 'Change', 'Change %']].rename(
            columns={'Month': 'Month'}
        ), use_container_width=True, hide_index=True)
    
    # =================================================================
    # MONTHLY SUMMARY TABLE
    # =================================================================
    st.markdown("---")
    st.markdown("#### 📈 Monthly Volume Summary")
    
    # Prepare monthly summary data
    summary_data = []
    
    # Include semua bulan: adjustment
    all_display_months = [f'Cons_{m}' for m in st.session_state.adjustment_months]
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

# ============================================================================
# TAB 3: FOCUS AREAS
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
        low_growth_mask = (all_df['Feb-26'] / all_df['L3M_Avg'].replace(0, np.nan) * 100) < 90
        low_growth_skus = all_df[low_growth_mask].sort_values('L3M_Avg')
        alerts_data['low_growth'] = {
            'count': len(low_growth_skus),
            'data': low_growth_skus,
            'title': '📉 Low Growth SKUs',
            'subtitle': '<90% growth',
            'color': '#F59E0B'
        }
        
        high_growth_mask = (all_df['Feb-26'] / all_df['L3M_Avg'].replace(0, np.nan) * 100) > 130
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
        st.info("No alert data available.")

# ============================================================================
# FOOTER
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
