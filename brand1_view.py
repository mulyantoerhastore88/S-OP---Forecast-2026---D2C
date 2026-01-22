import streamlit as st
import pandas as pd
from datetime import datetime
from modules.gsheet_connector import GSheetConnector

def show_brand1_page(username):
    st.title("🏷️ Brand Group 1 Forecast Input")
    st.markdown("---")
    
    # Initialize connector
    gs = GSheetConnector()
    
    # Load data - Filter for Brand Group 1 only
    with st.spinner("Loading data for Brand Group 1..."):
        rofo_df = gs.get_rofo_current()
        
        # Get brand groups from sales_history to identify Brand Group 1 SKUs
        sales_df = gs.get_sheet_data("sales_history")
        
        if not sales_df.empty and 'Brand_Group' in sales_df.columns:
            # Identify Brand Group 1 SKUs (assuming Acneact, Age Corrector, etc.)
            brand1_groups = ['Acneact', 'Age Corrector']  # Add all Brand Group 1 names here
            
            brand1_skus = sales_df[
                sales_df['Brand_Group'].isin(brand1_groups)
            ]['sku_code'].unique()
            
            # Filter ROFO data
            rofo_df = rofo_df[rofo_df['sku_code'].isin(brand1_skus)]
        
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
        st.warning("No SKUs found for Brand Group 1. Please check your data.")
        return
    
    # Identify month columns
    month_columns = [col for col in merged_df.columns if '-' in str(col) and len(str(col)) >= 6]
    
    # Create input form
    st.subheader("📝 Brand Group 1 Forecast Adjustment")
    st.caption(f"Logged in as: **{username}** | Role: **Brand Group 1**")
    
    with st.form("brand1_input_form"):
        # Create editable dataframe
        edited_df = merged_df.copy()
        
        # Display current stock
        st.metric("Brand Group 1 SKUs", len(merged_df))
        
        # Create input columns for each month
        for month in month_columns:
            edited_df[f"{month}_input"] = merged_df[month]
        
        # Use data editor
        st.write("### Adjust Forecast Quantities (±40% limit)")
        
        # Convert for editing
        display_columns = ['sku_code', 'Product_Name', 'Brand', 'SKU_Tier', 'Stock_Qty']
        
        # Add month columns
        for month in month_columns:
            display_columns.append(month)
            display_columns.append(f"{month}_input")
        
        # Reorder dataframe
        display_df = edited_df[display_columns].copy()
        
        # Create editable config
        column_config = {}
        for month in month_columns:
            baseline_col = month
            input_col = f"{month}_input"
            
            column_config[baseline_col] = st.column_config.NumberColumn(
                label=f"Baseline {month}",
                disabled=True,
                format="%d"
            )
            
            column_config[input_col] = st.column_config.NumberColumn(
                label=f"Your Input {month}",
                min_value=0,
                format="%d"
            )
        
        column_config['sku_code'] = st.column_config.TextColumn("SKU Code", disabled=True)
        column_config['Product_Name'] = st.column_config.TextColumn("Product Name", disabled=True)
        column_config['Stock_Qty'] = st.column_config.NumberColumn("Stock Qty", disabled=True, format="%d")
        
        # Display data editor
        edited_data = st.data_editor(
            display_df,
            column_config=column_config,
            use_container_width=True,
            height=400,
            num_rows="dynamic"
        )
        
        # Campaign notes field
        campaign_name = st.text_input("Campaign Name (if applicable)", 
                                    placeholder="e.g., Q2 Promotion, New Product Launch")
        notes = st.text_area("Campaign Impact Notes", 
                           placeholder="Describe campaign impact, ROI expectations...")
        
        submit = st.form_submit_button("💾 Save to Brand Group 1 Input", use_container_width=True)
        
        if submit:
            # Validate adjustments (±40%)
            validation_passed = True
            errors = []
            
            for month in month_columns:
                input_col = f"{month}_input"
                baseline_col = month
                
                for idx, row in edited_data.iterrows():
                    baseline = row[baseline_col]
                    new_value = row[input_col]
                    
                    if pd.isna(baseline) or pd.isna(new_value):
                        continue
                    
                    max_change = baseline * 0.4
                    min_allowed = baseline - max_change
                    max_allowed = baseline + max_change
                    
                    if new_value < min_allowed or new_value > max_allowed:
                        validation_passed = False
                        errors.append(
                            f"SKU {row['sku_code']} - {month}: "
                            f"Adjustment {new_value} exceeds ±40% limit "
                            f"(Baseline: {baseline}, Allowed: {min_allowed:.0f}-{max_allowed:.0f})"
                        )
            
            if not validation_passed:
                st.error("❌ Validation Failed")
                for error in errors[:5]:
                    st.error(error)
                if len(errors) > 5:
                    st.error(f"... and {len(errors) - 5} more errors")
            else:
                # Prepare data for saving
                save_df = edited_data.copy()
                
                # Keep only necessary columns
                save_columns = ['sku_code', 'Product_Name', 'Brand_Group', 'Brand', 'SKU_Tier']
                
                # Add month inputs
                for month in month_columns:
                    save_columns.append(month)
                    save_df[month] = save_df[f"{month}_input"]
                
                # Add metadata
                save_df['campaign_name'] = campaign_name
                save_df['notes'] = notes
                save_df['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                save_df['submitted_by'] = username
                
                save_df = save_df[save_columns + ['campaign_name', 'notes', 'last_updated', 'submitted_by']]
                
                # Save to GSheet
                with st.spinner("Saving to Google Sheets..."):
                    success = gs.update_sheet("brand1_input", save_df)
                    
                    # Log submission
                    if success:
                        log_entry = {
                            'submission_id': f"B1_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                            'username': username,
                            'role': 'brand1',
                            'submission_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'status': 'submitted'
                        }
                        gs.append_to_sheet("input_log", log_entry)
                        
                        st.success("✅ Brand Group 1 input saved successfully!")
                        st.balloons()
                    else:
                        st.error("❌ Failed to save data. Please try again.")
    
    # Display summary
    st.markdown("---")
    st.subheader("📈 Brand Group 1 Status")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Brand Group 1 SKUs", len(merged_df))
    
    with col2:
        total_stock = merged_df['Stock_Qty'].sum() if 'Stock_Qty' in merged_df.columns else 0
        st.metric("Total Stock", f"{total_stock:,.0f}")
    
    with col3:
        try:
            log_df = gs.get_sheet_data("input_log")
            user_logs = log_df[(log_df['username'] == username) & (log_df['status'] == 'submitted')]
            last_submission = user_logs['submission_date'].max() if not user_logs.empty else "Never"
            st.metric("Last Submission", str(last_submission))
        except:
            st.metric("Last Submission", "Never")
