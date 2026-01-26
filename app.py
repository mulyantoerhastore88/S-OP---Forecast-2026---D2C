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
    
    .ag-row:hover {
        background-color: #f8fafc !important;
    }
    
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
            df_clean = df.fillna('').infer_objects(copy=False)
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
    if pd.isna(val) or val == '' or val is None:
        return 0
    val_str = str(val)
    clean_str = re.sub(r'[^0-9]', '', val_str)
    try:
        return float(clean_str)
    except:
        return 0

def find_matching_column(target_month, available_columns):
    if target_month in available_columns: 
        return target_month
    target_clean = target_month.lower().replace('-', '').replace(' ', '').replace('_', '')
    for col in available_columns:
        col_str = str(col)
        col_clean = col_str.lower().replace('-', '').replace(' ', '').replace('_', '')
        if target_clean in col_clean or col_clean in target_clean:
            return col
    return None

def parse_month_year(date_str):
    try:
        return datetime.strptime(date_str, "%b-%y")
    except:
        return datetime(1900, 1, 1)

def sort_month_columns(columns):
    month_cols = [c for c in columns if re.match(r'^[A-Za-z]{3}-\d{2}$', str(c))]
    month_cols.sort(key=lambda x: parse_month_year(x))
    return month_cols

# ============================================================================
# 2. DATA LOADER WITH ENHANCED ERROR HANDLING
# ============================================================================
@st.cache_data(ttl=600, show_spinner="Loading data from Google Sheets...")
def load_data_v5(start_date_str, all_months=False):
    try:
        gs = GSheetConnector()
        if not gs.client:
            return pd.DataFrame()
        with st.spinner("Fetching sales history..."):
            sales_df = gs.get_sheet_data("sales_history")
        with st.spinner("Fetching ROFO data..."):
            rofo_df = gs.get_sheet_data("rofo_current")
        with st.spinner("Fetching stock data..."):
            stock_df = gs.get_sheet_data("stock_onhand")
        if sales_df.empty:
            st.error("⚠️ Sales history data is empty")
            return pd.DataFrame()
        if rofo_df.empty:
            st.error("⚠️ ROFO data is empty")
            return pd.DataFrame()
        for df in [sales_df, rofo_df, stock_df]:
            if not df.empty:
                df.columns = [str(c).strip() for c in df.columns]
        try:
            start_date = datetime.strptime(start_date_str, "%b-%y")
            horizon_months = [(start_date + relativedelta(months=i)).strftime("%b-%y") for i in range(12)]
            adjustment_months = horizon_months if all_months else horizon_months[:3]
            st.session_state.horizon_months = horizon_months
            st.session_state.adjustment_months = adjustment_months
            st.session_state.all_months_mode = all_months
        except:
            st.error("Invalid date format")
            return pd.DataFrame()
        if 'floor_price' in rofo_df.columns:
            rofo_df['floor_price'] = rofo_df['floor_price'].apply(clean_currency)
        else:
            floor_cols = [c for c in rofo_df.columns if 'floor' in c.lower()]
            if floor_cols:
                rofo_df.rename(columns={floor_cols[0]: 'floor_price'}, inplace=True)
                rofo_df['floor_price'] = rofo_df['floor_price'].apply(clean_currency)
            else:
                rofo_df['floor_price'] = 0
        key_map = {'Product Name': 'Product_Name', 'Brand Group': 'Brand_Group', 'SKU Tier': 'SKU_Tier', 'product name': 'Product_Name', 'brand group': 'Brand_Group', 'sku tier': 'SKU_Tier'}
        for df in [sales_df, rofo_df]:
            df.rename(columns=lambda x: key_map.get(x, x), inplace=True)
        possible_keys = ['sku_code', 'Product_Name', 'Brand', 'Brand_Group', 'SKU_Tier', 'Channel']
        valid_keys = [k for k in possible_keys if k in sales_df.columns and k in rofo_df.columns]
        if not valid_keys:
            st.error("❌ No common columns found for merging sales and ROFO data")
            return pd.DataFrame()
        sales_date_cols = [c for c in sales_df.columns if re.search(r'^[A-Za-z]{3}-\d{2}$', str(c))]
        sales_date_cols = sort_month_columns(sales_date_cols)
        l3m_cols = sales_date_cols[-3:] if len(sales_date_cols) >= 3 else sales_date_cols
        if l3m_cols:
            sales_df['L3M_Avg'] = sales_df[l3m_cols].applymap(lambda x: clean_currency(x) if pd.notna(x) else 0).mean(axis=1).round(0)
        else:
            sales_df['L3M_Avg'] = 0
        sales_subset_cols = valid_keys + ['L3M_Avg']
        if l3m_cols: sales_subset_cols.extend(l3m_cols)
        sales_subset = sales_df[sales_subset_cols].copy()
        rofo_cols_to_fetch = valid_keys.copy()
        for extra in ['Channel', 'Product_Focus', 'floor_price', 'category', 'sub_category']:
            if extra in rofo_df.columns and extra not in rofo_cols_to_fetch: rofo_cols_to_fetch.append(extra)
        month_mapping = {}
        missing_months = []
        for m in horizon_months:
            real_col = find_matching_column(m, rofo_df.columns)
            if real_col:
                month_mapping[m] = real_col
                if real_col not in rofo_cols_to_fetch: rofo_cols_to_fetch.append(real_col)
            else:
                missing_months.append(m)
        st.session_state.missing_months = missing_months
        rofo_subset = rofo_df[rofo_cols_to_fetch].copy()
        inv_map = {v: k for k, v in month_mapping.items()}
        rofo_subset.rename(columns=inv_map, inplace=True)
        merged_df = pd.merge(sales_subset, rofo_subset, on=valid_keys, how='inner')
        if merged_df.empty:
            st.warning("⚠️ No matching records found after merging sales and ROFO data")
            return pd.DataFrame()
        if 'Product_Focus' not in merged_df.columns: merged_df['Product_Focus'] = ""
        else: merged_df['Product_Focus'] = merged_df['Product_Focus'].fillna("").astype(str)
        if 'floor_price' not in merged_df.columns: merged_df['floor_price'] = 0
        else: merged_df['floor_price'] = merged_df['floor_price'].fillna(0)
        for m in horizon_months:
            if m not in merged_df.columns: merged_df[m] = 0
            else: merged_df[m] = merged_df[m].apply(clean_currency)
        if not stock_df.empty and 'sku_code' in stock_df.columns:
            stock_col = next((c for c in ['Stock_Qty', 'stock_qty', 'Stock On Hand', 'stock_on_hand'] if c in stock_df.columns), stock_df.columns[1] if len(stock_df.columns) > 1 else 'stock_qty')
            stock_df_clean = stock_df[['sku_code', stock_col]].copy()
            stock_df_clean.columns = ['sku_code', 'Stock_Qty']
            stock_df_clean['Stock_Qty'] = stock_df_clean['Stock_Qty'].apply(clean_currency)
            merged_df = pd.merge(merged_df, stock_df_clean, on='sku_code', how='left')
        else:
            merged_df['Stock_Qty'] = 0
        merged_df['Stock_Qty'] = merged_df['Stock_Qty'].fillna(0)
        merged_df['Month_Cover'] = np.where(merged_df['L3M_Avg'] > 0, (merged_df['Stock_Qty'] / merged_df['L3M_Avg']).round(1), 0)
        merged_df['Month_Cover'] = merged_df['Month_Cover'].replace([np.inf, -np.inf], 0)
        adjustment_months = st.session_state.get('adjustment_months', [])
        for m in adjustment_months: merged_df[f'Cons_{m}'] = merged_df[m]
        merged_df['Total_Forecast'] = merged_df[adjustment_months].sum(axis=1)
        return merged_df
    except Exception as e:
        st.error(f"❌ Error Loading Data: {str(e)}")
        return pd.DataFrame()

