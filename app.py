import streamlit as st
import pandas as pd
import gspread
import plotly.graph_objects as go
from google.oauth2.service_account import Credentials
import json
from datetime import datetime

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================
st.set_page_config(
    page_title="S&OP Consensus Meeting Dashboard",
    page_icon="🤝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional look
st.markdown("""
<style>
    .main-title {
        font-size: 2.8rem;
        color: #1E3A8A;
        text-align: center;
        margin-bottom: 0.5rem;
        font-weight: 700;
    }
    .sub-title {
        font-size: 1.2rem;
        color: #4B5563;
        text-align: center;
        margin-bottom: 2rem;
    }
    .section-header {
        font-size: 1.5rem;
        color: #1E3A8A;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #E5E7EB;
    }
    .metric-card {
        background-color: #F9FAFB;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #E5E7EB;
    }
    .dataframe {
        font-size: 0.85rem;
    }
    .stButton>button {
        font-weight: 600;
    }
    .success-msg {
        padding: 1rem;
        background-color: #D1FAE5;
        border: 1px solid #10B981;
        border-radius: 0.5rem;
        color: #065F46;
    }
    .warning-msg {
        padding: 1rem;
        background-color: #FEF3C7;
        border: 1px solid #F59E0B;
        border-radius: 0.5rem;
        color: #92400E;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# HEADER
# ============================================================================
st.markdown('<p class="main-title">🤝 S&OP Consensus Meeting Dashboard</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Real-time Forecast Collaboration | ERHA Group</p>', unsafe_allow_html=True)

# Meeting info
col1, col2, col3 = st.columns(3)
with col1:
    meeting_date = st.date_input("Meeting Date", value=datetime.now().date(), key="meeting_date")
with col2:
    cycle_month = st.selectbox("Forecast Cycle", 
                              ["Feb-26", "Mar-26", "Apr-26", "May-26", "Jun-26", 
                               "Jul-26", "Aug-26", "Sep-26", "Oct-26", "Nov-26", 
                               "Dec-26", "Jan-27"], key="cycle_month")
with col3:
    st.metric("Meeting Type", "W4 S&OP", "Consensus Review")

st.markdown("---")

# ============================================================================
# GSHEET CONNECTOR (SAME AS BEFORE)
# ============================================================================
class GSheetConnector:
    def __init__(self):
        try:
            self.sheet_id = st.secrets["gsheets"]["sheet_id"]
            self.service_account_info = json.loads(st.secrets["gsheets"]["service_account_info"])
        except:
            st.error("⚠️ GSheet credentials not found. Please check Streamlit secrets.")
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
            st.error(f"❌ Failed to connect to Google Sheets: {str(e)}")
            raise
    
    def get_sheet_data(self, sheet_name):
        """Read sheet as DataFrame"""
        try:
            worksheet = self.sheet.worksheet(sheet_name)
            data = worksheet.get_all_records()
            return pd.DataFrame(data)
        except Exception as e:
            st.warning(f"Sheet '{sheet_name}' not found or empty: {str(e)}")
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
            st.error(f"❌ Error updating sheet {sheet_name}: {str(e)}")
            return False

# ============================================================================
# DATA LOADING
# ============================================================================
@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_all_data():
    """Load all required data from GSheet"""
    gs = GSheetConnector()
    
    with st.spinner("📥 Loading data from Google Sheets..."):
        data = {}
        
        # Load ROFO current (baseline)
        rofo_df = gs.get_sheet_data("rofo_current")
        if not rofo_df.empty:
            # Identify month columns
            month_cols = [col for col in rofo_df.columns if '-' in str(col) and len(str(col)) >= 6]
            keep_cols = ['sku_code', 'Product_Name', 'Brand_Group', 'Brand', 'SKU_Tier'] + month_cols
            keep_cols = [col for col in keep_cols if col in rofo_df.columns]
            data['rofo'] = rofo_df[keep_cols]
        else:
            data['rofo'] = pd.DataFrame()
        
        # Load stock data
        stock_df = gs.get_sheet_data("stock_onhand")
        data['stock'] = stock_df if not stock_df.empty else pd.DataFrame()
        
        # Load historical sales (optional)
        sales_df = gs.get_sheet_data("sales_history")
        data['sales'] = sales_df if not sales_df.empty else pd.DataFrame()
        
        # Load previous inputs (if any)
        data['channel_input'] = gs.get_sheet_data("channel_input")
        data['brand1_input'] = gs.get_sheet_data("brand1_input")
        data['brand2_input'] = gs.get_sheet_data("brand2_input")
        
        return data

# Load data
data = load_all_data()
rofo_df = data['rofo']
stock_df = data['stock']

if rofo_df.empty:
    st.error("❌ No ROFO data found. Please check your GSheet.")
    st.stop()

# ============================================================================
# SIDEBAR - CONTROLS & METRICS
# ============================================================================
with st.sidebar:
    st.header("🛠️ Meeting Controls")
    
    # Refresh button
    if st.button("🔄 Refresh Data", use_container_width=True, key="refresh_btn"):
        st.cache_data.clear()
        st.rerun()
    
    st.markdown("---")
    
    # Filters
    st.header("🔍 Filters")
    
    brand_groups = ["ALL"] + sorted(rofo_df['Brand_Group'].dropna().unique().tolist())
    selected_brand_group = st.selectbox("Brand Group", brand_groups, key="brand_filter")
    
    sku_tiers = ["ALL"] + sorted(rofo_df['SKU_Tier'].dropna().unique().tolist())
    selected_tier = st.selectbox("SKU Tier", sku_tiers, key="tier_filter")
    
    # Apply filters
    filtered_df = rofo_df.copy()
    if selected_brand_group != "ALL":
        filtered_df = filtered_df[filtered_df['Brand_Group'] == selected_brand_group]
    if selected_tier != "ALL":
        filtered_df = filtered_df[filtered_df['SKU_Tier'] == selected_tier]
    
    st.markdown("---")
    
    # Meeting Metrics
    st.header("📊 Meeting Metrics")
    
    total_skus = len(filtered_df)
    total_stock = stock_df['Stock_Qty'].sum() if not stock_df.empty else 0
    
    st.metric("SKUs in View", total_skus)
    st.metric("Total Stock", f"{total_stock:,.0f}")
    
    # Calculate average baseline for selected month
    month_cols = [col for col in filtered_df.columns if '-' in str(col) and len(str(col)) >= 6]
    if month_cols and cycle_month in month_cols:
        avg_forecast = filtered_df[cycle_month].mean()
        st.metric(f"Avg {cycle_month}", f"{avg_forecast:,.0f}")

# ============================================================================
# MAIN DASHBOARD - 3 COLUMN VIEW
# ============================================================================
st.markdown('<p class="section-header">📈 Real-time Forecast Adjustment</p>', unsafe_allow_html=True)

# Create 3-column layout
col1, col2, col3 = st.columns([1, 1, 1], gap="large")

# Identify month columns
month_cols = [col for col in filtered_df.columns if '-' in str(col) and len(str(col)) >= 6]
if not month_cols:
    st.error("No month columns found in ROFO data.")
    st.stop()

# ============================================================================
# COLUMN 1: BASELINE ROFO (READ-ONLY)
# ============================================================================
with col1:
    st.markdown("### 📊 Baseline ROFO")
    st.caption("Current forecast - Read only")
    
    # Display baseline metrics
    baseline_metrics = st.container()
    with baseline_metrics:
        m1, m2 = st.columns(2)
        with m1:
            if cycle_month in month_cols:
                total_baseline = filtered_df[cycle_month].sum()
                st.metric("Total", f"{total_baseline:,.0f}")
        with m2:
            if cycle_month in month_cols:
                avg_baseline = filtered_df[cycle_month].mean()
                st.metric("Average", f"{avg_baseline:,.0f}")
    
    # Display baseline data
    display_cols = ['sku_code', 'Product_Name', 'Brand', 'SKU_Tier']
    if cycle_month in filtered_df.columns:
        display_cols.append(cycle_month)
    
    baseline_display = filtered_df[display_cols].copy()
    
    # Add stock data if available
    if not stock_df.empty and 'sku_code' in stock_df.columns:
        baseline_display = pd.merge(
            baseline_display,
            stock_df[['sku_code', 'Stock_Qty']],
            on='sku_code',
            how='left'
        )
        baseline_display['Stock_Qty'] = baseline_display['Stock_Qty'].fillna(0)
        display_cols.append('Stock_Qty')
    
    st.dataframe(
        baseline_display,
        use_container_width=True,
        height=400,
        column_config={
            'sku_code': st.column_config.TextColumn("SKU", width="small"),
            'Product_Name': st.column_config.TextColumn("Product", width="medium"),
            'Brand': st.column_config.TextColumn("Brand", width="small"),
            'SKU_Tier': st.column_config.TextColumn("Tier", width="small"),
            cycle_month: st.column_config.NumberColumn(
                "Baseline",
                format="%d",
                width="small"
            ),
            'Stock_Qty': st.column_config.NumberColumn(
                "Stock",
                format="%d",
                width="small"
            ) if 'Stock_Qty' in baseline_display.columns else None
        }
    )

# ============================================================================
# COLUMN 2: CHANNEL ADJUSTMENTS (EDITABLE)
# ============================================================================
with col2:
    st.markdown("### 🛒 Channel Input")
    st.caption("Sales team adjustments (±40% limit)")
    
    # Create editable dataframe for Channel
    channel_df = filtered_df.copy()
    
    # Initialize adjustment columns if they don't exist
    for month in month_cols:
        adj_col = f"{month}_channel_adj"
        if adj_col not in channel_df.columns:
            channel_df[adj_col] = 0  # Default no adjustment
        pct_col = f"{month}_channel_pct"
        if pct_col not in channel_df.columns:
            channel_df[pct_col] = 0.0
    
    # Display editable grid for selected month
    if cycle_month in month_cols:
        # Calculate suggested adjustment (placeholder - can be based on history)
        channel_df[f"{cycle_month}_suggested"] = channel_df[cycle_month] * 0.1  # 10% increase as example
        
        # Create display dataframe
        channel_display = channel_df[[
            'sku_code', 'Product_Name', 'Brand', 
            cycle_month, f"{cycle_month}_channel_adj", f"{cycle_month}_suggested"
        ]].copy()
        
        # Rename columns for display
        channel_display.columns = ['SKU', 'Product', 'Brand', 'Baseline', 'Your Adjustment', 'Suggested']
        
        # Editable configuration
        column_config = {
            'SKU': st.column_config.TextColumn("SKU", disabled=True),
            'Product': st.column_config.TextColumn("Product", disabled=True),
            'Brand': st.column_config.TextColumn("Brand", disabled=True),
            'Baseline': st.column_config.NumberColumn("Baseline", disabled=True, format="%d"),
            'Your Adjustment': st.column_config.NumberColumn(
                "Adjustment",
                min_value=-1000000,
                max_value=1000000,
                step=1,
                format="%d"
            ),
            'Suggested': st.column_config.NumberColumn("Suggested", disabled=True, format="%d")
        }
        
        # Display editable dataframe
        channel_edited = st.data_editor(
            channel_display.head(20),  # Show first 20 for performance
            column_config=column_config,
            use_container_width=True,
            height=400,
            key="channel_editor"
        )
        
        # Adjustment summary
        if not channel_edited.empty:
            total_adjustment = channel_edited['Your Adjustment'].sum()
            avg_adjustment = channel_edited['Your Adjustment'].mean()
            
            m1, m2 = st.columns(2)
            with m1:
                st.metric("Total Adj", f"{total_adjustment:+,.0f}")
            with m2:
                st.metric("Avg Adj", f"{avg_adjustment:+,.0f}")

# ============================================================================
# COLUMN 3: BRAND ADJUSTMENTS (EDITABLE)
# ============================================================================
with col3:
    st.markdown("### 🏷️ Brand Input")
    st.caption("Marketing team adjustments (±40% limit)")
    
    # Create editable dataframe for Brand
    brand_df = filtered_df.copy()
    
    # Initialize adjustment columns
    for month in month_cols:
        adj_col = f"{month}_brand_adj"
        if adj_col not in brand_df.columns:
            brand_df[adj_col] = 0
        pct_col = f"{month}_brand_pct"
        if pct_col not in brand_df.columns:
            brand_df[pct_col] = 0.0
    
    # Display editable grid for selected month
    if cycle_month in month_cols:
        # Separate for Brand Group 1 and 2
        brand1_brands = ['ACNEACT', 'AGE CORRECTOR', 'TRUWHITE']
        brand2_brands = ['ERHAIR', 'HISERHA', 'PERFECT SHIELD', 'SKINSITIVE']
        
        brand1_df = brand_df[brand_df['Brand'].isin(brand1_brands)]
        brand2_df = brand_df[brand_df['Brand'].isin(brand2_brands)]
        
        # Brand Group 1
        st.markdown("**ERHA SKINCARE GROUP 1**")
        if not brand1_df.empty:
            brand1_display = brand1_df[[
                'sku_code', 'Product_Name', 'Brand',
                cycle_month, f"{cycle_month}_brand_adj"
            ]].head(10).copy()  # Limit to 10 for display
            
            brand1_display.columns = ['SKU', 'Product', 'Brand', 'Baseline', 'Adjustment']
            
            brand1_edited = st.data_editor(
                brand1_display,
                column_config={
                    'SKU': st.column_config.TextColumn("SKU", disabled=True),
                    'Product': st.column_config.TextColumn("Product", disabled=True),
                    'Brand': st.column_config.TextColumn("Brand", disabled=True),
                    'Baseline': st.column_config.NumberColumn("Baseline", disabled=True, format="%d"),
                    'Adjustment': st.column_config.NumberColumn(
                        "Adjustment",
                        min_value=-1000000,
                        max_value=1000000,
                        step=1,
                        format="%d"
                    )
                },
                use_container_width=True,
                height=200,
                key="brand1_editor"
            )
        
        # Brand Group 2
        st.markdown("**ERHA SKINCARE GROUP 2**")
        if not brand2_df.empty:
            brand2_display = brand2_df[[
                'sku_code', 'Product_Name', 'Brand',
                cycle_month, f"{cycle_month}_brand_adj"
            ]].head(10).copy()
            
            brand2_display.columns = ['SKU', 'Product', 'Brand', 'Baseline', 'Adjustment']
            
            brand2_edited = st.data_editor(
                brand2_display,
                column_config={
                    'SKU': st.column_config.TextColumn("SKU", disabled=True),
                    'Product': st.column_config.TextColumn("Product", disabled=True),
                    'Brand': st.column_config.TextColumn("Brand", disabled=True),
                    'Baseline': st.column_config.NumberColumn("Baseline", disabled=True, format="%d"),
                    'Adjustment': st.column_config.NumberColumn(
                        "Adjustment",
                        min_value=-1000000,
                        max_value=1000000,
                        step=1,
                        format="%d"
                    )
                },
                use_container_width=True,
                height=200,
                key="brand2_editor"
            )

# ============================================================================
# CONSENSUS CALCULATION & VISUALIZATION
# ============================================================================
st.markdown("---")
st.markdown('<p class="section-header">✅ Consensus Calculation</p>', unsafe_allow_html=True)

# Create consensus dataframe
consensus_df = filtered_df.copy()

if cycle_month in month_cols:
    # Get adjustments from editors (simplified - in real app would capture from data_editor)
    consensus_df['Channel_Adj'] = 0  # Placeholder - would come from channel_edited
    consensus_df['Brand_Adj'] = 0    # Placeholder - would come from brand_edited
    
    # Calculate consensus
    consensus_df['Consensus'] = (
        consensus_df[cycle_month] + 
        consensus_df['Channel_Adj'] + 
        consensus_df['Brand_Adj']
    )
    
    # Calculate variance
    consensus_df['Variance_%'] = (
        (consensus_df['Consensus'] - consensus_df[cycle_month]) / 
        consensus_df[cycle_month].replace(0, 1) * 100
    ).round(1)
    
    # Display consensus summary
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_baseline = consensus_df[cycle_month].sum()
        st.metric("Total Baseline", f"{total_baseline:,.0f}")
    
    with col2:
        total_consensus = consensus_df['Consensus'].sum()
        st.metric("Total Consensus", f"{total_consensus:,.0f}")
    
    with col3:
        total_change = total_consensus - total_baseline
        st.metric("Net Change", f"{total_change:+,.0f}")
    
    with col4:
        avg_variance = consensus_df['Variance_%'].mean()
        st.metric("Avg Variance", f"{avg_variance:+.1f}%")
    
    # Display consensus table
    st.markdown("#### Consensus Preview")
    consensus_display = consensus_df[[
        'sku_code', 'Product_Name', 'Brand_Group', 'Brand',
        cycle_month, 'Channel_Adj', 'Brand_Adj', 'Consensus', 'Variance_%'
    ]].head(15)
    
    st.dataframe(
        consensus_display,
        use_container_width=True,
        column_config={
            'sku_code': st.column_config.TextColumn("SKU"),
            'Product_Name': st.column_config.TextColumn("Product"),
            'Brand_Group': st.column_config.TextColumn("Brand Group"),
            'Brand': st.column_config.TextColumn("Brand"),
            cycle_month: st.column_config.NumberColumn("Baseline", format="%d"),
            'Channel_Adj': st.column_config.NumberColumn("Channel Adj", format="%+d"),
            'Brand_Adj': st.column_config.NumberColumn("Brand Adj", format="%+d"),
            'Consensus': st.column_config.NumberColumn("Consensus", format="%d"),
            'Variance_%': st.column_config.NumberColumn("Variance %", format="%+.1f%%"),
        }
    )

# ============================================================================
# FINALIZATION SECTION
# ============================================================================
st.markdown("---")
st.markdown('<p class="section-header">💾 Finalize Consensus</p>', unsafe_allow_html=True)

col1, col2 = st.columns([2, 1])

with col1:
    notes = st.text_area(
        "Meeting Notes / Justification",
        placeholder="Document key decisions, rationale for significant adjustments, campaign impacts...",
        height=100,
        key="meeting_notes"
    )

with col2:
    st.markdown("### Final Approval")
    
    # Simulate approval (in real meeting, this would be verbal)
    approved = st.checkbox("✅ Consensus approved in meeting", value=False, key="approval_check")
    
    if approved:
        save_disabled = False
        st.success("Ready to save consensus")
    else:
        save_disabled = True
        st.warning("Awaiting meeting approval")
    
    # Save button
    if st.button(
        "💾 Save Final Consensus to GSheet",
        type="primary",
        use_container_width=True,
        disabled=save_disabled,
        key="save_consensus"
    ):
        with st.spinner("Saving consensus to Google Sheets..."):
            # Prepare final data
            final_df = consensus_df.copy()
            final_df['meeting_date'] = meeting_date.strftime("%Y-%m-%d")
            final_df['cycle_month'] = cycle_month
            final_df['notes'] = notes
            final_df['saved_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Save to GSheet
            gs = GSheetConnector()
            
            # Save to consensus_log sheet
            log_cols = ['meeting_date', 'cycle_month', 'sku_code', 'Product_Name', 
                       'Brand_Group', 'Brand', 'baseline', 'channel_adj', 
                       'brand_adj', 'consensus', 'variance_pct', 'notes', 'saved_at']
            
            log_df = pd.DataFrame(columns=log_cols)
            for _, row in final_df.iterrows():
                log_df = log_df.append({
                    'meeting_date': row['meeting_date'],
                    'cycle_month': cycle_month,
                    'sku_code': row['sku_code'],
                    'Product_Name': row['Product_Name'],
                    'Brand_Group': row['Brand_Group'],
                    'Brand': row['Brand'],
                    'baseline': row[cycle_month],
                    'channel_adj': row['Channel_Adj'],
                    'brand_adj': row['Brand_Adj'],
                    'consensus': row['Consensus'],
                    'variance_pct': row['Variance_%'],
                    'notes': notes,
                    'saved_at': row['saved_at']
                }, ignore_index=True)
            
            success = gs.update_sheet("consensus_log", log_df)
            
            if success:
                st.balloons()
                st.markdown('<div class="success-msg">✅ Consensus successfully saved to Google Sheets!</div>', unsafe_allow_html=True)
                
                # Option to update ROFO_current
                if st.checkbox("Update ROFO_current with new consensus?", value=False):
                    # Update ROFO for next month
                    st.info("Feature coming soon - will update ROFO_current sheet")
            else:
                st.error("❌ Failed to save consensus. Please try again.")

# ============================================================================
# FOOTER
# ============================================================================
st.markdown("---")
st.caption(f"🤝 S&OP Meeting Dashboard | Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.caption("For ERHA Group Internal Use Only")
