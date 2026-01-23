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
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode, JsCode
from streamlit_extras.metric_cards import style_metric_cards
from streamlit_extras.stylable_container import stylable_container

# ============================================================================
# PAGE CONFIG
# ============================================================================
st.set_page_config(
    page_title="ERHA S&OP Dashboard V6.0",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# CSS
# ============================================================================
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
        padding: 1.5rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .stSelectbox label { font-weight: bold; }
    div[data-testid="stMetricValue"] { font-size: 1.4rem; }
    .block-container { padding: 2rem; max-width: 100%; }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# CONNECTOR
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
            
            # Untuk stock_onhand, gunakan UNFORMATTED_VALUE
            if sheet_name == "stock_onhand":
                data = worksheet.get_all_records(value_render_option='UNFORMATTED_VALUE')
            else:
                data = worksheet.get_all_records(value_render_option='FORMATTED_VALUE')
                
            return pd.DataFrame(data)
        except Exception as e:
            st.error(f"Error loading {sheet_name}: {str(e)}")
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
# HELPER FUNCTIONS (FIXED STOCK LOGIC)
# ============================================================================
def clean_currency(val):
    """
    Clean currency values from Google Sheets.
    Handles:
    - Rp 1.250.000 → 1250000
    - 1,250 → 1250
    - 1250 → 1250 (tetap)
    - '125' → 125 (tidak dikalikan 10)
    """
    if pd.isna(val) or val == '' or val is None:
        return 0
    
    val_str = str(val).strip()
    
    # Jika sudah berupa angka (tanpa Rp, koma, titik)
    if val_str.replace('.', '').replace(',', '').isdigit():
        # Cek jika ada titik sebagai pemisah ribuan
        if '.' in val_str and ',' not in val_str:
            # Format: 1.250 (ribuan) atau 1.250.000 (jutaan)
            parts = val_str.split('.')
            if len(parts[-1]) == 3:  # 3 digit terakhir
                # Ini format ribuan: 1.250 → 1250
                return float(val_str.replace('.', ''))
            else:
                # Format desimal atau ambigu
                try:
                    return float(val_str.replace('.', ''))
                except:
                    return float(val_str)
        elif ',' in val_str and '.' not in val_str:
            # Format: 1,250 (ribuan) atau 1,250,000
            return float(val_str.replace(',', ''))
        else:
            # Angka biasa tanpa separator
            try:
                return float(val_str)
            except:
                return 0
    
    # Jika ada Rp atau simbol mata uang
    if 'rp' in val_str.lower():
        # Hapus Rp dan spasi
        clean = re.sub(r'[^0-9.,]', '', val_str.lower().replace('rp', ''))
        # Hapus titik dan koma
        clean = clean.replace('.', '').replace(',', '')
        try:
            return float(clean) if clean else 0
        except:
            return 0
    
    # Untuk nilai dengan titik sebagai desimal
    if '.' in val_str and val_str.count('.') == 1:
        try:
            return float(val_str)
        except:
            pass
    
    # Fallback: coba konversi langsung
    try:
        return float(val_str)
    except:
        return 0

def find_matching_column(target_month, available_columns):
    if target_month in available_columns: return target_month
    tgt = target_month.lower().replace('-', '').replace(' ', '').replace('_', '')
    for col in available_columns:
        c = str(col).lower().replace('-', '').replace(' ', '').replace('_', '')
        if tgt == c: return col
    return None

def identify_sales_columns(columns):
    sales_cols = []
    for col in columns:
        try:
            # Cek ada angka digit dalam nama kolom (Oct-25)
            if any(char.isdigit() for char in str(col)):
                pd.to_datetime(col, errors='raise')
                sales_cols.append(col)
        except:
            pass
    if not sales_cols:
        months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
        for col in columns:
            c_lower = str(col).lower()
            if any(m in c_lower for m in months) and any(char.isdigit() for char in c_lower):
                sales_cols.append(col)
    return sorted(sales_cols)

# ============================================================================
# DATA LOADER
# ============================================================================
@st.cache_data(ttl=300, show_spinner=False)
def load_data_v5(start_date_str):
    try:
        gs = GSheetConnector()
        sales_df = gs.get_sheet_data("sales_history")
        rofo_df = gs.get_sheet_data("rofo_current")
        stock_df = gs.get_sheet_data("stock_onhand")
        
        # 1. Clean Headers
        for df in [sales_df, rofo_df, stock_df]:
            if not df.empty:
                df.columns = [str(c).strip() for c in df.columns]

        if sales_df.empty or rofo_df.empty: return pd.DataFrame()

        # 2. Horizon
        start_date = datetime.strptime(start_date_str, "%b-%y")
        horizon_months = [(start_date + relativedelta(months=i)).strftime("%b-%y") for i in range(12)]
        st.session_state.horizon_months = horizon_months

        # 3. Keys & Renaming
        key_map = {'Product Name': 'Product_Name', 'Brand Group': 'Brand_Group', 'SKU Tier': 'SKU_Tier'}
        sales_df.rename(columns=key_map, inplace=True)
        rofo_df.rename(columns=key_map, inplace=True)
        
        possible_keys = ['sku_code', 'Product_Name', 'Brand', 'Brand_Group', 'SKU_Tier', 'Channel']
        valid_keys = [k for k in possible_keys if k in sales_df.columns and k in rofo_df.columns]

        # 4. SALES (FIXED: Clean Values First)
        sales_date_cols = identify_sales_columns(sales_df.columns)
        st.session_state.debug_sales_cols = sales_date_cols
        
        l3m_cols = sales_date_cols[-3:] if len(sales_date_cols) >= 3 else sales_date_cols
        
        if l3m_cols:
            for c in l3m_cols:
                sales_df[c] = sales_df[c].apply(clean_currency)
            sales_df['L3M_Avg'] = sales_df[l3m_cols].mean(axis=1).round(0)
        else:
            sales_df['L3M_Avg'] = 0
            
        sales_subset = sales_df[valid_keys + ['L3M_Avg'] + l3m_cols].copy()

        # 5. ROFO
        rofo_cols_to_fetch = valid_keys.copy()
        
        # Floor Price
        if 'floor_price' in rofo_df.columns:
            rofo_df['floor_price'] = rofo_df['floor_price'].apply(clean_currency)
        else:
            fp_candidates = [c for c in rofo_df.columns if 'floor' in c.lower()]
            if fp_candidates:
                rofo_df.rename(columns={fp_candidates[0]: 'floor_price'}, inplace=True)
                rofo_df['floor_price'] = rofo_df['floor_price'].apply(clean_currency)
            else:
                rofo_df['floor_price'] = 0
        
        for extra in ['Channel', 'Product_Focus', 'floor_price']:
            if extra in rofo_df.columns and extra not in rofo_cols_to_fetch:
                rofo_cols_to_fetch.append(extra)
        
        month_mapping = {}
        for m in horizon_months:
            real_col = find_matching_column(m, rofo_df.columns)
            if real_col:
                month_mapping[m] = real_col
                if real_col not in rofo_cols_to_fetch: rofo_cols_to_fetch.append(real_col)
                rofo_df[real_col] = rofo_df[real_col].apply(clean_currency)
        
        rofo_subset = rofo_df[rofo_cols_to_fetch].copy()
        inv_map = {v: k for k, v in month_mapping.items()}
        rofo_subset.rename(columns=inv_map, inplace=True)

        # 6. MERGE
        merged_df = pd.merge(sales_subset, rofo_subset, on=valid_keys, how='inner')
        
        for col in ['Product_Focus', 'Channel']:
            if col not in merged_df.columns: merged_df[col] = ""
            else: merged_df[col] = merged_df[col].fillna("")
            
        if 'floor_price' not in merged_df.columns: merged_df['floor_price'] = 0
        else: merged_df['floor_price'] = merged_df['floor_price'].fillna(0)
        
        for m in horizon_months:
            if m not in merged_df.columns: merged_df[m] = 0

        # 7. STOCK (FIXED CLEANING)
        if not stock_df.empty and 'sku_code' in stock_df.columns:
            stock_cols = [c for c in stock_df.columns if 'qty' in c.lower() or 'stock' in c.lower()]
            target_stock_col = stock_cols[0] if stock_cols else stock_df.columns[1]
            stock_df[target_stock_col] = stock_df[target_stock_col].apply(clean_currency)
            stock_df_agg = stock_df.groupby('sku_code')[target_stock_col].sum().reset_index()
            stock_df_agg.rename(columns={target_stock_col: 'Stock_Qty'}, inplace=True)
            merged_df = pd.merge(merged_df, stock_df_agg, on='sku_code', how='left')
        else:
            merged_df['Stock_Qty'] = 0
            
        merged_df['Stock_Qty'] = merged_df['Stock_Qty'].fillna(0)

        # 8. METRICS (LOGIC FIX: NO MORE *10 ERROR)
        # Jika L3M = 0 dan Stock > 0 -> Month Cover = 999 (Infinite)
        # Jika L3M > 0 -> Hitung normal
        
        mask_zero_l3m = merged_df['L3M_Avg'] <= 0
        merged_df.loc[mask_zero_l3m, 'Month_Cover'] = np.where(merged_df.loc[mask_zero_l3m, 'Stock_Qty'] > 0, 999, 0)
        merged_df.loc[~mask_zero_l3m, 'Month_Cover'] = (merged_df.loc[~mask_zero_l3m, 'Stock_Qty'] / merged_df.loc[~mask_zero_l3m, 'L3M_Avg']).round(1)
        
        cycle_months = horizon_months[:3]
        for m in cycle_months:
            merged_df[f'Cons_{m}'] = merged_df[m]
            
        return merged_df

    except Exception as e:
        st.error(f"Error Loading: {str(e)}")
        return pd.DataFrame()

def calculate_pct(df, months):
    df_calc = df.copy()
    for m in months:
        if f'Cons_{m}' in df_calc.columns:
            pct = (df_calc[f'Cons_{m}'] / df_calc['L3M_Avg'].replace(0, np.nan) * 100).round(1)
            df_calc[f'{m}_%'] = pct.replace([np.inf, -np.inf], 0).fillna(100)
    return df_calc

# ============================================================================
# UI
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
    st.info(f"**Cycle:** {', '.join(cycle_months)}")
    if st.button("🔄 Reload Data"): st.cache_data.clear(); st.rerun()
    
    with st.expander("🕵️ Debug L3M Sales"):
        if 'debug_sales_cols' in st.session_state:
            st.write("Detected Sales Cols:", st.session_state.debug_sales_cols)
        else:
            st.warning("No sales columns detected")

st.markdown(f"""
<div class="main-header">
    <h2>📊 ERHA S&OP Dashboard V6.0</h2>
    <p>Horizon: <b>{cycle_months[0]} - {cycle_months[2]} (Consensus)</b> + Next 9 Months (ROFO)</p>
</div>
""", unsafe_allow_html=True)

all_df = load_data_v5(selected_start_str)
if all_df.empty: st.warning("No data found."); st.stop()

with stylable_container(key="filters", css_styles="{background:white; padding:15px; border-radius:10px; border:1px solid #E2E8F0;}"):
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
elif sel_cover == "Healthy": filtered_df = filtered_df[(filtered_df['Month_Cover'] >= 0.5) & (filtered_df['Month_Cover'] <= 1.5)]
elif sel_cover == "Low": filtered_df = filtered_df[filtered_df['Month_Cover'] < 0.5]

tab1, tab2 = st.tabs(["📝 Forecast Worksheet", "📈 Analytics"])

with tab1:
    edit_df = filtered_df.copy()
    edit_df = calculate_pct(edit_df, cycle_months)
    
    ag_cols = ['sku_code', 'Product_Name', 'Channel', 'Brand', 'SKU_Tier', 'Product_Focus', 'floor_price']
    
    hist_cols = [c for c in edit_df.columns if c in st.session_state.get('debug_sales_cols', [])][-3:]
    
    ag_cols.extend(hist_cols)
    ag_cols.extend(['L3M_Avg', 'Stock_Qty', 'Month_Cover'])
    ag_cols.extend(st.session_state.horizon_months)
    ag_cols.extend([f'{m}_%' for m in cycle_months])
    ag_cols.extend([f'Cons_{m}' for m in cycle_months])
    
    ag_cols = list(dict.fromkeys(ag_cols))
    ag_cols = [c for c in ag_cols if c in edit_df.columns]
    
    ag_df = edit_df[ag_cols].copy()

    js_sku_focus = JsCode("function(p) { if(p.data.Product_Focus === 'Yes') return {'backgroundColor': '#CCFBF1', 'color': '#0F766E', 'fontWeight': 'bold', 'borderLeft': '4px solid #14B8A6'}; return null; }")
    js_brand = JsCode("function(p) { if(!p.value) return null; const b=p.value.toLowerCase(); if(b.includes('acne')) return {'backgroundColor':'#E0F2FE','color':'#0284C7','fontWeight':'bold'}; if(b.includes('tru')) return {'backgroundColor':'#DCFCE7','color':'#16A34A','fontWeight':'bold'}; if(b.includes('hair')) return {'backgroundColor':'#FEF3C7','color':'#D97706','fontWeight':'bold'}; if(b.includes('age')) return {'backgroundColor':'#E0E7FF','color':'#4F46E5','fontWeight':'bold'}; if(b.includes('his')) return {'backgroundColor':'#F3E8FF','color':'#7C3AED','fontWeight':'bold'}; return {'backgroundColor':'#F3F4F6'}; }")
    js_channel = JsCode("function(p) { if(!p.value) return null; if(p.value==='E-commerce') return {'color':'#EA580C','fontWeight':'bold'}; if(p.value==='Reseller') return {'color':'#059669','fontWeight':'bold'}; return null; }")
    js_cover = JsCode("function(p) { if(p.value > 1.5 && p.value < 900) return {'backgroundColor': '#FECACA', 'color': '#B91C1C', 'fontWeight': 'bold'}; if(p.value >= 900) return {'color': '#9CA3AF', 'fontStyle': 'italic'}; return null; }")
    js_pct = JsCode("function(p) { if(p.value < 90) return {'backgroundColor': '#FFEDD5', 'color': '#9A3412', 'fontWeight': 'bold'}; if(p.value > 130) return {'backgroundColor': '#FEE2E2', 'color': '#991B1B', 'fontWeight': 'bold'}; return {'color': '#374151'}; }")
    js_edit = JsCode("function(p) { return {'backgroundColor': '#EFF6FF', 'border': '1px solid #93C5FD', 'fontWeight': 'bold', 'color': '#1E40AF'}; }")

    gb = GridOptionsBuilder.from_dataframe(ag_df)
    gb.configure_grid_options(rowHeight=35, headerHeight=40)
    gb.configure_default_column(resizable=True, filterable=True, sortable=True, editable=False, minWidth=95)
    
    gb.configure_column("sku_code", pinned="left", width=100, cellStyle=js_sku_focus)
    gb.configure_column("Product_Name", pinned="left", minWidth=200, flex=1)
    gb.configure_column("Channel", pinned="left", width=110, cellStyle=js_channel)
    gb.configure_column("Product_Focus", hide=True)
    gb.configure_column("floor_price", hide=True) 
    gb.configure_column("Brand", cellStyle=js_brand, width=120)
    gb.configure_column("Month_Cover", cellStyle=js_cover, width=100)
    
    for m in st.session_state.horizon_months:
        if m not in cycle_months: gb.configure_column(m, hide=True)
    
    for c in ag_cols:
        if c not in ['sku_code', 'Product_Name', 'Channel', 'Brand', 'SKU_Tier', 'Month_Cover', 'Product_Focus', 'floor_price'] and '%' not in c:
            gb.configure_column(c, type=["numericColumn"], valueFormatter="x.toLocaleString()", minWidth=105)
            
    for m in cycle_months:
        if f'{m}_%' in ag_cols: gb.configure_column(f'{m}_%', header_name=f"{m} %", type=["numericColumn"], valueFormatter="x.toFixed(1) + '%'", cellStyle=js_pct, minWidth=90)
        if f'Cons_{m}' in ag_cols: gb.configure_column(f'Cons_{m}', header_name=f"✏️ {m}", editable=True, cellStyle=js_edit, width=115, pinned="right", type=["numericColumn"], valueFormatter="x.toLocaleString()")

    gb.configure_selection('single')
    grid_res = AgGrid(ag_df, gridOptions=gb.build(), allow_unsafe_jscode=True, update_mode=GridUpdateMode.VALUE_CHANGED, height=600, theme='alpine', key='v5_worksheet', use_container_width=True)
    updated_df = pd.DataFrame(grid_res['data'])

    st.markdown("---")
    c_save, c_push, c_info = st.columns([1, 1, 2])
    with c_save:
        if st.button("💾 Save (Local)", type="primary", use_container_width=True):
            st.session_state.edited_v5 = updated_df.copy(); st.success("Saved!")
    with c_push:
        if st.button("☁️ Push (GSheets)", type="secondary", use_container_width=True):
            if 'edited_v5' not in st.session_state: st.warning("Save locally first!")
            else:
                with st.spinner("Pushing..."):
                    keep = ['sku_code', 'Product_Name', 'Channel', 'Brand', 'SKU_Tier', 'Product_Focus'] + [f'Cons_{m}' for m in cycle_months]
                    final = st.session_state.edited_v5[keep].copy()
                    final['Last_Update'] = datetime.now().strftime('%Y-%m-%d %H:%M')
                    gs = GSheetConnector()
                    ok, msg = gs.save_data(final, "consensus_rofo")
                    if ok: st.balloons(); st.success("Done!")
                    else: st.error(msg)
    with c_info:
        total = 0
        for m in cycle_months:
             if f'Cons_{m}' in updated_df.columns: total += updated_df[f'Cons_{m}'].sum()
        st.metric("Total Consensus (M1-M3)", f"{total:,.0f}")

with tab2:
    st.markdown("### 📈 Projection Analytics")
    base_df = updated_df if not updated_df.empty else filtered_df
    if base_df.empty: st.stop()
    full_horizon = st.session_state.horizon_months
    
    c_view, c_year = st.columns([2, 1])
    with c_view: chart_view = st.radio("Chart View:", ["Total Volume", "Breakdown by Brand"], horizontal=True)
    with c_year: show_2026_only = st.checkbox("📅 View 2026 Only", value=False)

    if show_2026_only: active_months = [m for m in full_horizon if "-26" in m]
    else: active_months = full_horizon

    calc_df = base_df.copy()
    if 'floor_price' not in calc_df.columns: calc_df['floor_price'] = 0
    total_qty_cols, total_val_cols = [], []
    
    for m in active_months:
        qty_col, val_col = f'Final_Qty_{m}', f'Final_Val_{m}'
        if m in cycle_months: source_col = f'Cons_{m}'
        else: source_col = m
        if source_col in calc_df.columns: calc_df[qty_col] = pd.to_numeric(calc_df[source_col], errors='coerce').fillna(0)
        else: calc_df[qty_col] = 0
        calc_df[val_col] = calc_df[qty_col] * calc_df['floor_price']
        total_qty_cols.append(qty_col); total_val_cols.append(val_col)

    grand_total_qty = calc_df[total_qty_cols].sum().sum()
    grand_total_val = calc_df[total_val_cols].sum().sum()
    
    with stylable_container(key="kpi_v5", css_styles="{background-color:#F1F5F9; padding:20px; border-radius:10px; border:1px solid #CBD5E1;}"):
        k1, k2 = st.columns(2)
        p_label = "2026 Only" if show_2026_only else "12-Month"
        with k1: st.metric(f"{p_label} Volume", f"{grand_total_qty:,.0f} pcs", "Forecast")
        with k2: st.metric(f"{p_label} Revenue", f"Rp {grand_total_val/1_000_000_000:,.2f} M", "Estimated @ Floor Price")
            
    st.markdown("---")
    chart_data = []
    if chart_view == "Total Volume":
        for m in active_months:
            q = calc_df[f'Final_Qty_{m}'].sum()
            v = calc_df[f'Final_Val_{m}'].sum()
            chart_data.append({"Month": m, "Volume": q, "Value": v, "Type": "Total"})
    else:
        for m in active_months:
            grp = calc_df.groupby('Brand')[[f'Final_Qty_{m}', f'Final_Val_{m}']].sum().reset_index()
            total_v_month = grp[f'Final_Val_{m}'].sum()
            for idx, row in grp.iterrows():
                chart_data.append({"Month": m, "Brand": row['Brand'], "Volume": row[f'Final_Qty_{m}'], "Value": total_v_month})

    chart_df = pd.DataFrame(chart_data)
    fig_combo = go.Figure()
    if chart_view == "Total Volume":
        fig_combo.add_trace(go.Bar(x=chart_df['Month'], y=chart_df['Volume'], name='Volume (Qty)', marker_color='#3B82F6', opacity=0.8))
    else:
        brands = chart_df['Brand'].unique()
        colors = px.colors.qualitative.Pastel
        for i, brand in enumerate(brands):
            b_data = chart_df[chart_df['Brand'] == brand]
            color = colors[i % len(colors)]
            fig_combo.add_trace(go.Bar(x=b_data['Month'], y=b_data['Volume'], name=brand, marker_color=color))
        fig_combo.update_layout(barmode='stack')

    line_data = chart_df.drop_duplicates(subset=['Month'])
    fig_combo.add_trace(go.Scatter(x=line_data['Month'], y=line_data['Value'], name='Total Value (Rp)', yaxis='y2', line=dict(color='#EF4444', width=3), mode='lines+markers'))
    fig_combo.update_layout(title=f"Forecast Trend ({p_label})", yaxis=dict(title="Volume (Units)", showgrid=False), yaxis2=dict(title="Value (Rp)", overlaying='y', side='right', showgrid=False), legend=dict(x=0, y=1.1, orientation='h'), hovermode="x unified", height=500)
    st.plotly_chart(fig_combo, use_container_width=True)
    
    with st.expander(f"🔎 View Breakdown by Brand ({p_label})", expanded=True):
        brand_summ = calc_df.groupby('Brand')[total_val_cols].sum().reset_index()
        rename_map = {old: old.replace('Final_Val_', '') for old in total_val_cols}
        brand_summ.rename(columns=rename_map, inplace=True)
        brand_summ['Total Period'] = brand_summ.iloc[:, 1:].sum(axis=1)
        brand_summ = brand_summ.sort_values('Total Period', ascending=False)
        fmt_df = brand_summ.copy()
        for c in fmt_df.columns:
            if c != 'Brand': fmt_df[c] = fmt_df[c].apply(lambda x: f"Rp {x:,.0f}")
        st.dataframe(fmt_df, hide_index=True, use_container_width=True)