def calculate_pct(df, months):
    df_calc = df.copy()
    for m in months:
        if f'Cons_{m}' in df_calc.columns:
            mask = df_calc['L3M_Avg'] > 0
            df_calc.loc[mask, f'{m}_%'] = (df_calc.loc[mask, f'Cons_{m}'] / df_calc.loc[mask, 'L3M_Avg'] * 100).round(1)
            df_calc.loc[~mask, f'{m}_%'] = 100
    return df_calc

# ============================================================================
# SIDEBAR WITH IMPROVED UX
# ============================================================================
with st.sidebar:
    st.image("https://www.erhagroup.com/assets/img/logo-erha.png", width=150)
    st.markdown("### ⚙️ Planning Cycle Configuration")
    curr_date = datetime.now()
    start_options = [(curr_date + relativedelta(months=i)).strftime("%b-%y") for i in range(-2, 4)]
    default_idx = 2 if curr_date.day >= 15 else 1
    selected_start_str = st.selectbox("Forecast Start Month", options=start_options, index=default_idx)
    show_all_months = st.checkbox("📅 Show & Adjust All 12 Months", value=False)
    try:
        start_date = datetime.strptime(selected_start_str, "%b-%y")
        horizon_months = [(start_date + relativedelta(months=i)).strftime("%b-%y") for i in range(12)]
        adjustment_months = horizon_months if show_all_months else horizon_months[:3]
        st.session_state.adjustment_months = adjustment_months
        st.session_state.horizon_months = horizon_months
        st.session_state.all_months_mode = show_all_months
        if show_all_months: st.info(f"**Planning Cycle:** ALL 12 Months")
        else: st.info(f"**Planning Cycle:** M1-M3 Editable")
    except: st.error("Invalid date selected")
    st.markdown("---")
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    if st.button("📊 Clear Cache", use_container_width=True):
        st.cache_data.clear()
        st.success("Cache cleared!")

