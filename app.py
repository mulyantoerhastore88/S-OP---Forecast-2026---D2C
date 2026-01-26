import streamlit as st
import pandas as pd
import numpy as np
import gspread
import plotly.graph_objects as go
import plotly.express as px
from google.oauth2.service_account import Credentials
import json
from datetime import datetime
import re
from dateutil.relativedelta import relativedelta
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode
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
# CSS STYLING
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
    .block-container { padding: 1rem 1.5rem; max-width: 100%; }
    .ag-theme-alpine { --ag-font-size: 12px !important; --ag-border-radius: 6px !important; }
    .ag-root-wrapper { min-height: 500px !important; height: calc(100vh - 320px) !important; border-radius: 8px !important; }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# GSHEET CONNECTOR
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
                st.error(f"❌ Error secrets: {str(e)}")
        else:
            st.error("❌ Secrets 'gsheets' not found.")

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
            worksheet = self.sheet.worksheet(sheet_name)
            data = worksheet.get_all_records(value_render_option='FORMATTED_VALUE') 
            return pd.DataFrame(data)
        except Exception as e:
            return pd.DataFrame()

    def save_data(self, df, sheet_name):
        try:
            try: worksheet = self.sheet.worksheet(sheet_name)
            except: worksheet = self.sheet.add_worksheet(title=sheet_name, rows=df.shape[0] + 100, cols=df.shape[1] + 5)
            df_clean = df.fillna('').infer_objects(copy=False)
            data_to_upload = [df_clean.columns.values.tolist()]
            for row in df_clean.values.tolist():
                data_to_upload.append([str(cell) for cell in row])
            worksheet.clear()
            worksheet.update(data_to_upload, value_input_option='USER_ENTERED')
            return True, "Success"
        except Exception as e:
            return False, str(e)

# ============================================================================
# HELPERS
# ============================================================================
def clean_currency(val):
    if pd.isna(val) or val == '' or val is None: return 0
    clean_str = re.sub(r'[^0-9]', '', str(val))
    try: return float(clean_str)
    except: return 0

def find_matching_column(target, cols):
    target_clean = target.lower().replace('-', '').replace(' ', '')
    for col in cols:
        if target_clean in str(col).lower().replace('-', '').replace(' ', ''): return col
    return None

def sort_month_columns(columns):
    month_cols = [c for c in columns if re.match(r'^[A-Za-z]{3}-\d{2}$', str(c))]
    month_cols.sort(key=lambda x: datetime.strptime(str(x), "%b-%y"))
    return month_cols

def calculate_pct(df, months):
    df_calc = df.copy()
    for m in months:
        if f'Cons_{m}' in df_calc.columns:
            mask = df_calc['L3M_Avg'] > 0
            df_calc.loc[mask, f'{m}_%'] = (df_calc.loc[mask, f'Cons_{m}'] / df_calc.loc[mask, 'L3M_Avg'] * 100).round(1)
            df_calc.loc[~mask, f'{m}_%'] = 100
    return df_calc

# ============================================================================
# DATA LOADER
# ============================================================================
@st.cache_data(ttl=600, show_spinner="Loading data...")
def load_data_v5(start_date_str, all_months=False):
    gs = GSheetConnector()
    sales_df = gs.get_sheet_data("sales_history")
    rofo_df = gs.get_sheet_data("rofo_current")
    stock_df = gs.get_sheet_data("stock_onhand")
    
    if sales_df.empty or rofo_df.empty: return pd.DataFrame()

    start_date = datetime.strptime(start_date_str, "%b-%y")
    horizon_months = [(start_date + relativedelta(months=i)).strftime("%b-%y") for i in range(12)]
    adjustment_months = horizon_months if all_months else horizon_months[:3]
    
    st.session_state.horizon_months = horizon_months
    st.session_state.adjustment_months = adjustment_months
    
    # Process ROFO
    floor_col = next((c for c in rofo_df.columns if 'floor' in c.lower()), None)
    rofo_df['floor_price'] = rofo_df[floor_col].apply(clean_currency) if floor_col else 0
    
    # Merge Logic
    keys = ['sku_code', 'Product_Name', 'Brand', 'Channel']
    sales_date_cols = sort_month_columns(sales_df.columns)
    l3m_cols = sales_date_cols[-3:] if len(sales_date_cols) >= 3 else sales_date_cols
    sales_df['L3M_Avg'] = sales_df[l3m_cols].applymap(clean_currency).mean(axis=1).round(0)
    
    merged_df = pd.merge(sales_df[keys + ['L3M_Avg']], rofo_df, on=keys, how='inner')
    
    # Stock Merge
    if not stock_df.empty:
        merged_df = pd.merge(merged_df, stock_df[['sku_code', stock_df.columns[1]]], on='sku_code', how='left')
        merged_df.rename(columns={stock_df.columns[1]: 'Stock_Qty'}, inplace=True)
        merged_df['Stock_Qty'] = merged_df['Stock_Qty'].apply(clean_currency).fillna(0)
    
    merged_df['Month_Cover'] = np.where(merged_df['L3M_Avg'] > 0, (merged_df['Stock_Qty'] / merged_df['L3M_Avg']).round(1), 0)
    
    for m in adjustment_months:
        real_col = find_matching_column(m, rofo_df.columns)
        merged_df[f'Cons_{m}'] = merged_df[real_col].apply(clean_currency) if real_col else 0
        
    return merged_df

