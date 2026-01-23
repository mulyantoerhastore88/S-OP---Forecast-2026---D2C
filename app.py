import streamlit as st
import pandas as pd
import numpy as np
import gspread
import plotly.graph_objects as go
import plotly.express as px
from google.oauth2.service_account import Credentials
import json
from datetime import datetime
from dateutil.relativedelta import relativedelta
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode, JsCode
from streamlit_extras.metric_cards import style_metric_cards
from streamlit_extras.stylable_container import stylable_container

# ============================================================================
# PAGE CONFIG
# ============================================================================
st.set_page_config(
    page_title="ERHA S&OP Dashboard V4.2",
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
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        padding: 1.5rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .stSelectbox label { font-weight: bold; }
    div[data-testid="stMetricValue"] { font-size: 1.5rem; }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# 1. GSHEET CONNECTOR
# ============================================================================
class GSheetConnector:
    def __init__(self):
        if "gsheets" in st.secrets:
            self.sheet_id = st.secrets["gsheets"]["sheet_id"]
            self.service_account_info = json.loads(st.secrets["gsheets"]["service_account_info"])
            self.client = None
            self.connect()
        else:
            st.error("❌ Secrets 'gsheets' not found.")

    def connect(self):
        try:
            scope = ['https://www.googleapis.com/auth/spreadsheets']
            creds = Credentials.from_service_account_info(self.service_account_info, scopes=scope)
            self.client = gspread.authorize(creds)
            self.sheet = self.client.open_by_key(self.sheet_id)
        except Exception as e:
            st.error(f"Connection Error: {str(e)}")

    def get_sheet_data(self, sheet_name):
        try:
            worksheet = self.sheet.worksheet(sheet_name)
            data = worksheet.get_all_records()
            return pd.DataFrame(data)
        except:
            return pd.DataFrame()

    def save_data(self, df, sheet_name):
        try:
            try:
                worksheet = self.sheet.worksheet(sheet_name)
            except gspread.WorksheetNotFound:
                worksheet = self.sheet.add_worksheet(title=sheet_name, rows=1000, cols=20)
            
            df_clean = df.fillna('')
            data_to_upload = [df_clean.columns.values.tolist()] + df_clean.values.tolist()
            worksheet.clear()
            worksheet.update(data_to_upload)
            return True, "Success"
        except Exception as e:
            return False, str(e)

# ============================================================================
# 2. DATA LOADER (UPDATED WITH PRODUCT FOCUS)
# ============================================================================
@st.cache_data(ttl=300, show_spinner=False)
def load_data_with_cycle(selected_months):
    try:
        gs = GSheetConnector()
        sales_df = gs.get_sheet_data("sales_history")
        rofo_df = gs.get_sheet_data("rofo_current")
        stock_df = gs.get_sheet_data("stock_onhand")
        
        # Clean Columns
        for df in [sales_df, rofo_df, stock_df]:
            if not df.empty:
                df.columns = [c.strip().replace(' ', '_') for c in df.columns]
        
        if sales_df.empty or rofo_df.empty:
            return pd.DataFrame()

        # Merge Logic
        possible_keys = ['sku_code', 'Product_Name', 'Brand', 'Brand_Group', 'SKU_Tier', 'Channel']
        valid_keys = [k for k in possible_keys if k in sales_df.columns and k in rofo_df.columns]
        
        # Prepare Sales
        sales_date_cols = [c for c in sales_df.columns if '-' in c]
        l3m_cols = sales_date_cols[-3:] if len(sales_date_cols) >= 3 else sales_date_cols
        
        if l3m_cols:
            sales_df['L3M_Avg'] = sales_df[l3m_cols].mean(axis=1).round(0)
        else:
            sales_df['L3M_Avg'] = 0
            
        sales_subset = sales_df[valid_keys + ['L3M_Avg'] + l3m_cols].copy()
        
        # Prepare ROFO (Updated to fetch Product_Focus)
        rofo_cols = valid_keys.copy()
        
        # Cek kolom tambahan
        extra_cols = ['Channel', 'Product_Focus'] # LIST KOLOM TAMBAHAN DARI ROFO
        for col in extra_cols:
            if col in rofo_df.columns and col not in rofo_cols:
                rofo_cols.append(col)
            
        for m in selected_months:
            if m in rofo_df.columns:
                rofo_cols.append(m)
        
        rofo_subset = rofo_df[rofo_cols].copy()
        
        # Merge
        merged_df = pd.merge(sales_subset, rofo_subset, on=valid_keys, how='inner')
        
        # Isi blank jika Product_Focus tidak ada
        if 'Product_Focus' not in merged_df.columns:
            merged_df['Product_Focus'] = ""
        else:
            merged_df['Product_Focus'] = merged_df['Product_Focus'].fillna("")

        for m in selected_months:
            if m not in merged_df.columns:
                merged_df[m] = 0
                
        # Merge Stock
        if not stock_df.empty and 'sku_code' in stock_df.columns:
            stock_col = 'Stock_Qty' if 'Stock_Qty' in stock_df.columns else stock_df.columns[1]
            merged_df = pd.merge(merged_df, stock_df[['sku_code', stock_col]], on='sku_code', how='left')
            merged_df.rename(columns={stock_col: 'Stock_Qty'}, inplace=True)
        else:
            merged_df['Stock_Qty'] = 0
        merged_df['Stock_Qty'] = merged_df['Stock_Qty'].fillna(0)

        # Metrics
        merged_df['Month_Cover'] = (merged_df['Stock_Qty'] / merged_df['L3M_Avg'].replace(0, 1)).round(1)
        merged_df['Month_Cover'] = merged_df['Month_Cover'].replace([np.inf, -np.inf], 0)
        
        # Init Consensus
        for m in selected_months:
            merged_df[f'Cons_{m}'] = merged_df[m]
            
        return merged_df

    except Exception as e:
        st.error(f"Error: {str(e)}")
        return pd.DataFrame()

def calculate_pct(df, months):
    df_calc = df.copy()
    for m in months:
        if f'Cons_{m}' in df_calc.columns:
            pct = (df_calc[f'Cons_{m}'] / df_calc['L3M_Avg'].replace(0, np.nan) * 100).round(1)
            df_calc[f'{m}_%'] = pct.replace([np.inf, -np.inf], 0).fillna(100)
    return df_calc

# ============================================================================
# SIDEBAR
# ============================================================================
with st.sidebar:
    st.image("https://www.erhagroup.com/assets/img/logo-erha.png", width=150)
    st.markdown("### ⚙️ Planning Cycle")
    
    curr_date = datetime.now()
    start_list = [curr_date + relativedelta(months=i) for i in range(-1, 3)]
    option_map = {d.strftime("%b-%y"): d for d in start_list}
    default_idx = 1 if curr_date.day < 5 else 2
    
    selected_start_str = st.selectbox("Forecast Start Month", options=list(option_map.keys()), index=default_idx)
    
    start_date = option_map[selected_start_str]
    cycle_months = [
        (start_date).strftime("%b-%y"),
        (start_date + relativedelta(months=1)).strftime("%b-%y"),
        (start_date + relativedelta(months=2)).strftime("%b-%y")
    ]
    st.session_state.adjustment_months = cycle_months
    
    st.info(f"📅 Active Cycle:\n**{', '.join(cycle_months)}**")
    if st.button("🔄 Reload Data Source"):
        st.cache_data.clear()
        st.rerun()

# ============================================================================
# MAIN CONTENT
# ============================================================================

st.markdown(f"""
<div class="main-header">
    <h2>📊 ERHA S&OP Dashboard - Multi Channel</h2>
    <p>Cycle: <b>{cycle_months[0]} - {cycle_months[2]}</b> | Mode: E-Commerce & Reseller Stacked</p>
</div>
""", unsafe_allow_html=True)

all_df = load_data_with_cycle(cycle_months)
if all_df.empty:
    st.warning("No data found.")
    st.stop()

# FILTER BAR
with stylable_container(key="filters", css_styles="{background:white; padding:15px; border-radius:10px; border:1px solid #ddd;}"):
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        channels = ["ALL"] + sorted(all_df['Channel'].dropna().unique().tolist()) if 'Channel' in all_df.columns else ["ALL"]
        sel_channel = st.selectbox("🛒 Channel", channels)
    with c2:
        brands = ["ALL"] + sorted(all_df['Brand'].dropna().unique().tolist()) if 'Brand' in all_df.columns else ["ALL"]
        sel_brand = st.selectbox("🏷️ Brand", brands)
    with c3:
        b_groups = ["ALL"] + sorted(all_df['Brand_Group'].dropna().unique().tolist()) if 'Brand_Group' in all_df.columns else ["ALL"]
        sel_group = st.selectbox("📦 Brand Group", b_groups)
    with c4:
        tiers = ["ALL"] + sorted(all_df['SKU_Tier'].dropna().unique().tolist()) if 'SKU_Tier' in all_df.columns else ["ALL"]
        sel_tier = st.selectbox("💎 Tier", tiers)
    with c5:
        covers = ["ALL", "Over (>1.5)", "Healthy", "Low"]
        sel_cover = st.selectbox("📉 Stock Cover", covers)

filtered_df = all_df.copy()
if sel_channel != "ALL" and 'Channel' in filtered_df.columns: filtered_df = filtered_df[filtered_df['Channel'] == sel_channel]
if sel_brand != "ALL": filtered_df = filtered_df[filtered_df['Brand'] == sel_brand]
if sel_group != "ALL": filtered_df = filtered_df[filtered_df['Brand_Group'] == sel_group]
if sel_tier != "ALL": filtered_df = filtered_df[filtered_df['SKU_Tier'] == sel_tier]
if sel_cover == "Over (>1.5)": filtered_df = filtered_df[filtered_df['Month_Cover'] > 1.5]

tab1, tab2 = st.tabs(["📝 Forecast Worksheet", "📈 Analytics Summary"])

# ============================================================================
# TAB 1: WORKSHEET
# ============================================================================
with tab1:
    edit_df = filtered_df.copy()
    edit_df = calculate_pct(edit_df, cycle_months)
    
    # KITA MASUKKAN Product_Focus KE AG_COLS AGAR BISA DIBACA JS
    ag_cols = ['sku_code', 'Product_Name', 'Channel', 'Brand', 'SKU_Tier', 'Product_Focus']
    
    hist_cols = [c for c in edit_df.columns if '-' in c and c not in cycle_months and 'Cons' not in c and '%' not in c][-3:]
    ag_cols.extend(hist_cols)
    ag_cols.extend(['L3M_Avg', 'Stock_Qty', 'Month_Cover'])
    ag_cols.extend(cycle_months)
    ag_cols.extend([f'{m}_%' for m in cycle_months])
    ag_cols.extend([f'Cons_{m}' for m in cycle_months])
    ag_cols = [c for c in ag_cols if c in edit_df.columns]
    
    ag_df = edit_df[ag_cols].copy()

    # --- JS STYLING ---
    
    # 1. WARNA SKU JIKA FOCUS PRODUCT (Highlight Kuning Emas)
    # params.data.Product_Focus mengakses data kolom lain di baris yg sama
    js_sku_focus = JsCode("""
    function(params) {
        if (params.data.Product_Focus === 'Yes') {
            return {
                'backgroundColor': '#FEF9C3', // Yellow 100
                'color': '#854D0E',           // Yellow 800
                'fontWeight': 'bold',
                'borderLeft': '4px solid #FACC15' // Gold Bar
            };
        }
        return null; 
    }
    """)

    js_brand = JsCode("""
    function(params) {
        if (!params.value) return null;
        const b = params.value.toLowerCase();
        if (b.includes('acne')) return {'backgroundColor': '#E0F2FE', 'color': '#0284C7', 'fontWeight': 'bold'};
        if (b.includes('tru')) return {'backgroundColor': '#DCFCE7', 'color': '#16A34A', 'fontWeight': 'bold'};
        if (b.includes('hair')) return {'backgroundColor': '#FEF3C7', 'color': '#D97706', 'fontWeight': 'bold'};
        if (b.includes('age')) return {'backgroundColor': '#E0E7FF', 'color': '#4F46E5', 'fontWeight': 'bold'};
        if (b.includes('his')) return {'backgroundColor': '#F3E8FF', 'color': '#7C3AED', 'fontWeight': 'bold'};
        return {'backgroundColor': '#F3F4F6'};
    }
    """)
    
    js_channel = JsCode("""
    function(params) {
        if (!params.value) return null;
        if (params.value === 'E-commerce') return {'color': '#EA580C', 'fontWeight': 'bold'};
        if (params.value === 'Reseller') return {'color': '#059669', 'fontWeight': 'bold'};
        return null;
    }
    """)
    
    js_cover = JsCode("function(p) { if(p.value > 1.5) return {'backgroundColor': '#FCE7F3', 'color': '#BE185D', 'fontWeight': 'bold'}; return null; }")
    
    js_pct = JsCode("""
    function(params) {
        if (params.value < 90) return {'backgroundColor': '#FFEDD5', 'color': '#9A3412', 'fontWeight': 'bold'};
        if (params.value > 130) return {'backgroundColor': '#FEE2E2', 'color': '#991B1B', 'fontWeight': 'bold'};
        return {'color': '#374151'};
    }
    """)
    
    js_edit = JsCode("function(p) { return {'backgroundColor': '#EFF6FF', 'border': '1px solid #93C5FD', 'fontWeight': 'bold', 'color': '#1E40AF'}; }")

    # --- GRID CONFIG ---
    gb = GridOptionsBuilder.from_dataframe(ag_df)
    gb.configure_default_column(resizable=True, filterable=True, sortable=True, editable=False)
    
    # Apply Highlight to SKU Code based on Hidden Column
    gb.configure_column("sku_code", pinned="left", width=100, cellStyle=js_sku_focus)
    
    # HIDE PRODUCT FOCUS COLUMN (Data ada di grid, tapi user gak liat)
    gb.configure_column("Product_Focus", hide=True)
    
    gb.configure_column("Product_Name", pinned="left", width=200)
    gb.configure_column("Channel", pinned="left", width=100, cellStyle=js_channel)
    gb.configure_column("Brand", cellStyle=js_brand, width=110)
    gb.configure_column("Month_Cover", cellStyle=js_cover, width=90)
    
    # Apply number format
    for c in ag_cols:
        if c not in ['sku_code', 'Product_Name', 'Channel', 'Brand', 'SKU_Tier', 'Month_Cover', 'Product_Focus'] and '%' not in c:
            gb.configure_column(c, type=["numericColumn"], valueFormatter="x.toLocaleString()", width=95)
    
    for m in cycle_months:
        pct_col = f'{m}_%'
        if pct_col in ag_cols:
            gb.configure_column(pct_col, header_name=f"{m} %", type=["numericColumn"], 
                              valueFormatter="x.toFixed(1) + '%'", cellStyle=js_pct, width=85)

    for m in cycle_months:
        if f'Cons_{m}' in ag_cols:
            gb.configure_column(f'Cons_{m}', header_name=f"✏️ {m}", editable=True, 
                                cellStyle=js_edit, width=110, pinned="right", 
                                type=["numericColumn"], valueFormatter="x.toLocaleString()")

    gb.configure_selection('single')
    
    # Legend
    st.markdown("""
    <div style="font-size:0.8rem; margin-bottom:5px;">
        <span style="background:#FEF9C3; color:#854D0E; padding:2px 6px; border-radius:4px; border:1px solid #FACC15"><b>★ Focus SKU</b></span>
        <span style="background:#FCE7F3; color:#BE185D; padding:2px 6px; border-radius:4px;"><b>Cover > 1.5</b></span>
        <span style="background:#FFEDD5; color:#9A3412; padding:2px 6px; border-radius:4px;"><b>Growth < 90%</b></span>
    </div>
    """, unsafe_allow_html=True)
    
    grid_res = AgGrid(ag_df, gridOptions=gb.build(), allow_unsafe_jscode=True, 
                      update_mode=GridUpdateMode.VALUE_CHANGED, height=550, theme='alpine', key='v4_2_grid')
    
    updated_df = pd.DataFrame(grid_res['data'])

    # ACTIONS
    st.markdown("---")
    c_save, c_push, c_info = st.columns([1, 1, 2])
    with c_save:
        if st.button("💾 Save Changes (Local)", type="primary", use_container_width=True):
            st.session_state.edited_v4 = updated_df.copy()
            st.success("Saved to session!")
    with c_push:
        if st.button("☁️ Push to GSheets", type="secondary", use_container_width=True):
            if 'edited_v4' not in st.session_state: st.warning("Save locally first!")
            else:
                with st.spinner("Pushing data..."):
                    # Jangan lupa sertakan Product_Focus saat save balik agar tidak hilang
                    keep = ['sku_code', 'Product_Name', 'Channel', 'Brand', 'SKU_Tier', 'Product_Focus'] + [f'Cons_{m}' for m in cycle_months]
                    final = st.session_state.edited_v4[keep].copy()
                    final['Last_Update'] = datetime.now().strftime('%Y-%m-%d %H:%M')
                    gs = GSheetConnector()
                    ok, msg = gs.save_data(final, "consensus_rofo")
                    if ok: st.balloons(); st.success("Done!")
                    else: st.error(msg)
    with c_info:
        total = 0
        for m in cycle_months:
             if f'Cons_{m}' in updated_df.columns: total += updated_df[f'Cons_{m}'].sum()
        st.metric("Total Forecast", f"{total:,.0f}")

with tab2:
    viz_df = updated_df if not updated_df.empty else filtered_df
    c1, c2 = st.columns(2)
    with c1:
        if 'Channel' in viz_df.columns:
            cons_cols = [f'Cons_{m}' for m in cycle_months if f'Cons_{m}' in viz_df.columns]
            if cons_cols:
                viz_df['Total_Cons'] = viz_df[cons_cols].sum(axis=1)
                ch_agg = viz_df.groupby('Channel')['Total_Cons'].sum().reset_index()
                fig = px.bar(ch_agg, x='Channel', y='Total_Cons', title="Total Volume by Channel", color='Channel', color_discrete_map={'E-commerce':'#EA580C', 'Reseller':'#059669'})
                st.plotly_chart(fig, use_container_width=True)
    with c2:
        trend_data = []
        for m in cycle_months:
             if f'Cons_{m}' in viz_df.columns: trend_data.append({'Month': m, 'Value': viz_df[f'Cons_{m}'].sum()})
        if trend_data:
            st.plotly_chart(px.line(pd.DataFrame(trend_data), x='Month', y='Value', markers=True, title="Monthly Trend"), use_container_width=True)