# ============================================================================
# MAIN DASHBOARD
# ============================================================================
st.markdown(f"""
<div class="main-header">
    <h2>📊 ERHA S&OP Dashboard V5.5</h2>
    <p>Forecast Horizon: <b>{horizon_months[0]} - {horizon_months[-1]}</b> | Editable: <b>{', '.join(adjustment_months)}</b></p>
</div>
""", unsafe_allow_html=True)

all_df = load_data_v5(selected_start_str, show_all_months)
if all_df.empty: st.stop()

with stylable_container(key="summary_stats", css_styles="{background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); padding: 1rem; border-radius: 10px; border: 1px solid #e2e8f0; margin-bottom: 1.5rem;}"):
    stat1, stat2, stat3, stat4 = st.columns(4)
    stat1.metric("📦 Total SKUs", f"{len(all_df):,}")
    stat2.metric("🏷️ Brands", f"{all_df['Brand'].nunique():,}")
    stat3.metric("💰 L3M Avg", f"{all_df['L3M_Avg'].sum():,.0f}")
    stat4.metric("📈 Total Forecast", f"{all_df['Total_Forecast'].sum():,.0f}")

with stylable_container(key="filters", css_styles="{background: white; padding: 1.25rem; border-radius: 10px; border: 1px solid #E2E8F0; margin-bottom: 1.5rem; shadow: 0 2px 4px rgba(0,0,0,0.05);}"):
    st.markdown("### 🔍 Data Filters")
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    sel_channel = col1.selectbox("🛒 Channel", ["ALL"] + sorted(all_df['Channel'].dropna().unique().tolist()))
    sel_brand = col2.selectbox("🏷️ Brand", ["ALL"] + sorted(all_df['Brand'].dropna().unique().tolist()))
    sel_group = col3.selectbox("📦 Brand Group", ["ALL"] + sorted(all_df['Brand_Group'].dropna().unique().tolist()))
    sel_tier = col4.selectbox("💎 Tier", ["ALL"] + sorted(all_df['SKU_Tier'].dropna().unique().tolist()))
    sel_cover = col5.selectbox("📦 Stock Cover", ["ALL", "Overstock (>1.5)", "Healthy (0.5-1.5)", "Low (<0.5)", "Out of Stock (0)"])
    sel_focus = col6.selectbox("🎯 Product Focus", ["ALL", "Yes", "No"])

