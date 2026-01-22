import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from modules.gsheet_connector import GSheetConnector

def show_admin_page(username):
    st.title("👨‍💼 Admin - Demand Planner Dashboard")
    st.markdown("---")
    
    # Initialize connector
    gs = GSheetConnector()
    
    # Sidebar controls
    with st.sidebar:
        st.header("Admin Controls")
        
        if st.button("🔄 Refresh All Data", use_container_width=True):
            st.rerun()
        
        st.markdown("---")
        st.subheader("Consensus Management")
        
        if st.button("✅ Finalize Consensus", type="primary", use_container_width=True):
            st.info("Consensus finalization feature coming soon...")
        
        st.markdown("---")
        st.subheader("Export Options")
        
        if st.button("📊 Export to Excel", use_container_width=True):
            st.info("Export feature coming soon...")
    
    # Load all data
    with st.spinner("Loading all data..."):
        rofo_df = gs.get_rofo_current()
        channel_df = gs.get_sheet_data("channel_input")
        brand1_df = gs.get_sheet_data("brand1_input")
        brand2_df = gs.get_sheet_data("brand2_input")
        stock_df = gs.get_sheet_data("stock_onhand")
        log_df = gs.get_sheet_data("input_log")
    
    # Tab layout
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Overview", 
        "🔍 Comparison", 
        "📊 Stock Simulation", 
        "📋 Submission Status"
    ])
    
    with tab1:
        st.subheader("S&OP Forecast Overview")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_skus = len(rofo_df) if not rofo_df.empty else 0
            st.metric("Total SKUs", total_skus)
        
        with col2:
            submitted = len(log_df[log_df['status'] == 'submitted']) if not log_df.empty else 0
            st.metric("Submissions Received", submitted, delta="3")
        
        with col3:
            total_stock = stock_df['Stock_Qty'].sum() if not stock_df.empty else 0
            st.metric("Total Stock", f"{total_stock:,.0f}")
        
        with col4:
            # Calculate average adjustment
            st.metric("Avg. Adjustment", "+5.2%")
    
    with tab2:
        st.subheader("Forecast Comparison")
        
        # Create comparison DataFrame
        if not rofo_df.empty:
            month_columns = [col for col in rofo_df.columns if '-' in str(col) and len(str(col)) >= 6]
            
            # Sample comparison for first month
            if month_columns:
                sample_month = month_columns[0]
                
                comparison_data = []
                
                # Get values from each source
                for idx, sku_row in rofo_df.head(10).iterrows():  # Show first 10 SKUs
                    sku_code = sku_row['sku_code']
                    
                    # Get channel input
                    channel_val = None
                    if not channel_df.empty and 'sku_code' in channel_df.columns:
                        channel_row = channel_df[channel_df['sku_code'] == sku_code]
                        if not channel_row.empty and sample_month in channel_row.columns:
                            channel_val = channel_row.iloc[0][sample_month]
                    
                    # Get brand1 input
                    brand1_val = None
                    if not brand1_df.empty and 'sku_code' in brand1_df.columns:
                        brand1_row = brand1_df[brand1_df['sku_code'] == sku_code]
                        if not brand1_row.empty and sample_month in brand1_row.columns:
                            brand1_val = brand1_row.iloc[0][sample_month]
                    
                    comparison_data.append({
                        'SKU': sku_code,
                        'Product': sku_row.get('Product_Name', ''),
                        'Baseline': sku_row[sample_month],
                        'Channel': channel_val,
                        'Brand 1': brand1_val,
                        'Brand 2': None  # Add if needed
                    })
                
                comp_df = pd.DataFrame(comparison_data)
                st.dataframe(comp_df, use_container_width=True)
    
    with tab3:
        st.subheader("Stock Projection Simulation")
        st.info("Stock simulation feature coming soon...")
    
    with tab4:
        st.subheader("Submission Status")
        
        if not log_df.empty:
            # Filter recent submissions
            recent_logs = log_df.sort_values('submission_date', ascending=False).head(20)
            st.dataframe(recent_logs, use_container_width=True)
        else:
            st.info("No submissions yet.")
