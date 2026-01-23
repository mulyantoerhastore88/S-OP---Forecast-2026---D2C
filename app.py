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
    
    /* Scrollable Table Container */
    .table-container {
        max-height: 600px;
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
    .brand-erha-others { background-color: #F5F5F5 !important; }
    
    /* Percentage styling */
    .percentage-cell {
        text-align: right !important;
        font-weight: 500 !important;
    }
    
    /* Consensus cell styling (editable) */
    .consensus-cell-editable {
        background-color: #F0F9FF !important;
        border: 1px solid #3B82F6 !important;
        font-weight: 600 !important;
    }
    
    .consensus-cell-editable:hover {
        background-color: #DBEAFE !important;
        cursor: pointer;
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
    
    /* Data Editor Custom Styling */
    div[data-testid="stDataEditor"] {
        border-radius: 8px;
        border: 1px solid #E5E7EB;
    }
    
    /* Focus on editable cells */
    div[data-testid="stEditableColumn"] {
        background-color: #F0F9FF !important;
    }
    
    div[data-testid="stEditableColumn"]:focus {
        outline: 2px solid #3B82F6 !important;
        outline-offset: -2px;
    }
    
    /* Responsive */
    @media (max-width: 768px) {
        .main-title { font-size: 2rem; }
        .table-container { max-height: 400px; }
    }
</style>
""", unsafe_allow_html=True)

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

# ============================================================================
# DATA LOADER DENGAN GSHEETCONNECTOR
# ============================================================================
@st.cache_data(ttl=300, show_spinner=False)
def load_all_data():
    """Load and process all required data dari Google Sheets"""
    
    try:
        # Gunakan GSheetConnector
        gs = GSheetConnector()
        
        # Load sales history
        sales_df = gs.get_sheet_data("sales_history")
        
        if sales_df.empty:
            st.error("❌ No sales history data found")
            return pd.DataFrame()
        
        # Load ROFO current
        rofo_df = gs.get_sheet_data("rofo_current")
        
        if rofo_df.empty:
            st.error("❌ No ROFO forecast data found")
            return pd.DataFrame()
        
        # Load stock data
        stock_df = gs.get_sheet_data("stock_onhand")
        
        # ===== PROSES DATA =====
        
        # 1. Get last 3 months sales
        sales_months = ['Oct-25', 'Nov-25', 'Dec-25']
        available_sales_months = [m for m in sales_months if m in sales_df.columns]
        
        if len(available_sales_months) < 3:
            st.warning(f"⚠️ Only {len(available_sales_months)} of last 3 months available")
        
        # Calculate L3M Average
        sales_df['L3M_Avg'] = sales_df[available_sales_months].mean(axis=1).round(0)
        
        # 2. Get ROFO months
        adjustment_months = ['Feb-26', 'Mar-26', 'Apr-26']
        available_rofo_months = [m for m in adjustment_months if m in rofo_df.columns]
        
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
        
        # Simpan informasi bulan ke session state
        st.session_state.adjustment_months = [m for m in adjustment_months if m in available_rofo_months]
        
        return merged_df
        
    except Exception as e:
        st.error(f"❌ Error loading data: {str(e)}")
        st.info("⚠️ Using demo data for now.")
        
        # Fallback ke data dummy
        return create_demo_data()

def create_demo_data():
    """Create demo data if Google Sheets fails"""
    
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

def create_styled_html_table(df, editable_consensus=False):
    """Create HTML table with styling from dataframe"""
    
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
            if '_%' in col:
                try:
                    # Extract numeric value untuk conditional formatting
                    if isinstance(value, str) and '%' in value:
                        num_value = float(value.replace('%', ''))
                    else:
                        num_value = float(value)
                    
                    display_value = f"{num_value:.1f}%" if isinstance(num_value, (int, float)) else value
                    cell_class += 'percentage-cell '
                    
                    if num_value < 90:
                        cell_class += 'growth-low '
                    elif num_value > 130:
                        cell_class += 'growth-high '
                except:
                    pass
            
            # Conditional formatting untuk Month_Cover
            elif col == 'Month_Cover':
                try:
                    num_value = float(value)
                    if num_value > 1.5:
                        cell_class += 'month-cover-high '
                    display_value = f"{num_value:.1f}"
                except:
                    pass
            
            # Brand coloring
            elif col == 'Brand':
                if isinstance(value, str):
                    brand_lower = value.lower().replace(' ', '-').replace('_', '-')
                    cell_class += f'brand-{brand_lower} '
            
            # Consensus cells styling jika editable
            elif col.startswith('Cons_') and editable_consensus:
                cell_class += 'consensus-cell-editable '
            
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
# TAB 1: INPUT & ADJUSTMENT (DIRECT EDITABLE TABLE)
# ============================================================================
with tab1:
    st.markdown("### 🎯 Interactive Forecast Adjustment")
    st.markdown("*Edit consensus values directly in the table below*")
    
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
    # PREPARE DATA FOR EDITABLE TABLE
    # =================================================================
    
    # Buat dataframe untuk editing
    edit_df = filtered_df.copy()
    
    # Tambahkan row numbers
    edit_df.insert(0, 'No.', range(1, len(edit_df) + 1))
    
    # Hitung percentage columns
    edit_df = calculate_percentage_columns(edit_df)
    
    # Pilih kolom untuk ditampilkan (dalam urutan yang logis)
    display_cols = ['No.', 'sku_code', 'Product_Name', 'Brand', 'SKU_Tier']
    
    # Tambahkan sales months
    sales_cols = [col for col in ['Oct-25', 'Nov-25', 'Dec-25'] if col in edit_df.columns]
    display_cols.extend(sales_cols)
    
    # Tambahkan calculated columns
    calc_cols = ['L3M_Avg', 'Stock_Qty', 'Month_Cover']
    display_cols.extend([col for col in calc_cols if col in edit_df.columns])
    
    # Tambahkan original forecast columns (read-only)
    for month in st.session_state.adjustment_months:
        if month in edit_df.columns:
            display_cols.append(month)
    
    # Tambahkan percentage columns (read-only)
    for month in st.session_state.adjustment_months:
        pct_col = f'{month}_%'
        if pct_col in edit_df.columns:
            display_cols.append(pct_col)
    
    # Tambahkan consensus columns (EDITABLE - inilah yang penting!)
    consensus_cols = []
    for month in st.session_state.adjustment_months:
        cons_col = f'Cons_{month}'
        if cons_col not in edit_df.columns:
            # Initialize jika belum ada
            edit_df[cons_col] = edit_df[month] if month in edit_df.columns else 0
        consensus_cols.append(cons_col)
        display_cols.append(cons_col)
    
    # =================================================================
    # COLUMN CONFIGURATION FOR DATA EDITOR
    # =================================================================
    
    column_config = {}
    
    # Read-only columns (semua kecuali consensus)
    readonly_cols = ['No.', 'sku_code', 'Product_Name', 'Brand', 'SKU_Tier']
    readonly_cols.extend(sales_cols)
    readonly_cols.extend([col for col in calc_cols if col in edit_df.columns])
    readonly_cols.extend(st.session_state.adjustment_months)  # Original forecast
    
    # Tambahkan percentage columns ke readonly
    for month in st.session_state.adjustment_months:
        pct_col = f'{month}_%'
        if pct_col in edit_df.columns:
            readonly_cols.append(pct_col)
    
    for col in readonly_cols:
        if col in display_cols:
            display_name = col.replace('_', ' ').replace('-', ' ')
            
            # Special handling untuk percentage columns
            if '_%' in col:
                column_config[col] = st.column_config.NumberColumn(
                    display_name,
                    format="%.1f%%",
                    disabled=True
                )
            # Special handling untuk Month_Cover
            elif col == 'Month_Cover':
                column_config[col] = st.column_config.NumberColumn(
                    display_name,
                    format="%.1f",
                    disabled=True
                )
            # Special handling untuk numeric columns
            elif col in ['L3M_Avg', 'Stock_Qty'] + sales_cols + st.session_state.adjustment_months:
                column_config[col] = st.column_config.NumberColumn(
                    display_name,
                    format="%d",
                    disabled=True
                )
            # Untuk text columns
            else:
                column_config[col] = st.column_config.Column(
                    display_name,
                    disabled=True
                )
    
    # Editable consensus columns
    for month in st.session_state.adjustment_months:
        cons_col = f'Cons_{month}'
        column_config[cons_col] = st.column_config.NumberColumn(
            f"Consensus {month}",
            min_value=0,
            step=1,
            format="%d",
            help=f"Double-click to edit consensus value for {month}"
        )
    
    # =================================================================
    # DISPLAY EDITABLE TABLE
    # =================================================================
    
    st.markdown("#### 📋 Edit Consensus Values in Table")
    st.markdown("*Double-click on any cell in the Consensus columns to edit*")
    
    # Display the data editor - INI TABEL UTAMA YANG BISA DIEDIT
    edited_df = st.data_editor(
        edit_df[display_cols],
        column_config=column_config,
        use_container_width=True,
        height=600,
        key="main_forecast_editor",
        num_rows="fixed",
        hide_index=True
    )
    
    # =================================================================
    # CALCULATE UPDATED PERCENTAGES
    # =================================================================
    
    # Update percentage columns berdasarkan edited consensus values
    for month in st.session_state.adjustment_months:
        cons_col = f'Cons_{month}'
        pct_col = f'{month}_%'
        
        if cons_col in edited_df.columns and 'L3M_Avg' in edited_df.columns:
            edited_df[pct_col] = (edited_df[cons_col] / 
                                 edited_df['L3M_Avg'].replace(0, np.nan) * 100).round(1)
            edited_df[pct_col] = edited_df[pct_col].replace([np.inf, -np.inf], 0).fillna(100)
    
    # =================================================================
    # DISPLAY UPDATED VIEW (READ-ONLY)
    # =================================================================
    
    st.markdown("---")
    st.markdown("#### 📊 Updated View with Changes")
    
    # Buat formatted display untuk updated view
    display_view_df = edited_df.copy()
    
    # Format columns untuk display
    for month in st.session_state.adjustment_months:
        pct_col = f'{month}_%'
        if pct_col in display_view_df.columns:
            display_view_df[pct_col] = display_view_df[pct_col].apply(
                lambda x: f"{x:.1f}%" if pd.notnull(x) else "0.0%"
            )
    
    # Display dengan HTML styling
    html_table = create_styled_html_table(display_view_df, editable_consensus=False)
    st.markdown(html_table, unsafe_allow_html=True)
    
    # =================================================================
    # SAVE & ACTIONS
    # =================================================================
    
    st.markdown("---")
    st.markdown("### 💾 Save & Actions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("💾 Save All Changes", type="primary", use_container_width=True):
            # Simpan ke session state
            st.session_state.edited_forecast_data = edited_df.copy()
            
            # Calculate changes vs original
            changes_summary = []
            for month in st.session_state.adjustment_months:
                cons_col = f'Cons_{month}'
                if cons_col in edited_df.columns and cons_col in edit_df.columns:
                    original_total = edit_df[cons_col].sum()
                    new_total = edited_df[cons_col].sum()
                    change = new_total - original_total
                    change_pct = (change / original_total * 100) if original_total > 0 else 0
                    
                    changes_summary.append({
                        'Month': month,
                        'Original': f"{original_total:,.0f}",
                        'New': f"{new_total:,.0f}",
                        'Change': f"{change:+,.0f}",
                        'Change %': f"{change_pct:+.1f}%"
                    })
            
            st.session_state.forecast_changes = changes_summary
            st.success("✅ All changes saved successfully!")
            
            # Show summary
            if changes_summary:
                with st.expander("📊 View Changes Summary", expanded=True):
                    changes_df = pd.DataFrame(changes_summary)
                    st.dataframe(changes_df, use_container_width=True, hide_index=True)
                    
                    # Total changes
                    total_change = sum([int(c['Change'].replace(',', '').replace('+', '')) for c in changes_summary])
                    st.metric("Total Change", f"{total_change:+,.0f} units")
    
    with col2:
        if st.button("📤 Export Edited Data", use_container_width=True):
            csv = edited_df.to_csv(index=False)
            st.download_button(
                label="⬇️ Download CSV",
                data=csv,
                file_name=f"edited_forecast_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                key="download_edited"
            )
    
    with col3:
        if st.button("🔄 Reset All Changes", type="secondary", use_container_width=True):
            if 'edited_forecast_data' in st.session_state:
                del st.session_state.edited_forecast_data
            if 'forecast_changes' in st.session_state:
                del st.session_state.forecast_changes
            st.rerun()
    
    # =================================================================
    # QUICK STATS AFTER EDITING
    # =================================================================
    
    st.markdown("---")
    st.markdown("#### 📈 Quick Stats After Editing")
    
    stats_cols = st.columns(len(st.session_state.adjustment_months) + 2)
    
    with stats_cols[0]:
        total_skus = len(edited_df)
        st.metric("Total SKUs", f"{total_skus:,}")
    
    with stats_cols[1]:
        if 'L3M_Avg' in edited_df.columns:
            l3m_avg = edited_df['L3M_Avg'].astype(float).mean()
            st.metric("Avg L3M Sales", f"{l3m_avg:,.0f}")
    
    # Stats per bulan
    for i, month in enumerate(st.session_state.adjustment_months):
        cons_col = f'Cons_{month}'
        if cons_col in edited_df.columns:
            with stats_cols[i+2]:
                month_total = edited_df[cons_col].astype(float).sum()
                if 'L3M_Avg' in edited_df.columns:
                    baseline_total = edited_df['L3M_Avg'].astype(float).sum() / 3
                    growth = ((month_total - baseline_total) / baseline_total * 100) if baseline_total > 0 else 0
                    st.metric(f"{month} Total", f"{month_total:,.0f}", f"{growth:+.1f}%")
                else:
                    st.metric(f"{month} Total", f"{month_total:,.0f}")

# ============================================================================
# TAB 2: ANALYTICS DASHBOARD
# ============================================================================
with tab2:
    st.markdown("### 📈 Consensus Results & Projections")
    
    # Gunakan edited consensus data jika ada
    results_df = all_df.copy()
    
    if 'edited_forecast_data' in st.session_state:
        # Map edited data back ke results_df
        edited_data = st.session_state.edited_forecast_data
        
        for month in st.session_state.adjustment_months:
            cons_col = f'Cons_{month}'
            if cons_col in edited_data.columns:
                # Create mapping dari sku_code ke consensus value
                consensus_map = dict(zip(edited_data['sku_code'], edited_data[cons_col]))
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
    
    # Show changes summary jika ada
    if 'forecast_changes' in st.session_state:
        st.markdown("---")
        st.markdown("#### 📝 Consensus Changes Summary")
        
        changes_df = pd.DataFrame(st.session_state.forecast_changes)
        
        # Display
        st.dataframe(changes_df[['Month', 'Original', 'New', 'Change', 'Change %']].rename(
            columns={'Month': 'Month'}
        ), use_container_width=True, hide_index=True)
    
    # =================================================================
    # VISUAL ANALYTICS
    # =================================================================
    st.markdown("---")
    st.markdown("### 📊 Visual Analytics")
    
    # Prepare data untuk charts
    chart_data = []
    
    # Actual sales data
    if 'L3M_Avg' in results_df.columns:
        chart_data.append({
            'Period': 'L3M Avg',
            'Value': results_df['L3M_Avg'].sum() / 3,  # Monthly average
            'Type': 'Actual'
        })
    
    # Consensus data
    for month in st.session_state.adjustment_months:
        cons_col = f'Cons_{month}'
        if cons_col in results_df.columns:
            chart_data.append({
                'Period': month,
                'Value': results_df[cons_col].sum(),
                'Type': 'Consensus'
            })
    
    if chart_data:
        chart_df = pd.DataFrame(chart_data)
        
        # Chart 1: Bar chart
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📈 Monthly Volume Comparison")
            
            fig = px.bar(
                chart_df,
                x='Period',
                y='Value',
                color='Type',
                title="Monthly Sales vs Consensus",
                color_discrete_map={'Actual': '#10B981', 'Consensus': '#3B82F6'}
            )
            
            fig.update_layout(
                height=400,
                showlegend=True,
                plot_bgcolor='white',
                yaxis=dict(
                    title="Volume (units)", 
                    gridcolor='#E5E7EB',
                    tickformat=',.0f'
                )
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.markdown("#### 📊 Brand Distribution")
            
            if 'Brand' in results_df.columns:
                # Aggregate by brand
                brand_data = []
                for brand in results_df['Brand'].unique():
                    brand_total = 0
                    for month in st.session_state.adjustment_months:
                        cons_col = f'Cons_{month}'
                        if cons_col in results_df.columns:
                            brand_total += results_df.loc[results_df['Brand'] == brand, cons_col].sum()
                    
                    brand_data.append({
                        'Brand': brand,
                        'Total': brand_total
                    })
                
                brand_df = pd.DataFrame(brand_data)
                brand_df = brand_df.sort_values('Total', ascending=False).head(10)
                
                fig = px.pie(
                    brand_df,
                    values='Total',
                    names='Brand',
                    title="Top 10 Brands by Consensus Volume",
                    hole=0.4
                )
                
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)

# ============================================================================
# TAB 3: FOCUS AREAS
# ============================================================================
with tab3:
    st.markdown("### 🎯 Focus Areas & Action Items")
    
    # Gunakan edited data jika ada
    focus_df = all_df.copy()
    
    if 'edited_forecast_data' in st.session_state:
        # Update dengan edited data
        edited_data = st.session_state.edited_forecast_data
        for month in st.session_state.adjustment_months:
            cons_col = f'Cons_{month}'
            if cons_col in edited_data.columns:
                focus_df[cons_col] = focus_df['sku_code'].map(
                    dict(zip(edited_data['sku_code'], edited_data[cons_col]))
                ).fillna(focus_df[month])
    
    # Generate alerts
    alerts_data = {}
    
    if 'Month_Cover' in focus_df.columns:
        high_cover_skus = focus_df[focus_df['Month_Cover'] > 1.5].sort_values('Month_Cover', ascending=False)
        alerts_data['high_cover'] = {
            'count': len(high_cover_skus),
            'data': high_cover_skus,
            'title': '⚠️ High Month Cover',
            'subtitle': 'Month Cover > 1.5',
            'color': '#EF4444'
        }
    
    if 'L3M_Avg' in focus_df.columns and 'Feb-26' in focus_df.columns:
        low_growth_mask = (focus_df['Feb-26'] / focus_df['L3M_Avg'].replace(0, np.nan) * 100) < 90
        low_growth_skus = focus_df[low_growth_mask].sort_values('L3M_Avg')
        alerts_data['low_growth'] = {
            'count': len(low_growth_skus),
            'data': low_growth_skus,
            'title': '📉 Low Growth SKUs',
            'subtitle': '<90% growth',
            'color': '#F59E0B'
        }
        
        high_growth_mask = (focus_df['Feb-26'] / focus_df['L3M_Avg'].replace(0, np.nan) * 100) > 130
        high_growth_skus = focus_df[high_growth_mask].sort_values('Feb-26', ascending=False)
        alerts_data['high_growth'] = {
            'count': len(high_growth_skus),
            'data': high_growth_skus,
            'title': '📈 High Growth SKUs',
            'subtitle': '>130% growth',
            'color': '#10B981'
        }
    
    if 'Stock_Qty' in focus_df.columns and 'L3M_Avg' in focus_df.columns:
        low_stock_skus = focus_df[focus_df['Stock_Qty'] < focus_df['L3M_Avg']].sort_values('Stock_Qty')
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

# ============================================================================
# SIDEBAR (OPTIONAL)
# ============================================================================
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    
    # Auto-refresh
    auto_refresh = st.checkbox("Auto-refresh data", value=False)
    
    # Data range
    st.markdown("---")
    st.markdown("#### 📅 Data Range")
    
    start_date = st.date_input("From", value=datetime(2025, 10, 1).date())
    end_date = st.date_input("To", value=datetime(2026, 4, 30).date())
    
    # Export options
    st.markdown("---")
    st.markdown("#### 📤 Quick Export")
    
    if st.button("Export Current View", use_container_width=True):
        st.info("Use the export buttons in Tab 1")
    
    # Debug info
    st.markdown("---")
    with st.expander("Debug Info"):
        st.write(f"Data shape: {all_df.shape}")
        st.write(f"SKUs loaded: {len(all_df)}")
        st.write(f"Adjustment months: {st.session_state.adjustment_months}")