# ============================================================================
# SIDEBAR
# ============================================================================
with st.sidebar:
    st.image("https://www.erhagroup.com/assets/img/logo-erha.png", width=150)
    start_options = [(datetime.now() + relativedelta(months=i)).strftime("%b-%y") for i in range(-1, 3)]
    selected_start_str = st.selectbox("Forecast Start Month", options=start_options, index=1)
    show_all_months = st.checkbox("📅 Show & Adjust All 12 Months", value=False)
    
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ============================================================================
# MAIN
# ============================================================================
all_df = load_data_v5(selected_start_str, show_all_months)
if all_df.empty: st.stop()

horizon_months = st.session_state.horizon_months
adjustment_months = st.session_state.adjustment_months

st.markdown(f'<div class="main-header"><h2>📊 ERHA S&OP Dashboard V5.5</h2><p>Horizon: {horizon_months[0]} - {horizon_months[-1]}</p></div>', unsafe_allow_html=True)

# Filters
col1, col2, col3, col4 = st.columns(4)
with col1: sel_brand = st.selectbox("🏷️ Brand", ["ALL"] + sorted(all_df['Brand'].unique().tolist()))
with col2: sel_channel = st.selectbox("🛒 Channel", ["ALL"] + sorted(all_df['Channel'].unique().tolist()))
with col3: 
    cover_opt = ["ALL", "Low (<0.5)", "Healthy (0.5-1.5)", "Overstock (>1.5)"]
    sel_cover = st.selectbox("📦 Stock Cover", cover_opt)

filtered_df = all_df.copy()
if sel_brand != "ALL": filtered_df = filtered_df[filtered_df['Brand'] == sel_brand]
if sel_channel != "ALL": filtered_df = filtered_df[filtered_df['Channel'] == sel_channel]
if sel_cover == "Low (<0.5)": filtered_df = filtered_df[filtered_df['Month_Cover'] < 0.5]
elif sel_cover == "Overstock (>1.5)": filtered_df = filtered_df[filtered_df['Month_Cover'] > 1.5]

tab1, tab2, tab3 = st.tabs(["📝 Forecast Worksheet", "📈 Analytics Dashboard", "📊 Summary Reports"])

# ============================================================================
# TAB 1: WORKSHEET
# ============================================================================
with tab1:
    edit_df = calculate_pct(filtered_df, adjustment_months)
    ag_df = edit_df.copy()
    
    gb = GridOptionsBuilder.from_dataframe(ag_df)
    gb.configure_default_column(resizable=True, filterable=True, sortable=True)
    gb.configure_column("sku_code", pinned="left", width=100)
    gb.configure_column("Product_Name", pinned="left", width=250)
    
    for m in adjustment_months:
        gb.configure_column(f'Cons_{m}', headerName=f"✏️ {m}", editable=True, 
                          cellStyle={'backgroundColor': '#EFF6FF', 'border': '1px solid #60A5FA'},
                          valueFormatter="params.value ? params.value.toLocaleString() : ''")

    grid_response = AgGrid(ag_df, gridOptions=gb.build(), update_mode=GridUpdateMode.VALUE_CHANGED, theme='alpine')
    updated_df = pd.DataFrame(grid_response['data'])

