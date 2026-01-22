import streamlit as st
import pandas as pd
import numpy as np
import gspread
import plotly.graph_objects as go
import plotly.express as px
from google.oauth2.service_account import Credentials
import json
from datetime import datetime

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================
st.set_page_config(
    page_title="ERHA S&OP 3-Month Consensus Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================================
# CUSTOM CSS
# ============================================================================
st.markdown("""
<style>
    /* Main Title */
    .main-title {
        font-size: 2.8rem;
        background: linear-gradient(90deg, #1E3A8A 0%, #3B82F6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0.5rem;
        font-weight: 800;
        letter-spacing: -0.5px;
    }
    
    /* Sub Title */
    .sub-title {
        font-size: 1.3rem;
        color: #6B7280;
        text-align: center;
        margin-bottom: 2rem;
        font-weight: 400;
    }
    
    /* Tab Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #F9FAFB;
        padding: 8px;
        border-radius: 10px;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #FFFFFF;
        border-radius: 8px;
        border: 1px solid #E5E7EB;
        font-weight: 600;
        padding: 10px 20px;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #3B82F6 !important;
        color: white !important;
        border-color: #3B82F6 !important;
    }
    
    /* Filter Section */
    .filter-section {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    .filter-label {
        color: white !important;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    
    /* Table Styling */
    .dataframe {
        width: 100%;
        border-collapse: collapse;
    }
    
    .dataframe th {
        background-color: #F3F4F6;
        font-weight: 600;
        padding: 12px;
        text-align: left;
        border-bottom: 2px solid #D1D5DB;
    }
    
    .dataframe td {
        padding: 10px 12px;
        border-bottom: 1px solid #E5E7EB;
    }
    
    .dataframe tr:hover {
        background-color: #F9FAFB;
    }
    
    /* Conditional Formatting Classes */
    .month-cover-high {
        background-color: #FCE7F3 !important;
        color: #BE185D !important;
        font-weight: 600;
        border-left: 3px solid #BE185D !important;
    }
    
    .growth-low {
        background-color: #FFEDD5 !important;
        color: #9A3412 !important;
        font-weight: 600;
        border-left: 3px solid #9A3412 !important;
    }
    
    .growth-high {
        background-color: #FEE2E2 !important;
        color: #991B1B !important;
        font-weight: 600;
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
    
    /* Button Styling */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s ease;
        border: 1px solid #3B82F6;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# HEADER
# ============================================================================
st.markdown('<p class="main-title">📊 ERHA S&OP 3-Month Consensus Dashboard</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Last 3M Sales vs ROFO Adjustment | Real-time Collaboration</p>', unsafe_allow_html=True)

# Meeting info bar
meeting_date = st.date_input("📅 Meeting Date", value=datetime.now().date(), key="meeting_date")

# ============================================================================
# GSHEET CONNECTOR
# ============================================================================
class GSheetConnector:
    def __init__(self):
        try:
            self.sheet_id = st.secrets["gsheets"]["sheet_id"]
            self.service_account_info = json.loads(st.secrets["gsheets"]["service_account_info"])
        except:
            st.error("GSheet credentials not found.")
            raise
        self.client = None
        self.connect()
    
    def connect(self):
        try:
            scope = ['https://www.googleapis.com/auth/spreadsheets']
            creds = Credentials.from_service_account_info(self.service_account_info, scopes=scope)
            self.client = gspread.authorize(creds)
            self.sheet = self.client.open_by_key(self.sheet_id)
        except Exception as e:
            st.error(f"Connection error: {str(e)}")
            raise
    
    def get_sheet_data(self, sheet_name):
        try:
            worksheet = self.sheet.worksheet(sheet_name)
            data = worksheet.get_all_records()
            return pd.DataFrame(data)
        except:
            return pd.DataFrame()

# ============================================================================
# DATA LOADING & PROCESSING
# ============================================================================
@st.cache_data(ttl=300)
def load_all_data():
    """Load and process all required data"""
    gs = GSheetConnector()
    
    # 1. Load sales history
    sales_df = gs.get_sheet_data("sales_history")
    if sales_df.empty:
        st.error("❌ No sales history data found")
        return None
    
    # 2. Load ROFO current with floor_price
    rofo_df = gs.get_sheet_data("rofo_current")
    if rofo_df.empty:
        st.error("❌ No ROFO data found")
        return None
    
    # 3. Load stock data
    stock_df = gs.get_sheet_data("stock_onhand")
    
    # 4. Get last 3 months sales (Oct, Nov, Dec 2025)
    sales_months = ['Oct-25', 'Nov-25', 'Dec-25']
    available_sales_months = [m for m in sales_months if m in sales_df.columns]
    
    if len(available_sales_months) < 3:
        st.warning(f"⚠️ Only {len(available_sales_months)} of last 3 months available")
    
    # Calculate L3M Average
    sales_df['L3M_Avg'] = sales_df[available_sales_months].mean(axis=1).round(0)
    
    # 5. Get ROFO months
    adjustment_months = ['Feb-26', 'Mar-26', 'Apr-26']
    projection_months = ['May-26', 'Jun-26', 'Jul-26', 'Aug-26', 'Sep-26', 
                         'Oct-26', 'Nov-26', 'Dec-26', 'Jan-27']
    
    all_rofo_months = adjustment_months + projection_months
    available_rofo_months = [m for m in all_rofo_months if m in rofo_df.columns]
    
    # 6. Merge data
    sales_cols = ['sku_code', 'Product_Name', 'Brand_Group', 'Brand', 'SKU_Tier', 'L3M_Avg']
    sales_cols += available_sales_months
    sales_essential = sales_df[sales_cols].copy()
    
    rofo_cols = ['sku_code', 'Product_Name', 'Brand_Group', 'Brand', 'SKU_Tier', 'floor_price']
    rofo_cols += [m for m in available_rofo_months if m in rofo_df.columns]
    rofo_essential = rofo_df[rofo_cols].copy()
    
    merged_df = pd.merge(
        sales_essential,
        rofo_essential,
        on=['sku_code', 'Product_Name', 'Brand_Group', 'Brand', 'SKU_Tier'],
        how='inner',
        suffixes=('_sales', '_rofo')
    )
    
    # Merge with stock
    if not stock_df.empty and 'sku_code' in stock_df.columns:
        merged_df = pd.merge(
            merged_df,
            stock_df[['sku_code', 'Stock_Qty']],
            on='sku_code',
            how='left'
        )
        merged_df['Stock_Qty'] = merged_df['Stock_Qty'].fillna(0)
    else:
        merged_df['Stock_Qty'] = 0
    
    # Calculate Month Cover
    merged_df['Month_Cover'] = (merged_df['Stock_Qty'] / merged_df['L3M_Avg'].replace(0, 1)).round(1)
    merged_df['Month_Cover'] = merged_df['Month_Cover'].replace([np.inf, -np.inf], 0)
    
    return {
        'data': merged_df,
        'sales_months': available_sales_months,
        'adjustment_months': [m for m in adjustment_months if m in available_rofo_months],
        'projection_months': [m for m in projection_months if m in available_rofo_months],
        'has_floor_price': 'floor_price' in merged_df.columns
    }

# Load ALL data (not filtered)
with st.spinner("📥 Loading data from Google Sheets..."):
    data_result = load_all_data()
    
if not data_result:
    st.stop()

all_df = data_result['data']  # Keep full dataset for Tab 2
adjustment_months = data_result['adjustment_months']
projection_months = data_result['projection_months']
has_floor_price = data_result['has_floor_price']

# ============================================================================
# FILTER SECTION (ONLY FOR TAB 1)
# ============================================================================
st.markdown("""
<div class="filter-section">
    <div style="display: flex; gap: 2rem; align-items: center;">
""", unsafe_allow_html=True)

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.markdown('<p class="filter-label">Brand Group</p>', unsafe_allow_html=True)
    brand_groups = ["ALL"] + sorted(all_df['Brand_Group'].dropna().unique().tolist())
    selected_brand_group = st.selectbox("", brand_groups, key="filter_brand_group", label_visibility="collapsed")

with col2:
    st.markdown('<p class="filter-label">Brand</p>', unsafe_allow_html=True)
    brands = ["ALL"] + sorted(all_df['Brand'].dropna().unique().tolist())
    selected_brand = st.selectbox("", brands, key="filter_brand", label_visibility="collapsed")

with col3:
    st.markdown('<p class="filter-label">SKU Tier</p>', unsafe_allow_html=True)
    sku_tiers = ["ALL"] + sorted(all_df['SKU_Tier'].dropna().unique().tolist())
    selected_tier = st.selectbox("", sku_tiers, key="filter_tier", label_visibility="collapsed")

with col4:
    st.markdown('<p class="filter-label">Month Cover</p>', unsafe_allow_html=True)
    month_cover_filter = st.selectbox(
        "", 
        ["ALL", "< 1.5 months", "1.5 - 3 months", "> 3 months"],
        key="filter_month_cover",
        label_visibility="collapsed"
    )

with col5:
    st.markdown('<p class="filter-label">&nbsp;</p>', unsafe_allow_html=True)
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.markdown("</div></div>", unsafe_allow_html=True)

# Apply filters for Tab 1 only
filtered_df = all_df.copy()
if selected_brand_group != "ALL":
    filtered_df = filtered_df[filtered_df['Brand_Group'] == selected_brand_group]
if selected_brand != "ALL":
    filtered_df = filtered_df[filtered_df['Brand'] == selected_brand]
if selected_tier != "ALL":
    filtered_df = filtered_df[filtered_df['SKU_Tier'] == selected_tier]

if month_cover_filter != "ALL":
    if month_cover_filter == "< 1.5 months":
        filtered_df = filtered_df[filtered_df['Month_Cover'] < 1.5]
    elif month_cover_filter == "1.5 - 3 months":
        filtered_df = filtered_df[(filtered_df['Month_Cover'] >= 1.5) & (filtered_df['Month_Cover'] <= 3)]
    elif month_cover_filter == "> 3 months":
        filtered_df = filtered_df[filtered_df['Month_Cover'] > 3]

# ============================================================================
# TAB INTERFACE
# ============================================================================
tab1, tab2 = st.tabs(["📝 Input & Adjustment", "📊 Results & Analytics"])

# ============================================================================
# TAB 1: INPUT TABLE (WITH CONDITIONAL FORMATTING)
# ============================================================================
with tab1:
    st.markdown("### 🎯 3-Month Forecast Adjustment")
    
    # Summary metrics untuk Tab 1
    metric_cols = st.columns(5)
    with metric_cols[0]:
        total_skus = len(filtered_df)
        st.metric("SKUs in View", f"{total_skus:,}")
    with metric_cols[1]:
        avg_l3m = filtered_df['L3M_Avg'].mean()
        st.metric("Avg L3M Sales", f"{avg_l3m:,.0f}")
    with metric_cols[2]:
        total_stock = filtered_df['Stock_Qty'].sum()
        st.metric("Total Stock", f"{total_stock:,}")
    with metric_cols[3]:
        avg_month_cover = filtered_df['Month_Cover'].mean()
        st.metric("Avg Month Cover", f"{avg_month_cover:.1f}")
    with metric_cols[4]:
        if adjustment_months:
            month = adjustment_months[0]
            avg_growth = ((filtered_df[month].mean() - filtered_df['L3M_Avg'].mean()) / 
                         filtered_df['L3M_Avg'].mean() * 100).round(1)
            st.metric(f"Avg {month} Growth", f"{avg_growth:+.1f}%")
    
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
    
    # Prepare dataframe for editing
    editor_df = filtered_df.copy()
    
    # Add percentage columns for ROFO vs L3M
    for month in adjustment_months:
        if month in editor_df.columns:
            # Calculate % vs L3M (as PERCENTAGE)
            pct_col = f"{month}_%"
            editor_df[pct_col] = (editor_df[month] / editor_df['L3M_Avg'].replace(0, 1) * 100).round(1)
            
            # Add consensus columns (initially same as ROFO)
            cons_col = f"Cons_{month}"
            editor_df[cons_col] = editor_df[month]
    
    # Create display dataframe
    display_cols = ['sku_code', 'Product_Name', 'Brand', 'SKU_Tier']
    
    # Add sales months
    sales_months = ['Oct-25', 'Nov-25', 'Dec-25']
    display_cols += [m for m in sales_months if m in editor_df.columns]
    
    # Add calculated columns
    display_cols += ['L3M_Avg', 'Stock_Qty', 'Month_Cover']
    
    # Add ROFO months and their %
    for month in adjustment_months:
        if month in editor_df.columns:
            display_cols.append(month)
            display_cols.append(f"{month}_%")
    
    # Add consensus columns
    for month in adjustment_months:
        cons_col = f"Cons_{month}"
        if cons_col in editor_df.columns:
            display_cols.append(cons_col)
    
    # Create display dataframe
    display_df = editor_df[display_cols].copy()
    
    # Add row numbers
    display_df.insert(0, 'No.', range(1, len(display_df) + 1))
    
    # =================================================================
    # CREATE STYLED TABLE DENGAN CONDITIONAL FORMATTING
    # =================================================================
    
    # Fungsi untuk apply styling
    def style_dataframe(df):
        # Convert to HTML dengan styling
        html = '<table class="dataframe"><thead><tr>'
        
        # Header
        for col in df.columns:
            html += f'<th>{col}</th>'
        html += '</tr></thead><tbody>'
        
        # Rows dengan conditional formatting
        for idx, row in df.iterrows():
            html += '<tr>'
            
            for col_idx, col_name in enumerate(df.columns):
                value = row[col_name]
                cell_class = ''
                
                # Apply conditional formatting
                if col_name == 'Month_Cover':
                    try:
                        if float(value) > 1.5:
                            cell_class = 'month-cover-high'
                    except:
                        pass
                
                elif '_%' in col_name:
                    try:
                        num_val = float(value)
                        if num_val < 90:
                            cell_class = 'growth-low'
                        elif num_val > 130:
                            cell_class = 'growth-high'
                    except:
                        pass
                
                elif col_name == 'Brand':
                    brand_lower = str(value).lower().replace(' ', '-')
                    cell_class = f'brand-{brand_lower}'
                
                html += f'<td class="{cell_class}">{value}</td>'
            
            html += '</tr>'
        
        html += '</tbody></table>'
        return html
    
    # Display the styled table
    st.markdown("#### 📋 Current Forecast (Read-only View)")
    
    # Limit rows untuk performance
    display_limit = 100
    if len(display_df) > display_limit:
        st.warning(f"Showing first {display_limit} of {len(display_df)} rows. Use filters to narrow down.")
        display_sample = display_df.head(display_limit)
    else:
        display_sample = display_df
    
    # Display styled table
    st.markdown(style_dataframe(display_sample), unsafe_allow_html=True)
    
    # =================================================================
    # EDITABLE CONSENSUS SECTION
    # =================================================================
    st.markdown("---")
    st.markdown("### ✏️ Edit Consensus Values")
    
    # Create editable dataframe hanya untuk consensus columns
    editable_cols = ['No.', 'sku_code', 'Product_Name', 'Brand', 'SKU_Tier', 'L3M_Avg']
    
    # Add consensus columns
    for month in adjustment_months:
        cons_col = f"Cons_{month}"
        if cons_col in editor_df.columns:
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
    for month in adjustment_months:
        cons_col = f"Cons_{month}"
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
                for month in adjustment_months:
                    cons_col = f"Cons_{month}"
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
# TAB 2: RESULTS & ANALYTICS (FULL DATASET)
# ============================================================================
with tab2:
    st.markdown("### 📈 Consensus Results & Projections")
    
    # Use edited consensus data if available
    if 'consensus_data' in st.session_state:
        consensus_df = st.session_state.consensus_data.copy()
        
        # Map consensus values back to full dataset
        for month in adjustment_months:
            cons_col = f"Cons_{month}"
            if cons_col in consensus_df.columns:
                # Create mapping dari sku_code ke consensus value
                consensus_map = dict(zip(consensus_df['sku_code'], consensus_df[cons_col]))
                all_df[cons_col] = all_df['sku_code'].map(consensus_map).fillna(all_df[month])
    else:
        # Initialize consensus columns as same as ROFO
        for month in adjustment_months:
            cons_col = f"Cons_{month}"
            all_df[cons_col] = all_df[month]
    
    # Use FULL dataset untuk analytics
    results_df = all_df.copy()
    
    # Summary untuk Tab 2 (FULL dataset)
    st.markdown("#### 📊 Overall Summary")
    metric_cols2 = st.columns(4)
    
    with metric_cols2[0]:
        total_all_skus = len(results_df)
        st.metric("Total SKUs", f"{total_all_skus:,}")
    
    with metric_cols2[1]:
        total_all_l3m = results_df['L3M_Avg'].sum()
        st.metric("Total L3M Sales", f"{total_all_l3m:,.0f}")
    
    with metric_cols2[2]:
        total_all_stock = results_df['Stock_Qty'].sum()
        st.metric("Total Stock", f"{total_all_stock:,}")
    
    with metric_cols2[3]:
        if adjustment_months:
            month = adjustment_months[0]
            total_consensus = results_df[f"Cons_{month}"].sum()
            total_baseline = results_df['L3M_Avg'].sum()
            total_growth = ((total_consensus - total_baseline) / total_baseline * 100).round(1)
            st.metric(f"Total {month} Growth", f"{total_growth:+.1f}%")
    
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
    st.markdown("#### 📈 Monthly Volume & Value Summary")
    
    # Prepare monthly summary data - SIMPAN DUA VERSI
    summary_data = []
    display_summary_data = []  # Untuk formatting
    
    # Include semua bulan: adjustment + projection
    all_display_months = [f"Cons_{m}" for m in adjustment_months] + projection_months
    all_display_months = [m for m in all_display_months if m in results_df.columns]
    
    for month in all_display_months:
        month_name = month.replace('Cons_', '')
        total_qty = results_df[month].sum()
        
        # Calculate value jika ada floor_price
        total_value = None
        if has_floor_price and 'floor_price' in results_df.columns:
            total_value = (results_df[month] * results_df['floor_price']).sum()
        
        # Calculate growth vs L3M untuk consensus months
        growth_pct = None
        if month.startswith('Cons_'):
            growth_pct = ((results_df[month].sum() - results_df['L3M_Avg'].sum()) / 
                         results_df['L3M_Avg'].sum() * 100).round(1)
        
        # Data untuk chart (numerik)
        summary_data.append({
            'Month': month_name,
            'Total Volume': total_qty,
            'Total Value (Rp)': total_value,
            'Growth vs L3M': growth_pct
        })
        
        # Data untuk display (diformat)
        display_row = {
            'Month': month_name,
            'Total Volume': f"{total_qty:,.0f}"
        }
        
        if has_floor_price and total_value is not None:
            display_row['Total Value (Rp)'] = f"Rp {total_value:,.0f}"
        else:
            display_row['Total Value (Rp)'] = "N/A"
        
        if growth_pct is not None:
            display_row['Growth vs L3M'] = f"{growth_pct:+.1f}%"
        else:
            display_row['Growth vs L3M'] = "N/A"
        
        display_summary_data.append(display_row)
    
    # Buat DataFrames terpisah
    summary_df = pd.DataFrame(summary_data)  # Untuk chart (numerik)
    display_summary_df = pd.DataFrame(display_summary_data)  # Untuk display (formatted)
    
    # Display summary table
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.dataframe(display_summary_df, use_container_width=True, hide_index=True)
    
    with col2:
        # Key metrics card
        st.markdown("#### 🎯 Key Metrics")
        
        # Calculate averages dari summary_df (yang numerik)
        growth_values = summary_df['Growth vs L3M'].dropna()
        if not growth_values.empty:
            avg_growth = growth_values.mean()
            st.metric("Avg Growth vs L3M", f"{avg_growth:+.1f}%")
        
        # Stock metrics
        high_cover_count = len(results_df[results_df['Month_Cover'] > 1.5])
        st.metric("SKUs with Month Cover > 1.5", f"{high_cover_count:,}")
        
        avg_month_cover_all = results_df['Month_Cover'].mean()
        st.metric("Overall Avg Month Cover", f"{avg_month_cover_all:.1f}")
        
        if has_floor_price:
            # Hitung total value dari 3 bulan adjustment
            adjustment_value = 0
            for month in adjustment_months:
                cons_col = f"Cons_{month}"
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
    if len(summary_df) > 0:
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            st.markdown("#### 📈 Monthly Volume Trend")
            
            # Buat DataFrame khusus untuk chart (tanpa formatting string)
            chart_data = []
            
            for idx, row in summary_df.iterrows():
                month_name = row['Month']
                total_volume = row['Total Volume']  # Masih numerik di sini
                
                # Determine type
                if month_name in [m.replace('Cons_', '') for m in adjustment_months]:
                    chart_type = 'Adjusted'
                elif month_name in projection_months:
                    chart_type = 'Projected'
                else:
                    chart_type = 'Other'
                
                chart_data.append({
                    'Month': month_name,
                    'Volume': total_volume,
                    'Type': chart_type
                })
            
            chart_df = pd.DataFrame(chart_data)
            
            # Debug info (bisa di-remove nanti)
            # st.write("Chart Data Preview:", chart_df.head())
            # st.write("Data types:", chart_df.dtypes)
            
            if not chart_df.empty:
                fig = px.line(
                    chart_df,
                    x='Month',
                    y='Volume',
                    color='Type',
                    markers=True,
                    line_shape='spline',
                    title="12-Month Forecast Volume Trend",
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
                        type='category'  # Pastikan bulan sebagai kategori
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
            st.markdown("#### 📊 Brand Contribution (Adjusted Months)")
            
            # Calculate brand totals untuk adjusted months
            brand_data = []
            for brand in results_df['Brand'].dropna().unique():
                brand_qty = 0
                for month in adjustment_months:
                    cons_col = f"Cons_{month}"
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
    
    # Chart 3: Value Contribution jika ada floor price
    if has_floor_price and len(summary_df) > 0:
        st.markdown("#### 💰 Monthly Value Contribution")
        
        # Filter hanya bulan yang ada value
        value_df = summary_df[summary_df['Total Value (Rp)'].notnull()].copy()
        
        if len(value_df) > 0:
            value_df['Value Numeric'] = value_df['Total Value (Rp)']
            value_df['Type'] = value_df['Month'].apply(
                lambda x: 'Adjusted' if x in [m.replace('Cons_', '') for m in adjustment_months] else 'Projected'
            )
            
            fig = px.bar(
                value_df,
                x='Month',
                y='Value Numeric',
                color='Type',
                title="Monthly Forecast Value",
                color_discrete_map={'Adjusted': '#3B82F6', 'Projected': '#10B981'}
            )
            
            fig.update_layout(
                height=400,
                showlegend=True,
                plot_bgcolor='white',
                yaxis=dict(
                    title="Value (Rp)",
                    tickprefix='Rp ',
                    tickformat=',.0f',
                    gridcolor='#E5E7EB'
                ),
                xaxis=dict(title="Month", tickangle=45, gridcolor='#E5E7EB')
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    # =================================================================
    # DETAILED DATA TABLE
    # =================================================================
    st.markdown("---")
    st.markdown("#### 📋 Detailed Consensus Data")
    
    # Prepare detailed view
    detailed_cols = ['sku_code', 'Product_Name', 'Brand', 'SKU_Tier', 'L3M_Avg', 'Month_Cover']
    
    # Add consensus columns
    for month in adjustment_months:
        cons_col = f"Cons_{month}"
        if cons_col in results_df.columns:
            detailed_cols.append(cons_col)
    
    # Add growth % columns
    for month in adjustment_months:
        cons_col = f"Cons_{month}"
        if cons_col in results_df.columns:
            growth_col = f"Cons_{month}_Growth"
            results_df[growth_col] = (results_df[cons_col] / results_df['L3M_Avg'].replace(0, 1) * 100).round(1)
            detailed_cols.append(growth_col)
    
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
# FOOTER
# ============================================================================
st.markdown("---")
st.markdown(f"""
<div style="text-align: center; color: #6B7280; padding: 1rem;">
    <p style="margin-bottom: 0.5rem;">
        📊 <strong>ERHA S&OP Dashboard</strong> | Meeting: {meeting_date} | 
        Total SKUs: {len(all_df):,} | Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    </p>
    <p style="font-size: 0.9rem; margin-top: 0;">
        Tab 1: Filtered View with Conditional Formatting | Tab 2: Full Dataset Analytics | For internal S&OP meetings only
    </p>
</div>
""", unsafe_allow_html=True)
