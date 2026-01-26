import streamlit as st
import pandas as pd
import numpy as np
import gspread
import plotly.graph_objects as go
import plotly.express as px
from google.oauth2.service_account import Credentials
import json
from datetime import datetime, timedelta
import re
from dateutil.relativedelta import relativedelta
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode, JsCode
from streamlit_extras.metric_cards import style_metric_cards
from streamlit_extras.stylable_container import stylable_container

# ============================================================================
# PAGE CONFIG
# ============================================================================
st.set_page_config(
    page_title="ERHA S&OP Dashboard V5.5",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# CSS STYLING - IMPROVED RESPONSIVENESS
# ============================================================================
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
        padding: 1.5rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .stSelectbox label, .stRadio label { font-weight: 600 !important; }
    div[data-testid="stMetricValue"] { font-size: 1.4rem; }
    
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        padding-left: 1.5rem;
        padding-right: 1.5rem;
        max-width: 100%;
    }
    
    /* Improved responsive grid */
    .ag-theme-alpine {
        --ag-font-size: 12px !important;
        --ag-border-radius: 6px !important;
    }
    
    .ag-root-wrapper {
        min-height: 500px !important;
        height: calc(100vh - 320px) !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 8px !important;
    }
    
    /* Better hover effects */
    .ag-row:hover {
        background-color: #f8fafc !important;
    }
    
    /* Responsive adjustments */
    @media screen and (max-width: 1400px) {
        .ag-header-cell-text { font-size: 11px !important; }
        .ag-cell { font-size: 11px !important; }
    }
    
    @media screen and (max-width: 992px) {
        .main-header h2 { font-size: 1.4rem !important; }
        .main-header p { font-size: 0.85rem !important; }
        .block-container {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
    }
    
    @media screen and (max-width: 768px) {
        .main-header { padding: 1rem !important; }
        .main-header h2 { font-size: 1.2rem !important; }
        div[data-testid="stMetricValue"] { font-size: 1.2rem; }
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# 1. GSHEET CONNECTOR WITH ERROR HANDLING
# ============================================================================
class GSheetConnector:
    def __init__(self):
        if "gsheets" in st.secrets:
            try:
                self.sheet_id = st.secrets["gsheets"]["sheet_id"]
                self.service_account_info = json.loads(st.secrets["gsheets"]["service_account_info"])
                self.client = None
                self.connect()
            except Exception as e:
                st.error(f"❌ Error loading secrets: {str(e)}")
                self.client = None
        else:
            st.error("❌ Secrets 'gsheets' not found in Streamlit secrets.")
            self.client = None

    def connect(self):
        try:
            scope = ['https://www.googleapis.com/auth/spreadsheets']
            creds = Credentials.from_service_account_info(self.service_account_info, scopes=scope)
            self.client = gspread.authorize(creds)
            self.sheet = self.client.open_by_key(self.sheet_id)
            return True
        except Exception as e:
            st.error(f"🔌 Connection Error: {str(e)}")
            return False

    def get_sheet_data(self, sheet_name):
        try:
            if not self.client:
                st.error("Not connected to Google Sheets")
                return pd.DataFrame()
                
            worksheet = self.sheet.worksheet(sheet_name)
            data = worksheet.get_all_records(value_render_option='FORMATTED_VALUE') 
            return pd.DataFrame(data)
        except gspread.WorksheetNotFound:
            st.warning(f"Worksheet '{sheet_name}' not found")
            return pd.DataFrame()
        except Exception as e:
            st.error(f"Error reading {sheet_name}: {str(e)}")
            return pd.DataFrame()

    def save_data(self, df, sheet_name):
        try:
            if not self.client:
                return False, "Not connected to Google Sheets"
                
            try:
                worksheet = self.sheet.worksheet(sheet_name)
            except gspread.WorksheetNotFound:
                worksheet = self.sheet.add_worksheet(title=sheet_name, rows=df.shape[0] + 100, cols=df.shape[1] + 5)
            
            # Clean and prepare data
            df_clean = df.fillna('').infer_objects(copy=False)
            
            # Convert all data to string for safe upload
            data_to_upload = [df_clean.columns.values.tolist()]
            for row in df_clean.values.tolist():
                data_to_upload.append([str(cell) if cell is not None else '' for cell in row])
            
            worksheet.clear()
            worksheet.update(data_to_upload, value_input_option='USER_ENTERED')
            return True, "Successfully saved to Google Sheets"
        except Exception as e:
            return False, f"Save error: {str(e)}"

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def clean_currency(val):
    """Clean currency values from various formats"""
    if pd.isna(val) or val == '' or val is None:
        return 0
    val_str = str(val)
    # Remove Rp, spaces, commas, dots (thousand separators)
    clean_str = re.sub(r'[^0-9]', '', val_str)
    try:
        return float(clean_str)
    except:
        return 0

def find_matching_column(target_month, available_columns):
    """Find matching month column with fuzzy matching"""
    if target_month in available_columns: 
        return target_month
    
    # Create clean versions for comparison
    target_clean = target_month.lower().replace('-', '').replace(' ', '').replace('_', '')
    
    for col in available_columns:
        col_str = str(col)
        col_clean = col_str.lower().replace('-', '').replace(' ', '').replace('_', '')
        if target_clean in col_clean or col_clean in target_clean:
            return col
    
    return None

def parse_month_year(date_str):
    """Parse month-year string to datetime for sorting"""
    try:
        return datetime.strptime(date_str, "%b-%y")
    except:
        return datetime(1900, 1, 1)  # Default for invalid dates

def sort_month_columns(columns):
    """Sort month columns chronologically (Oct-25, Nov-25, Dec-25, etc.)"""
    month_cols = [c for c in columns if re.match(r'^[A-Za-z]{3}-\d{2}$', str(c))]
    
    # Sort by date
    month_cols.sort(key=lambda x: parse_month_year(x))
    
    return month_cols

# ============================================================================
# 2. DATA LOADER WITH ENHANCED ERROR HANDLING
# ============================================================================
@st.cache_data(ttl=600, show_spinner="Loading data from Google Sheets...")
def load_data_v5(start_date_str, all_months=False):
    """
    Load and process data from Google Sheets
    all_months: If True, load all 12 months for adjustment
    """
    try:
        gs = GSheetConnector()
        if not gs.client:
            return pd.DataFrame()
        
        # Load data
        with st.spinner("Fetching sales history..."):
            sales_df = gs.get_sheet_data("sales_history")
        
        with st.spinner("Fetching ROFO data..."):
            rofo_df = gs.get_sheet_data("rofo_current")
        
        with st.spinner("Fetching stock data..."):
            stock_df = gs.get_sheet_data("stock_onhand")
        
        # Check if essential data exists
        if sales_df.empty:
            st.error("⚠️ Sales history data is empty")
            return pd.DataFrame()
        if rofo_df.empty:
            st.error("⚠️ ROFO data is empty")
            return pd.DataFrame()
        
        # Standardize column names
        for df in [sales_df, rofo_df, stock_df]:
            if not df.empty:
                df.columns = [str(c).strip() for c in df.columns]
        
        # Calculate horizon months
        try:
            start_date = datetime.strptime(start_date_str, "%b-%y")
            
            if all_months:
                # Show all 12 months for adjustment
                horizon_months = [(start_date + relativedelta(months=i)).strftime("%b-%y") for i in range(12)]
                adjustment_months = horizon_months  # All months are adjustable
            else:
                # Default: first 3 months for adjustment, next 9 for display only
                horizon_months = [(start_date + relativedelta(months=i)).strftime("%b-%y") for i in range(12)]
                adjustment_months = horizon_months[:3]  # Only first 3 are adjustable
            
            st.session_state.horizon_months = horizon_months
            st.session_state.adjustment_months = adjustment_months
            st.session_state.all_months_mode = all_months
            
        except:
            st.error("Invalid date format")
            return pd.DataFrame()
        
        # Process floor price
        if 'floor_price' in rofo_df.columns:
            rofo_df['floor_price'] = rofo_df['floor_price'].apply(clean_currency)
        else:
            floor_cols = [c for c in rofo_df.columns if 'floor' in c.lower()]
            if floor_cols:
                rofo_df.rename(columns={floor_cols[0]: 'floor_price'}, inplace=True)
                rofo_df['floor_price'] = rofo_df['floor_price'].apply(clean_currency)
            else:
                rofo_df['floor_price'] = 0
        
        # Standardize column names
        key_map = {
            'Product Name': 'Product_Name', 
            'Brand Group': 'Brand_Group', 
            'SKU Tier': 'SKU_Tier',
            'product name': 'Product_Name',
            'brand group': 'Brand_Group',
            'sku tier': 'SKU_Tier'
        }
        
        for df in [sales_df, rofo_df]:
            df.rename(columns=lambda x: key_map.get(x, x), inplace=True)
        
        # Identify common keys for merging
        possible_keys = ['sku_code', 'Product_Name', 'Brand', 'Brand_Group', 'SKU_Tier', 'Channel']
        valid_keys = [k for k in possible_keys if k in sales_df.columns and k in rofo_df.columns]
        
        if not valid_keys:
            st.error("❌ No common columns found for merging sales and ROFO data")
            return pd.DataFrame()
        
        # Get sales date columns and sort them chronologically
        sales_date_cols = [c for c in sales_df.columns if re.search(r'^[A-Za-z]{3}-\d{2}$', str(c))]
        sales_date_cols = sort_month_columns(sales_date_cols)
        
        # Get LAST 3 months for L3M calculation (correct order: Oct-25, Nov-25, Dec-25)
        if len(sales_date_cols) >= 3:
            l3m_cols = sales_date_cols[-3:]  # Last 3 months in chronological order
        else:
            l3m_cols = sales_date_cols
        
        if l3m_cols:
            # Calculate L3M average correctly
            sales_df['L3M_Avg'] = sales_df[l3m_cols].applymap(
                lambda x: clean_currency(x) if pd.notna(x) else 0
            ).mean(axis=1).round(0)
        else:
            sales_df['L3M_Avg'] = 0
        
        # Prepare sales subset
        sales_subset_cols = valid_keys + ['L3M_Avg']
        if l3m_cols:
            sales_subset_cols.extend(l3m_cols)
        sales_subset = sales_df[sales_subset_cols].copy()
        
        # Prepare ROFO subset
        rofo_cols_to_fetch = valid_keys.copy()
        for extra in ['Channel', 'Product_Focus', 'floor_price', 'category', 'sub_category']:
            if extra in rofo_df.columns and extra not in rofo_cols_to_fetch:
                rofo_cols_to_fetch.append(extra)
        
        # Map month columns
        month_mapping = {}
        missing_months = []
        for m in horizon_months:
            real_col = find_matching_column(m, rofo_df.columns)
            if real_col:
                month_mapping[m] = real_col
                if real_col not in rofo_cols_to_fetch:
                    rofo_cols_to_fetch.append(real_col)
            else:
                missing_months.append(m)
        
        st.session_state.missing_months = missing_months
        
        rofo_subset = rofo_df[rofo_cols_to_fetch].copy()
        inv_map = {v: k for k, v in month_mapping.items()}
        rofo_subset.rename(columns=inv_map, inplace=True)
        
        # Merge data
        merged_df = pd.merge(sales_subset, rofo_subset, on=valid_keys, how='inner')
        
        if merged_df.empty:
            st.warning("⚠️ No matching records found after merging sales and ROFO data")
            return pd.DataFrame()
        
        # Handle missing columns
        if 'Product_Focus' not in merged_df.columns: 
            merged_df['Product_Focus'] = ""
        else: 
            merged_df['Product_Focus'] = merged_df['Product_Focus'].fillna("").astype(str)
        
        if 'floor_price' not in merged_df.columns: 
            merged_df['floor_price'] = 0
        else: 
            merged_df['floor_price'] = merged_df['floor_price'].fillna(0)
        
        # Ensure all horizon months exist
        for m in horizon_months:
            if m not in merged_df.columns:
                merged_df[m] = 0
            else:
                merged_df[m] = merged_df[m].apply(clean_currency)
        
        # Merge stock data
        if not stock_df.empty and 'sku_code' in stock_df.columns:
            stock_col = next((c for c in ['Stock_Qty', 'stock_qty', 'Stock On Hand', 'stock_on_hand'] 
                            if c in stock_df.columns), stock_df.columns[1] if len(stock_df.columns) > 1 else 'stock_qty')
            
            stock_df_clean = stock_df[['sku_code', stock_col]].copy()
            stock_df_clean.columns = ['sku_code', 'Stock_Qty']
            stock_df_clean['Stock_Qty'] = stock_df_clean['Stock_Qty'].apply(clean_currency)
            
            merged_df = pd.merge(merged_df, stock_df_clean, on='sku_code', how='left')
        else:
            merged_df['Stock_Qty'] = 0
        
        merged_df['Stock_Qty'] = merged_df['Stock_Qty'].fillna(0)
        
        # Calculate month cover
        merged_df['Month_Cover'] = np.where(
            merged_df['L3M_Avg'] > 0,
            (merged_df['Stock_Qty'] / merged_df['L3M_Avg']).round(1),
            0
        )
        merged_df['Month_Cover'] = merged_df['Month_Cover'].replace([np.inf, -np.inf], 0)
        
        # Initialize consensus columns for adjustment months
        adjustment_months = st.session_state.get('adjustment_months', [])
        for m in adjustment_months:
            merged_df[f'Cons_{m}'] = merged_df[m]
        
        # Add summary columns
        merged_df['Total_Forecast'] = merged_df[adjustment_months].sum(axis=1)
        
        return merged_df
        
    except Exception as e:
        st.error(f"❌ Error Loading Data: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return pd.DataFrame()

def calculate_pct(df, months):
    """Calculate percentage compared to L3M average"""
    df_calc = df.copy()
    for m in months:
        if f'Cons_{m}' in df_calc.columns:
            # Avoid division by zero
            mask = df_calc['L3M_Avg'] > 0
            df_calc.loc[mask, f'{m}_%'] = (
                df_calc.loc[mask, f'Cons_{m}'] / df_calc.loc[mask, 'L3M_Avg'] * 100
            ).round(1)
            df_calc.loc[~mask, f'{m}_%'] = 100  # Default if no L3M data
    return df_calc

# ============================================================================
# SIDEBAR WITH IMPROVED UX - PERBAIKAN: TAMBAH OPTION ALL MONTHS
# ============================================================================
with st.sidebar:
    st.image("https://www.erhagroup.com/assets/img/logo-erha.png", width=150)
    st.markdown("### ⚙️ Planning Cycle Configuration")
    
    curr_date = datetime.now()
    
    # Generate options for forecast start
    start_options = []
    for i in range(-2, 4):  # -2 months to +3 months from current
        option_date = curr_date + relativedelta(months=i)
        start_options.append(option_date.strftime("%b-%y"))
    
    # Default selection logic
    default_idx = 1  # Default to current month
    if curr_date.day >= 15:  # If past mid-month, default to next month
        default_idx = 2
    
    selected_start_str = st.selectbox(
        "Forecast Start Month",
        options=start_options,
        index=default_idx,
        help="Select the starting month for your forecasting horizon"
    )
    
    # PERBAIKAN: Tambah option untuk show all months
    show_all_months = st.checkbox(
        "📅 Show & Adjust All 12 Months",
        value=False,
        help="If checked, all 12 months will be editable. Default: only first 3 months editable"
    )
    
    # Calculate cycle months based on selection
    try:
        start_date = datetime.strptime(selected_start_str, "%b-%y")
        
        if show_all_months:
            # All 12 months are adjustable
            horizon_months = [(start_date + relativedelta(months=i)).strftime("%b-%y") for i in range(12)]
            adjustment_months = horizon_months  # All months adjustable
            cycle_months = horizon_months  # For display purposes
            st.session_state.adjustment_months = adjustment_months
            st.info(f"**Planning Cycle:** ALL 12 Months ({horizon_months[0]} - {horizon_months[-1]})")
        else:
            # Only first 3 months adjustable
            horizon_months = [(start_date + relativedelta(months=i)).strftime("%b-%y") for i in range(12)]
            adjustment_months = horizon_months[:3]  # Only first 3 adjustable
            cycle_months = adjustment_months  # For display purposes
            st.session_state.adjustment_months = adjustment_months
            st.info(f"""
            **Planning Cycle:**  
            🗓️ **Editable (M1-M3):** {cycle_months[0]}, {cycle_months[1]}, {cycle_months[2]}  
            📋 **View Only (M4-M12):** {horizon_months[3]} - {horizon_months[-1]}
            """)
        
        st.session_state.horizon_months = horizon_months
        st.session_state.all_months_mode = show_all_months
        
    except:
        st.error("Invalid date selected")
    
    st.markdown("---")
    
    # Data management
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    with col2:
        if st.button("📊 Clear Cache", use_container_width=True):
            st.cache_data.clear()
            st.success("Cache cleared!")
    
    with st.expander("🔍 Data Quality Check", expanded=False):
        if 'missing_months' in st.session_state and st.session_state.missing_months:
            st.error(f"❌ Missing months in ROFO: {', '.join(st.session_state.missing_months)}")
        else:
            st.success("✅ All months mapped successfully")

# ============================================================================
# MAIN DASHBOARD
# ============================================================================
st.markdown(f"""
<div class="main-header">
    <h2>📊 ERHA S&OP Dashboard V5.5</h2>
    <p>Forecast Horizon: <b>{horizon_months[0]} - {horizon_months[-1]}</b> | Editable: <b>{', '.join(adjustment_months)}</b></p>
</div>
""", unsafe_allow_html=True)

# Load data dengan parameter all_months
all_df = load_data_v5(selected_start_str, show_all_months)

if all_df.empty:
    st.error("""
    ⚠️ **No data loaded.** Possible issues:
    1. Google Sheets connection failed
    2. Required worksheets are empty
    3. No matching data between sales and ROFO
    
    Check the sidebar debugger for more details.
    """)
    st.stop()

# Display quick stats
total_skus = len(all_df)
total_brands = all_df['Brand'].nunique() if 'Brand' in all_df.columns else 0
total_forecast = all_df['Total_Forecast'].sum() if 'Total_Forecast' in all_df.columns else 0

with stylable_container(
    key="summary_stats",
    css_styles="""
    {
        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid #e2e8f0;
        margin-bottom: 1.5rem;
    }
    """
):
    stat1, stat2, stat3, stat4 = st.columns(4)
    with stat1:
        st.metric("📦 Total SKUs", f"{total_skus:,}")
    with stat2:
        st.metric("🏷️ Brands", f"{total_brands:,}")
    with stat3:
        # Get L3M months from sales history (correct order)
        sales_date_cols = [c for c in all_df.columns if re.search(r'^[A-Za-z]{3}-\d{2}$', str(c)) 
                          and not c.startswith('Cons_') and '%' not in c]
        sales_date_cols = sort_month_columns(sales_date_cols)
        l3m_months = sales_date_cols[-3:] if len(sales_date_cols) >= 3 else sales_date_cols
        l3m_label = f"L3M ({', '.join(l3m_months)})" if l3m_months else "L3M Avg"
        st.metric(f"💰 {l3m_label}", f"{all_df['L3M_Avg'].sum():,.0f}")
    with stat4:
        st.metric("📈 Total Forecast", f"{total_forecast:,.0f}")

# FILTERS SECTION - PERBAIKAN: TAMBAH FILTER BRAND & CHANNEL
with stylable_container(
    key="filters", 
    css_styles="""
    {
        background: white;
        padding: 1.25rem;
        border-radius: 10px;
        border: 1px solid #E2E8F0;
        margin-bottom: 1.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    """
):
    st.markdown("### 🔍 Data Filters")
    
    # PERBAIKAN: Tambah filter untuk Brand dan Channel secara spesifik untuk adjustment
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        channels = ["ALL"] + sorted(all_df['Channel'].dropna().unique().tolist()) if 'Channel' in all_df.columns else ["ALL"]
        sel_channel = st.selectbox("🛒 Channel", channels, help="Filter by sales channel")
    
    with col2:
        brands = ["ALL"] + sorted(all_df['Brand'].dropna().unique().tolist()) if 'Brand' in all_df.columns else ["ALL"]
        sel_brand = st.selectbox("🏷️ Brand", brands, help="Filter by brand")
    
    with col3:
        b_groups = ["ALL"] + sorted(all_df['Brand_Group'].dropna().unique().tolist()) if 'Brand_Group' in all_df.columns else ["ALL"]
        sel_group = st.selectbox("📦 Brand Group", b_groups, help="Filter by brand group")
    
    with col4:
        tiers = ["ALL"] + sorted(all_df['SKU_Tier'].dropna().unique().tolist()) if 'SKU_Tier' in all_df.columns else ["ALL"]
        sel_tier = st.selectbox("💎 Tier", tiers, help="Filter by SKU tier")
    
    with col5:
        cover_options = ["ALL", "Overstock (>1.5)", "Healthy (0.5-1.5)", "Low (<0.5)", "Out of Stock (0)"]
        sel_cover = st.selectbox("📦 Stock Cover", cover_options, help="Filter by month's cover stock")
    
    with col6:
        # PERBAIKAN: Filter untuk Product Focus
        focus_options = ["ALL", "Yes", "No"]
        sel_focus = st.selectbox("🎯 Product Focus", focus_options, help="Filter by product focus status")

# Apply filters
filtered_df = all_df.copy()

if sel_channel != "ALL" and 'Channel' in filtered_df.columns:
    filtered_df = filtered_df[filtered_df['Channel'] == sel_channel]

if sel_brand != "ALL" and 'Brand' in filtered_df.columns:
    filtered_df = filtered_df[filtered_df['Brand'] == sel_brand]

if sel_group != "ALL" and 'Brand_Group' in filtered_df.columns:
    filtered_df = filtered_df[filtered_df['Brand_Group'] == sel_group]

if sel_tier != "ALL" and 'SKU_Tier' in filtered_df.columns:
    filtered_df = filtered_df[filtered_df['SKU_Tier'] == sel_tier]

if sel_cover != "ALL":
    if sel_cover == "Overstock (>1.5)":
        filtered_df = filtered_df[filtered_df['Month_Cover'] > 1.5]
    elif sel_cover == "Healthy (0.5-1.5)":
        filtered_df = filtered_df[(filtered_df['Month_Cover'] >= 0.5) & (filtered_df['Month_Cover'] <= 1.5)]
    elif sel_cover == "Low (<0.5)":
        filtered_df = filtered_df[filtered_df['Month_Cover'] < 0.5]
    elif sel_cover == "Out of Stock (0)":
        filtered_df = filtered_df[filtered_df['Month_Cover'] == 0]

if sel_focus != "ALL" and 'Product_Focus' in filtered_df.columns:
    if sel_focus == "Yes":
        filtered_df = filtered_df[filtered_df['Product_Focus'].str.contains('Yes', case=False, na=False)]
    else:
        filtered_df = filtered_df[~filtered_df['Product_Focus'].str.contains('Yes', case=False, na=False)]

# Display filter results
filtered_skus = len(filtered_df)
if filtered_skus < total_skus:
    st.success(f"✅ Showing {filtered_skus:,} of {total_skus:,} SKUs ({filtered_skus/total_skus*100:.1f}%)")

# Create tabs
tab1, tab2, tab3 = st.tabs([
    "📝 Forecast Worksheet", 
    "📈 Analytics Dashboard", 
    "📊 Summary Reports" 
])

# ============================================================================
# TAB 1: FORECAST WORKSHEET - PERBAIKAN: TAMPILKAN SEMUA BULAN SESUAI SETTING
# ============================================================================
with tab1:
    if filtered_df.empty:
        st.warning("⚠️ No data matches the selected filters. Please adjust your filters.")
    else:
        # Color code legend
        with st.expander("🎨 **Color Coding Legend**", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("""
                **Cell Background Colors:**
                - 🟢 **Product Focus:** Priority SKUs (Green highlight)
                - 🔵 **Acne Products:** Light blue background
                - 🟢 **Tru Skincare:** Light green background
                - 🟡 **Hair Products:** Light yellow background
                - 🟣 **Age Products:** Light purple background
                - 🟣 **His Products:** Light lavender background
                """)
            
            with col2:
                st.markdown("""
                **Conditional Formatting:**
                - 🔴 **High Stock (>1.5mo):** Pink highlight
                - 🟠 **Low % (<90%):** Orange (below L3M avg)
                - 🔴 **High % (>130%):** Red (above L3M avg)
                - 🔵 **Editable Cells:** Blue border
                """)
        
        # Process data for worksheet
        edit_df = filtered_df.copy()
        
        # PERBAIKAN: Calculate percentage hanya untuk adjustment months
        adjustment_months = st.session_state.get('adjustment_months', [])
        edit_df = calculate_pct(edit_df, adjustment_months)
        
        # Define columns to display
        base_cols = ['sku_code', 'Product_Name', 'Channel', 'Brand', 'SKU_Tier', 'Product_Focus', 'floor_price']
        
        # Get horizon months
        horizon_months = st.session_state.get('horizon_months', [])
        
        # Get historical columns (last 3 months before horizon) - PERBAIKAN: SORT CHRONOLOGICAL
        hist_cols = [c for c in edit_df.columns if re.search(r'^[A-Za-z]{3}-\d{2}$', str(c)) 
                    and c not in horizon_months 
                    and not c.startswith('Cons_') 
                    and '%' not in c]
        hist_cols = sort_month_columns(hist_cols)
        
        if hist_cols:
            hist_cols = hist_cols[-3:]  # Last 3 historical months in correct order
        
        # Build column list
        display_cols = base_cols.copy()
        
        if hist_cols:
            display_cols.extend(hist_cols)
        
        display_cols.extend(['L3M_Avg', 'Stock_Qty', 'Month_Cover'])
        display_cols.extend(horizon_months)
        
        # PERBAIKAN: Tambah persentase hanya untuk adjustment months
        display_cols.extend([f'{m}_%' for m in adjustment_months])
        
        # PERBAIKAN: Tambah consensus columns untuk semua adjustment months
        display_cols.extend([f'Cons_{m}' for m in adjustment_months])
        
        # Remove duplicates and ensure columns exist
        display_cols = list(dict.fromkeys(display_cols))
        display_cols = [c for c in display_cols if c in edit_df.columns]
        
        # Prepare dataframe for AgGrid
        ag_df = edit_df[display_cols].copy()
        
        # JavaScript styling functions
        js_sku_focus = JsCode("""
            function(params) {
                if (params.data.Product_Focus && params.data.Product_Focus.toString().toLowerCase() === 'yes') {
                    return {
                        'backgroundColor': '#CCFBF1',
                        'color': '#0F766E',
                        'fontWeight': 'bold',
                        'borderLeft': '4px solid #14B8A6'
                    };
                }
                return null;
            }
        """)
        
        js_brand = JsCode("""
            function(params) {
                if (!params.value) return null;
                const brand = params.value.toString().toLowerCase();
                
                if (brand.includes('acne')) return {
                    'backgroundColor': '#E0F2FE',
                    'color': '#0284C7',
                    'fontWeight': '600'
                };
                
                if (brand.includes('tru')) return {
                    'backgroundColor': '#DCFCE7',
                    'color': '#16A34A',
                    'fontWeight': '600'
                };
                
                if (brand.includes('hair')) return {
                    'backgroundColor': '#FEF3C7',
                    'color': '#D97706',
                    'fontWeight': '600'
                };
                
                if (brand.includes('age')) return {
                    'backgroundColor': '#E0E7FF',
                    'color': '#4F46E5',
                    'fontWeight': '600'
                };
                
                if (brand.includes('his')) return {
                    'backgroundColor': '#F3E8FF',
                    'color': '#7C3AED',
                    'fontWeight': '600'
                };
                
                return null;
            }
        """)
        
        js_channel = JsCode("""
            function(params) {
                if (!params.value) return null;
                const channel = params.value.toString();
                
                if (channel === 'E-commerce') return {
                    'color': '#EA580C',
                    'fontWeight': 'bold'
                };
                
                if (channel === 'Reseller') return {
                    'color': '#059669',
                    'fontWeight': 'bold'
                };
                
                return null;
            }
        """)
        
        js_cover = JsCode("""
            function(params) {
                if (params.value > 1.5) {
                    return {
                        'backgroundColor': '#FCE7F3',
                        'color': '#BE185D',
                        'fontWeight': 'bold'
                    };
                }
                return null;
            }
        """)
        
        js_pct = JsCode("""
            function(params) {
                if (params.value < 90) {
                    return {
                        'backgroundColor': '#FFEDD5',
                        'color': '#9A3412',
                        'fontWeight': 'bold'
                    };
                }
                
                if (params.value > 130) {
                    return {
                        'backgroundColor': '#FEE2E2',
                        'color': '#991B1B',
                        'fontWeight': 'bold'
                    };
                }
                
                return {
                    'color': '#374151'
                };
            }
        """)
        
        js_edit = JsCode("""
            function(params) {
                return {
                    'backgroundColor': '#EFF6FF',
                    'border': '2px solid #60A5FA',
                    'fontWeight': 'bold',
                    'color': '#1E40AF'
                };
            }
        """)
        
        # Configure GridOptions
        gb = GridOptionsBuilder.from_dataframe(ag_df)
        
        # Grid configuration
        gb.configure_grid_options(
            rowHeight=38,
            headerHeight=45,
            suppressHorizontalScroll=False,
            domLayout='normal',
            enableRangeSelection=True,
            suppressRowClickSelection=False,
            rowSelection='single',
            animateRows=True,
            suppressColumnMoveAnimation=False,
            enableCellTextSelection=True,
            ensureDomOrder=True
        )
        
        # Default column configuration
        gb.configure_default_column(
            resizable=True,
            filterable=True,
            sortable=True,
            editable=False,
            minWidth=85,
            maxWidth=180,
            flex=1,
            suppressSizeToFit=False,
            autoHeight=False,
            wrapText=False
        )
        
        # Configure specific columns
        # Pinned columns (left side)
        gb.configure_column("sku_code",
                          pinned="left",
                          width=95,
                          maxWidth=110,
                          cellStyle=js_sku_focus,
                          suppressSizeToFit=True,
                          headerName="SKU Code")
        
        gb.configure_column("Product_Name",
                          pinned="left",
                          minWidth=180,
                          maxWidth=300,
                          flex=2,
                          suppressSizeToFit=False,
                          headerName="Product Name",
                          tooltipField="Product_Name")
        
        gb.configure_column("Channel",
                          pinned="left",
                          width=110,
                          maxWidth=130,
                          cellStyle=js_channel,
                          suppressSizeToFit=True,
                          headerName="Channel")
        
        # Hidden columns
        gb.configure_column("Product_Focus", hide=True)
        gb.configure_column("floor_price", hide=True)
        
        # Brand column with coloring
        gb.configure_column("Brand",
                          width=110,
                          maxWidth=140,
                          cellStyle=js_brand,
                          flex=1,
                          suppressSizeToFit=False,
                          headerName="Brand")
        
        # Month cover
        gb.configure_column("Month_Cover",
                          width=95,
                          maxWidth=110,
                          cellStyle=js_cover,
                          type=["numericColumn"],
                          valueFormatter="params.value ? params.value.toFixed(1) : ''",
                          suppressSizeToFit=True,
                          headerName="Month Cover")
        
        # PERBAIKAN: Sembunyikan bulan-bulan yang tidak dalam adjustment jika mode default
        if not show_all_months:
            # Dalam mode default, sembunyikan bulan M4-M12 dari horizon
            for m in horizon_months:
                if m not in adjustment_months:
                    gb.configure_column(m, hide=True)
        
        # Configure numeric columns (historical and forecast months)
        for col in display_cols:
            if col not in ['sku_code', 'Product_Name', 'Channel', 'Brand', 'SKU_Tier', 
                          'Month_Cover', 'Product_Focus', 'floor_price'] and '%' not in col:
                gb.configure_column(col,
                                  type=["numericColumn"],
                                  valueFormatter="params.value ? params.value.toLocaleString() : ''",
                                  minWidth=95,
                                  maxWidth=130,
                                  flex=1,
                                  suppressSizeToFit=False)
        
        # PERBAIKAN: Percentage columns hanya untuk adjustment months
        for m in adjustment_months:
            pct_col = f'{m}_%'
            if pct_col in display_cols:
                gb.configure_column(pct_col,
                                  headerName=f"{m} %",
                                  type=["numericColumn"],
                                  valueFormatter="params.value ? params.value.toFixed(1) + '%' : ''",
                                  cellStyle=js_pct,
                                  minWidth=85,
                                  maxWidth=100,
                                  suppressSizeToFit=True)
        
        # PERBAIKAN: Editable consensus columns untuk SEMUA adjustment months
        for m in adjustment_months:
            cons_col = f'Cons_{m}'
            if cons_col in display_cols:
                gb.configure_column(cons_col,
                                  headerName=f"✏️ {m}",
                                  editable=True,
                                  cellStyle=js_edit,
                                  width=105,
                                  maxWidth=120,
                                  pinned="right",
                                  type=["numericColumn"],
                                  valueFormatter="params.value ? params.value.toLocaleString() : ''",
                                  suppressSizeToFit=True)
        
        # Configure selection
        gb.configure_selection('single',
                             use_checkbox=False,
                             pre_selected_rows=[],
                             suppressRowDeselection=False)
        
        # Build grid options
        grid_options = gb.build()
        
        # Display the grid
        mode_label = "ALL 12 Months" if show_all_months else f"First {len(adjustment_months)} Months"
        st.markdown(f"**Worksheet:** Editing consensus for {mode_label} ({len(ag_df):,} SKUs)")
        
        with stylable_container(
            key="worksheet_container",
            css_styles="""
            {
                height: 68vh !important;
                min-height: 500px;
                max-height: 800px;
                overflow: hidden;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                padding: 10px;
                background-color: white;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
                margin-bottom: 1.5rem;
            }
            """
        ):
            grid_response = AgGrid(
                ag_df,
                gridOptions=grid_options,
                allow_unsafe_jscode=True,
                update_mode=GridUpdateMode.VALUE_CHANGED,
                height=600,
                theme='alpine',
                key='forecast_worksheet',
                use_container_width=True,
                fit_columns_on_grid_load=True,
                enable_enterprise_modules=False,
                reload_data=False,
                try_to_convert_back_to_original_types=False,
                allow_unsafe_html=True
            )
        
        # Get updated data
        updated_df = pd.DataFrame(grid_response['data'])
        
        # Save and export section
        st.markdown("---")
        st.markdown("### 💾 Data Management")
        
        col_save, col_push, col_export, col_info = st.columns([1, 1, 1, 2])
        
        with col_save:
            if st.button("💾 **Save Locally**", type="primary", use_container_width=True):
                st.session_state.edited_v5 = updated_df.copy()
                st.success("✅ Data saved to session state!")
        
        with col_push:
            if st.button("☁️ **Push to GSheets**", type="secondary", use_container_width=True):
                if 'edited_v5' not in st.session_state:
                    st.warning("⚠️ Please save locally first!")
                else:
                    with st.spinner("Uploading to Google Sheets..."):
                        # Prepare data for export
                        keep_cols = ['sku_code', 'Product_Name', 'Channel', 'Brand', 'SKU_Tier', 'Product_Focus']
                        keep_cols.extend([f'Cons_{m}' for m in adjustment_months])
                        
                        final_df = st.session_state.edited_v5[keep_cols].copy()
                        final_df['Last_Update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        final_df['Updated_By'] = "S&OP Dashboard"
                        
                        gs = GSheetConnector()
                        success, message = gs.save_data(final_df, "consensus_rofo")
                        
                        if success:
                            st.balloons()
                            st.success("✅ Successfully uploaded to Google Sheets!")
                        else:
                            st.error(f"❌ {message}")
        
        with col_export:
            if st.button("📥 **Export CSV**", use_container_width=True):
                if 'edited_v5' in st.session_state:
                    csv_data = st.session_state.edited_v5.to_csv(index=False)
                    st.download_button(
                        label="Download CSV",
                        data=csv_data,
                        file_name=f"forecast_consensus_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv"
                    )
        
        with col_info:
            # Calculate totals for adjustment months
            total_consensus = 0
            for m in adjustment_months:
                cons_col = f'Cons_{m}'
                if cons_col in updated_df.columns:
                    total_consensus += updated_df[cons_col].sum()
            
            st.metric(
                "📊 **Total Consensus**",
                f"{total_consensus:,.0f}",
                f"Adjustable Months: {', '.join(adjustment_months[:3])}" + ("..." if len(adjustment_months) > 3 else "")
            )

# ============================================================================
# TAB 2: ANALYTICS DASHBOARD - FULL VERSION (FORMATTED & ERROR-FREE)
# ============================================================================
with tab2:
    st.markdown("### 📊 Strategic Forecast Analytics")
    
    # 1. Data Preparation Logic
    base_df = updated_df if 'updated_df' in locals() and not updated_df.empty else filtered_df
    
    if base_df.empty:
        st.warning("⚠️ Belum ada data untuk dianalisis. Silakan sesuaikan filter atau muat data.")
    else:
        # Identifikasi bulan aktif
        full_horizon = st.session_state.get('horizon_months', [])
        active_months = [m for m in full_horizon if "-26" in m] if show_2026_only else full_horizon
        
        # Pre-calculating Volume & Value columns secara dinamis
        calc_df = base_df.copy()
        qty_cols = []
        val_cols = []
        
        for m in active_months:
            source_col = f'Cons_{m}' if f'Cons_{m}' in calc_df.columns else m
            q_col = f'Qty_{m}'
            v_col = f'Val_{m}'
            
            calc_df[q_col] = pd.to_numeric(calc_df[source_col], errors='coerce').fillna(0)
            calc_df[v_col] = calc_df[q_col] * calc_df.get('floor_price', 0)
            
            qty_cols.append(q_col)
            val_cols.append(v_col)

        # --- TOP METRICS SECTION ---
        total_vol = calc_df[qty_cols].sum().sum()
        total_rev = calc_df[val_cols].sum().sum()
        
        # Perhitungan Growth vs L3M (M1-M3)
        m1_m3_target = adjustment_months[:3]
        m1_m3_qty_cols = [f'Qty_{m}' for m in m1_m3_target if f'Qty_{m}' in calc_df.columns]
        m1_m3_vol = calc_df[m1_m3_qty_cols].sum().sum()
        l3m_baseline = calc_df['L3M_Avg'].sum() * len(m1_m3_qty_cols)
        growth_vs_l3m = ((m1_m3_vol / l3m_baseline) - 1) if l3m_baseline > 0 else 0

        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("📦 Projected Volume", f"{total_vol:,.0f} units")
        with m2:
            st.metric("💰 Projected Revenue", f"Rp {total_rev:,.0f}")
        with m3:
            st.metric("📈 Growth (M1-M3 vs L3M)", f"{growth_vs_l3m:+.1%}")
        
        style_metric_cards(background_color="#FFFFFF", border_left_color="#1E40AF")

        st.markdown("---")

        # --- CHART CONTROLS ---
        col_c1, col_c2 = st.columns([3, 1])
        with col_c1:
            chart_view = st.radio("**Select Visualization:**", ["Brand Trends", "Channel Mix", "Aggregate Trend"], horizontal=True)
        with col_c2:
            val_mode = st.toggle("💰 Show IDR Value", value=False)

        prefix = "Val_" if val_mode else "Qty_"
        y_label = "Value (IDR)" if val_mode else "Volume (Units)"

        # --- VISUALIZATIONS ---
        if chart_view == "Brand Trends":
            # Baris 1: Grafik Garis
            plot_list = []
            for m in active_months:
                temp = calc_df.groupby('Brand')[f'{prefix}{m}'].sum().reset_index()
                temp['Month'] = m
                temp.columns = ['Brand', 'Value', 'Month']
                plot_list.append(temp)
            
            df_plot = pd.concat(plot_list)
            fig = px.line(df_plot, x='Month', y='Value', color='Brand', markers=True)
            fig.update_layout(yaxis=dict(tickformat=",.0f"), hovermode="x unified")
            fig.update_traces(hovertemplate="%{y:,.0f}")
            st.plotly_chart(fig, use_container_width=True)

            # Baris 2: Tabel Ranking (DENGAN KOMA RIBUAN)
            st.markdown("##### 🏆 Brand Ranking Summary")
            brand_rank = []
            for b in calc_df['Brand'].unique():
                b_df = calc_df[calc_df['Brand'] == b]
                brand_rank.append({
                    "Brand": b,
                    "Total Volume": b_df[qty_cols].sum().sum(),
                    "Total Revenue": b_df[val_cols].sum().sum()
                })
            
            df_rank = pd.DataFrame(brand_rank).sort_values("Total Revenue", ascending=False)
            st.dataframe(
                df_rank,
                column_config={
                    "Total Volume": st.column_config.NumberColumn("Total Volume", format="%d"),
                    "Total Revenue": st.column_config.NumberColumn("Total Revenue", format="Rp %,.0f")
                },
                hide_index=True,
                use_container_width=True
            )

        elif chart_view == "Channel Mix":
            chan_list = []
            for m in active_months:
                temp = calc_df.groupby('Channel')[f'{prefix}{m}'].sum().reset_index()
                temp['Month'] = m
                temp.columns = ['Channel', 'Value', 'Month']
                chan_list.append(temp)
            
            df_chan = pd.concat(chan_list)
            fig = px.bar(df_chan, x='Month', y='Value', color='Channel', barmode='group')
            fig.update_layout(yaxis=dict(tickformat=",.0f"))
            fig.update_traces(hovertemplate="%{y:,.0f}")
            st.plotly_chart(fig, use_container_width=True)

        else: # Aggregate Trend
            agg_list = [{"Month": m, "Value": calc_df[f'{prefix}{m}'].sum()} for m in active_months]
            df_agg = pd.DataFrame(agg_list)
            fig = px.area(df_agg, x='Month', y='Value')
            fig.update_layout(yaxis=dict(tickformat=",.0f"))
            fig.update_traces(hovertemplate="%{y:,.0f}", line_color='#1E40AF', fillcolor="rgba(30, 64, 175, 0.2)")
            st.plotly_chart(fig, use_container_width=True)

        # --- INSIGHTS ---
        with st.expander("💡 Key Strategic Insights", expanded=True):
            # Analisis Top SKU dinamis
            calc_df['Analytic_Total'] = calc_df[qty_cols].sum(axis=1)
            top_sku_row = calc_df.loc[calc_df['Analytic_Total'].idxmax()]
            
            st.write(f"🌟 **Top Performer:** SKU `{top_sku_row['Product_Name']}` berkontribusi sebesar **{top_sku_row['Analytic_Total']:,.0f} units**.")
            
            oos_count = len(calc_df[calc_df['Month_Cover'] < 0.5])
            if oos_count > 0:
                st.error(f"⚠️ **Inventory Risk:** Terdapat {oos_count} SKU dengan stok kritis di bawah 0.5 bulan.")
            else:
                st.success("✅ **Supply Health:** Stok untuk semua SKU terpantau aman (MoS > 0.5).")
# ============================================================================
# TAB 3: SUMMARY REPORTS - EXECUTIVE PRESENTATION (SAFE MODE)
# ============================================================================
with tab3:
    st.markdown("### 📋 Executive Summary Reports")
    
    report_df = updated_df if 'updated_df' in locals() and not updated_df.empty else filtered_df
    
    if report_df.empty:
        st.warning("Data kosong. Silakan sesuaikan filter.")
    else:
        # --- PERBAIKAN FATAL: Hitung ulang Total_Forecast agar tidak KeyError ---
        adj_cols = [f'Cons_{m}' for m in adjustment_months if f'Cons_{m}' in report_df.columns]
        # Jika kolom Cons_ belum ada (belum diedit), gunakan kolom bulan asli
        if not adj_cols:
            adj_cols = [m for m in adjustment_months if m in report_df.columns]
        
        # Buat kolom temporary untuk sorting di Tab 3
        report_df = report_df.copy()
        report_df['Temp_Total'] = report_df[adj_cols].sum(axis=1)
        
        # --- Metrics Calculation ---
        total_f_qty = report_df['Temp_Total'].sum()
        total_l3m_qty = (report_df['L3M_Avg'].sum() * len(adjustment_months))
        growth_pct = ((total_f_qty / total_l3m_qty) - 1) * 100 if total_l3m_qty > 0 else 0

        r1, r2 = st.columns([2, 1])
        with r1:
            st.info(f"💡 **S&OP Perspective:** Forecast periode ini menunjukkan tren **{'Naik' if growth_pct > 0 else 'Turun'} {abs(growth_pct):.1f}%** dibandingkan rata-rata penjualan 3 bulan terakhir.")
        
        # 1. Top 10 SKU (Menggunakan Temp_Total agar tidak error)
        st.markdown("#### 🎯 Focus Area: Top SKU Contribution")
        top_10_skus = report_df.nlargest(10, 'Temp_Total')
        
        st.dataframe(
            top_10_skus[['sku_code', 'Product_Name', 'Brand', 'L3M_Avg', 'Temp_Total', 'Month_Cover']],
            column_config={
                "Temp_Total": st.column_config.NumberColumn("Total Forecast", format="%d 📦"),
                "L3M_Avg": st.column_config.NumberColumn("L3M Avg", format="%d"),
                "Month_Cover": st.column_config.NumberColumn("MoS", format="%.1f Mo"),
            },
            use_container_width=True,
            hide_index=True
        )

        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("##### 📦 Inventory Risk Matrix")
            risk_counts = {
                "Critical Out (MoS < 0.5)": len(report_df[report_df['Month_Cover'] < 0.5]),
                "Understock (0.5 - 1.0)": len(report_df[(report_df['Month_Cover'] >= 0.5) & (report_df['Month_Cover'] < 1.0)]),
                "Optimal (1.0 - 1.5)": len(report_df[(report_df['Month_Cover'] >= 1.0) & (report_df['Month_Cover'] <= 1.5)]),
                "Overstock (> 1.5)": len(report_df[report_df['Month_Cover'] > 1.5])
            }
            for label, count in risk_counts.items():
                color = "red" if "Critical" in label else "orange" if "Under" in label else "green" if "Optimal" in label else "blue"
                st.markdown(f"- **{label}**: :{color}[{count} SKUs]")

        with c2:
            st.markdown("##### 🏷️ Brand Concentration")
            brand_pie = px.pie(report_df, values='Temp_Total', names='Brand', hole=0.4,
                             color_discrete_sequence=px.colors.qualitative.Safe)
            brand_pie.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=200, showlegend=False)
            st.plotly_chart(brand_pie, use_container_width=True)


# ============================================================================
# FOOTER
# ============================================================================
st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: #6B7280; font-size: 0.9rem;">
    <p>📊 <b>ERHA S&OP Dashboard V5.5</b> | Last Updated: {date} | For internal use only</p>
    </div>
    """.format(date=datetime.now().strftime("%Y-%m-%d %H:%M")),
    unsafe_allow_html=True
)
