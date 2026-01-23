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

# ============================================================================
# PAGE CONFIG
# ============================================================================
st.set_page_config(
    page_title="ERHA S&OP 3-Month Consensus Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================================
# CSS STYLING
# ============================================================================
st.markdown("""
<style>
    /* Main Header */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        color: white;
    }
    
    .main-title {
        font-size: 2.8rem;
        font-weight: 800;
        margin: 0;
        background: linear-gradient(90deg, #FFFFFF 0%, #E5E7EB 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    /* Scrollable Table */
    .table-container {
        max-height: 600px;
        overflow-y: auto;
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        margin: 15px 0;
    }
    
    .sticky-header {
        position: sticky;
        top: 0;
        background-color: #1E3A8A !important;
        z-index: 100;
    }
    
    /* Conditional Formatting */
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
    
    /* Editable Cell Highlight */
    .editable-cell {
        background-color: #F0F9FF !important;
        border: 1px solid #3B82F6 !important;
    }
    
    .editable-cell:hover {
        background-color: #DBEAFE !important;
        cursor: pointer;
    }
    
    /* Metrics Cards */
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #E5E7EB;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    
    /* Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent;
        padding: 0;
        border-bottom: 2px solid #E5E7EB;
    }
    
    .stTabs [aria-selected="true"] {
        background: transparent !important;
        color: #3B82F6 !important;
        border-bottom: 3px solid #3B82F6 !important;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# GSHEET CONNECTOR
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
# DATA LOADER
# ============================================================================
@st.cache_data(ttl=300)
def load_all_data():
    """Load and process all required data dari Google Sheets"""
    
    try:
        gs = GSheetConnector()
        
        # Load data
        sales_df = gs.get_sheet_data("sales_history")
        rofo_df = gs.get_sheet_data("rofo_current")
        stock_df = gs.get_sheet_data("stock_onhand")
        
        if sales_df.empty or rofo_df.empty:
            st.error("❌ Data tidak ditemukan di Google Sheets")
            return create_demo_data()
        
        # Proses data
        sales_months = ['Oct-25', 'Nov-25', 'Dec-25']
        available_sales = [m for m in sales_months if m in sales_df.columns]
        
        # Calculate L3M Average
        sales_df['L3M_Avg'] = sales_df[available_sales].mean(axis=1).round(0)
        
        # Get forecast months
        adjustment_months = ['Feb-26', 'Mar-26', 'Apr-26']
        available_forecast = [m for m in adjustment_months if m in rofo_df.columns]
        
        # Merge data
        sales_cols = ['sku_code', 'Product_Name', 'Brand_Group', 'Brand', 'SKU_Tier', 'L3M_Avg'] + available_sales
        rofo_cols = ['sku_code', 'Product_Name', 'Brand_Group', 'Brand', 'SKU_Tier'] + available_forecast
        
        merged_df = pd.merge(
            sales_df[sales_cols],
            rofo_df[rofo_cols],
            on=['sku_code', 'Product_Name', 'Brand_Group', 'Brand', 'SKU_Tier'],
            how='inner'
        )
        
        # Add stock data
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
        
        # Add consensus columns (sama dengan forecast awal)
        for month in available_forecast:
            merged_df[f'Cons_{month}'] = merged_df[month]
        
        # Simpan info bulan ke session state
        st.session_state.adjustment_months = available_forecast
        
        return merged_df
        
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return create_demo_data()

def create_demo_data():
    """Create demo data"""
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
    
    st.session_state.adjustment_months = ['Feb-26', 'Mar-26', 'Apr-26']
    
    return df

# ============================================================================
# HEADER
# ============================================================================
st.markdown("""
<div class="main-header">
    <h1 class="main-title">📊 ERHA S&OP Dashboard</h1>
    <p style="opacity: 0.9;">3-Month Consensus | Direct Editing Table</p>
</div>
""", unsafe_allow_html=True)

# ============================================================================
# LOAD DATA
# ============================================================================
with st.spinner('🔄 Loading data...'):
    all_df = load_all_data()

# Initialize adjustment months
if 'adjustment_months' not in st.session_state:
    st.session_state.adjustment_months = ['Feb-26', 'Mar-26', 'Apr-26']

# ============================================================================
# TOP METRICS
# ============================================================================
st.markdown("### 📊 Quick Overview")
metrics_cols = st.columns(5)

with metrics_cols[0]:
    st.metric("Total SKUs", f"{len(all_df):,}")

with metrics_cols[1]:
    total_sales = all_df['L3M_Avg'].sum() * 3
    st.metric("Total Sales L3M", f"{total_sales:,.0f}")

with metrics_cols[2]:
    avg_cover = all_df['Month_Cover'].mean()
    st.metric("Avg Month Cover", f"{avg_cover:.1f}")

with metrics_cols[3]:
    high_cover = len(all_df[all_df['Month_Cover'] > 1.5])
    st.metric("High Cover SKUs", f"{high_cover:,}")

with metrics_cols[4]:
    forecast_total = 0
    for month in st.session_state.adjustment_months:
        if month in all_df.columns:
            forecast_total += all_df[month].sum()
    growth = ((forecast_total - total_sales) / total_sales * 100) if total_sales > 0 else 0
    st.metric("3M Forecast", f"{forecast_total:,.0f}", f"{growth:+.1f}%")

# ============================================================================
# FILTERS
# ============================================================================
st.markdown("### 🔍 Filter Data")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    brand_groups = ["ALL"] + sorted(all_df['Brand_Group'].dropna().unique().tolist())
    selected_brand_group = st.selectbox("Brand Group", brand_groups)

with col2:
    brands = ["ALL"] + sorted(all_df['Brand'].dropna().unique().tolist())
    selected_brand = st.selectbox("Brand", brands)

with col3:
    sku_tiers = ["ALL"] + sorted(all_df['SKU_Tier'].dropna().unique().tolist())
    selected_tier = st.selectbox("SKU Tier", sku_tiers)

with col4:
    month_cover_filter = st.selectbox(
        "Month Cover",
        ["ALL", "< 1.5 months", "1.5 - 3 months", "> 3 months"]
    )

with col5:
    st.markdown("&nbsp;")
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

# ============================================================================
# APPLY FILTERS
# ============================================================================
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
tab1, tab2 = st.tabs(["📝 Edit Forecast", "📊 Analytics"])

# ============================================================================
# TAB 1: SINGLE EDITABLE TABLE
# ============================================================================
with tab1:
    st.markdown("### 🎯 Edit Consensus Values Directly in Table")
    st.markdown("*Double-click on Consensus cells to edit*")
    
    st.info(f"📋 Showing **{len(filtered_df)}** SKUs | Use filters above to narrow down")
    
    # Color Legend
    st.markdown("""
    <div style="display: flex; gap: 1rem; margin: 1rem 0; padding: 0.75rem; background: #F9FAFB; border-radius: 8px; align-items: center;">
        <div style="font-size: 0.85rem; font-weight: 500; color: #6B7280;">Color Legend:</div>
        <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
            <div style="display: flex; align-items: center; gap: 4px;">
                <div style="width: 16px; height: 16px; background-color: #FCE7F3; border-left: 3px solid #BE185D;"></div>
                <span style="font-size: 0.8rem;">Month Cover > 1.5</span>
            </div>
            <div style="display: flex; align-items: center; gap: 4px;">
                <div style="width: 16px; height: 16px; background-color: #FFEDD5; border-left: 3px solid #9A3412;"></div>
                <span style="font-size: 0.8rem;">Growth < 90%</span>
            </div>
            <div style="display: flex; align-items: center; gap: 4px;">
                <div style="width: 16px; height: 16px; background-color: #FEE2E2; border-left: 3px solid #991B1B;"></div>
                <span style="font-size: 0.8rem;">Growth > 130%</span>
            </div>
            <div style="display: flex; align-items: center; gap: 4px;">
                <div style="width: 16px; height: 16px; background-color: #F0F9FF; border: 1px solid #3B82F6;"></div>
                <span style="font-size: 0.8rem;">Editable Cell</span>
            </div>
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
    
    # Calculate percentage columns
    for month in st.session_state.adjustment_months:
        if month in edit_df.columns and 'L3M_Avg' in edit_df.columns:
            pct_col = f'{month}_%'
            edit_df[pct_col] = (edit_df[month] / edit_df['L3M_Avg'].replace(0, np.nan) * 100).round(1)
            edit_df[pct_col] = edit_df[pct_col].replace([np.inf, -np.inf], 0).fillna(100)
    
    # Pilih kolom untuk ditampilkan
    display_cols = ['No.', 'sku_code', 'Product_Name', 'Brand', 'SKU_Tier']
    
    # Tambahkan sales months
    sales_cols = [col for col in ['Oct-25', 'Nov-25', 'Dec-25'] if col in edit_df.columns]
    display_cols.extend(sales_cols)
    
    # Tambahkan calculated columns
    display_cols.extend(['L3M_Avg', 'Stock_Qty', 'Month_Cover'])
    
    # Tambahkan original forecast columns
    for month in st.session_state.adjustment_months:
        if month in edit_df.columns:
            display_cols.append(month)
    
    # Tambahkan percentage columns
    for month in st.session_state.adjustment_months:
        pct_col = f'{month}_%'
        if pct_col in edit_df.columns:
            display_cols.append(pct_col)
    
    # Tambahkan consensus columns (EDITABLE)
    for month in st.session_state.adjustment_months:
        cons_col = f'Cons_{month}'
        display_cols.append(cons_col)
    
    # =================================================================
    # COLUMN CONFIGURATION
    # =================================================================
    
    column_config = {}
    
    # Read-only columns
    readonly_cols = ['No.', 'sku_code', 'Product_Name', 'Brand', 'SKU_Tier']
    readonly_cols.extend(sales_cols)
    readonly_cols.extend(['L3M_Avg', 'Stock_Qty', 'Month_Cover'])
    readonly_cols.extend(st.session_state.adjustment_months)  # Original forecast
    
    # Percentage columns juga read-only
    for month in st.session_state.adjustment_months:
        pct_col = f'{month}_%'
        readonly_cols.append(pct_col)
    
    for col in readonly_cols:
        if col in display_cols:
            display_name = col.replace('_', ' ').replace('-', ' ')
            
            if '_%' in col:
                column_config[col] = st.column_config.NumberColumn(
                    display_name,
                    format="%.1f%%",
                    disabled=True
                )
            elif col == 'Month_Cover':
                column_config[col] = st.column_config.NumberColumn(
                    display_name,
                    format="%.1f",
                    disabled=True
                )
            elif col in ['L3M_Avg', 'Stock_Qty'] + sales_cols + st.session_state.adjustment_months:
                column_config[col] = st.column_config.NumberColumn(
                    display_name,
                    format="%d",
                    disabled=True
                )
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
            help=f"Double-click to edit consensus value"
        )
    
    # =================================================================
    # DISPLAY EDITABLE TABLE
    # =================================================================
    
    st.markdown("#### 📋 Forecast Adjustment Table")
    
    # Display the data editor - SATU TABEL SAJA!
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
    # SAVE & ACTIONS
    # =================================================================
    
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("💾 Save Consensus Values", type="primary", use_container_width=True):
            # Simpan ke session state
            st.session_state.edited_data = edited_df.copy()
            
            # Calculate changes
            changes = []
            for month in st.session_state.adjustment_months:
                cons_col = f'Cons_{month}'
                if cons_col in edited_df.columns:
                    original_total = edit_df[cons_col].sum()
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
            
            st.session_state.changes = changes
            st.success("✅ Consensus values saved!")
            
            # Show summary
            if changes:
                with st.expander("📊 View Changes Summary"):
                    changes_df = pd.DataFrame(changes)
                    st.dataframe(changes_df, use_container_width=True)
                    
                    # Chart
                    fig = px.bar(
                        pd.DataFrame(changes),
                        x='Month',
                        y='Change',
                        title="Changes vs Original Forecast",
                        text='Change'
                    )
                    fig.update_traces(texttemplate='%{text}', textposition='outside')
                    fig.update_layout(height=300)
                    st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        if st.button("📥 Export Edited Data", use_container_width=True):
            csv = edited_df.to_csv(index=False)
            st.download_button(
                label="⬇️ Download CSV",
                data=csv,
                file_name=f"consensus_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
    
    with col3:
        if st.button("🔄 Reset to Original", type="secondary", use_container_width=True):
            if 'edited_data' in st.session_state:
                del st.session_state.edited_data
            if 'changes' in st.session_state:
                del st.session_state.changes
            st.rerun()
    
    # =================================================================
    # QUICK STATS
    # =================================================================
    
    st.markdown("#### 📈 Quick Stats")
    
    stats_cols = st.columns(len(st.session_state.adjustment_months) + 1)
    
    with stats_cols[0]:
        st.metric("Total SKUs", f"{len(edited_df):,}")
    
    for i, month in enumerate(st.session_state.adjustment_months):
        cons_col = f'Cons_{month}'
        if cons_col in edited_df.columns:
            with stats_cols[i+1]:
                month_total = edited_df[cons_col].sum()
                if 'L3M_Avg' in edited_df.columns:
                    baseline = edited_df['L3M_Avg'].sum() / 3
                    growth = ((month_total - baseline) / baseline * 100) if baseline > 0 else 0
                    st.metric(f"{month}", f"{month_total:,.0f}", f"{growth:+.1f}%")

# ============================================================================
# TAB 2: ANALYTICS
# ============================================================================
with tab2:
    st.markdown("### 📊 Analytics Dashboard")
    
    # Prepare data untuk analytics
    if 'edited_data' in st.session_state:
        analytics_df = st.session_state.edited_data.copy()
    else:
        analytics_df = filtered_df.copy()
        analytics_df['No.'] = range(1, len(analytics_df) + 1)
    
    # Summary metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_consensus = 0
        for month in st.session_state.adjustment_months:
            cons_col = f'Cons_{month}'
            if cons_col in analytics_df.columns:
                total_consensus += analytics_df[cons_col].sum()
        st.metric("Total Consensus", f"{total_consensus:,.0f}")
    
    with col2:
        avg_month_cover = analytics_df['Month_Cover'].mean()
        st.metric("Avg Month Cover", f"{avg_month_cover:.1f}")
    
    with col3:
        if 'changes' in st.session_state:
            total_change = 0
            for change in st.session_state.changes:
                total_change += int(change['Change'].replace(',', '').replace('+', ''))
            st.metric("Total Change", f"{total_change:+,.0f}")
    
    # Charts
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📈 Monthly Forecast")
        
        monthly_data = []
        for month in st.session_state.adjustment_months:
            cons_col = f'Cons_{month}'
            if cons_col in analytics_df.columns:
                monthly_total = analytics_df[cons_col].sum()
                monthly_data.append({
                    'Month': month,
                    'Volume': monthly_total
                })
        
        if monthly_data:
            monthly_df = pd.DataFrame(monthly_data)
            
            fig = px.bar(
                monthly_df,
                x='Month',
                y='Volume',
                title="Consensus Forecast by Month"
            )
            
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("#### 🎯 Brand Performance")
        
        if 'Brand' in analytics_df.columns:
            brand_data = []
            for brand in analytics_df['Brand'].unique():
                brand_total = 0
                for month in st.session_state.adjustment_months:
                    cons_col = f'Cons_{month}'
                    if cons_col in analytics_df.columns:
                        brand_total += analytics_df.loc[analytics_df['Brand'] == brand, cons_col].sum()
                
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
                title="Top 10 Brands by Consensus",
                hole=0.4
            )
            
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
    
    # Changes summary
    if 'changes' in st.session_state:
        st.markdown("---")
        st.markdown("#### 📝 Changes Summary")
        
        changes_df = pd.DataFrame(st.session_state.changes)
        st.dataframe(changes_df, use_container_width=True)

# ============================================================================
# FOOTER
# ============================================================================
st.markdown("---")
st.markdown(f"""
<div style="text-align: center; color: #6B7280; font-size: 0.9rem;">
    <p>📊 <strong>ERHA S&OP Dashboard</strong> | Meeting: {datetime.now().strftime('%Y-%m-%d')} | 
    Total SKUs: {len(all_df):,} | Last Updated: {datetime.now().strftime('%H:%M:%S')}</p>
</div>
""", unsafe_allow_html=True)
