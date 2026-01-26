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
    
    /* Custom scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: #c1c1c1;
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: #a1a1a1;
    }
    
    /* Card styling */
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
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

def format_number(x):
    """Format numbers with thousand separators"""
    try:
        if pd.isna(x):
            return ''
        return f"{float(x):,.0f}"
    except:
        return str(x)

# ============================================================================
# 2. DATA LOADER WITH ENHANCED ERROR HANDLING
# ============================================================================
@st.cache_data(ttl=600, show_spinner="Loading data from Google Sheets...")
def load_data_v5(start_date_str):
    try:
        gs = GSheetConnector()
        if not gs.client:
            return pd.DataFrame()
        
        # Load data with progress indication
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
            horizon_months = [(start_date + relativedelta(months=i)).strftime("%b-%y") for i in range(12)]
            st.session_state.horizon_months = horizon_months
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
        
        # Calculate L3M average
        sales_date_cols = [c for c in sales_df.columns if re.search(r'\w+-\d{2}', str(c))]
        l3m_cols = sales_date_cols[-3:] if len(sales_date_cols) >= 3 else sales_date_cols
        
        if l3m_cols:
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
        
        # Initialize consensus columns
        cycle_months = horizon_months[:3]
        for m in cycle_months:
            merged_df[f'Cons_{m}'] = merged_df[m]
        
        # Add summary columns
        merged_df['Total_Forecast'] = merged_df[cycle_months].sum(axis=1)
        
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
# SIDEBAR WITH IMPROVED UX
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
    
    # Calculate cycle months
    try:
        start_date = datetime.strptime(selected_start_str, "%b-%y")
        cycle_months = [
            start_date.strftime("%b-%y"),
            (start_date + relativedelta(months=1)).strftime("%b-%y"),
            (start_date + relativedelta(months=2)).strftime("%b-%y")
        ]
        st.session_state.adjustment_months = cycle_months
        
        st.info(f"""
        **Planning Cycle:**  
        🗓️ **M1:** {cycle_months[0]}  
        🗓️ **M2:** {cycle_months[1]}  
        🗓️ **M3:** {cycle_months[2]}
        """)
        
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
        
        if st.button("Check Data Structure"):
            st.info("Data structure check would run here")

# ============================================================================
# MAIN DASHBOARD
# ============================================================================
st.markdown(f"""
<div class="main-header">
    <h2>📊 ERHA S&OP Dashboard V5.5</h2>
    <p>Forecast Horizon: <b>{cycle_months[0]} - {cycle_months[2]} (Consensus Editing)</b> | Next 9 Months (ROFO Projection)</p>
</div>
""", unsafe_allow_html=True)

# Load data
all_df = load_data_v5(selected_start_str)

