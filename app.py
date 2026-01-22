import streamlit as st
import pandas as pd
import numpy as np
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================
st.set_page_config(
    page_title="S&OP 3-Month Consensus Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1E3A8A;
        text-align: center;
        margin-bottom: 0.5rem;
        font-weight: 700;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #4B5563;
        text-align: center;
        margin-bottom: 2rem;
    }
    .highlight-box {
        background-color: #F0F9FF;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 2px solid #0EA5E9;
        margin-bottom: 1rem;
    }
    .data-table {
        font-size: 0.85rem;
    }
    .positive {
        color: #10B981;
        font-weight: 600;
    }
    .negative {
        color: #EF4444;
        font-weight: 600;
    }
    .neutral {
        color: #6B7280;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# HEADER
# ============================================================================
st.markdown('<p class="main-header">📈 S&OP 3-Month Consensus Dashboard</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Last 3M Sales vs ROFO Feb-Apr 2026 | Real-time Adjustment</p>', unsafe_allow_html=True)

# Meeting info
with st.container():
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        meeting_date = st.date_input("Meeting Date", value=datetime.now().date(), key="meeting_date")
    with col2:
        st.metric("Cycle", "Q1 2026", "Feb-Apr Forecast")
    with col3:
        baseline_period = st.selectbox(
            "Baseline Period",
            ["Oct-Dec 2025", "Nov 2025-Jan 2026", "Dec 2025-Feb 2026"],
            key="baseline_period"
        )
    with col4:
        st.metric("SKUs", "Loading...", "0")

st.markdown("---")

# Highlight info box
st.markdown("""
<div class="highlight-box">
    <strong>📊 Workflow:</strong> 
    1. Baseline = Average of Last 3 Month Actual Sales<br>
    2. Adjust Current ROFO (Feb-Apr 2026) based on Channel & Brand input<br>
    3. Calculate % growth vs Baseline<br>
    4. Finalize consensus for next 3 months
</div>
""", unsafe_allow_html=True)

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
# DATA PROCESSING FUNCTIONS
# ============================================================================
@st.cache_data
def load_and_process_data():
    """Load and process data for 3-month comparison"""
    gs = GSheetConnector()
    
    # 1. Load historical sales
    sales_df = gs.get_sheet_data("sales_history")
    if sales_df.empty:
        st.error("No sales history data found")
        return None
    
    # 2. Load current ROFO
    rofo_df = gs.get_sheet_data("rofo_current")
    if rofo_df.empty:
        st.error("No ROFO data found")
        return None
    
    # 3. Load stock data
    stock_df = gs.get_sheet_data("stock_onhand")
    
    # ============================================
    # PROCESS SALES DATA - Calculate last 3 month average
    # ============================================
    
    # Identify sales month columns (assuming format like "Oct-24", "Nov-24")
    sales_month_cols = [col for col in sales_df.columns if '-' in str(col)]
    
    # Get last 3 months based on baseline_period selection
    # For now, hardcode last 3 months from available data
    if len(sales_month_cols) >= 3:
        last_3_months = sales_month_cols[-3:]  # Last 3 columns
    else:
        last_3_months = sales_month_cols  # Use whatever is available
    
    # Calculate baseline (average of last 3 months)
    sales_df['Baseline_3M_Avg'] = sales_df[last_3_months].mean(axis=1)
    
    # Keep only essential columns from sales
    sales_essential = sales_df[['sku_code', 'Product_Name', 'Brand_Group', 'Brand', 'SKU_Tier', 'Baseline_3M_Avg']]
    
    # ============================================
    # PROCESS ROFO DATA - Focus on Feb-Apr 2026
    # ============================================
    
    # Identify ROFO month columns
    rofo_month_cols = [col for col in rofo_df.columns if '-' in str(col)]
    
    # Filter for Feb, Mar, Apr 2026
    target_months = ['Feb-26', 'Mar-26', 'Apr-26']
    available_months = [m for m in target_months if m in rofo_month_cols]
    
    # Keep essential columns from ROFO
    rofo_essential_cols = ['sku_code', 'Product_Name', 'Brand_Group', 'Brand', 'SKU_Tier'] + available_months
    rofo_essential_cols = [col for col in rofo_essential_cols if col in rofo_df.columns]
    rofo_essential = rofo_df[rofo_essential_cols]
    
    # ============================================
    # MERGE DATA
    # ============================================
    
    # Merge sales baseline with ROFO data
    merged_df = pd.merge(
        sales_essential,
        rofo_essential,
        on=['sku_code', 'Product_Name', 'Brand_Group', 'Brand', 'SKU_Tier'],
        how='inner',
        suffixes=('', '_rofo')
    )
    
    # Merge with stock data if available
    if not stock_df.empty and 'sku_code' in stock_df.columns:
        merged_df = pd.merge(
            merged_df,
            stock_df[['sku_code', 'Stock_Qty']],
            on='sku_code',
            how='left'
        )
        merged_df['Stock_Qty'] = merged_df['Stock_Qty'].fillna(0)
    
    return {
        'data': merged_df,
        'available_months': available_months,
        'last_3_months': last_3_months,
        'stock': stock_df
    }

# ============================================================================
# MAIN DATA LOADING
# ============================================================================
with st.spinner("Loading and processing data..."):
    processed_data = load_and_process_data()
    
if not processed_data:
    st.stop()

df = processed_data['data']
available_months = processed_data['available_months']
last_3_months = processed_data['last_3_months']
stock_df = processed_data['stock']

st.success(f"✅ Loaded {len(df)} SKUs | Baseline: {', '.join(last_3_months)} | ROFO Months: {', '.join(available_months)}")

# ============================================================================
# SIDEBAR - FILTERS & CONTROLS
# ============================================================================
with st.sidebar:
    st.header("🔍 Filters & Controls")
    
    # Refresh button
    if st.button("🔄 Refresh Data", use_container_width=True, key="refresh_all"):
        st.cache_data.clear()
        st.rerun()
    
    st.markdown("---")
    
    # Brand Group Filter
    brand_groups = ["ALL"] + sorted(df['Brand_Group'].dropna().unique().tolist())
    selected_brand = st.selectbox("Brand Group", brand_groups, key="filter_brand")
    
    # SKU Tier Filter
    sku_tiers = ["ALL"] + sorted(df['SKU_Tier'].dropna().unique().tolist())
    selected_tier = st.selectbox("SKU Tier", sku_tiers, key="filter_tier")
    
    # Brand Filter
    brands = ["ALL"] + sorted(df['Brand'].dropna().unique().tolist())
    selected_brand_name = st.selectbox("Brand", brands, key="filter_brand_name")
    
    # Apply filters
    filtered_df = df.copy()
    if selected_brand != "ALL":
        filtered_df = filtered_df[filtered_df['Brand_Group'] == selected_brand]
    if selected_tier != "ALL":
        filtered_df = filtered_df[filtered_df['SKU_Tier'] == selected_tier]
    if selected_brand_name != "ALL":
        filtered_df = filtered_df[filtered_df['Brand'] == selected_brand_name]
    
    st.markdown("---")
    
    # Summary Metrics
    st.header("📊 Summary")
    
    total_skus = len(filtered_df)
    total_baseline = filtered_df['Baseline_3M_Avg'].sum()
    total_stock = filtered_df['Stock_Qty'].sum() if 'Stock_Qty' in filtered_df.columns else 0
    
    st.metric("SKUs in View", f"{total_skus:,}")
    st.metric("Avg Baseline/3M", f"{total_baseline/total_skus:,.0f}" if total_skus > 0 else "0")
    st.metric("Total Stock", f"{total_stock:,}")
    
    # Calculate average ROFO growth
    if available_months:
        for month in available_months[:1]:  # Show first month only
            if month in filtered_df.columns:
                avg_rofo = filtered_df[month].mean()
                avg_baseline = filtered_df['Baseline_3M_Avg'].mean()
                if avg_baseline > 0:
                    growth_pct = ((avg_rofo - avg_baseline) / avg_baseline * 100)
                    st.metric(f"Avg {month} vs Baseline", f"{growth_pct:+.1f}%")

# ============================================================================
# MAIN DASHBOARD - 3 MONTH COMPARISON TABLE
# ============================================================================
st.header("📋 3-Month Forecast Adjustment Table")

# Calculate percentage columns for display
display_df = filtered_df.copy()

# Add % columns for ROFO vs Baseline
for month in available_months:
    if month in display_df.columns:
        pct_col = f"{month}_vs_Baseline_%"
        display_df[pct_col] = (
            (display_df[month] - display_df['Baseline_3M_Avg']) / 
            display_df['Baseline_3M_Avg'].replace(0, 1) * 100
        ).round(1)
        
        # Add consensus columns (initially same as ROFO)
        cons_col = f"Consensus_{month}"
        display_df[cons_col] = display_df[month]
        
        # Add consensus % columns
        cons_pct_col = f"Consensus_{month}_vs_Baseline_%"
        display_df[cons_pct_col] = display_df[pct_col]

# Create editable dataframe
editable_cols = ['sku_code', 'Product_Name', 'Brand_Group', 'Brand', 'SKU_Tier']

if 'Stock_Qty' in display_df.columns:
    editable_cols.append('Stock_Qty')

editable_cols.append('Baseline_3M_Avg')

# Add ROFO months and their % columns
for month in available_months:
    if month in display_df.columns:
        editable_cols.extend([month, f"{month}_vs_Baseline_%"])

# Add Consensus columns (editable)
for month in available_months:
    cons_col = f"Consensus_{month}"
    cons_pct_col = f"Consensus_{month}_vs_Baseline_%"
    editable_cols.extend([cons_col, cons_pct_col])

# Prepare dataframe for editing
editor_df = display_df[editable_cols].copy()

# Define column configuration
column_config = {}

# Fixed columns
column_config['sku_code'] = st.column_config.TextColumn("SKU", width="small", disabled=True)
column_config['Product_Name'] = st.column_config.TextColumn("Product", width="medium", disabled=True)
column_config['Brand_Group'] = st.column_config.TextColumn("Brand Group", width="small", disabled=True)
column_config['Brand'] = st.column_config.TextColumn("Brand", width="small", disabled=True)
column_config['SKU_Tier'] = st.column_config.TextColumn("Tier", width="small", disabled=True)

if 'Stock_Qty' in editor_df.columns:
    column_config['Stock_Qty'] = st.column_config.NumberColumn("Stock", format="%d", width="small", disabled=True)

column_config['Baseline_3M_Avg'] = st.column_config.NumberColumn(
    "Baseline (Avg 3M)", 
    format="%.0f", 
    width="small", 
    disabled=True,
    help="Average of last 3 month actual sales"
)

# ROFO columns (read-only)
for month in available_months:
    if month in editor_df.columns:
        column_config[month] = st.column_config.NumberColumn(
            f"ROFO {month}", 
            format="%d", 
            width="small", 
            disabled=True,
            help="Current ROFO forecast"
        )
        
        pct_col = f"{month}_vs_Baseline_%"
        column_config[pct_col] = st.column_config.NumberColumn(
            f"% vs Baseline", 
            format="%+.1f%%", 
            width="small", 
            disabled=True
        )

# Consensus columns (EDITABLE)
for month in available_months:
    cons_col = f"Consensus_{month}"
    column_config[cons_col] = st.column_config.NumberColumn(
        f"Consensus {month}",
        min_value=0,
        step=1,
        format="%d",
        width="small",
        help="Final consensus quantity after discussion"
    )
    
    cons_pct_col = f"Consensus_{month}_vs_Baseline_%"
    column_config[cons_pct_col] = st.column_config.NumberColumn(
        f"Consensus %",
        format="%+.1f%%",
        width="small",
        disabled=True
    )

# Display the editable table
st.caption(f"Showing {len(editor_df)} SKUs. Green/red percentages show growth/decline vs 3-month baseline.")
edited_df = st.data_editor(
    editor_df.head(50),  # Limit to 50 rows for performance
    column_config=column_config,
    use_container_width=True,
    height=500,
    key="consensus_editor"
)

# ============================================================================
# CONSENSUS SUMMARY & ANALYSIS
# ============================================================================
st.markdown("---")
st.header("📊 Consensus Analysis")

if not edited_df.empty:
    # Calculate totals
    analysis_cols = ['Baseline_3M_Avg'] + [f"Consensus_{month}" for month in available_months]
    analysis_cols = [col for col in analysis_cols if col in edited_df.columns]
    
    if analysis_cols:
        # Create summary dataframe
        summary_data = []
        total_baseline = edited_df['Baseline_3M_Avg'].sum()
        
        for month in available_months:
            cons_col = f"Consensus_{month}"
            if cons_col in edited_df.columns:
                total_consensus = edited_df[cons_col].sum()
                change = total_consensus - total_baseline
                change_pct = (change / total_baseline * 100) if total_baseline > 0 else 0
                
                summary_data.append({
                    'Period': month,
                    'Baseline (3M Avg)': f"{total_baseline:,.0f}",
                    'Consensus': f"{total_consensus:,.0f}",
                    'Change (Qty)': f"{change:+,.0f}",
                    'Change (%)': f"{change_pct:+.1f}%"
                })
        
        summary_df = pd.DataFrame(summary_data)
        
        # Display summary
        col1, col2 = st.columns([3, 2])
        
        with col1:
            st.markdown("#### Total Volume Summary")
            st.dataframe(summary_df, use_container_width=True, hide_index=True)
        
        with col2:
            st.markdown("#### Key Metrics")
            
            if summary_data:
                # Calculate average growth
                avg_growth = np.mean([float(d['Change (%)'].replace('%', '').replace('+', '')) 
                                     for d in summary_data])
                
                # Calculate consistency
                changes = [float(d['Change (%)'].replace('%', '').replace('+', '')) 
                          for d in summary_data]
                consistency = 100 - np.std(changes) if len(changes) > 1 else 100
                
                st.metric("Avg Growth vs Baseline", f"{avg_growth:+.1f}%")
                st.metric("Forecast Consistency", f"{consistency:.0f}%")
                st.metric("SKUs Adjusted", f"{len(edited_df):,}")

# ============================================================================
# MEETING NOTES & FINALIZATION
# ============================================================================
st.markdown("---")
st.header("💾 Finalize Consensus")

with st.container():
    col1, col2 = st.columns([3, 1])
    
    with col1:
        notes = st.text_area(
            "Meeting Notes & Rationale",
            placeholder="Document key decisions:\n"
                       "1. Major adjustments and reasons\n"
                       "2. Campaign impacts\n"
                       "3. Market intelligence\n"
                       "4. Growth assumptions",
            height=150,
            key="final_notes"
        )
    
    with col2:
        st.markdown("### Approval")
        
        # Simple approval toggle
        approved = st.toggle("✅ Consensus Approved", value=False, key="approval_toggle")
        
        if approved:
            save_disabled = False
            st.success("Ready to save")
        else:
            save_disabled = True
            st.warning("Pending approval")
        
        # Save button
        if st.button(
            "💾 Save to GSheet",
            type="primary",
            use_container_width=True,
            disabled=save_disabled,
            key="save_final"
        ):
            with st.spinner("Saving consensus..."):
                # Prepare data for saving
                save_data = edited_df.copy()
                
                # Add metadata
                save_data['meeting_date'] = meeting_date.strftime("%Y-%m-%d")
                save_data['baseline_period'] = baseline_period
                save_data['notes'] = notes
                save_data['saved_by'] = "S&OP Meeting"
                save_data['saved_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Connect to GSheet and save
                gs = GSheetConnector()
                
                # Create consensus log entry
                log_entries = []
                for _, row in save_data.iterrows():
                    for month in available_months:
                        cons_col = f"Consensus_{month}"
                        if cons_col in row:
                            log_entries.append({
                                'meeting_date': row['meeting_date'],
                                'sku_code': row['sku_code'],
                                'product_name': row['Product_Name'],
                                'brand_group': row['Brand_Group'],
                                'brand': row['Brand'],
                                'baseline_3m_avg': row['Baseline_3M_Avg'],
                                'month': month,
                                'current_rofo': row.get(month, 0),
                                'consensus_qty': row[cons_col],
                                'growth_pct': row.get(f"Consensus_{month}_vs_Baseline_%", 0),
                                'notes': row['notes'],
                                'saved_at': row['saved_at']
                            })
                
                if log_entries:
                    log_df = pd.DataFrame(log_entries)
                    success = gs.update_sheet("consensus_log", log_df)
                    
                    if success:
                        st.balloons()
                        st.success("✅ Consensus saved successfully!")
                        
                        # Show summary
                        total_changes = sum([
                            abs(row.get(month, 0) - row.get(f"Consensus_{month}", 0))
                            for _, row in save_data.iterrows()
                            for month in available_months
                            if f"Consensus_{month}" in row
                        ])
                        
                        st.info(f"**Summary:** {len(log_entries)} month-SKU combinations saved | Total adjustment: {total_changes:,.0f} units")
                    else:
                        st.error("❌ Failed to save. Please try again.")

# ============================================================================
# FOOTER
# ============================================================================
st.markdown("---")
st.caption(f"📊 S&OP 3-Month Consensus Dashboard | Meeting: {meeting_date} | Data as of {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.caption("ERHA Group | For internal S&OP meetings only")