filtered_df = all_df.copy()
if sel_channel != "ALL": filtered_df = filtered_df[filtered_df['Channel'] == sel_channel]
if sel_brand != "ALL": filtered_df = filtered_df[filtered_df['Brand'] == sel_brand]
if sel_group != "ALL": filtered_df = filtered_df[filtered_df['Brand_Group'] == sel_group]
if sel_tier != "ALL": filtered_df = filtered_df[filtered_df['SKU_Tier'] == sel_tier]
if sel_cover == "Overstock (>1.5)": filtered_df = filtered_df[filtered_df['Month_Cover'] > 1.5]
elif sel_cover == "Healthy (0.5-1.5)": filtered_df = filtered_df[(filtered_df['Month_Cover'] >= 0.5) & (filtered_df['Month_Cover'] <= 1.5)]
elif sel_cover == "Low (<0.5)": filtered_df = filtered_df[filtered_df['Month_Cover'] < 0.5]
elif sel_cover == "Out of Stock (0)": filtered_df = filtered_df[filtered_df['Month_Cover'] == 0]
if sel_focus == "Yes": filtered_df = filtered_df[filtered_df['Product_Focus'].str.contains('Yes', case=False, na=False)]
elif sel_focus == "No": filtered_df = filtered_df[~filtered_df['Product_Focus'].str.contains('Yes', case=False, na=False)]

tab1, tab2, tab3 = st.tabs(["📝 Forecast Worksheet", "📈 Analytics Dashboard", "📊 Summary Reports"])

# ============================================================================
# TAB 1: FORECAST WORKSHEET
# ============================================================================
with tab1:
    if filtered_df.empty: st.warning("⚠️ No data matches filters.")
    else:
        edit_df = calculate_pct(filtered_df, adjustment_months)
        display_cols = ['sku_code', 'Product_Name', 'Channel', 'Brand', 'L3M_Avg', 'Stock_Qty', 'Month_Cover'] + horizon_months + [f'Cons_{m}' for m in adjustment_months]
        ag_df = edit_df[[c for c in display_cols if c in edit_df.columns]].copy()
        gb = GridOptionsBuilder.from_dataframe(ag_df)
        gb.configure_default_column(resizable=True, filterable=True, sortable=True, minWidth=100)
        gb.configure_column("sku_code", pinned="left")
        gb.configure_column("Product_Name", pinned="left", width=250)
        for m in adjustment_months:
            gb.configure_column(f'Cons_{m}', editable=True, cellStyle={'backgroundColor': '#EFF6FF', 'border': '2px solid #60A5FA'})
        grid_response = AgGrid(ag_df, gridOptions=gb.build(), update_mode=GridUpdateMode.VALUE_CHANGED, theme='alpine', allow_unsafe_jscode=True)
        updated_df = pd.DataFrame(grid_response['data'])
        if st.button("💾 Save Locally"): st.session_state.edited_v5 = updated_df.copy(); st.success("Saved!")