# ============================================================================
# TAB 2: ANALYTICS (FIXED FORMATTING)
# ============================================================================
with tab2:
    st.markdown("""<div style="background-color: #f8fafc; padding: 15px; border-radius: 10px; border-left: 5px solid #1E40AF; margin-bottom: 20px;">
        <h3 style="margin:0;">📊 Strategic Forecast Analytics</h3></div>""", unsafe_allow_html=True)
    
    base_df = updated_df if not updated_df.empty else filtered_df
    
    # Controls
    c_view, c_mode, c_year = st.columns([2, 1, 1])
    with c_view: chart_view = st.radio("**View Dimension:**", ["Total Volume", "Brand Performance", "Channel Mix"], horizontal=True)
    with c_mode: val_mode = st.toggle("💰 Show in Value (IDR)", value=False)
    with c_year: show_2026_only = st.checkbox("📅 2026 Only", value=True)

    active_months = [m for m in horizon_months if "-26" in m] if show_2026_only else horizon_months
    
    # Calculations
    calc_df = base_df.copy()
    for m in active_months:
        source = f'Cons_{m}' if f'Cons_{m}' in calc_df.columns else m
        calc_df[f'Qty_{m}'] = pd.to_numeric(calc_df[source], errors='coerce').fillna(0)
        calc_df[f'Val_{m}'] = calc_df[f'Qty_{m}'] * calc_df['floor_price']

    qty_cols = [f'Qty_{m}' for m in active_months]
    val_cols = [f'Val_{m}' for m in active_months]
    total_vol = calc_df[qty_cols].sum().sum()
    total_rev = calc_df[val_cols].sum().sum()

    # Metrics with Comma
    m1, m2, m3 = st.columns(3)
    with m1: st.metric("📦 Projected Volume", f"{total_vol:,.0f} units")
    with m2: st.metric("💰 Projected Revenue", f"Rp {total_rev:,.0f}")
    with m3: 
        m1_qty = calc_df[qty_cols[:3]].sum().sum() if len(qty_cols) >=3 else total_vol
        st.metric("📈 Growth (vs L3M)", f"{((m1_qty/(calc_df['L3M_Avg'].sum()*3 if calc_df['L3M_Avg'].sum()>0 else 1))-1):+.1%}")
    
    style_metric_cards(background_color="#FFFFFF", border_left_color="#1E40AF")

    # Table Ranking with Comma
    st.markdown("#### 🏆 Top Performance Ranking")
    rank_df = calc_df.groupby('Brand').agg({qty_cols[0]: 'sum', val_cols[0]: 'sum'}).reset_index() # Simplified for example
    rank_df = []
    for brand in calc_df['Brand'].unique():
        b_df = calc_df[calc_df['Brand'] == brand]
        rank_df.append({
            "Brand": brand, 
            "Total Qty": b_df[qty_cols].sum().sum(), 
            "Total Revenue": b_df[val_cols].sum().sum()
        })
    df_rank = pd.DataFrame(rank_df).sort_values("Total Revenue", ascending=False)
    
    st.dataframe(
        df_rank,
        column_config={
            "Total Qty": st.column_config.NumberColumn("Total Qty", format="%,d"),
            "Total Revenue": st.column_config.NumberColumn("Total IDR", format="Rp %,d")
        },
        use_container_width=True, hide_index=True
    )

    # Chart
    plot_prefix = "Val_" if val_mode else "Qty_"
    plot_data = []
    for m in active_months:
        temp = calc_df.groupby('Brand' if chart_view=="Brand Performance" else 'Channel' if chart_view=="Channel Mix" else 'Brand')[f'{plot_prefix}{m}'].sum().reset_index()
        temp['Month'] = m
        temp.columns = ['Category', 'Value', 'Month']
        plot_data.append(temp)
    
    df_chart = pd.concat(plot_data)
    fig = px.line(df_chart, x='Month', y='Value', color='Category', markers=True)
    fig.update_layout(yaxis=dict(tickformat=",.0f"), hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

# ============================================================================
# TAB 3: SUMMARY
# ============================================================================
with tab3:
    st.markdown("### 📋 Executive Summary Reports")
    report_df = base_df.copy()
    report_df['Temp_Total'] = report_df[[f'Cons_{m}' for m in adjustment_months if f'Cons_{m}' in report_df.columns]].sum(axis=1)
    
    top_10 = report_df.nlargest(10, 'Temp_Total')
    st.markdown("#### 🎯 Focus Area: Top 10 SKU Contribution")
    st.dataframe(
        top_10[['sku_code', 'Product_Name', 'Brand', 'L3M_Avg', 'Temp_Total', 'Month_Cover']],
        column_config={
            "Temp_Total": st.column_config.NumberColumn("Forecast Qty", format="%,d"),
            "L3M_Avg": st.column_config.NumberColumn("L3M Avg", format="%,d"),
            "Month_Cover": st.column_config.NumberColumn("MoS", format="%.1f")
        },
        use_container_width=True, hide_index=True
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### 📦 Inventory Risk Matrix")
        st.write(f"- Critical (<0.5): {len(report_df[report_df['Month_Cover']<0.5])} SKUs")
        st.write(f"- Healthy (0.5-1.5): {len(report_df[(report_df['Month_Cover']>=0.5)&(report_df['Month_Cover']<=1.5)])} SKUs")
    with c2:
        fig_pie = px.pie(report_df, values='Temp_Total', names='Brand', hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)

# Footer
st.markdown("---")
st.markdown(f'<div style="text-align:center;color:grey;font-size:0.8rem;">ERHA S&OP Dashboard | {datetime.now().strftime("%Y-%m-%d %H:%M")}</div>', unsafe_allow_html=True)
