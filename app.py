import streamlit as st
import pandas as pd
import numpy as np
import gspread
import plotly.graph_objects as go
import plotly.express as px
from google.oauth2.service_account import Credentials
import json
from datetime import datetime

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================
st.set_page_config(
    page_title="ERHA S&OP 3-Month Consensus Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================================
# CUSTOM CSS - DENGAN CONDITIONAL FORMATTING SPECIFIC
# ============================================================================
st.markdown("""
<style>
    /* Main Title */
    .main-title {
        font-size: 2.8rem;
        background: linear-gradient(90deg, #1E3A8A 0%, #3B82F6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0.5rem;
        font-weight: 800;
        letter-spacing: -0.5px;
    }
    
    /* Sub Title */
    .sub-title {
        font-size: 1.3rem;
        color: #6B7280;
        text-align: center;
        margin-bottom: 2rem;
        font-weight: 400;
    }
    
    /* Tab Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #F9FAFB;
        padding: 8px;
        border-radius: 10px;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #FFFFFF;
        border-radius: 8px;
        border: 1px solid #E5E7EB;
        font-weight: 600;
        padding: 10px 20px;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #3B82F6 !important;
        color: white !important;
        border-color: #3B82F6 !important;
    }
    
    /* Filter Section */
    .filter-section {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    .filter-label {
        color: white !important;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    
    /* Custom styling for data editor cells */
    div[data-testid="stDataEditor"] div[role="cell"] {
        font-size: 0.85rem;
        padding: 4px 8px;
        transition: background-color 0.3s ease;
    }
    
    /* Brand Colors - Applied via JavaScript */
    .brand-acneact { background-color: #E0F2FE !important; }
    .brand-age-corrector { background-color: #F0F9FF !important; }
    .brand-truwhite { background-color: #F0FDF4 !important; }
    .brand-erhair { background-color: #FEF3C7 !important; }
    .brand-hiserha { background-color: #FEF7CD !important; }
    .brand-perfect-shield { background-color: #FCE7F3 !important; }
    .brand-skinsitive { background-color: #F3E8FF !important; }
    .brand-erha-others { background-color: #F5F5F5 !important; }
    
    /* ===== CONDITIONAL FORMATTING ===== */
    
    /* 1. Month Cover > 1.5 = PINK/MAGENTA */
    .warning-month-cover-pink { 
        background-color: #FCE7F3 !important; 
        color: #BE185D !important; 
        font-weight: 600; 
        border-left: 3px solid #BE185D !important;
    }
    
    /* 2. Growth < 90% = ORANGE */
    .warning-growth-orange { 
        background-color: #FFEDD5 !important; 
        color: #9A3412 !important; 
        font-weight: 600;
        border-left: 3px solid #9A3412 !important;
    }
    
    /* 3. Growth > 130% = RED */
    .warning-growth-red { 
        background-color: #FEE2E2 !important; 
        color: #991B1B !important; 
        font-weight: 600;
        border-left: 3px solid #991B1B !important;
    }
    
    /* Button Styling */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s ease;
        border: 1px solid #3B82F6;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* Data Editor Header Styling */
    div[data-testid="stDataEditor"] th {
        background-color: #F3F4F6 !important;
        font-weight: 600 !important;
        color: #1F2937 !important;
        border-bottom: 2px solid #D1D5DB !important;
    }
</style>

<script>
// JavaScript untuk apply conditional formatting
function applyCellColoring() {
    // Tunggu tabel load
    setTimeout(() => {
        const cells = document.querySelectorAll('div[role="cell"]');
        
        cells.forEach(cell => {
            const cellText = cell.textContent.trim();
            const columnHeader = cell.getAttribute('data-column-id');
            
            // 1. Apply brand colors untuk kolom Brand
            if (columnHeader === 'Brand') {
                const brandClass = cellText.toLowerCase().replace(/[^a-z]/g, '-');
                cell.classList.add('brand-' + brandClass);
            }
            
            // 2. Conditional: Month Cover > 1.5 = PINK
            if (columnHeader === 'Month_Cover') {
                const value = parseFloat(cellText);
                if (!isNaN(value) && value > 1.5) {
                    cell.classList.add('warning-month-cover-pink');
                }
            }
            
            // 3. Conditional: Feb-26%, Mar-26%, Apr-26% 
            //    < 90% = ORANGE, > 130% = RED
            if (columnHeader && (columnHeader === 'Feb-26_%' || 
                                 columnHeader === 'Mar-26_%' || 
                                 columnHeader === 'Apr-26_%')) {
                const value = parseFloat(cellText);
                if (!isNaN(value)) {
                    if (value < 90) {  // Kurang dari 90%
                        cell.classList.add('warning-growth-orange');
                    } else if (value > 130) {  // Lebih dari 130%
                        cell.classList.add('warning-growth-red');
                    }
                }
            }
        });
        
        // Juga apply ke header untuk konsistensi visual
        const headers = document.querySelectorAll('th[role="columnheader"]');
        headers.forEach(header => {
            const headerText = header.textContent.trim();
            if (headerText === 'Month Cover') {
                header.style.color = '#BE185D';
                header.style.fontWeight = '700';
            }
            if (headerText.includes('%')) {
                header.style.color = '#991B1B';
                header.style.fontWeight = '700';
            }
        });
        
    }, 1500); // Delay sedikit lebih lama untuk pastikan tabel fully loaded
}

// Run saat page load
document.addEventListener('DOMContentLoaded', applyCellColoring);
window.addEventListener('load', applyCellColoring);

// Refresh coloring ketika data di-edit
const observer = new MutationObserver(function(mutations) {
    mutations.forEach(function(mutation) {
        if (mutation.addedNodes.length) {
            applyCellColoring();
        }
    });
});

observer.observe(document.body, { 
    childList: true, 
    subtree: true 
});

// Juga apply setiap kali user scroll (untuk virtual scrolling)
window.addEventListener('scroll', applyCellColoring);
</script>
""", unsafe_allow_html=True)

# ============================================================================
# HEADER
# ============================================================================
st.markdown('<p class="main-title">📊 ERHA S&OP 3-Month Consensus Dashboard</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Last 3M Sales vs ROFO Adjustment | Real-time Collaboration</p>', unsafe_allow_html=True)

# Meeting info bar
meeting_date = st.date_input("📅 Meeting Date", value=datetime.now().date(), key="meeting_date")

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
# DATA LOADING & PROCESSING
# ============================================================================
@st.cache_data(ttl=300)
def load_all_data():
    """Load and process all required data"""
    gs = GSheetConnector()
    
    # 1. Load sales history
    sales_df = gs.get_sheet_data("sales_history")
    if sales_df.empty:
        st.error("❌ No sales history data found")
        return None
    
    # 2. Load ROFO current with floor_price
    rofo_df = gs.get_sheet_data("rofo_current")
    if rofo_df.empty:
        st.error("❌ No ROFO data found")
        return None
    
    # 3. Load stock data
    stock_df = gs.get_sheet_data("stock_onhand")
    
    # 4. Get last 3 months sales (Oct, Nov, Dec 2025)
    sales_months = ['Oct-25', 'Nov-25', 'Dec-25']
    available_sales_months = [m for m in sales_months if m in sales_df.columns]
    
    if len(available_sales_months) < 3:
        st.warning(f"⚠️ Only {len(available_sales_months)} of last 3 months available")
    
    # Calculate L3M Average
    sales_df['L3M_Avg'] = sales_df[available_sales_months].mean(axis=1).round(0)
    
    # 5. Get ROFO months
    adjustment_months = ['Feb-26', 'Mar-26', 'Apr-26']
    projection_months = ['May-26', 'Jun-26', 'Jul-26', 'Aug-26', 'Sep-26', 
                         'Oct-26', 'Nov-26', 'Dec-26', 'Jan-27']
    
    all_rofo_months = adjustment_months + projection_months
    available_rofo_months = [m for m in all_rofo_months if m in rofo_df.columns]
    
    # 6. Merge data
    sales_cols = ['sku_code', 'Product_Name', 'Brand_Group', 'Brand', 'SKU_Tier', 'L3M_Avg']
    sales_cols += available_sales_months
    sales_essential = sales_df[sales_cols].copy()
    
    rofo_cols = ['sku_code', 'Product_Name', 'Brand_Group', 'Brand', 'SKU_Tier', 'floor_price']
    rofo_cols += [m for m in available_rofo_months if m in rofo_df.columns]
    rofo_essential = rofo_df[rofo_cols].copy()
    
    merged_df = pd.merge(
        sales_essential,
        rofo_essential,
        on=['sku_code', 'Product_Name', 'Brand_Group', 'Brand', 'SKU_Tier'],
        how='inner',
        suffixes=('_sales', '_rofo')
    )
    
    # Merge with stock
    if not stock_df.empty and 'sku_code' in stock_df.columns:
        merged_df = pd.merge(
            merged_df,
            stock_df[['sku_code', 'Stock_Qty']],
            on='sku_code',
            how='left'
        )
        merged_df['Stock_Qty'] = merged_df['Stock_Qty'].fillna(0)
    else:
        merged_df['Stock_Qty'] = 0
    
    # Calculate Month Cover
    merged_df['Month_Cover'] = (merged_df['Stock_Qty'] / merged_df['L3M_Avg'].replace(0, 1)).round(1)
    merged_df['Month_Cover'] = merged_df['Month_Cover'].replace([np.inf, -np.inf], 0)
    
    return {
        'data': merged_df,
        'sales_months': available_sales_months,
        'adjustment_months': [m for m in adjustment_months if m in available_rofo_months],
        'projection_months': [m for m in projection_months if m in available_rofo_months],
        'has_floor_price': 'floor_price' in merged_df.columns
    }

# Load ALL data (not filtered)
with st.spinner("📥 Loading data from Google Sheets..."):
    data_result = load_all_data()
    
if not data_result:
    st.stop()

all_df = data_result['data']  # Keep full dataset for Tab 2
adjustment_months = data_result['adjustment_months']
projection_months = data_result['projection_months']
has_floor_price = data_result['has_floor_price']

# ============================================================================
# FILTER SECTION (ONLY FOR TAB 1)
# ============================================================================
st.markdown("""
<div class="filter-section">
    <div style="display: flex; gap: 2rem; align-items: center;">
""", unsafe_allow_html=True)

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.markdown('<p class="filter-label">Brand Group</p>', unsafe_allow_html=True)
    brand_groups = ["ALL"] + sorted(all_df['Brand_Group'].dropna().unique().tolist())
    selected_brand_group = st.selectbox("", brand_groups, key="filter_brand_group", label_visibility="collapsed")

with col2:
    st.markdown('<p class="filter-label">Brand</p>', unsafe_allow_html=True)
    brands = ["ALL"] + sorted(all_df['Brand'].dropna().unique().tolist())
    selected_brand = st.selectbox("", brands, key="filter_brand", label_visibility="collapsed")

with col3:
    st.markdown('<p class="filter-label">SKU Tier</p>', unsafe_allow_html=True)
    sku_tiers = ["ALL"] + sorted(all_df['SKU_Tier'].dropna().unique().tolist())
    selected_tier = st.selectbox("", sku_tiers, key="filter_tier", label_visibility="collapsed")

with col4:
    st.markdown('<p class="filter-label">Month Cover</p>', unsafe_allow_html=True)
    month_cover_filter = st.selectbox(
        "", 
        ["ALL", "< 1.5 months", "1.5 - 3 months", "> 3 months"],
        key="filter_month_cover",
        label_visibility="collapsed"
    )

with col5:
    st.markdown('<p class="filter-label">&nbsp;</p>', unsafe_allow_html=True)
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.markdown("</div></div>", unsafe_allow_html=True)

# Apply filters for Tab 1 only
filtered_df = all_df.copy()
if selected_brand_group != "ALL":
    filtered_df = filtered_df[filtered_df['Brand_Group'] == selected_brand_group]
if selected_brand != "ALL":
    filtered_df = filtered_df[filtered_df['Brand'] == selected_brand]
if selected_tier != "ALL":
    filtered_df = filtered_df[filtered_df['SKU_Tier'] == selected_tier]

if month_cover_filter != "ALL":
    if month_cover_filter == "< 1.5 months":
        filtered_df = filtered_df[filtered_df['Month_Cover'] < 1.5]
    elif month_cover_filter == "1.5 - 3 months":
        filtered_df = filtered_df[(filtered_df['Month_Cover'] >= 1.5) & (filtered_df['Month_Cover'] <= 3)]
    elif month_cover_filter == "> 3 months":
        filtered_df = filtered_df[filtered_df['Month_Cover'] > 3]

# ============================================================================
# TAB INTERFACE
# ============================================================================
tab1, tab2 = st.tabs(["📝 Input & Adjustment", "📊 Results & Analytics"])

# ============================================================================
# TAB 1: INPUT TABLE (WITH CONDITIONAL FORMATTING)
# ============================================================================
with tab1:
    st.markdown("### 🎯 3-Month Forecast Adjustment")
    
    # Summary metrics untuk Tab 1
    metric_cols = st.columns(5)
    with metric_cols[0]:
        total_skus = len(filtered_df)
        st.metric("SKUs in View", f"{total_skus:,}")
    with metric_cols[1]:
        avg_l3m = filtered_df['L3M_Avg'].mean()
        st.metric("Avg L3M Sales", f"{avg_l3m:,.0f}")
    with metric_cols[2]:
        total_stock = filtered_df['Stock_Qty'].sum()
        st.metric("Total Stock", f"{total_stock:,}")
    with metric_cols[3]:
        avg_month_cover = filtered_df['Month_Cover'].mean()
        st.metric("Avg Month Cover", f"{avg_month_cover:.1f}")
    with metric_cols[4]:
        if adjustment_months:
            month = adjustment_months[0]
            avg_growth = ((filtered_df[month].mean() - filtered_df['L3M_Avg'].mean()) / 
                         filtered_df['L3M_Avg'].mean() * 100).round(1)
            st.metric(f"Avg {month} Growth", f"{avg_growth:+.1f}%")
    
    # Tambahkan color legend
    st.markdown("""
    <div style="display: flex; gap: 1rem; margin: 1rem 0; padding: 0.75rem; background: #F9FAFB; border-radius: 8px; align-items: center;">
        <div style="font-size: 0.85rem; font-weight: 500; color: #6B7280;">Color Legend:</div>
        <div style="display: flex; gap: 0.5rem;">
            <div style="background-color: #FCE7F3; color: #BE185D; padding: 4px 12px; border-radius: 4px; font-size: 0.8rem; font-weight: 600;">
                Month Cover > 1.5
            </div>
            <div style="background-color: #FFEDD5; color: #9A3412; padding: 4px 12px; border-radius: 4px; font-size: 0.8rem; font-weight: 600;">
                Growth < 90%
            </div>
            <div style="background-color: #FEE2E2; color: #991B1B; padding: 4px 12px; border-radius: 4px; font-size: 0.8rem; font-weight: 600;">
                Growth > 130%
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Prepare dataframe for editing
    editor_df = filtered_df.copy()
    
    # Add percentage columns for ROFO vs L3M - FORMAT AS PERCENTAGE (90, 130)
    for month in adjustment_months:
        if month in editor_df.columns:
            # Calculate % vs L3M (as PERCENTAGE 90%, bukan decimal 0.9)
            pct_col = f"{month}_%"
            editor_df[pct_col] = (editor_df[month] / editor_df['L3M_Avg'].replace(0, 1) * 100).round(1)
            
            # Add consensus columns (initially same as ROFO)
            cons_col = f"Cons_{month}"
            editor_df[cons_col] = editor_df[month]
    
    # Create column order
    display_cols = ['sku_code', 'Product_Name', 'Brand', 'SKU_Tier']
    
    # Add sales months
    sales_months = ['Oct-25', 'Nov-25', 'Dec-25']
    display_cols += [m for m in sales_months if m in editor_df.columns]
    
    # Add calculated columns
    display_cols += ['L3M_Avg', 'Stock_Qty', 'Month_Cover']
    
    # Add ROFO months and their % (DENGAN FORMAT PERSEN)
    for month in adjustment_months:
        if month in editor_df.columns:
            display_cols.append(month)
            display_cols.append(f"{month}_%")
    
    # Add consensus columns
    for month in adjustment_months:
        cons_col = f"Cons_{month}"
        if cons_col in editor_df.columns:
            display_cols.append(cons_col)
    
    # Create display dataframe
    display_df = editor_df[display_cols].copy()
    
    # Add row numbers
    display_df.insert(0, 'No.', range(1, len(display_df) + 1))
    
    # Instructions dengan conditional formatting
    st.markdown("""
    <div style="background: white; padding: 1rem; border-radius: 10px; border: 1px solid #E5E7EB; margin-bottom: 1rem;">
    <p style="color: #6B7280; margin-bottom: 0.5rem; font-size: 0.95rem;">
    💡 <strong>Instructions:</strong> 
    <br>1. Edit only the <strong style="color: #1E40AF;">Cons_Feb-26, Cons_Mar-26, Cons_Apr-26</strong> columns
    <br>2. <strong>Conditional Formatting Applied:</strong>
    </p>
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; margin-top: 0.5rem;">
        <div>
            <strong style="color: #BE185D;">Month Cover Column:</strong>
            <ul style="margin: 0.25rem 0; padding-left: 1.2rem; font-size: 0.9rem;">
                <li>Value > 1.5 → Pink background</li>
            </ul>
        </div>
        <div>
            <strong style="color: #991B1B;">Growth % Columns:</strong>
            <ul style="margin: 0.25rem 0; padding-left: 1.2rem; font-size: 0.9rem;">
                <li>< 90% → Orange background</li>
                <li>> 130% → Red background</li>
            </ul>
        </div>
    </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Create column configuration dengan formatting yang tepat
    column_config = {}
    
    # Read-only columns
    read_only_cols = ['No.', 'sku_code', 'Product_Name', 'Brand', 'SKU_Tier'] + \
                     sales_months + ['L3M_Avg', 'Stock_Qty', 'Month_Cover'] + \
                     adjustment_months
    
    for col in read_only_cols:
        if col in display_df.columns:
            if col == 'Month_Cover':
                column_config[col] = st.column_config.NumberColumn(
                    "Month Cover",
                    format="%.1f",
                    disabled=True,
                    help="Stock coverage in months. >1.5 highlighted in pink"
                )
            else:
                column_config[col] = st.column_config.Column(
                    col.replace('_', ' ').title(),
                    disabled=True
                )
    
    # Percentage columns (read-only, formatted as number tanpa % symbol)
    for month in adjustment_months:
        pct_col = f"{month}_%"
        if pct_col in display_df.columns:
            column_config[pct_col] = st.column_config.NumberColumn(
                f"{month} %",
                format="%.1f",
                disabled=True,
                help=f"Growth % vs L3M. <90% (orange), >130% (red)"
            )
    
    # Editable consensus columns
    for month in adjustment_months:
        cons_col = f"Cons_{month}"
        if cons_col in display_df.columns:
            column_config[cons_col] = st.column_config.NumberColumn(
                f"Cons {month}",
                min_value=0,
                step=1,
                format="%d",
                help=f"Final consensus quantity for {month}"
            )
    
    # Display data editor dengan conditional formatting
    st.markdown("**📋 Adjustment Table (Editable - Apply your adjustments here)**")
    
    # Tampilkan warning jika banyak data
    if len(display_df) > 200:
        st.warning(f"⚠️ Showing {len(display_df)} rows. Conditional formatting may take a moment to load.")
    
    edited_data = st.data_editor(
        display_df,
        column_config=column_config,
        use_container_width=True,
        height=600,
        key="input_editor",
        num_rows="dynamic"
    )
    
    # Save button section
    st.markdown("---")
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    
    with col2:
        if st.button("💾 Save Adjustments", type="primary", use_container_width=True, key="save_tab1"):
            with st.spinner("Saving adjustments..."):
                # Calculate changes
                changes = []
                total_adjustment = 0
                
                for month in adjustment_months:
                    cons_col = f"Cons_{month}"
                    if cons_col in edited_data.columns:
                        month_change = (edited_data[cons_col] - edited_data[month]).sum()
                        changes.append(f"{month}: {month_change:+,.0f}")
                        total_adjustment += month_change
                
                # Store in session state for Tab 2
                st.session_state.consensus_data = edited_data.copy()
                st.session_state.adjustment_changes = changes
                st.session_state.total_adjustment = total_adjustment
                
                st.success(f"✅ Adjustments saved!")
                
                # Show summary of changes
                st.info(f"**Summary of Changes:**")
                for change in changes:
                    st.write(f"  - {change}")
                st.write(f"**Total Adjustment:** {total_adjustment:+,.0f}")
    
    with col3:
        if st.button("📤 Export to Excel", use_container_width=True, key="export_tab1"):
            export_df = edited_data.copy()
            
            # Add timestamp
            export_df['Exported_At'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            export_df['Meeting_Date'] = meeting_date.strftime('%Y-%m-%d')
            
            # Create download button
            csv = export_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="⬇️ Download CSV",
                data=csv,
                file_name=f"sop_adjustments_{meeting_date}.csv",
                mime="text/csv",
                use_container_width=True,
                key="download_tab1"
            )
    
    with col4:
        # Stats button untuk melihat summary
        if st.button("📊 Show Stats", use_container_width=True, key="stats_tab1"):
            st.session_state.show_stats = True
        
        if 'show_stats' in st.session_state and st.session_state.show_stats:
            # Calculate statistics
            stats_cols = st.columns(4)
            
            with stats_cols[0]:
                # Count of SKUs with Month Cover > 1.5
                high_cover = len(edited_data[edited_data['Month_Cover'] > 1.5])
                st.metric("SKUs Month Cover > 1.5", high_cover)
            
            with stats_cols[1]:
                # Count of SKUs with growth < 90%
                low_growth = 0
                for month in adjustment_months:
                    pct_col = f"{month}_%"
                    if pct_col in edited_data.columns:
                        low_growth += len(edited_data[edited_data[pct_col] < 90])
                st.metric("SKUs Growth < 90%", low_growth)
            
            with stats_cols[2]:
                # Count of SKUs with growth > 130%
                high_growth = 0
                for month in adjustment_months:
                    pct_col = f"{month}_%"
                    if pct_col in edited_data.columns:
                        high_growth += len(edited_data[edited_data[pct_col] > 130])
                st.metric("SKUs Growth > 130%", high_growth)
            
            with stats_cols[3]:
                # Average month cover
                avg_cover = edited_data['Month_Cover'].mean()
                st.metric("Avg Month Cover", f"{avg_cover:.1f}")

# ============================================================================
# FOOTER
# ============================================================================
st.markdown("---")
st.markdown(f"""
<div style="text-align: center; color: #6B7280; padding: 1rem;">
    <p style="margin-bottom: 0.5rem;">
        📊 <strong>ERHA S&OP Dashboard</strong> | Meeting: {meeting_date} | 
        Total SKUs: {len(all_df):,} | Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    </p>
    <p style="font-size: 0.9rem; margin-top: 0;">
        Tab 1: Filtered View with Conditional Formatting | Tab 2: Full Dataset | For internal S&OP meetings only
    </p>
</div>
""", unsafe_allow_html=True)