# ============================================================================
# TAB 2: ANALYTICS DASHBOARD (PREMIUM VERSION WITH COMMA FORMATTING)
# ============================================================================
with tab2:
    st.markdown("""<div style="background-color: #f8fafc; padding: 10px; border-radius: 10px; border-left: 5px solid #1E40AF; margin-bottom: 20px;"><h3 style="margin:0;">📊 Strategic Forecast Analytics</h3><p style="margin:0; color: #64748b; font-size: 0.9rem;">Deep dive into volume trends, revenue projections, and brand performance.</p></div>""", unsafe_allow_html=True)
    base_df = updated_df if 'updated_df' in locals() and not updated_df.empty else filtered_df
    if base_df.empty: st.warning("No data available."); st.stop()
    col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([2, 1, 1])
    chart_view = col_ctrl1.segmented_control("**Dimension View:**", ["Total Volume", "Brand Performance", "Channel Mix"], default="Brand Performance")
    val_mode = col_ctrl2.toggle("💰 Show in Value (IDR)", value=False)
    show_2026_only = col_ctrl3.checkbox("📅 2026 Only", value=True)
    active_months = [m for m in horizon_months if "-26" in m] if show_2026_only else horizon_months
    calc_df = base_df.copy()
    for m in active_months:
        source_col = f'Cons_{m}' if f'Cons_{m}' in calc_df.columns else m
        calc_df[f'Qty_{m}'] = pd.to_numeric(calc_df[source_col], errors='coerce').fillna(0)
        calc_df[f'Val_{m}'] = calc_df[f'Qty_{m}'] * calc_df.get('floor_price', 0)
    total_vol = sum(calc_df[f'Qty_{m}'].sum() for m in active_months)
    total_rev = sum(calc_df[f'Val_{m}'].sum() for m in active_months)
    m1_m3_vol = sum(calc_df[f'Qty_{m}'].sum() for m in adjustment_months[:3] if f'Qty_{m}' in calc_df.columns)
    l3m_total_avg = calc_df['L3M_Avg'].sum() * 3
    growth_vs_l3m = ((m1_m3_vol / l3m_total_avg) - 1) if l3m_total_avg > 0 else 0
    k1, k2, k3 = st.columns(3)
    k1.metric("📦 Projected Volume", f"{total_vol:,.0f} units")
    k2.metric("💰 Projected Revenue", f"Rp {total_rev:,.0f}")
    k3.metric("📈 Growth (M1-M3 vs L3M)", f"{growth_vs_l3m:+.1%}")
    style_metric_cards(background_color="#FFFFFF", border_left_color="#1E40AF", border_size_px=1, box_shadow=True)
    st.markdown("---")
    if chart_view == "Brand Performance":
        col_t, col_c = st.columns([1, 1])
        brand_data = [{"Brand": b, "Volume": sum(calc_df[calc_df['Brand']==b][f'Qty_{m}'].sum() for m in active_months), "Revenue": sum(calc_df[calc_df['Brand']==b][f'Val_{m}'].sum() for m in active_months)} for b in calc_df['Brand'].unique()]
        brand_summary = pd.DataFrame(brand_data).sort_values("Revenue", ascending=False)
        brand_summary['Share %'] = (brand_summary['Revenue'] / total_rev * 100).round(1) if total_rev > 0 else 0
        col_t.markdown("##### 🏆 Ranking by Revenue Share")
        col_t.dataframe(brand_summary, column_config={"Volume": st.column_config.NumberColumn(format="%,d"), "Revenue": st.column_config.NumberColumn(format="Rp %,d"), "Share %": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f%%")}, hide_index=True, use_container_width=True)
        plot_list = []
        for m in active_months:
            temp = calc_df.groupby('Brand')[f'Val_{m}' if val_mode else f'Qty_{m}'].sum().reset_index()
            temp['Month'], temp.columns = m, ['Brand', 'Value', 'Month']; plot_list.append(temp)
        fig = px.line(pd.concat(plot_list), x='Month', y='Value', color='Brand', markers=True); fig.update_layout(yaxis=dict(tickformat=",.0f"), hovermode="x unified"); col_c.plotly_chart(fig, use_container_width=True)
    elif chart_view == "Channel Mix":
        chan_list = []
        for m in active_months:
            temp = calc_df.groupby('Channel')[f'Val_{m}' if val_mode else f'Qty_{m}'].sum().reset_index()
            temp['Month'], temp.columns = m, ['Channel', 'Value', 'Month']; chan_list.append(temp)
        fig = px.bar(pd.concat(chan_list), x='Month', y='Value', color='Channel', barmode='group'); fig.update_layout(yaxis=dict(tickformat=",.0f")); st.plotly_chart(fig, use_container_width=True)
    else:
        agg_data = [{"Month": m, "Value": calc_df[f'Val_{m}' if val_mode else f'Qty_{m}'].sum()} for m in active_months]
        fig = px.area(pd.DataFrame(agg_data), x='Month', y='Value'); fig.update_layout(yaxis=dict(tickformat=",.0f")); st.plotly_chart(fig, use_container_width=True)
    with st.expander("💡 Key Strategic Insights", expanded=True):
        try:
            qty_available = [c for c in calc_df.columns if c.startswith('Qty_')]
            if qty_available and not calc_df.empty:
                temp_sum = calc_df[qty_available].sum(axis=1)
                st.write(f"🌟 **Leading SKU:** `{calc_df.loc[temp_sum.idxmax(), 'Product_Name']}` berkontribusi sebesar **{temp_sum.max():,.0f} units**.")
            st.info(f"💰 **Revenue Focus:** Total estimasi revenue sebesar **Rp {total_rev:,.0f}**.")
        except: st.error("Insights unavailable.")

# ============================================================================
# TAB 3: SUMMARY REPORTS - EXECUTIVE PRESENTATION (SAFE MODE)
# ============================================================================
with tab3:
    st.markdown("### 📋 Executive Summary Reports")
    report_df = updated_df if 'updated_df' in locals() and not updated_df.empty else filtered_df
    if report_df.empty: st.warning("Data kosong.")
    else:
        adj_cols = [f'Cons_{m}' for m in adjustment_months if f'Cons_{m}' in report_df.columns]
        if not adj_cols: adj_cols = [m for m in adjustment_months if m in report_df.columns]
        report_df = report_df.copy(); report_df['Temp_Total'] = report_df[adj_cols].sum(axis=1)
        total_f_qty = report_df['Temp_Total'].sum()
        total_l3m_qty = report_df['L3M_Avg'].sum() * len(adjustment_months)
        growth_pct = ((total_f_qty / total_l3m_qty) - 1) * 100 if total_l3m_qty > 0 else 0
        st.info(f"💡 **S&OP Perspective:** Forecast periode ini menunjukkan tren **{'Naik' if growth_pct > 0 else 'Turun'} {abs(growth_pct):.1f}%** vs L3M.")
        st.markdown("#### 🎯 Focus Area: Top SKU Contribution")
        st.dataframe(report_df.nlargest(10, 'Temp_Total')[['sku_code', 'Product_Name', 'Brand', 'L3M_Avg', 'Temp_Total', 'Month_Cover']], column_config={"Temp_Total": st.column_config.NumberColumn(format="%,d"), "L3M_Avg": st.column_config.NumberColumn(format="%,d"), "Month_Cover": st.column_config.NumberColumn(format="%.1f Mo")}, use_container_width=True, hide_index=True)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("##### 📦 Inventory Risk Matrix")
            risks = {"Critical Out (MoS < 0.5)": len(report_df[report_df['Month_Cover'] < 0.5]), "Healthy (0.5 - 1.5)": len(report_df[(report_df['Month_Cover'] >= 0.5) & (report_df['Month_Cover'] <= 1.5)]), "Overstock (> 1.5)": len(report_df[report_df['Month_Cover'] > 1.5])}
            for l, c in risks.items(): st.markdown(f"- **{l}**: :{'red' if 'Critical' in l else 'green' if 'Healthy' in l else 'blue'}[{c:,} SKUs]")
        with c2:
            st.markdown("##### 🏷️ Brand Concentration")
            st.plotly_chart(px.pie(report_df, values='Temp_Total', names='Brand', hole=0.4).update_layout(margin=dict(l=0,r=0,t=0,b=0), height=250), use_container_width=True)

# ============================================================================
# FOOTER
# ============================================================================
st.markdown("---")
st.markdown(f"""<div style="text-align: center; color: #6B7280; font-size: 0.9rem;"><p>📊 <b>ERHA S&OP Dashboard V5.5</b> | Last Updated: {datetime.now().strftime("%Y-%m-%d %H:%M")} | For internal use only</p></div>""", unsafe_allow_html=True)
