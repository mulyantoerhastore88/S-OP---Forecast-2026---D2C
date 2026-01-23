import streamlit as st
import pandas as pd
import numpy as np
import gspread
import plotly.graph_objects as go
import plotly.express as px
from google.oauth2.service_account import Credentials
import json
from datetime import datetime
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode, JsCode
from streamlit_extras.metric_cards import style_metric_cards
from streamlit_extras.stylable_container import stylable_container
from streamlit_extras.toggle_switch import st_toggle_switch
import time
from streamlit_autorefresh import st_autorefresh

# ============================================================================
# PAGE CONFIG - MODERN
# ============================================================================
st.set_page_config(
    page_title="ERHA S&OP 3-Month Consensus Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        'Get Help': 'https://www.erhagroup.com',
        'Report a bug': None,
        'About': "ERHA S&OP Dashboard v2.0"
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
        --primary-dark: #1E3A8A;
        --secondary: #10B981;
        --danger: #EF4444;
        --warning: #F59E0B;
        --light: #F9FAFB;
        --dark: #1F2937;
        --border: #E5E7EB;
        --shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
    }
    
    /* Modern Header */
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
        letter-spacing: -0.5px;
    }
    
    .sub-title {
        font-size: 1.1rem;
        opacity: 0.9;
        margin-top: 0.5rem;
        font-weight: 400;
    }
    
    /* Modern Cards */
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid var(--border);
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        transition: all 0.3s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow);
    }
    
    /* Modern Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent;
        padding: 0;
        border-bottom: 2px solid var(--border);
    }
    
    .stTabs [data-baseweb="tab"] {
        padding: 12px 24px;
        border: none;
        border-bottom: 3px solid transparent;
        background: transparent;
        font-weight: 600;
        color: var(--dark);
        opacity: 0.7;
        transition: all 0.2s ease;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        opacity: 1;
        color: var(--primary);
    }
    
    .stTabs [aria-selected="true"] {
        background: transparent !important;
        color: var(--primary) !important;
        opacity: 1 !important;
        border-bottom: 3px solid var(--primary) !important;
    }
    
    /* Modern Filter Bar */
    .filter-bar {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid var(--border);
        margin-bottom: 2rem;
        display: flex;
        gap: 1rem;
        align-items: center;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    
    /* Badge Styles */
    .badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        margin: 0 4px;
    }
    
    .badge-primary { background: #DBEAFE; color: #1E40AF; }
    .badge-success { background: #D1FAE5; color: #065F46; }
    .badge-warning { background: #FEF3C7; color: #92400E; }
    .badge-danger { background: #FEE2E2; color: #991B1B; }
    
    /* Loading Animation */
    .loading-pulse {
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0% { opacity: 0.6; }
        50% { opacity: 1; }
        100% { opacity: 0.6; }
    }
    
    /* Responsive */
    @media (max-width: 768px) {
        .main-title { font-size: 2rem; }
        .filter-bar { flex-direction: column; }
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# AUTO-REFRESH (setiap 5 menit)
# ============================================================================
# Uncomment untuk auto-refresh
# st_autorefresh(interval=5 * 60 * 1000, key="data_refresh")

# ============================================================================
# MODERN HEADER
# ============================================================================
with st.container():
    st.markdown("""
    <div class="main-header">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h1 class="main-title">📊 ERHA S&OP Dashboard</h1>
                <p class="sub-title">3-Month Consensus | Real-time Collaboration | AI-Powered Insights</p>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 0.9rem; opacity: 0.8;">Meeting Status</div>
                <div style="display: flex; align-items: center; gap: 8px; margin-top: 4px;">
                    <div style="width: 8px; height: 8px; background: #10B981; border-radius: 50%;"></div>
                    <span style="font-weight: 600;">Live</span>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ============================================================================
# MEETING INFO BAR - MODERN
# ============================================================================
with stylable_container(
    key="meeting_bar",
    css_styles="""
    {
        background: white;
        padding: 1rem 1.5rem;
        border-radius: 12px;
        border: 1px solid #E5E7EB;
        margin-bottom: 1.5rem;
    }
    """
):
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    with col1:
        meeting_date = st.date_input("📅 Meeting Date", value=datetime.now().date(), key="meeting_date")
    with col2:
        st.selectbox("👥 Participants", ["All Teams", "Supply Chain", "Marketing", "Finance"], key="participants")
    with col3:
        st.selectbox("📁 Version", ["v2.0 - Current", "v1.0 - Previous"], key="version")
    with col4:
        st_toggle_switch("🔔 Notifications", key="notifications")

# ============================================================================
# DATA LOADER DENGAN LOADING STATE
# ============================================================================
@st.cache_data(ttl=300, show_spinner=False)
def load_all_data():
    """Load and process all required data"""
    # Simulasi loading - ganti dengan koneksi Google Sheets asli
    time.sleep(1)  # Simulasi loading
    
    # Buat data dummy untuk demo
    np.random.seed(42)
    
    # Sales data
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
        'floor_price': np.random.randint(50000, 500000, 100),
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
    
    return df

# ============================================================================
# LOAD DATA DENGAN LOADING ANIMATION
# ============================================================================
with st.spinner('🔄 Loading latest data...'):
    all_df = load_all_data()

# ============================================================================
# QUICK METRICS OVERVIEW - MODERN
# ============================================================================
st.markdown("### 📊 Quick Overview")
metrics_cols = st.columns(5)

with metrics_cols[0]:
    with stylable_container(
        key="metric1",
        css_styles="""
        {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 1.5rem;
            border-radius: 12px;
            color: white;
        }
        """
    ):
        st.metric("Total SKUs", f"{len(all_df):,}", "100 SKUs")
        style_metric_cards()

with metrics_cols[1]:
    with stylable_container(
        key="metric2",
        css_styles="""
        {
            background: linear-gradient(135deg, #10B981 0%, #059669 100%);
            padding: 1.5rem;
            border-radius: 12px;
            color: white;
        }
        """
    ):
        total_sales = all_df[['Oct-25', 'Nov-25', 'Dec-25']].sum().sum()
        st.metric("Total Sales L3M", f"{total_sales:,.0f}", "+12.5%")
        style_metric_cards()

with metrics_cols[2]:
    with stylable_container(
        key="metric3",
        css_styles="""
        {
            background: linear-gradient(135deg, #F59E0B 0%, #D97706 100%);
            padding: 1.5rem;
            border-radius: 12px;
            color: white;
        }
        """
    ):
        avg_cover = all_df['Month_Cover'].mean()
        st.metric("Avg Month Cover", f"{avg_cover:.1f}", "1.5 months")
        style_metric_cards()

with metrics_cols[3]:
    with stylable_container(
        key="metric4",
        css_styles="""
        {
            background: linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%);
            padding: 1.5rem;
            border-radius: 12px;
            color: white;
        }
        """
    ):
        high_cover = len(all_df[all_df['Month_Cover'] > 1.5])
        st.metric("High Cover SKUs", f"{high_cover:,}", f"{high_cover/len(all_df)*100:.0f}%")
        style_metric_cards()

with metrics_cols[4]:
    with stylable_container(
        key="metric5",
        css_styles="""
        {
            background: linear-gradient(135deg, #8B5CF6 0%, #7C3AED 100%);
            padding: 1.5rem;
            border-radius: 12px;
            color: white;
        }
        """
    ):
        forecast_total = all_df[['Feb-26', 'Mar-26', 'Apr-26']].sum().sum()
        growth = ((forecast_total - total_sales) / total_sales * 100) if total_sales > 0 else 0
        st.metric("3M Forecast", f"{forecast_total:,.0f}", f"{growth:+.1f}%")
        style_metric_cards()

# ============================================================================
# MODERN FILTER BAR
# ============================================================================
with st.container():
    st.markdown("### 🔍 Filter Data")
    
    with stylable_container(
        key="filter_container",
        css_styles="""
        {
            background: white;
            padding: 1.5rem;
            border-radius: 12px;
            border: 1px solid #E5E7EB;
            margin-bottom: 1.5rem;
        }
        """
    ):
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            brand_groups = ["ALL"] + sorted(all_df['Brand_Group'].unique())
            selected_brand_group = st.selectbox(
                "Brand Group",
                brand_groups,
                key="filter_brand_group"
            )
        
        with col2:
            brands = ["ALL"] + sorted(all_df['Brand'].unique())
            selected_brand = st.selectbox(
                "Brand",
                brands,
                key="filter_brand"
            )
        
        with col3:
            sku_tiers = ["ALL"] + sorted(all_df['SKU_Tier'].unique())
            selected_tier = st.selectbox(
                "SKU Tier",
                sku_tiers,
                key="filter_tier"
            )
        
        with col4:
            month_cover_filter = st.selectbox(
                "Month Cover",
                ["ALL", "< 1.5 months", "1.5 - 3 months", "> 3 months"],
                key="filter_month_cover"
            )
        
        with col5:
            st.markdown("&nbsp;")
            col5a, col5b = st.columns(2)
            with col5a:
                if st.button("🔄 Refresh", use_container_width=True):
                    st.cache_data.clear()
                    st.rerun()
            with col5b:
                if st.button("📊 Reset Filters", type="secondary", use_container_width=True):
                    st.rerun()

# ============================================================================
# TAB INTERFACE - MODERN
# ============================================================================
tab1, tab2, tab3 = st.tabs(["📝 Input & Adjustment", "📊 Analytics Dashboard", "🎯 Focus Areas"])

# ============================================================================
# TAB 1: INPUT TABLE DENGAN AgGrid - FIXED VERSION
# ============================================================================
with tab1:
    st.markdown("### 🎯 3-Month Forecast Adjustment")
    
    # Filter data untuk tab 1
    filtered_df = all_df.copy()
    if selected_brand_group != "ALL":
        filtered_df = filtered_df[filtered_df['Brand_Group'] == selected_brand_group]
    if selected_brand != "ALL":
        filtered_df = filtered_df[filtered_df['Brand'] == selected_brand]
    if selected_tier != "ALL":
        filtered_df = filtered_df[filtered_df['SKU_Tier'] == selected_tier]
    
    # Apply month cover filter
    if month_cover_filter == "< 1.5 months":
        filtered_df = filtered_df[filtered_df['Month_Cover'] < 1.5]
    elif month_cover_filter == "1.5 - 3 months":
        filtered_df = filtered_df[(filtered_df['Month_Cover'] >= 1.5) & (filtered_df['Month_Cover'] <= 3)]
    elif month_cover_filter == "> 3 months":
        filtered_df = filtered_df[filtered_df['Month_Cover'] > 3]
    
    # Prepare data untuk AgGrid
    display_df = filtered_df[['sku_code', 'Product_Name', 'Brand', 'SKU_Tier', 
                             'Oct-25', 'Nov-25', 'Dec-25', 'L3M_Avg', 
                             'Stock_Qty', 'Month_Cover', 'Feb-26', 'Mar-26', 'Apr-26']].copy()
    
    # Tambahkan calculated columns
    for month in ['Feb-26', 'Mar-26', 'Apr-26']:
        display_df[f'{month}_%'] = (display_df[month] / display_df['L3M_Avg'].replace(0, 1) * 100).round(1)
        display_df[f'Cons_{month}'] = display_df[month]  # Initial consensus
    
    # Konfigurasi AgGrid
    gb = GridOptionsBuilder.from_dataframe(display_df)
    
    # Set column properties
    gb.configure_default_column(
        filterable=True,
        sortable=True,
        resizable=True,
        editable=False,
        minWidth=100
    )
    
    # Buat consensus columns editable
    for month in ['Feb-26', 'Mar-26', 'Apr-26']:
        gb.configure_column(f'Cons_{month}', editable=True, type=["numericColumn", "numberColumnFilter"])
    
    # Cell styling berdasarkan rules
    cellstyle_jscode = JsCode("""
    function(params) {
        if (params.column.colId === 'Month_Cover') {
            if (params.value > 1.5) {
                return {
                    'backgroundColor': '#FCE7F3',
                    'color': '#BE185D',
                    'borderLeft': '3px solid #BE185D'
                };
            }
        }
        if (params.column.colId.includes('_%')) {
            if (params.value < 90) {
                return {
                    'backgroundColor': '#FFEDD5',
                    'color': '#9A3412',
                    'borderLeft': '3px solid #9A3412'
                };
            } else if (params.value > 130) {
                return {
                    'backgroundColor': '#FEE2E2',
                    'color': '#991B1B',
                    'borderLeft': '3px solid #991B1B'
                };
            }
        }
        return null;
    }
    """)
    
    gb.configure_grid_options(
        rowStyle=cellstyle_jscode,
        getRowStyle=cellstyle_jscode
    )
    
    # Configure pagination
    gb.configure_pagination(
        paginationAutoPageSize=False,
        paginationPageSize=20
    )
    
    # Configure selection
    gb.configure_selection(
        'multiple',
        use_checkbox=True,
        pre_selected_rows=[]
    )
    
    # Build grid options
    grid_options = gb.build()
    
    # Display AgGrid - DENGAN ERROR HANDLING YANG LEBIH BAIK
    st.markdown("**Interactive Data Grid (Double-click cells to edit):**")
    
    try:
        grid_response = AgGrid(
            display_df,
            gridOptions=grid_options,
            height=500,
            width='100%',
            data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
            update_mode=GridUpdateMode.MODEL_CHANGED,
            fit_columns_on_grid_load=True,
            theme='streamlit',
            allow_unsafe_jscode=True,
            reload_data=False
        )
        
        # AMAN: Ambil selected rows dengan cara yang aman
        selected = []
        if isinstance(grid_response, dict):
            selected = grid_response.get('selected_rows', [])
        elif hasattr(grid_response, 'selected_rows'):
            selected = grid_response.selected_rows
        
    except Exception as e:
        st.error(f"Error loading AgGrid: {e}")
        st.warning("Falling back to standard DataFrame display")
        st.dataframe(display_df, use_container_width=True)
        selected = []  # Pastikan selected adalah list kosong
        grid_response = None
    
    # FIX: Handle selected dengan aman
    if isinstance(selected, (list, pd.DataFrame)) and len(selected) > 0:
        st.info(f"📌 {len(selected)} rows selected")
        with st.expander("View Selected Rows"):
            if isinstance(selected, pd.DataFrame):
                st.dataframe(selected, use_container_width=True)
            else:
                st.dataframe(pd.DataFrame(selected), use_container_width=True)
    elif selected:  # Jika selected bukan list/DataFrame tapi truthy
        st.warning(f"Selected data in unexpected format: {type(selected)}")
    # else: tidak perlu else, jika kosong tidak tampilkan apa-apa

# ============================================================================
# TAB 2: MODERN ANALYTICS DASHBOARD
# ============================================================================
with tab2:
    st.markdown("### 📈 Advanced Analytics Dashboard")
    
    # Row 1: Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📊 Monthly Sales Trend")
        
        # Prepare data for chart
        monthly_data = []
        for month in ['Oct-25', 'Nov-25', 'Dec-25', 'Feb-26', 'Mar-26', 'Apr-26']:
            total = all_df[month].sum()
            monthly_data.append({
                'Month': month,
                'Sales': total,
                'Type': 'Actual' if month in ['Oct-25', 'Nov-25', 'Dec-25'] else 'Forecast'
            })
        
        monthly_df = pd.DataFrame(monthly_data)
        
        fig = px.line(
            monthly_df,
            x='Month',
            y='Sales',
            color='Type',
            markers=True,
            line_shape='spline',
            title="Monthly Sales Trend"
        )
        
        fig.update_layout(
            height=400,
            template='plotly_white',
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("#### 🎯 Brand Performance")
        
        brand_performance = all_df.groupby('Brand').agg({
            'L3M_Avg': 'sum',
            'Feb-26': 'sum'
        }).reset_index()
        
        brand_performance['Growth'] = ((brand_performance['Feb-26'] - brand_performance['L3M_Avg']) / 
                                       brand_performance['L3M_Avg'] * 100)
        
        fig = px.bar(
            brand_performance,
            x='Brand',
            y='Growth',
            color='Growth',
            color_continuous_scale='RdYlGn',
            title="Brand Growth % (Feb-26 vs L3M Avg)"
        )
        
        fig.update_layout(
            height=400,
            template='plotly_white',
            xaxis_tickangle=-45
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Row 2: More charts
    col3, col4 = st.columns(2)
    
    with col3:
        st.markdown("#### 📦 Stock Coverage Analysis")
        
        coverage_bins = pd.cut(
            all_df['Month_Cover'],
            bins=[-1, 0.5, 1, 1.5, 2, 3, float('inf')],
            labels=['<0.5', '0.5-1', '1-1.5', '1.5-2', '2-3', '>3']
        )
        
        coverage_dist = coverage_bins.value_counts().sort_index()
        
        fig = px.pie(
            values=coverage_dist.values,
            names=coverage_dist.index,
            title="SKU Distribution by Month Cover",
            hole=0.4
        )
        
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    with col4:
        st.markdown("#### 🔢 SKU Tier Analysis")
        
        tier_summary = all_df.groupby('SKU_Tier').agg({
            'sku_code': 'count',
            'L3M_Avg': 'sum',
            'Feb-26': 'sum'
        }).reset_index()
        
        fig = px.sunburst(
            tier_summary,
            path=['SKU_Tier'],
            values='L3M_Avg',
            title="Sales Contribution by SKU Tier",
            color='L3M_Avg',
            color_continuous_scale='Blues'
        )
        
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

# ============================================================================
# TAB 3: FOCUS AREAS & ALERTS
# ============================================================================
with tab3:
    st.markdown("### 🎯 Focus Areas & Action Items")
    
    # Generate alerts
    high_cover_skus = all_df[all_df['Month_Cover'] > 1.5].sort_values('Month_Cover', ascending=False)
    low_growth_skus = all_df[(all_df['Feb-26'] / all_df['L3M_Avg'].replace(0, 1) * 100) < 90].sort_values('L3M_Avg')
    high_growth_skus = all_df[(all_df['Feb-26'] / all_df['L3M_Avg'].replace(0, 1) * 100) > 130].sort_values('Feb-26', ascending=False)
    low_stock_skus = all_df[all_df['Stock_Qty'] < all_df['L3M_Avg']].sort_values('Stock_Qty')
    
    col1, col2 = st.columns(2)
    
    with col1:
        with stylable_container(
            key="alert_high_cover",
            css_styles="""
            {
                background: white;
                padding: 1.5rem;
                border-radius: 12px;
                border-left: 6px solid #EF4444;
                margin-bottom: 1rem;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            }
            """
        ):
            st.markdown("#### ⚠️ High Month Cover")
            st.metric("SKUs", f"{len(high_cover_skus):,}", f"{len(high_cover_skus)/len(all_df)*100:.0f}%")
            
            if len(high_cover_skus) > 0:
                with st.expander("View SKUs"):
                    st.dataframe(high_cover_skus[['sku_code', 'Product_Name', 'Brand', 'Month_Cover']].head(10))
    
    with col2:
        with stylable_container(
            key="alert_low_growth",
            css_styles="""
            {
                background: white;
                padding: 1.5rem;
                border-radius: 12px;
                border-left: 6px solid #F59E0B;
                margin-bottom: 1rem;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            }
            """
        ):
            st.markdown("#### 📉 Low Growth SKUs")
            st.metric("SKUs", f"{len(low_growth_skus):,}", "<90% growth")
            
            if len(low_growth_skus) > 0:
                with st.expander("View SKUs"):
                    st.dataframe(low_growth_skus[['sku_code', 'Product_Name', 'L3M_Avg', 'Feb-26']].head(10))
    
    col3, col4 = st.columns(2)
    
    with col3:
        with stylable_container(
            key="alert_high_growth",
            css_styles="""
            {
                background: white;
                padding: 1.5rem;
                border-radius: 12px;
                border-left: 6px solid #10B981;
                margin-bottom: 1rem;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            }
            """
        ):
            st.markdown("#### 📈 High Growth SKUs")
            st.metric("SKUs", f"{len(high_growth_skus):,}", ">130% growth")
            
            if len(high_growth_skus) > 0:
                with st.expander("View SKUs"):
                    st.dataframe(high_growth_skus[['sku_code', 'Product_Name', 'L3M_Avg', 'Feb-26']].head(10))
    
    with col4:
        with stylable_container(
            key="alert_low_stock",
            css_styles="""
            {
                background: white;
                padding: 1.5rem;
                border-radius: 12px;
                border-left: 6px solid #8B5CF6;
                margin-bottom: 1rem;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            }
            """
        ):
            st.markdown("#### 📦 Low Stock SKUs")
            st.metric("SKUs", f"{len(low_stock_skus):,}", "<1 month cover")
            
            if len(low_stock_skus) > 0:
                with st.expander("View SKUs"):
                    st.dataframe(low_stock_skus[['sku_code', 'Product_Name', 'Stock_Qty', 'L3M_Avg']].head(10))

# ============================================================================
# SIDEBAR CONFIGURATION
# ============================================================================
with st.sidebar:
    st.markdown("### ⚙️ Dashboard Settings")
    
    # Auto-refresh toggle
    auto_refresh = st.checkbox("🔄 Auto-refresh data", value=True)
    if auto_refresh:
        refresh_interval = st.slider("Refresh interval (minutes)", 1, 30, 5)
    
    # Theme selector
    theme = st.selectbox("🎨 Theme", ["Light", "Dark", "Auto"])
    
    # Data range
    st.markdown("---")
    st.markdown("### 📅 Data Range")
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("From", value=datetime(2025, 10, 1).date())
    with col2:
        end_date = st.date_input("To", value=datetime(2026, 4, 30).date())
    
    # Export options
    st.markdown("---")
    st.markdown("### 📤 Export Data")
    
    export_format = st.radio("Format", ["CSV", "Excel", "PDF"])
    
    if st.button("📥 Generate Export", use_container_width=True):
        st.success(f"Exporting data as {export_format}...")

# ============================================================================
# MODERN FOOTER
# ============================================================================
st.markdown("---")
footer_cols = st.columns([2, 1, 1])

with footer_cols[0]:
    st.markdown("""
    <div style="color: #6B7280; font-size: 0.9rem;">
        <p>📊 <strong>ERHA S&OP Dashboard v2.0</strong></p>
        <p>For internal use only. Data refreshed every 5 minutes.</p>
    </div>
    """, unsafe_allow_html=True)

with footer_cols[1]:
    st.markdown(f"""
    <div style="color: #6B7280; font-size: 0.9rem; text-align: center;">
        <p><strong>Meeting</strong></p>
        <p>{meeting_date}</p>
    </div>
    """, unsafe_allow_html=True)

with footer_cols[2]:
    st.markdown(f"""
    <div style="color: #6B7280; font-size: 0.9rem; text-align: center;">
        <p><strong>Last Updated</strong></p>
        <p>{datetime.now().strftime('%H:%M:%S')}</p>
    </div>
    """, unsafe_allow_html=True)

# ============================================================================
# DEPLOYMENT INSTRUCTIONS
# ============================================================================
with st.expander("🚀 Deployment Instructions", expanded=False):
    st.markdown("""
    ### **Deploy to Streamlit Cloud**
    
    1. **Push to GitHub:**
    ```bash
    git add .
    git commit -m "Add modern S&OP dashboard"
    git push origin main
    ```
    
    2. **Go to [share.streamlit.io](https://share.streamlit.io)**
    3. **Click "New app"** → Select repository
    4. **Set main file to:** `app.py`
    5. **Add secrets:** (in Streamlit Cloud dashboard)
    ```toml
    [gsheets]
    sheet_id = "your-sheet-id"
    service_account_info = '{"type": "service_account", ...}'
    ```
    
    ### **Requirements File**
    Create `requirements.txt`:
    ```txt
    streamlit>=1.28.0
    pandas>=2.0.0
    numpy>=1.24.0
    plotly>=5.17.0
    gspread>=5.11.0
    google-auth>=2.23.0
    streamlit-aggrid>=0.3.4
    streamlit-extras>=0.4.0
    streamlit-autorefresh>=0.1.4
    ```
    
    ### **Alternative Hosting:**
    - **Hugging Face Spaces:** Free, public only
    - **Render:** Free tier available
    - **Railway:** $5/month starter
    - **AWS EC2:** ~$10/month
    """)