if all_df.empty:
    st.error("""
    ⚠️ **No data loaded.** Possible issues:
    1. Google Sheets connection failed
    2. Required worksheets are empty
    3. No matching data between sales and ROFO
    4. Internet connectivity issues
    
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
        st.metric("💰 L3M Avg Total", f"{all_df['L3M_Avg'].sum():,.0f}")
    with stat4:
        st.metric("📈 Total Forecast", f"{total_forecast:,.0f}")

# FILTERS SECTION
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
    
    # Create filter columns
    col1, col2, col3, col4, col5 = st.columns(5)
    
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

# Display filter results
filtered_skus = len(filtered_df)
if filtered_skus < total_skus:
    st.success(f"✅ Showing {filtered_skus:,} of {total_skus:,} SKUs ({filtered_skus/total_skus*100:.1f}%)")

# Create tabs
tab1, tab2, tab3 = st.tabs(["📝 Forecast Worksheet", "📈 Analytics Dashboard", "📊 Summary Reports"])

# ============================================================================
# TAB 1: FORECAST WORKSHEET - IMPROVED
# ============================================================================
with tab1:
    if filtered_df.empty:
        st.warning("⚠️ No data matches the selected filters. Please adjust your filters.")
    else:
        # Color code legend with improved design
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
                - 🔵 **Editable Cells:** Blue border (consensus months)
                
                **Text Colors:**
                - 🟠 **E-commerce:** Orange text
                - 🟢 **Reseller:** Green text
                """)
        
        # Process data for worksheet
        edit_df = filtered_df.copy()
        edit_df = calculate_pct(edit_df, cycle_months)
        
        # Define columns to display
        base_cols = ['sku_code', 'Product_Name', 'Channel', 'Brand', 'SKU_Tier', 'Product_Focus', 'floor_price']
        
        # Get horizon months
        horizon_months = st.session_state.get('horizon_months', cycle_months + [
            (datetime.strptime(cycle_months[-1], "%b-%y") + relativedelta(months=i)).strftime("%b-%y") 
            for i in range(1, 10)
        ])
        
        # Historical columns (last 3 months before horizon)
        hist_cols = [c for c in edit_df.columns if re.search(r'\w+-\d{2}', str(c)) 
                    and c not in horizon_months 
                    and not c.startswith('Cons_') 
                    and '%' not in c]
        
        if hist_cols:
            hist_cols = sorted(hist_cols)[-3:]  # Last 3 historical months
        
        # Build column list
        display_cols = base_cols.copy()
        
        if hist_cols:
            display_cols.extend(hist_cols)
        
        display_cols.extend(['L3M_Avg', 'Stock_Qty', 'Month_Cover'])
        display_cols.extend(horizon_months)
        display_cols.extend([f'{m}_%' for m in cycle_months])
        display_cols.extend([f'Cons_{m}' for m in cycle_months])
        
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
                          headerName="SKU Code",
                          checkboxSelection=False)
        
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
        
        # Hidden columns (for reference only)
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
        
        # Month cover with conditional formatting
        gb.configure_column("Month_Cover",
                          width=95,
                          maxWidth=110,
                          cellStyle=js_cover,
                          type=["numericColumn"],
                          valueFormatter="params.value ? params.value.toFixed(1) : ''",
                          suppressSizeToFit=True,
                          headerName="Month Cover")
        
        # Hide non-cycle months from horizon
        for m in horizon_months:
            if m not in cycle_months:
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
        
        # Percentage columns
        for m in cycle_months:
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
        
        # Editable consensus columns (pinned right)
        for m in cycle_months:
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
        
        # Add custom CSS for better responsiveness
        st.markdown("""
        <style>
            .ag-theme-alpine .ag-header-cell {
                font-weight: 600 !important;
            }
            
            .ag-theme-alpine .ag-cell {
                display: flex;
                align-items: center;
            }
            
            /* Improve scrollbar */
            .ag-body-viewport::-webkit-scrollbar {
                width: 10px;
                height: 10px;
            }
        </style>
        """, unsafe_allow_html=True)
        
        # Display the grid
        st.markdown(f"**Worksheet:** Editing consensus for {cycle_months[0]} to {cycle_months[2]} ({len(ag_df):,} SKUs)")
        
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
            
            @media screen and (max-width: 1400px) {
                div {
                    height: 60vh !important;
                }
            }
            
            @media screen and (max-width: 992px) {
                div {
                    height: 55vh !important;
                }
            }
            
            @media screen and (max-width: 768px) {
                div {
                    height: 50vh !important;
                    padding: 5px !important;
                }
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
                allow_unsafe_html=True,
                custom_css={
                    ".ag-root-wrapper": {"border": "none"},
                    ".ag-header": {"border-bottom": "2px solid #e2e8f0"},
                }
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
                        keep_cols.extend([f'Cons_{m}' for m in cycle_months])
                        
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
            # Calculate totals
            total_consensus = 0
            for m in cycle_months:
                cons_col = f'Cons_{m}'
                if cons_col in updated_df.columns:
                    total_consensus += updated_df[cons_col].sum()
            
            st.metric(
                "📊 **Total Consensus**",
                f"{total_consensus:,.0f}",
                f"M1-M3: {', '.join(cycle_months)}"
            )

# ============================================================================
# TAB 2: ANALYTICS DASHBOARD - ENHANCED (FIXED VERSION)
# ============================================================================
with tab2:
    st.markdown("### 📊 Analytics Dashboard")
    
    # Use updated data if available, otherwise filtered data
    base_df = updated_df if 'updated_df' in locals() and not updated_df.empty else filtered_df
    
    if base_df.empty:
        st.warning("No data available for analytics. Please check filters or load data.")
        st.stop()
    
    # Get horizon months
    full_horizon = st.session_state.get('horizon_months', [])
    if not full_horizon:
        # Calculate if not in session state
        start_date = datetime.strptime(selected_start_str, "%b-%y")
        full_horizon = [(start_date + relativedelta(months=i)).strftime("%b-%y") for i in range(12)]
    
    # Analytics controls
    col_view, col_year, col_metric = st.columns([2, 1, 1])
    
    with col_view:
        chart_view = st.radio(
            "**Chart View:**",
            ["Total Volume", "Breakdown by Brand", "Channel Comparison", "Tier Analysis"],
            horizontal=True
        )
    
    with col_year:
        show_2026_only = st.checkbox("📅 **2026 Only**", value=False,
                                   help="Show only 2026 data")
    
    with col_metric:
        metric_type = st.selectbox(
            "**Metric:**",
            ["Volume (Units)", "Revenue (Rp)", "Both"],
            index=0
        )
    
    # Filter active months
    if show_2026_only:
        active_months = [m for m in full_horizon if "-26" in m]
    else:
        active_months = full_horizon
    
    if not active_months:
        st.warning("No months match the selected criteria")
        st.stop()
    
    # Prepare calculation dataframe
    calc_df = base_df.copy()
    
    # Ensure floor_price exists
    if 'floor_price' not in calc_df.columns:
        calc_df['floor_price'] = 0
    
    # Calculate quantities and values for each month
    total_qty_cols = []
    total_val_cols = []
    
    for m in active_months:
        qty_col = f'Final_Qty_{m}'
        val_col = f'Final_Val_{m}'
        
        # Determine source column
        if m in cycle_months:
            source_col = f'Cons_{m}'
        else:
            source_col = m
        
        # Get quantity
        if source_col in calc_df.columns:
            calc_df[qty_col] = pd.to_numeric(calc_df[source_col], errors='coerce').fillna(0)
        else:
            calc_df[qty_col] = 0
        
        # Calculate value
        calc_df[val_col] = calc_df[qty_col] * calc_df['floor_price']
        
        total_qty_cols.append(qty_col)
        total_val_cols.append(val_col)
    
    # Calculate totals
    grand_total_qty = calc_df[total_qty_cols].sum().sum()
    grand_total_val = calc_df[total_val_cols].sum().sum()
    
    # Display KPIs
    with stylable_container(
        key="analytics_kpi",
        css_styles="""
        {
            background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
            padding: 1.5rem;
            border-radius: 12px;
            border: 1px solid #bae6fd;
            margin-bottom: 2rem;
        }
        """
    ):
        k1, k2, k3 = st.columns(3)
        
        period_label = "2026" if show_2026_only else f"{len(active_months)}-Month"
        
        with k1:
            l3m_total = calc_df['L3M_Avg'].sum() * len(active_months) / 3
            delta_qty = ((grand_total_qty / l3m_total) - 1) * 100 if l3m_total > 0 else 0
            st.metric(
                f"📦 **{period_label} Volume**",
                f"{grand_total_qty:,.0f}",
                f"{delta_qty:+.1f}% vs L3M" if l3m_total > 0 else "No L3M data",
                delta_color="normal" if delta_qty >= 0 else "inverse"
            )
        
        with k2:
            avg_monthly = grand_total_val / len(active_months) if active_months else 0
            st.metric(
                f"💰 **{period_label} Revenue**",
                f"Rp {grand_total_val/1_000_000_000:,.2f}B",
                f"Avg: Rp {avg_monthly/1_000_000_000:,.1f}B/mo"
            )
        
        with k3:
            avg_floor_price = calc_df['floor_price'].mean() if not calc_df.empty and calc_df['floor_price'].sum() > 0 else 0
            sku_count = len(calc_df)
            st.metric(
                f"📊 **Average Metrics**",
                f"{sku_count:,} SKUs",
                f"Avg Price: Rp {avg_floor_price:,.0f}" if avg_floor_price > 0 else "No price data"
            )
    
    st.markdown("---")
    
    # Prepare chart data based on view type
    chart_data = []
    
    if chart_view == "Total Volume":
        # Simple monthly totals
        for m in active_months:
            qty = calc_df[f'Final_Qty_{m}'].sum()
            val = calc_df[f'Final_Val_{m}'].sum()
            chart_data.append({
                "Month": m,
                "Volume": qty,
                "Value": val,
                "Type": "Total"
            })
    
    elif chart_view == "Breakdown by Brand":
        # Group by brand
        for m in active_months:
            group = calc_df.groupby('Brand')[[f'Final_Qty_{m}', f'Final_Val_{m}']].sum().reset_index()
            total_val_month = group[f'Final_Val_{m}'].sum()
            
            for _, row in group.iterrows():
                chart_data.append({
                    "Month": m,
                    "Brand": row['Brand'],
                    "Volume": row[f'Final_Qty_{m}'],
                    "Value": total_val_month,
                    "Category": "Brand"
                })
    
    elif chart_view == "Channel Comparison":
        # Group by channel
        if 'Channel' in calc_df.columns:
            for m in active_months:
                group = calc_df.groupby('Channel')[[f'Final_Qty_{m}', f'Final_Val_{m}']].sum().reset_index()
                
                for _, row in group.iterrows():
                    chart_data.append({
                        "Month": m,
                        "Channel": row['Channel'],
                        "Volume": row[f'Final_Qty_{m}'],
                        "Value": row[f'Final_Val_{m}'],
                        "Category": "Channel"
                    })
        else:
            st.warning("Channel data not available")
    
    elif chart_view == "Tier Analysis":
        # Group by SKU tier
        if 'SKU_Tier' in calc_df.columns:
            for m in active_months:
                group = calc_df.groupby('SKU_Tier')[[f'Final_Qty_{m}', f'Final_Val_{m}']].sum().reset_index()
                
                for _, row in group.iterrows():
                    chart_data.append({
                        "Month": m,
                        "Tier": row['SKU_Tier'],
                        "Volume": row[f'Final_Qty_{m}'],
                        "Value": row[f'Final_Val_{m}'],
                        "Category": "Tier"
                    })
        else:
            st.warning("SKU Tier data not available")
    
    # Create dataframe from chart data
    if not chart_data:
        st.warning("No data available for the selected chart view")
        st.stop()
    
    chart_df = pd.DataFrame(chart_data)
    
    # Create combo chart
    fig = go.Figure()
    
    # Determine chart type based on selection
    if chart_view == "Total Volume":
        # Bar chart for volume
        fig.add_trace(go.Bar(
            x=chart_df['Month'],
            y=chart_df['Volume'],
            name='Volume (Units)',
            marker_color='#3B82F6',
            opacity=0.85,
            hovertemplate='<b>%{x}</b><br>Volume: %{y:,.0f} units<extra></extra>'
        ))
        
        # Line chart for value (secondary axis)
        fig.add_trace(go.Scatter(
            x=chart_df['Month'],
            y=chart_df['Value'],
            name='Revenue (Rp)',
            yaxis='y2',
            line=dict(color='#EF4444', width=3),
            mode='lines+markers',
            hovertemplate='<b>%{x}</b><br>Revenue: Rp %{y:,.0f}<extra></extra>'
        ))
    
    elif chart_view in ["Breakdown by Brand", "Channel Comparison", "Tier Analysis"]:
        # Determine grouping column
        group_col_map = {
            "Breakdown by Brand": "Brand",
            "Channel Comparison": "Channel",
            "Tier Analysis": "Tier"
        }
        group_col = group_col_map.get(chart_view, "Brand")
        
        if group_col not in chart_df.columns:
            st.warning(f"{group_col} data not available for chart")
            st.stop()
        
        # Get unique groups
        groups = chart_df[group_col].unique()
        
        # Color palette
        colors = px.colors.qualitative.Set3
        
        # Create stacked bar chart
        for i, group in enumerate(groups):
            group_data = chart_df[chart_df[group_col] == group]
            
            fig.add_trace(go.Bar(
                x=group_data['Month'],
                y=group_data['Volume'],
                name=str(group),
                marker_color=colors[i % len(colors)],
                hovertemplate=f'<b>{group}</b><br>Month: %{{x}}<br>Volume: %{{y:,.0f}}<extra></extra>'
            ))
        
        # Add value line (total) if Value column exists
        if 'Value' in chart_df.columns and not chart_df.empty:
            try:
                monthly_totals = chart_df.groupby('Month')['Volume'].sum().reset_index()
                value_by_month = chart_df.groupby('Month')['Value'].first()
                monthly_totals['Value_Total'] = monthly_totals['Month'].map(value_by_month)
                
                fig.add_trace(go.Scatter(
                    x=monthly_totals['Month'],
                    y=monthly_totals['Value_Total'],
                    name='Total Revenue (Rp)',
                    yaxis='y2',
                    line=dict(color='#000000', width=3, dash='dash'),
                    mode='lines+markers',
                    hovertemplate='<b>Total Revenue</b><br>Month: %{x}<br>Revenue: Rp %{y:,.0f}<extra></extra>'
                ))
            except Exception as e:
                st.warning(f"Could not add revenue line: {str(e)}")
        
        fig.update_layout(barmode='stack')
    
    # SIMPLIFIED LAYOUT UPDATE - FIXED
    fig.update_layout(
        title=f"📈 {chart_view} - {period_label} Horizon",
        yaxis_title="Volume (Units)",
        yaxis2=dict(
            title="Revenue (Rp)",
            overlaying='y',
            side='right'
        ),
        xaxis_title="Month",
        xaxis=dict(tickangle=45 if len(active_months) > 6 else 0),
        legend=dict(
            x=0.02,
            y=1.02,
            orientation='h'
        ),
        hovermode='x unified',
        plot_bgcolor='white',
        paper_bgcolor='white',
        height=500,
        margin=dict(l=50, r=50, t=80, b=80)
    )
    
    # Display chart
    st.plotly_chart(fig, use_container_width=True)
    
    # Add breakdown table
    with st.expander(f"📋 **Detailed {chart_view} Breakdown**", expanded=False):
        if chart_view == "Breakdown by Brand":
            # Brand breakdown table
            brand_summary = calc_df.groupby('Brand')[total_val_cols].sum().reset_index()
            
            # Rename columns
            rename_dict = {old: old.replace('Final_Val_', '') for old in total_val_cols}
            brand_summary.rename(columns=rename_dict, inplace=True)
            
            brand_summary['Total'] = brand_summary.iloc[:, 1:].sum(axis=1)
            brand_summary = brand_summary.sort_values('Total', ascending=False)
            
            # Format for display
            display_df = brand_summary.copy()
            for col in display_df.columns:
                if col != 'Brand':
                    display_df[col] = display_df[col].apply(lambda x: f"Rp {x:,.0f}")
            
            st.dataframe(display_df, use_container_width=True, height=300)
        
        elif chart_view == "Channel Comparison":
            # Channel breakdown
            if 'Channel' in calc_df.columns:
                channel_summary = calc_df.groupby('Channel')[total_val_cols].sum().reset_index()
                
                # Rename columns
                rename_dict = {old: old.replace('Final_Val_', '') for old in total_val_cols}
                channel_summary.rename(columns=rename_dict, inplace=True)
                
                channel_summary['Total'] = channel_summary.iloc[:, 1:].sum(axis=1)
                channel_summary = channel_summary.sort_values('Total', ascending=False)
                
                # Display
                st.dataframe(channel_summary, use_container_width=True, height=200)
        
        elif chart_view == "Tier Analysis":
            # Tier breakdown
            if 'SKU_Tier' in calc_df.columns:
                tier_summary = calc_df.groupby('SKU_Tier')[total_val_cols].sum().reset_index()
                
                # Rename columns
                rename_dict = {old: old.replace('Final_Val_', '') for old in total_val_cols}
                tier_summary.rename(columns=rename_dict, inplace=True)
                
                tier_summary['Total'] = tier_summary.iloc[:, 1:].sum(axis=1)
                tier_summary = tier_summary.sort_values('Total', ascending=False)
                
                # Display
                st.dataframe(tier_summary, use_container_width=True, height=200)

# ============================================================================
# TAB 3: SUMMARY REPORTS
# ============================================================================
with tab3:
    st.markdown("### 📊 Summary Reports")
    
    if filtered_df.empty:
        st.warning("No data available for reports")
    else:
        # Report selection
        report_type = st.radio(
            "Select Report:",
            ["📈 Performance Overview", "📦 Inventory Analysis", "💰 Financial Summary", "🎯 Product Focus"],
            horizontal=True
        )
        
        if report_type == "📈 Performance Overview":
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("##### Top 10 SKUs by Forecast")
                top_skus = filtered_df.nlargest(10, 'Total_Forecast')[['Product_Name', 'Brand', 'Total_Forecast', 'L3M_Avg']]
                top_skus['Growth %'] = ((top_skus['Total_Forecast'] / top_skus['L3M_Avg'].replace(0, 1)) - 1) * 100
                st.dataframe(top_skus.style.format({
                    'Total_Forecast': '{:,.0f}',
                    'L3M_Avg': '{:,.0f}',
                    'Growth %': '{:.1f}%'
                }), use_container_width=True)
            
            with col2:
                st.markdown("##### Brand Performance")
                brand_perf = filtered_df.groupby('Brand').agg({
                    'Total_Forecast': 'sum',
                    'L3M_Avg': 'sum',
                    'Month_Cover': 'mean'
                }).reset_index()
                brand_perf['Growth %'] = ((brand_perf['Total_Forecast'] / brand_perf['L3M_Avg'].replace(0, 1)) - 1) * 100
                brand_perf = brand_perf.sort_values('Total_Forecast', ascending=False)
                st.dataframe(brand_perf.head(10).style.format({
                    'Total_Forecast': '{:,.0f}',
                    'L3M_Avg': '{:,.0f}',
                    'Month_Cover': '{:.1f}',
                    'Growth %': '{:.1f}%'
                }), use_container_width=True)
        
        elif report_type == "📦 Inventory Analysis":
            st.markdown("##### Stock Cover Analysis")
            
            # Create bins for month cover
            cover_bins = pd.cut(filtered_df['Month_Cover'], 
                               bins=[-1, 0, 0.5, 1, 1.5, 3, float('inf')],
                               labels=['Out of Stock', 'Critical (<0.5)', 'Low (0.5-1)', 
                                      'Optimal (1-1.5)', 'High (1.5-3)', 'Excess (>3)'])
            
            cover_summary = filtered_df.groupby(cover_bins).agg({
                'sku_code': 'count',
                'Total_Forecast': 'sum',
                'Stock_Qty': 'sum'
            }).reset_index()
            cover_summary.columns = ['Stock Cover', 'SKU Count', 'Total Forecast', 'Total Stock']
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.dataframe(cover_summary.style.format({
                    'SKU Count': '{:,.0f}',
                    'Total Forecast': '{:,.0f}',
                    'Total Stock': '{:,.0f}'
                }), use_container_width=True)
            
            with col2:
                # Create pie chart
                fig_pie = px.pie(cover_summary, values='SKU Count', names='Stock Cover',
                                title='SKU Distribution by Stock Cover',
                                color_discrete_sequence=px.colors.qualitative.Set3)
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                fig_pie.update_layout(height=400)
                st.plotly_chart(fig_pie, use_container_width=True)
        
        elif report_type == "💰 Financial Summary":
            st.markdown("##### Financial Projection")
            
            # Calculate monthly financials
            financial_data = []
            for m in cycle_months:
                if m in filtered_df.columns:
                    month_qty = filtered_df[m].sum()
                    month_val = month_qty * filtered_df['floor_price'].mean()
                    financial_data.append({
                        'Month': m,
                        'Volume': month_qty,
                        'Revenue': month_val,
                        'Avg Price': filtered_df['floor_price'].mean()
                    })
            
            financial_df = pd.DataFrame(financial_data)
            
            if not financial_df.empty:
                col1, col2 = st.columns(2)
                
                with col1:
                    st.dataframe(financial_df.style.format({
                        'Volume': '{:,.0f}',
                        'Revenue': 'Rp {:,.0f}',
                        'Avg Price': 'Rp {:,.0f}'
                    }), use_container_width=True)
                
                with col2:
                    # Revenue trend
                    fig_rev = px.line(financial_df, x='Month', y='Revenue',
                                     title='Monthly Revenue Projection',
                                     markers=True)
                    fig_rev.update_traces(line=dict(width=3))
                    fig_rev.update_layout(height=400)
                    st.plotly_chart(fig_rev, use_container_width=True)
        
        elif report_type == "🎯 Product Focus":
            st.markdown("##### Focus Products Analysis")
            
            # Get focus products
            focus_df = filtered_df[filtered_df['Product_Focus'].str.contains('Yes', case=False, na=False)]
            
            if not focus_df.empty:
                st.success(f"✅ Found {len(focus_df)} focus products")
                
                # Display focus products
                focus_display = focus_df[['Product_Name', 'Brand', 'Total_Forecast', 
                                         'L3M_Avg', 'Month_Cover', 'floor_price']].copy()
                focus_display['Forecast vs L3M'] = ((focus_display['Total_Forecast'] / 
                                                    focus_display['L3M_Avg'].replace(0, 1)) - 1) * 100
                
                st.dataframe(focus_display.style.format({
                    'Total_Forecast': '{:,.0f}',
                    'L3M_Avg': '{:,.0f}',
                    'Month_Cover': '{:.1f}',
                    'floor_price': 'Rp {:,.0f}',
                    'Forecast vs L3M': '{:.1f}%'
                }).applymap(
                    lambda x: 'background-color: #CCFBF1' if isinstance(x, (int, float)) and x > 0 else '',
                    subset=['Forecast vs L3M']
                ), use_container_width=True, height=400)
            else:
                st.info("ℹ️ No products marked as 'Focus' in the current filter")

# ============================================================================
# FOOTER
# ============================================================================
st.markdown("---")
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.markdown(
        """
        <div style="text-align: center; color: #6B7280; font-size: 0.9rem;">
        <p>📊 <b>ERHA S&OP Dashboard V5.5</b> | Last Updated: {date} | For internal use only</p>
        </div>
        """.format(date=datetime.now().strftime("%Y-%m-%d %H:%M")),
        unsafe_allow_html=True
    )
