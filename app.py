import streamlit as st
import pandas as pd
import numpy as np
import gspread
import plotly.graph_objects as go
import plotly.express as px
from google.oauth2.service_account import Credentials
import json
from datetime import datetime
from typing import Dict, List, Tuple

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
# CUSTOM CSS FOR PROFESSIONAL STYLING
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
    
    /* Metric Cards */
    .metric-card {
        background: white;
        padding: 1.2rem;
        border-radius: 12px;
        border: 1px solid #E5E7EB;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
    }
    
    .metric-card:hover {
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transform: translateY(-2px);
    }
    
    /* Warning Colors */
    .warning-pink {
        background-color: #FCE7F3 !important;  /* Light pink */
        color: #BE185D !important;
        font-weight: 600;
    }
    
    .warning-orange {
        background-color: #FFEDD5 !important;  /* Light orange */
        color: #9A3412 !important;
        font-weight: 600;
    }
    
    .warning-red {
        background-color: #FEE2E2 !important;  /* Light red */
        color: #991B1B !important;
        font-weight: 600;
    }
    
    /* Brand Colors */
    .brand-ACNEACT { background-color: #E0F2FE !important; }
    .brand-AGE_CORRECTOR { background-color: #F0F9FF !important; }
    .brand-TRUWHITE { background-color: #F0FDF4 !important; }
    .brand-ERHAIR { background-color: #FEF3C7 !important; }
    .brand-HISERHA { background-color: #FEF7CD !important; }
    .brand-PERFECT_SHIELD { background-color: #FCE7F3 !important; }
    .brand-SKINSITIVE { background-color: #F3E8FF !important; }
    .brand-ERHA_OTHERS { background-color: #F5F5F5 !important; }
    
    /* Data Table */
    .dataframe {
        font-size: 0.85rem;
        border-collapse: separate;
        border-spacing: 0;
    }
    
    .dataframe th {
        background-color: #1E3A8A !important;
        color: white !important;
        font-weight: 600;
        text-align: center !important;
        position: sticky;
        top: 0;
        z-index: 100;
    }
    
    .dataframe td {
        border-bottom: 1px solid #E5E7EB !important;
    }
    
    /* Button Styling */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
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
    
    /* Chart Container */
    .chart-container {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #E5E7EB;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        margin-bottom: 1.5rem;
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
    
    def update_sheet(self, sheet_name, df):
        try:
            worksheet = self.sheet.worksheet(sheet_name)
            worksheet.clear()
            
            data = [df.columns.values.tolist()] + df.values.tolist()
            worksheet.update(data, value_input_option='USER_ENTERED')
            return True
        except Exception as e:
            st.error(f"Error updating sheet {sheet_name}: {str(e)}")
            return False

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
    
    # 5. Get ROFO months (Feb-Apr 2026 for adjustment, May-Jan for projection)
    adjustment_months = ['Feb-26', 'Mar-26', 'Apr-26']
    projection_months = ['May-26', 'Jun-26', 'Jul-26', 'Aug-26', 'Sep-26', 
                         'Oct-26', 'Nov-26', 'Dec-26', 'Jan-27']
    
    all_rofo_months = adjustment_months + projection_months
    available_rofo_months = [m for m in all_rofo_months if m in rofo_df.columns]
    
    # 6. Merge data
    # Sales essential columns
    sales_cols = ['sku_code', 'Product_Name', 'Brand_Group', 'Brand', 'SKU_Tier', 'L3M_Avg']
    sales_cols += available_sales_months
    sales_essential = sales_df[sales_cols].copy()
    
    # ROFO essential columns
    rofo_cols = ['sku_code', 'Product_Name', 'Brand_Group', 'Brand', 'SKU_Tier', 'floor_price']
    rofo_cols += [m for m in available_rofo_months if m in rofo_df.columns]
    rofo_essential = rofo_df[rofo_cols].copy()
    
    # Merge
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
    merged_df['Month_Cover'] = (merged_df['Stock_Qty'] / merged_df['L3M_Avg']).round(1)
    merged_df['Month_Cover'] = merged_df['Month_Cover'].replace([np.inf, -np.inf], 0)
    
    return {
        'data': merged_df,
        'sales_months': available_sales_months,
        'adjustment_months': [m for m in adjustment_months if m in available_rofo_months],
        'projection_months': [m for m in projection_months if m in available_rofo_months],
        'has_floor_price': 'floor_price' in merged_df.columns
    }

# Load data
with st.spinner("📥 Loading data from Google Sheets..."):
    data_result = load_all_data()
    
if not data_result:
    st.stop()

df = data_result['data']
adjustment_months = data_result['adjustment_months']
projection_months = data_result['projection_months']
has_floor_price = data_result['has_floor_price']

st.success(f"✅ Loaded {len(df)} SKUs | Adjustment Months: {', '.join(adjustment_months)}")

# ============================================================================
# FILTER SECTION (TOP OF PAGE)
# ============================================================================
st.markdown("""
<div class="filter-section">
    <div style="display: flex; gap: 2rem; align-items: center;">
""", unsafe_allow_html=True)

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.markdown('<p class="filter-label">Brand Group</p>', unsafe_allow_html=True)
    brand_groups = ["ALL"] + sorted(df['Brand_Group'].dropna().unique().tolist())
    selected_brand_group = st.selectbox("", brand_groups, key="filter_brand_group", label_visibility="collapsed")

with col2:
    st.markdown('<p class="filter-label">Brand</p>', unsafe_allow_html=True)
    brands = ["ALL"] + sorted(df['Brand'].dropna().unique().tolist())
    selected_brand = st.selectbox("", brands, key="filter_brand", label_visibility="collapsed")

with col3:
    st.markdown('<p class="filter-label">SKU Tier</p>', unsafe_allow_html=True)
    sku_tiers = ["ALL"] + sorted(df['SKU_Tier'].dropna().unique().tolist())
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

# Apply filters
filtered_df = df.copy()
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
# SUMMARY METRICS
# ============================================================================
st.markdown("### 📊 Quick Summary")
metric_cols = st.columns(5)

with metric_cols[0]:
    total_skus = len(filtered_df)
    st.metric("Total SKUs", f"{total_skus:,}")

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

# ============================================================================
# TAB INTERFACE
# ============================================================================
tab1, tab2 = st.tabs(["📝 Input & Adjustment", "📊 Results & Analytics"])

# ============================================================================
# TAB 1: INPUT TABLE
# ============================================================================
with tab1:
    st.markdown("### 🎯 3-Month Forecast Adjustment")
    
    # Prepare dataframe for editing
    editor_df = filtered_df.copy()
    
    # Add percentage columns for ROFO vs L3M
    for month in adjustment_months:
        if month in editor_df.columns:
            # Calculate % vs L3M
            pct_col = f"{month}_%"
            editor_df[pct_col] = (editor_df[month] / editor_df['L3M_Avg'].replace(0, 1)).round(2)
            
            # Add consensus columns (initially same as ROFO)
            cons_col = f"Cons_{month}"
            editor_df[cons_col] = editor_df[month]
    
    # Create column order as requested
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
    
    # Define styling function
    def style_dataframe(df):
        """Apply custom styling to dataframe"""
        styles = []
        
        for idx, row in df.iterrows():
            row_styles = {}
            
            # 1. Color Brand column based on brand
            brand = str(row.get('Brand', ''))
            brand_class = f"brand-{brand.replace(' ', '_').replace('-', '_').upper()}"
            row_styles['Brand'] = f'background-color: var(--{brand_class});'
            
            # 2. Color Month_Cover if > 1.5
            month_cover = row.get('Month_Cover', 0)
            if pd.notna(month_cover) and month_cover > 1.5:
                row_styles['Month_Cover'] = 'warning-pink'
            
            # 3. Color percentage columns
            for month in adjustment_months:
                pct_col = f"{month}_%"
                if pct_col in row:
                    pct_val = row[pct_col]
                    if pd.notna(pct_val):
                        if pct_val < 0.9:  # Less than -10%
                            row_styles[pct_col] = 'warning-orange'
                        elif pct_val > 1.3:  # More than +30%
                            row_styles[pct_col] = 'warning-red'
            
            styles.append(row_styles)
        
        return pd.DataFrame(styles, index=df.index)
    
    # Apply initial styling
    styled_df = display_df.copy()
    
    # Display the dataframe with editing for consensus columns only
    st.markdown("""
    <div style="background: white; padding: 1rem; border-radius: 10px; border: 1px solid #E5E7EB; margin-bottom: 2rem;">
    <p style="color: #6B7280; margin-bottom: 1rem;">
    💡 <strong>Instructions:</strong> Edit only the <strong>Cons_</strong> columns. Other columns are read-only.
    Percentage warnings: <span style="color: #F59E0B;">Orange = < -10%</span>, 
    <span style="color: #EF4444;">Red = > +30%</span>,
    <span style="color: #EC4899;">Pink = Month Cover > 1.5</span>
    </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Create column configuration
    column_config = {}
    
    # Read-only columns
    read_only_cols = ['No.', 'sku_code', 'Product_Name', 'Brand', 'SKU_Tier'] + \
                     sales_months + ['L3M_Avg', 'Stock_Qty', 'Month_Cover'] + \
                     adjustment_months + [f"{m}_%" for m in adjustment_months]
    
    for col in read_only_cols:
        if col in styled_df.columns:
            column_config[col] = st.column_config.Column(
                col.replace('_', ' ').title(),
                disabled=True
            )
    
    # Editable consensus columns
    for month in adjustment_months:
        cons_col = f"Cons_{month}"
        if cons_col in styled_df.columns:
            column_config[cons_col] = st.column_config.NumberColumn(
                f"Cons {month}",
                min_value=0,
                step=1,
                format="%d",
                help=f"Final consensus for {month}"
            )
    
    # Display data editor
    edited_data = st.data_editor(
        styled_df.head(100),  # Limit for performance
        column_config=column_config,
        use_container_width=True,
        height=600,
        key="input_editor",
        use_container_width=True
    )
    
    # Save button
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col2:
        if st.button("💾 Save Adjustments", type="primary", use_container_width=True):
            # Process and save the adjustments
            with st.spinner("Saving adjustments..."):
                # Calculate changes
                changes = []
                for month in adjustment_months:
                    cons_col = f"Cons_{month}"
                    if cons_col in edited_data.columns:
                        total_change = (edited_data[cons_col] - edited_data[month]).sum()
                        changes.append(f"{month}: {total_change:+,.0f}")
                
                st.success(f"✅ Adjustments saved! Changes: {', '.join(changes)}")
    
    with col3:
        if st.button("📤 Export to Excel", use_container_width=True):
            # Create export dataframe
            export_df = edited_data.copy()
            st.download_button(
                label="⬇️ Download Excel",
                data=export_df.to_csv(index=False).encode('utf-8'),
                file_name=f"sop_adjustments_{meeting_date}.csv",
                mime="text/csv",
                use_container_width=True
            )

# ============================================================================
# TAB 2: RESULTS & ANALYTICS
# ============================================================================
with tab2:
    st.markdown("### 📈 Consensus Results & Projections")
    
    # Prepare results dataframe
    results_df = filtered_df.copy()
    
    # Get consensus values from edited data if available, else use original
    if 'input_editor' in st.session_state:
        edited_df = st.session_state.input_editor['edited_rows']
        # Apply edits to results_df
        for idx, edits in edited_df.items():
            for col, val in edits.items():
                if col in results_df.columns:
                    results_df.at[idx, col] = val
    else:
        # Initialize consensus columns as same as ROFO
        for month in adjustment_months:
            cons_col = f"Cons_{month}"
            results_df[cons_col] = results_df[month]
    
    # Create results display
    results_cols = [f"Cons_{m}" for m in adjustment_months] + projection_months
    
    # Add floor price if available
    if has_floor_price:
        results_cols.append('floor_price')
    
    results_display = results_df[['sku_code', 'Product_Name', 'Brand', 'SKU_Tier'] + 
                                 [c for c in results_cols if c in results_df.columns]].copy()
    
    # Calculate totals
    st.markdown("#### 📊 Volume Summary")
    
    summary_data = []
    all_months = [f"Cons_{m}" for m in adjustment_months] + projection_months
    all_months = [m for m in all_months if m in results_df.columns]
    
    for month in all_months:
        total_qty = results_df[month].sum()
        
        # Calculate value if floor_price exists
        total_value = None
        if has_floor_price:
            total_value = (results_df[month] * results_df['floor_price']).sum()
        
        # Calculate growth vs L3M for consensus months
        growth_pct = None
        if month.startswith('Cons_'):
            base_month = month.replace('Cons_', '')
            if base_month in results_df.columns:
                growth_pct = ((results_df[month].sum() - results_df['L3M_Avg'].sum()) / 
                             results_df['L3M_Avg'].sum() * 100).round(1)
        
        summary_data.append({
            'Month': month.replace('Cons_', ''),
            'Total Qty': f"{total_qty:,.0f}",
            'Total Value (Rp)': f"{total_value:,.0f}" if total_value else "N/A",
            'Growth vs L3M': f"{growth_pct:+.1f}%" if growth_pct else "N/A"
        })
    
    summary_df = pd.DataFrame(summary_data)
    
    # Display summary
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.dataframe(summary_df, use_container_width=True, hide_index=True)
    
    with col2:
        # Key metrics
        st.markdown("#### 📈 Key Metrics")
        
        if adjustment_months:
            # Average growth across adjustment months
            growth_vals = []
            for month in adjustment_months:
                cons_col = f"Cons_{month}"
                if cons_col in results_df.columns:
                    growth = ((results_df[cons_col].sum() - results_df['L3M_Avg'].sum()) / 
                             results_df['L3M_Avg'].sum() * 100).round(1)
                    growth_vals.append(growth)
            
            if growth_vals:
                avg_growth = np.mean(growth_vals)
                st.metric("Avg Consensus Growth", f"{avg_growth:+.1f}%")
            
            # Total value
            if has_floor_price:
                total_value_all = sum([
                    (results_df[f"Cons_{m}"] * results_df['floor_price']).sum() 
                    for m in adjustment_months if f"Cons_{m}" in results_df.columns
                ])
                st.metric("Total Value (Adj)", f"Rp {total_value_all:,.0f}")
    
    # ============================================================================
    # CHARTS SECTION
    # ============================================================================
    st.markdown("---")
    st.markdown("### 📊 Visual Analytics")
    
    # Chart 1: Monthly Volume Trend
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        st.markdown("#### 📈 Monthly Volume Trend")
        
        # Prepare data for line chart
        trend_data = []
        for month in all_months:
            total_qty = results_df[month].sum()
            trend_data.append({
                'Month': month.replace('Cons_', ''),
                'Volume': total_qty,
                'Type': 'Consensus' if month.startswith('Cons_') else 'Projection'
            })
        
        if trend_data:
            trend_df = pd.DataFrame(trend_data)
            
            fig = px.line(
                trend_df,
                x='Month',
                y='Volume',
                color='Type',
                markers=True,
                line_shape='spline',
                title="Monthly Forecast Volume",
                template='plotly_white'
            )
            
            fig.update_layout(
                height=400,
                hovermode='x unified',
                showlegend=True,
                plot_bgcolor='white',
                paper_bgcolor='white'
            )
            
            fig.update_traces(
                line=dict(width=3),
                marker=dict(size=8)
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    with chart_col2:
        st.markdown("#### 📊 Brand Contribution")
        
        # Calculate brand totals
        brand_totals = []
        for brand in results_df['Brand'].unique():
            brand_qty = results_df[results_df['Brand'] == brand][all_months].sum().sum()
            brand_totals.append({
                'Brand': brand,
                'Total Volume': brand_qty
            })
        
        if brand_totals:
            brand_df = pd.DataFrame(brand_totals)
            brand_df = brand_df.sort_values('Total Volume', ascending=True)
            
            fig = px.bar(
                brand_df,
                y='Brand',
                x='Total Volume',
                orientation='h',
                title="Total Volume by Brand",
                color='Total Volume',
                color_continuous_scale='Blues',
                template='plotly_white'
            )
            
            fig.update_layout(
                height=400,
                showlegend=False,
                plot_bgcolor='white',
                paper_bgcolor='white'
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    # Chart 3: Growth Distribution
    st.markdown("#### 📈 Growth Distribution vs L3M")
    
    # Calculate growth for each SKU
    growth_data = []
    for month in adjustment_months:
        cons_col = f"Cons_{month}"
        if cons_col in results_df.columns:
            for _, row in results_df.iterrows():
                if row['L3M_Avg'] > 0:
                    growth = (row[cons_col] - row['L3M_Avg']) / row['L3M_Avg'] * 100
                    growth_data.append({
                        'Month': month,
                        'SKU': row['Product_Name'][:20],
                        'Growth %': growth,
                        'Brand': row['Brand']
                    })
    
    if growth_data:
        growth_df = pd.DataFrame(growth_data)
        
        fig = px.box(
            growth_df,
            x='Month',
            y='Growth %',
            color='Brand',
            title="Growth Distribution by Brand",
            template='plotly_white',
            points="all"
        )
        
        fig.update_layout(
            height=400,
            showlegend=True,
            plot_bgcolor='white',
            paper_bgcolor='white'
        )
        
        # Add horizontal lines for thresholds
        fig.add_hline(y=-10, line_dash="dash", line_color="orange", annotation_text="-10%")
        fig.add_hline(y=30, line_dash="dash", line_color="red", annotation_text="+30%")
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Chart 4: Value Contribution
    if has_floor_price:
        st.markdown("#### 💰 Value Contribution by Month")
        
        value_data = []
        for month in all_months:
            month_value = (results_df[month] * results_df['floor_price']).sum()
            value_data.append({
                'Month': month.replace('Cons_', ''),
                'Value (Rp)': month_value,
                'Type': 'Consensus' if month.startswith('Cons_') else 'Projection'
            })
        
        if value_data:
            value_df = pd.DataFrame(value_data)
            
            fig = px.bar(
                value_df,
                x='Month',
                y='Value (Rp)',
                color='Type',
                title="Monthly Forecast Value",
                template='plotly_white'
            )
            
            fig.update_layout(
                height=400,
                showlegend=True,
                plot_bgcolor='white',
                paper_bgcolor='white',
                yaxis_tickprefix='Rp ',
                yaxis_tickformat=',.0f'
            )
            
            st.plotly_chart(fig, use_container_width=True)

# ============================================================================
# FOOTER
# ============================================================================
st.markdown("---")
st.markdown(f"""
<div style="text-align: center; color: #6B7280; padding: 1rem;">
    <p style="margin-bottom: 0.5rem;">
        📊 <strong>ERHA S&OP Dashboard</strong> | Meeting: {meeting_date} | 
        SKUs: {total_skus:,} | Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    </p>
    <p style="font-size: 0.9rem; margin-top: 0;">
        For internal S&OP meetings only | Version 2.0 | Powered by Streamlit & Google Sheets
    </p>
</div>
""", unsafe_allow_html=True)
