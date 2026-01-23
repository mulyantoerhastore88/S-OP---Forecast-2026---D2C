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
from dateutil.relativedelta import relativedelta # Library untuk hitung bulan otomatis
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode, JsCode
from streamlit_extras.metric_cards import style_metric_cards
from streamlit_extras.stylable_container import stylable_container
from streamlit_extras.toggle_switch import st_toggle_switch

# ============================================================================
# PAGE CONFIG
# ============================================================================
st.set_page_config(
    page_title="ERHA S&OP 3-Month Consensus Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        'About': "ERHA S&OP Dashboard v3.0 (Auto-Cycle & Write-Back)"
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
        --secondary: #10B981;
        --danger: #EF4444;
        --warning: #F59E0B;
        --light: #F9FAFB;
        --dark: #1F2937;
        --shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1);
    }
    
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
    }
    
    .sub-title {
        font-size: 1.1rem;
        opacity: 0.9;
        margin-top: 0.5rem;
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
    
    .legend-item { display: flex; align-items: center; gap: 4px; }
    .color-box { width: 16px; height: 16px; border-radius: 3px; }
    .legend-text { font-size: 0.8rem; font-weight: 500; color: #4B5563; }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# 1. GSHEET CONNECTOR (UPDATED WITH SAVE FUNCTION)
# ============================================================================
class GSheetConnector:
    def __init__(self):
        # Cek apakah secrets tersedia
        if "gsheets" in st.secrets:
            self.sheet_id = st.secrets["gsheets"]["sheet_id"]
            self.service_account_info = json.loads(st.secrets["gsheets"]["service_account_info"])
            self.client = None
            self.connect()
        else:
            st.error("❌ Secrets 'gsheets' not found in .streamlit/secrets.toml")

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
        except gspread.WorksheetNotFound:
            st.warning(f"⚠️ Worksheet '{sheet_name}' not found.")
            return pd.DataFrame()
        except Exception as e:
            st.error(f"Error reading sheet {sheet_name}: {str(e)}")
            return pd.DataFrame()

    def save_data(self, df, sheet_name):
        """Write DataFrame to Sheet (Overwrite)"""
        try:
            # 1. Cek sheet, create if not exists
            try:
                worksheet = self.sheet.worksheet(sheet_name)
            except gspread.WorksheetNotFound:
                worksheet = self.sheet.add_worksheet(title=sheet_name, rows=1000, cols=20)
                st.info(f"Created new worksheet: {sheet_name}")

            # 2. Prepare Data (Handle NaN -> Empty String for JSON)
            df_clean = df.fillna('')
            # Convert to list of lists (Header + Rows)
            data_to_upload = [df_clean.columns.values.tolist()] + df_clean.values.tolist()

            # 3. Clear & Update
            worksheet.clear()
            worksheet.update(data_to_upload)
            
            return True, "Success"
        except Exception as e:
            return False, str(e)

# ============================================================================
# 2. DATA LOADER (FIXED BRAND_GROUP ISSUE)
# ============================================================================
@st.cache_data(ttl=300, show_spinner=False)
def load_all_data():
    """Load and process all required data with Dynamic Month Logic & Fixed Columns"""
    
    try:
        gs = GSheetConnector()
        
        # Load Raw Data
        sales_df = gs.get_sheet_data("sales_history")
        rofo_df = gs.get_sheet_data("rofo_current")
        stock_df = gs.get_sheet_data("stock_onhand")
        
        # === 1. CLEAN COLUMN NAMES (Supaya aman spasi vs underscore) ===
        for df in [sales_df, rofo_df, stock_df]:
            if not df.empty:
                # Ganti spasi dengan underscore, hilangkan spasi depan/belakang
                df.columns = [c.strip().replace(' ', '_') for c in df.columns]
        # ===============================================================

        if sales_df.empty or rofo_df.empty:
            st.error("❌ Critical data missing (sales or rofo).")
            return pd.DataFrame()

        # ===== DYNAMIC MONTH LOGIC (AUTO CYCLE) =====
        current_date = datetime.now()
        adjustment_months = []
        
        for i in range(1, 4): 
            future_date = current_date + relativedelta(months=i)
            fname = future_date.strftime("%b-%y")
            adjustment_months.append(fname)
            
        st.session_state.adjustment_months = adjustment_months
        
        # ===== PROSES SALES HISTORY =====
        sales_cols_candidates = [c for c in sales_df.columns if '-' in c]
        available_sales_months = sales_cols_candidates[-3:]
        
        if available_sales_months:
            sales_df['L3M_Avg'] = sales_df[available_sales_months].mean(axis=1).round(0)
        else:
            sales_df['L3M_Avg'] = 0

        # ===== MERGE DATA =====
        # Update: Tambahkan 'Brand_Group' ke sini
        possible_keys = ['sku_code', 'Product_Name', 'Brand', 'Brand_Group', 'SKU_Tier']
        
        # Cek kunci mana saja yang VALID (ada di sales maupun rofo)
        # Kita prioritaskan kunci yang ada di KEDUA file
        valid_keys = [k for k in possible_keys if k in sales_df.columns and k in rofo_df.columns]
        
        # Siapkan kolom Sales
        sales_cols_to_keep = valid_keys + ['L3M_Avg'] + available_sales_months
        sales_subset = sales_df[sales_cols_to_keep].copy()
        
        # Siapkan kolom ROFO
        rofo_cols_to_take = valid_keys.copy()
        
        # === FIX: Pastikan Brand_Group terambil dari ROFO jika belum masuk valid_keys ===
        # (Kasus: Brand_Group ada di ROFO tapi TIDAK ada di Sales History)
        if 'Brand_Group' in rofo_df.columns and 'Brand_Group' not in valid_keys:
            rofo_cols_to_take.append('Brand_Group')
            
        # Ambil kolom bulan forecast
        for m in adjustment_months:
            if m in rofo_df.columns:
                rofo_cols_to_take.append(m)
                
        rofo_subset = rofo_df[rofo_cols_to_take].copy()
        
        # Merge Sales + ROFO
        merged_df = pd.merge(sales_subset, rofo_subset, on=valid_keys, how='inner')
        
        # Isi kolom bulan forecast yg hilang dengan 0
        for m in adjustment_months:
            if m not in merged_df.columns:
                merged_df[m] = 0
        
        # ===== MERGE STOCK =====
        if not stock_df.empty and 'sku_code' in stock_df.columns:
            stock_col = 'Stock_Qty' if 'Stock_Qty' in stock_df.columns else stock_df.columns[1]
            merged_df = pd.merge(merged_df, stock_df[['sku_code', stock_col]], on='sku_code', how='left')
            merged_df.rename(columns={stock_col: 'Stock_Qty'}, inplace=True)
        else:
            merged_df['Stock_Qty'] = 0
            
        merged_df['Stock_Qty'] = merged_df['Stock_Qty'].fillna(0)
        
        # ===== CALCULATE METRICS =====
        merged_df['Month_Cover'] = (merged_df['Stock_Qty'] / merged_df['L3M_Avg'].replace(0, 1)).round(1)
        merged_df['Month_Cover'] = merged_df['Month_Cover'].replace([np.inf, -np.inf], 0)
        
        # ===== INIT CONSENSUS COLUMNS =====
        for month in adjustment_months:
            merged_df[f'Cons_{month}'] = merged_df[month]
            
        return merged_df

    except Exception as e:
        st.error(f"❌ Error loading data: {str(e)}")
        return pd.DataFrame()

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def calculate_percentage_columns(df):
    """Calculate percentage columns vs L3M Avg"""
    df_calc = df.copy()
    for month in st.session_state.adjustment_months:
        cons_col = f'Cons_{month}'
        if cons_col in df_calc.columns and 'L3M_Avg' in df_calc.columns:
            pct_col = f'{month}_%'
            # Calculate percentage based on CONSENSUS value
            df_calc[pct_col] = (df_calc[cons_col] / df_calc['L3M_Avg'].replace(0, np.nan) * 100).round(1)
            df_calc[pct_col] = df_calc[pct_col].replace([np.inf, -np.inf], 0).fillna(100)
    return df_calc

# ============================================================================
# MAIN APP UI
# ============================================================================

# Header
with st.container():
    st.markdown("""
    <div class="main-header">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h1 class="main-title">📊 ERHA S&OP Dashboard</h1>
                <p class="sub-title">Rolling Forecast & Collaboration Tool</p>
            </div>
            <div>
                <span style="background: rgba(255,255,255,0.2); padding: 5px 15px; border-radius: 20px;">
                    📅 Cycle: Auto-Rolling
                </span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# Meeting Controls
with stylable_container(
    key="meeting_bar",
    css_styles="{background: white; padding: 1rem; border-radius: 12px; border: 1px solid #E5E7EB; margin-bottom: 1rem;}"
):
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        st.info(f"📅 **Current Period:** {datetime.now().strftime('%B %Y')}")
    with c2:
        st.warning("⚠️ Data Source: Google Sheets (Live)")
    with c3:
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()

# Load Data
with st.spinner('🔄 Loading & Calculating Forecast Cycle...'):
    all_df = load_all_data()

# Ensure adjustment_months exists in session state (fallback)
if 'adjustment_months' not in st.session_state:
    st.session_state.adjustment_months = []

# ============================================================================
# FILTER BAR
# ============================================================================
with st.container():
    with stylable_container(
        key="filter_box",
        css_styles="{background: white; padding: 1rem; border-radius: 12px; border: 1px solid #E5E7EB; margin-bottom: 1rem;}"
    ):
        st.markdown("#### 🔍 Filter SKUs")
        fc1, fc2, fc3, fc4 = st.columns(4)
        
        with fc1:
            brand_groups = ["ALL"] + sorted(all_df['Brand_Group'].dropna().unique().tolist()) if 'Brand_Group' in all_df.columns else ["ALL"]
            selected_brand_group = st.selectbox("Brand Group", brand_groups)
            
        with fc2:
            brands = ["ALL"] + sorted(all_df['Brand'].dropna().unique().tolist()) if 'Brand' in all_df.columns else ["ALL"]
            selected_brand = st.selectbox("Brand", brands)
            
        with fc3:
            tiers = ["ALL"] + sorted(all_df['SKU_Tier'].dropna().unique().tolist()) if 'SKU_Tier' in all_df.columns else ["ALL"]
            selected_tier = st.selectbox("SKU Tier", tiers)
            
        with fc4:
            month_cover_filter = st.selectbox("Month Cover Status", ["ALL", "< 1.5 months", "1.5 - 3 months", "> 3 months"])

# ============================================================================
# TABS
# ============================================================================
tab1, tab2, tab3 = st.tabs(["📝 Input & Adjustment", "📊 Analytics", "🎯 Focus Areas"])

# ============================================================================
# TAB 1: INPUT (AG-GRID)
# ============================================================================
with tab1:
    st.markdown("### 🎯 Interactive Forecast Adjustment")
    st.caption(f"Forecasting for: {', '.join(st.session_state.adjustment_months)}")
    
    # 1. Apply Filters
    filtered_df = all_df.copy()
    if selected_brand_group != "ALL" and 'Brand_Group' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['Brand_Group'] == selected_brand_group]
    if selected_brand != "ALL" and 'Brand' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['Brand'] == selected_brand]
    if selected_tier != "ALL" and 'SKU_Tier' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['SKU_Tier'] == selected_tier]
        
    if month_cover_filter != "ALL" and 'Month_Cover' in filtered_df.columns:
        if month_cover_filter == "< 1.5 months":
            filtered_df = filtered_df[filtered_df['Month_Cover'] < 1.5]
        elif month_cover_filter == "1.5 - 3 months":
            filtered_df = filtered_df[(filtered_df['Month_Cover'] >= 1.5) & (filtered_df['Month_Cover'] <= 3)]
        elif month_cover_filter == "> 3 months":
            filtered_df = filtered_df[filtered_df['Month_Cover'] > 3]

    st.success(f"📋 Loaded **{len(filtered_df)}** SKUs")

    # 2. Prepare Data for Grid
    edit_df = filtered_df.copy()
    
    # Init Consensus Cols if missing
    for month in st.session_state.adjustment_months:
        cons_col = f'Cons_{month}'
        if cons_col not in edit_df.columns:
            edit_df[cons_col] = edit_df[month] if month in edit_df.columns else 0

    # Calculate Pct
    edit_df = calculate_percentage_columns(edit_df)

    # 3. Define Column Order
    ag_cols = ['sku_code', 'Product_Name', 'Brand', 'SKU_Tier']
    
    # Sales History
    sales_cols = [c for c in edit_df.columns if '-' in c and c not in st.session_state.adjustment_months and 'Cons' not in c and '%' not in c][-3:]
    ag_cols.extend(sales_cols)
    
    # Metrics
    metrics_cols = ['L3M_Avg', 'Stock_Qty', 'Month_Cover']
    ag_cols.extend([c for c in metrics_cols if c in edit_df.columns])
    
    # Original ROFO
    ag_cols.extend([m for m in st.session_state.adjustment_months if m in edit_df.columns])
    
    # Percentage
    ag_cols.extend([f'{m}_%' for m in st.session_state.adjustment_months if f'{m}_%' in edit_df.columns])
    
    # Consensus (Input)
    ag_cols.extend([f'Cons_{m}' for m in st.session_state.adjustment_months])

    ag_df = edit_df[ag_cols].copy()

    # 4. JS Styling (Updated with Brand Colors)
    
    # --- WARNA BRAND ---
    js_brand_color = JsCode("""
    function(params) {
        if (!params.value) return null;
        const brand = params.value.toLowerCase();
        
        if (brand.includes('acneact')) return {'backgroundColor': '#E0F2FE', 'color': '#0369A1', 'fontWeight': 'bold'}; // Sky Blue
        if (brand.includes('truwhite')) return {'backgroundColor': '#DCFCE7', 'color': '#15803D', 'fontWeight': 'bold'}; // Green
        if (brand.includes('hair')) return {'backgroundColor': '#FEF3C7', 'color': '#B45309', 'fontWeight': 'bold'}; // Amber
        if (brand.includes('age')) return {'backgroundColor': '#E0E7FF', 'color': '#4338CA', 'fontWeight': 'bold'}; // Indigo
        if (brand.includes('his')) return {'backgroundColor': '#F3E8FF', 'color': '#7E22CE', 'fontWeight': 'bold'}; // Purple
        if (brand.includes('skinsitive')) return {'backgroundColor': '#FAE8FF', 'color': '#A21CAF', 'fontWeight': 'bold'}; // Fuchsia
        if (brand.includes('perfect')) return {'backgroundColor': '#FFEDD5', 'color': '#C2410C', 'fontWeight': 'bold'}; // Orange
        
        return {'backgroundColor': '#F3F4F6', 'color': '#374151'}; // Default Grey
    }
    """)
    
    js_month_cover = JsCode("""
    function(params) {
        if (params.value > 1.5) { return {'backgroundColor': '#FCE7F3', 'color': '#BE185D', 'fontWeight': 'bold'}; }
        return null;
    }
    """)
    
    js_growth_pct = JsCode("""
    function(params) {
        if (params.value < 90) { return {'backgroundColor': '#FFEDD5', 'color': '#9A3412', 'fontWeight': 'bold'}; }
        if (params.value > 130) { return {'backgroundColor': '#FEE2E2', 'color': '#991B1B', 'fontWeight': 'bold'}; }
        return {'color': 'black'};
    }
    """)
    
    js_editable_cell = JsCode("""
    function(params) {
        return {'backgroundColor': '#EFF6FF', 'border': '1px solid #93C5FD', 'color': '#1E3A8A', 'fontWeight': 'bold'};
    }
    """)

    # 5. Grid Config
    gb = GridOptionsBuilder.from_dataframe(ag_df)
    gb.configure_default_column(resizable=True, filterable=True, sortable=True, editable=False)
    
    # Pin Metadata
    gb.configure_column("sku_code", pinned="left", width=100)
    gb.configure_column("Product_Name", pinned="left", width=220)
    
    # === APPLY BRAND COLOR ===
    gb.configure_column("Brand", cellStyle=js_brand_color, width=120)
    
    # Numeric Formatting
    for col in ag_cols:
        if col not in ['sku_code', 'Product_Name', 'Brand', 'SKU_Tier'] and '_%' not in col and col != 'Month_Cover':
             gb.configure_column(col, type=["numericColumn"], valueFormatter="x.toLocaleString()", width=100)

    # Style Month Cover
    gb.configure_column("Month_Cover", type=["numericColumn"], precision=1, cellStyle=js_month_cover, width=90)

    # Style Percentage
    for month in st.session_state.adjustment_months:
        pct_col = f'{month}_%'
        if pct_col in ag_cols:
            gb.configure_column(pct_col, header_name=f"{month} %", type=["numericColumn"], 
                              valueFormatter="x.toFixed(1) + '%'", cellStyle=js_growth_pct, width=80)

    # Style & Configure Consensus (EDITABLE)
    for month in st.session_state.adjustment_months:
        cons_col = f'Cons_{month}'
        if cons_col in ag_cols:
            gb.configure_column(cons_col, header_name=f"✏️ {month}", editable=True, 
                              type=["numericColumn"], cellStyle=js_editable_cell, 
                              valueFormatter="x.toLocaleString()", width=110, pinned="right")

    gb.configure_selection('single')
    gridOptions = gb.build()

    # 6. Render Grid
    st.markdown("""
    <div style="margin-bottom:10px; font-size:0.8rem;">
        <span style="background:#FCE7F3; color:#BE185D; padding:2px 6px; border-radius:4px;"><b>Cover > 1.5</b></span>
        <span style="background:#FFEDD5; color:#9A3412; padding:2px 6px; border-radius:4px;"><b>Growth < 90%</b></span>
        <span style="background:#FEE2E2; color:#991B1B; padding:2px 6px; border-radius:4px;"><b>Growth > 130%</b></span>
        <span style="background:#EFF6FF; color:#1E3A8A; padding:2px 6px; border-radius:4px; border:1px solid #93C5FD;"><b>✏️ Editable</b></span>
    </div>
    """, unsafe_allow_html=True)

    grid_response = AgGrid(
        ag_df,
        gridOptions=gridOptions,
        enable_enterprise_modules=False,
        allow_unsafe_jscode=True,
        update_mode=GridUpdateMode.VALUE_CHANGED,
        height=550,
        theme='alpine',
        key='main_grid'
    )

    updated_df = pd.DataFrame(grid_response['data'])

    # 7. Actions
    st.markdown("---")
    ac1, ac2, ac3 = st.columns(3)
    
    with ac1:
        if st.button("💾 Save to Session", type="primary", use_container_width=True):
            st.session_state.edited_forecast_data = updated_df.copy()
            # Calc Changes
            changes = []
            for m in st.session_state.adjustment_months:
                c_col = f'Cons_{m}'
                if c_col in updated_df.columns:
                    orig = edit_df[c_col].sum()
                    new = updated_df[c_col].sum()
                    changes.append({'Month': m, 'Original': f"{orig:,.0f}", 'New': f"{new:,.0f}", 'Diff': f"{new-orig:,.0f}"})
            st.session_state.changes_log = changes
            st.success("✅ Saved locally!")
            if changes: st.dataframe(pd.DataFrame(changes), hide_index=True)

    with ac2:
        if st.button("☁️ Push to Google Sheets", type="secondary", use_container_width=True, help="Overwrites 'consensus_rofo' sheet"):
            if 'edited_forecast_data' not in st.session_state:
                st.warning("⚠️ Save to Session first!")
            else:
                with st.spinner("🚀 Uploading to GSheet..."):
                    # Prepare clean data for upload
                    final_data = st.session_state.edited_forecast_data.copy()
                    
                    # Columns to keep: Metadata + Consensus
                    keep_cols = ['sku_code', 'Product_Name', 'Brand', 'SKU_Tier'] + [f'Cons_{m}' for m in st.session_state.adjustment_months]
                    
                    # Optional: Add timestamp col
                    final_data['Last_Update'] = datetime.now().strftime('%Y-%m-%d %H:%M')
                    keep_cols.append('Last_Update')
                    
                    upload_df = final_data[keep_cols]
                    
                    gs = GSheetConnector()
                    success, msg = gs.save_data(upload_df, "consensus_rofo")
                    if success:
                        st.balloons()
                        st.success("✅ Data successfully pushed to Google Sheets!")
                    else:
                        st.error(f"❌ Upload failed: {msg}")

    with ac3:
        # Live Total
        total_fc = 0
        for m in st.session_state.adjustment_months:
            if f'Cons_{m}' in updated_df.columns:
                total_fc += updated_df[f'Cons_{m}'].sum()
        st.metric("Live Forecast Total", f"{total_fc:,.0f}")

# ============================================================================
# TAB 2: ANALYTICS (SIMPLE VIEW)
# ============================================================================
with tab2:
    st.markdown("### 📈 Projection Analysis")
    
    # Use edited data if available, else original
    viz_df = updated_df if not updated_df.empty else all_df
    
    # Chart 1: Monthly Trend
    chart_data = []
    # Add History Average
    if 'L3M_Avg' in viz_df.columns:
        chart_data.append({'Type': 'History (Avg)', 'Period': 'L3M', 'Value': viz_df['L3M_Avg'].sum()})
    
    # Add Consensus
    for m in st.session_state.adjustment_months:
        c_col = f'Cons_{m}'
        val = viz_df[c_col].sum() if c_col in viz_df.columns else 0
        chart_data.append({'Type': 'Forecast', 'Period': m, 'Value': val})
        
    chart_df = pd.DataFrame(chart_data)
    
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        fig = px.bar(chart_df, x='Period', y='Value', color='Type', title="Total Volume Trend",
                     color_discrete_map={'History (Avg)': '#9CA3AF', 'Forecast': '#3B82F6'})
        st.plotly_chart(fig, use_container_width=True)
        
    with col_chart2:
        if 'Brand' in viz_df.columns:
            brand_agg = viz_df.groupby('Brand')[[f'Cons_{m}' for m in st.session_state.adjustment_months]].sum().sum(axis=1).reset_index(name='Total')
            fig2 = px.pie(brand_agg, values='Total', names='Brand', title="Volume Share by Brand", hole=0.4)
            st.plotly_chart(fig2, use_container_width=True)

# ============================================================================
# TAB 3: FOCUS AREAS
# ============================================================================
with tab3:
    st.markdown("### ⚠️ Action Items")
    
    focus_df = updated_df if not updated_df.empty else all_df
    
    c_alert1, c_alert2 = st.columns(2)
    
    with c_alert1:
        if 'Month_Cover' in focus_df.columns:
            high_stock = focus_df[focus_df['Month_Cover'] > 1.5]
            with stylable_container(key="alert_stock", css_styles="{border-left: 5px solid #EF4444; background: white; padding: 1rem; border-radius: 8px;}"):
                st.markdown(f"#### 🛑 High Stock ({len(high_stock)})")
                st.caption("Month Cover > 1.5")
                if not high_stock.empty:
                    st.dataframe(high_stock[['sku_code', 'Product_Name', 'Month_Cover', 'Stock_Qty']].head(), hide_index=True)
    
    with c_alert2:
        if 'L3M_Avg' in focus_df.columns:
            # Check growth on first month of forecast
            first_m = st.session_state.adjustment_months[0]
            cons_col = f'Cons_{first_m}'
            if cons_col in focus_df.columns:
                focus_df['Growth_Check'] = (focus_df[cons_col] / focus_df['L3M_Avg'].replace(0, 1) * 100)
                low_growth = focus_df[focus_df['Growth_Check'] < 90]
                
                with stylable_container(key="alert_growth", css_styles="{border-left: 5px solid #F59E0B; background: white; padding: 1rem; border-radius: 8px;}"):
                    st.markdown(f"#### 📉 Low Growth ({len(low_growth)})")
                    st.caption(f"{first_m} vs L3M < 90%")
                    if not low_growth.empty:
                        st.dataframe(low_growth[['sku_code', 'Product_Name', 'L3M_Avg', cons_col, 'Growth_Check']].head(), hide_index=True)
