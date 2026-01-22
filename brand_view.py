import streamlit as st
import pandas as pd
from datetime import datetime
from modules.gsheet_connector import GSheetConnector

# Configuration for brand groups
BRAND_CONFIG = {
    'brand1': {
        'name': 'Brand Group 1',
        'brand_groups': ['Acneact', 'Age Corrector'],  # UPDATE: Add all Brand Group 1 names
        'sheet_name': 'brand1_input',
        'log_prefix': 'B1_',
        'icon': '🏷️'
    },
    'brand2': {
        'name': 'Brand Group 2',
        'brand_groups': ['Erhair', 'Skinsitive'],  # UPDATE: Add all Brand Group 2 names
        'sheet_name': 'brand2_input',
        'log_prefix': 'B2_',
        'icon': '🏷️'
    }
}

def show_brand_page(username, user_role):
    """Single brand view page for both brand groups"""
    
    # Get configuration for this user role
    config = BRAND_CONFIG.get(user_role)
    if not config:
        st.error("Invalid brand configuration. Please contact administrator.")
        return
    
    # Set page title and icon
    st.title(f"{config['icon']} {config['name']} Forecast Input")
    st.markdown("---")
    
    # Initialize connector
    gs = GSheetConnector()
    
    # Load data - Filter by brand group
    with st.spinner(f"Loading data for {config['name']}..."):
        # Get ROFO data
        rofo_df = gs.get_rofo_current()
        
        if rofo_df.empty:
            st.error("No ROFO data available. Please check your data source.")
            return
        
        # FILTER: Only show SKUs for this brand group
        if 'Brand_Group' in rofo_df.columns:
            # Filter by brand groups
            filtered_df = rofo_df[rofo_df['Brand_Group'].isin(config['brand_groups'])]
            
            if filtered_df.empty:
                st.warning(f"No SKUs found for {config['name']}. Please check Brand_Group configuration.")
                st.info(f"Looking for: {', '.join(config['brand_groups'])}")
                return
        else:
            st.error("Brand_Group column not found in ROFO data")
            return
        
        # Merge with stock data
        stock_df = gs.get_sheet_data("stock_onhand")
        if not stock_df.empty and 'sku_code' in stock_df.columns:
            merged_df = pd.merge(
                filtered_df,
                stock_df[['sku_code', 'Stock_Qty']],
                on='sku_code',
                how='left'
            )
            merged_df['Stock_Qty'] = merged_df['Stock_Qty'].fillna(0)
        else:
            merged_df = filtered_df.copy()
            merged_df['Stock_Qty'] = 0
    
    # Identify month columns (Feb-26, Mar-26, etc.)
    month_columns = [col for col in merged_df.columns if '-' in str(col) and len(str(col)) >= 6]
    
    # Create input form
    st.subheader("📝 Forecast Adjustment Input")
    st.caption(f"Logged in as: **{username}** | Role: **{config['name']}**")
    
    with st.form(f"{user_role}_input_form"):
        # Display metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(f"{config['name']} SKUs", len(merged_df))
        with col2:
            total_stock = merged_df['Stock_Qty'].sum()
            st.metric("Total Stock", f"{total_stock:,.0f}")
        with col3:
            # Check last submission
            try:
                log_df = gs.get_sheet_data("input_log")
                user_logs = log_df[(log_df['username'] == username) & (log_df['status'] == 'submitted')]
                last_submission = user_logs['submission_date'].max() if not user_logs.empty else "Never"
                st.metric("Last Submission", str(last_submission))
            except:
                st.metric("Last Submission", "Never")
        
        st.markdown("---")
        
        # Create editable dataframe
        edited_df = merged_df.copy()
        
        # Add input columns for each month
        for month in month_columns:
            edited_df[f"{month}_input"] = edited_df[month]
        
        # Display columns for editing
        display_columns = ['sku_code', 'Product_Name', 'Brand', 'SKU_Tier', 'Stock_Qty']
        for month in month_columns:
            display_columns.extend([month, f"{month}_input"])
        
        # Create column configuration
        column_config = {}
        
        # Fixed columns
        column_config['sku_code'] = st.column_config.TextColumn(
            "SKU Code", disabled=True
        )
        column_config['Product_Name'] = st.column_config.TextColumn(
            "Product Name", disabled=True
        )
        column_config['Brand'] = st.column_config.TextColumn(
            "Brand", disabled=True
        )
        column_config['SKU_Tier'] = st.column_config.TextColumn(
            "SKU Tier", disabled=True
        )
        column_config['Stock_Qty'] = st.column_config.NumberColumn(
            "Stock Qty", disabled=True, format="%d"
        )
        
        # Month columns - baseline (readonly) and input (editable)
        for month in month_columns:
            column_config[month] = st.column_config.NumberColumn(
                f"Baseline {month}",
                disabled=True,
                format="%d"
            )
            column_config[f"{month}_input"] = st.column_config.NumberColumn(
                f"Your Input {month}",
                min_value=0,
                step=1,
                format="%d"
            )
        
        # Display data editor
        edited_data = st.data_editor(
            edited_df[display_columns],
            column_config=column_config,
            use_container_width=True,
            height=400,
            num_rows="fixed"
        )
        
        # Additional input fields
        campaign_name = st.text_input(
            "Campaign Name (if applicable)",
            placeholder=f"e.g., {config['name']} Q2 Promotion"
        )
        
        notes = st.text_area(
            "Adjustment Notes / Justification",
            placeholder="Explain your forecast adjustments, campaign impact, market insights..."
        )
        
        # Submit button
        submit = st.form_submit_button(
            f"💾 Save to {config['name']} Input",
            use_container_width=True
        )
        
        if submit:
            # Validate adjustments (±40% limit)
            validation_errors = []
            
            for month in month_columns:
                input_col = f"{month}_input"
                baseline_col = month
                
                for idx, row in edited_data.iterrows():
                    baseline = row[baseline_col]
                    new_value = row[input_col]
                    
                    # Skip if NaN
                    if pd.isna(baseline) or pd.isna(new_value):
                        continue
                    
                    # Convert to float for calculation
                    try:
                        baseline = float(baseline)
                        new_value = float(new_value)
                    except:
                        continue
                    
                    # Calculate ±40% limits
                    max_change = baseline * 0.4
                    min_allowed = max(0, baseline - max_change)  # Don't go below 0
                    max_allowed = baseline + max_change
                    
                    if new_value < min_allowed or new_value > max_allowed:
                        validation_errors.append({
                            'sku': row['sku_code'],
                            'month': month,
                            'baseline': baseline,
                            'input': new_value,
                            'min_allowed': min_allowed,
                            'max_allowed': max_allowed
                        })
            
            # Show validation errors if any
            if validation_errors:
                st.error(f"❌ {len(validation_errors)} adjustments exceed ±40% limit")
                
                # Show first 5 errors
                for error in validation_errors[:5]:
                    st.error(
                        f"**{error['sku']} - {error['month']}:** "
                        f"Input {error['input']:.0f} vs Baseline {error['baseline']:.0f} "
                        f"(Allowed: {error['min_allowed']:.0f} - {error['max_allowed']:.0f})"
                    )
                
                if len(validation_errors) > 5:
                    st.error(f"... and {len(validation_errors) - 5} more errors")
            
            else:
                # Prepare data for saving
                save_df = edited_data.copy()
                
                # Keep only necessary columns
                save_columns = ['sku_code', 'Product_Name', 'Brand_Group', 'Brand', 'SKU_Tier']
                
                # Replace baseline with input values
                for month in month_columns:
                    save_df[month] = save_df[f"{month}_input"]
                    save_columns.append(month)
                
                # Add metadata
                save_df['campaign_name'] = campaign_name
                save_df['notes'] = notes
                save_df['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                save_df['submitted_by'] = username
                
                # Select final columns
                final_columns = save_columns + ['campaign_name', 'notes', 'last_updated', 'submitted_by']
                save_df = save_df[final_columns]
                
                # Save to GSheet
                with st.spinner(f"Saving to {config['name']}..."):
                    success = gs.update_sheet(config['sheet_name'], save_df)
                    
                    if success:
                        # Log submission
                        log_entry = {
                            'submission_id': f"{config['log_prefix']}{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                            'username': username,
                            'role': user_role,
                            'submission_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'status': 'submitted'
                        }
                        gs.append_to_sheet("input_log", log_entry)
                        
                        st.success(f"✅ {config['name']} input saved successfully!")
                        st.balloons()
                        
                        # Show summary
                        st.info(
                            f"**Summary:** {len(save_df)} SKUs updated | "
                            f"Saved to sheet: `{config['sheet_name']}`"
                        )
                    else:
                        st.error("❌ Failed to save data. Please try again.")
    
    # Information section
    st.markdown("---")
    st.subheader("ℹ️ Information")
    
    info_col1, info_col2 = st.columns(2)
    
    with info_col1:
        st.markdown("**Brand Groups in this view:**")
        for brand in config['brand_groups']:
            st.markdown(f"- {brand}")
    
    with info_col2:
        st.markdown("**Validation Rules:**")
        st.markdown("- Max adjustment: ±40% from baseline")
        st.markdown("- Input must be ≥ 0")
        st.markdown("- All months must be filled")
