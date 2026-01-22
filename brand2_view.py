import streamlit as st
import pandas as pd
from datetime import datetime
from modules.gsheet_connector import GSheetConnector

def show_brand2_page(username):
    st.title("🏷️ Brand Group 2 Forecast Input")
    st.markdown("---")
    
    # Initialize connector
    gs = GSheetConnector()
    
    # Load data - Filter for Brand Group 2 only
    with st.spinner("Loading data for Brand Group 2..."):
        rofo_df = gs.get_rofo_current()
        
        # Get brand groups from sales_history to identify Brand Group 2 SKUs
        sales_df = gs.get_sheet_data("sales_history")
        
        if not sales_df.empty and 'Brand_Group' in sales_df.columns:
            # Identify Brand Group 2 SKUs (assuming Erhair, Skinsitive, etc.)
            brand2_groups = ['Erhair', 'Skinsitive']  # Add all Brand Group 2 names here
            
            brand2_skus = sales_df[
                sales_df['Brand_Group'].isin(brand2_groups)
            ]['sku_code'].unique()
            
            # Filter ROFO data
            rofo_df = rofo_df[rofo_df['sku_code'].isin(brand2_skus)]
        
        stock_df = gs.get_sheet_data("stock_onhand")
        
        # Merge with stock data
        if not rofo_df.empty and not stock_df.empty:
            merged_df = pd.merge(
                rofo_df, 
                stock_df[['sku_code', 'Stock_Qty']], 
                on='sku_code', 
                how='left'
            )
            merged_df['Stock_Qty'] = merged_df['Stock_Qty'].fillna(0)
        else:
            merged_df = rofo_df
            merged_df['Stock_Qty'] = 0
    
    if merged_df.empty:
        st.warning("No SKUs found for Brand Group 2. Please check your data.")
        return
    
    # Identify month columns
    month_columns = [col for col in merged_df.columns if '-' in str(col) and len(str(col)) >= 6]
    
    # Create input form (similar to brand1_view with minor changes)
    # [Similar structure to brand1_view.py with "Brand Group 2" labels]
    # Save to "brand2_input" sheet instead
