import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials
import json

class GSheetConnector:
    def __init__(self):
        self.sheet_id = st.secrets["gsheets"]["sheet_id"]
        self.service_account_info = json.loads(st.secrets["gsheets"]["service_account_info"])
        self.client = None
        self.connect()
    
    def connect(self):
        """Connect to Google Sheets API"""
        try:
            scope = ['https://www.googleapis.com/auth/spreadsheets']
            creds = Credentials.from_service_account_info(
                self.service_account_info, scopes=scope)
            self.client = gspread.authorize(creds)
            self.sheet = self.client.open_by_key(self.sheet_id)
        except Exception as e:
            st.error(f"Failed to connect to Google Sheets: {str(e)}")
            raise
    
    def get_sheet_data(self, sheet_name):
        """Read sheet as DataFrame"""
        try:
            worksheet = self.sheet.worksheet(sheet_name)
            data = worksheet.get_all_records()
            return pd.DataFrame(data)
        except Exception as e:
            st.error(f"Error reading sheet {sheet_name}: {str(e)}")
            return pd.DataFrame()
    
    def update_sheet(self, sheet_name, df):
        """Update sheet with DataFrame"""
        try:
            worksheet = self.sheet.worksheet(sheet_name)
            worksheet.clear()
            
            # Convert DataFrame to list of lists
            data = [df.columns.values.tolist()] + df.values.tolist()
            worksheet.update(data, value_input_option='USER_ENTERED')
            return True
        except Exception as e:
            st.error(f"Error updating sheet {sheet_name}: {str(e)}")
            return False
    
    def append_to_sheet(self, sheet_name, data_dict):
        """Append single row to sheet"""
        try:
            worksheet = self.sheet.worksheet(sheet_name)
            worksheet.append_row(list(data_dict.values()))
            return True
        except Exception as e:
            st.error(f"Error appending to sheet {sheet_name}: {str(e)}")
            return False
    
    def get_rofo_current(self):
        """Get ROFO current data with proper column handling"""
        df = self.get_sheet_data("rofo_current")
        
        # Identify month columns (Feb-26, Mar-26, etc.)
        month_columns = [col for col in df.columns if '-' in str(col) and len(str(col)) >= 6]
        
        # Keep only relevant columns
        keep_columns = ['sku_code', 'Product_Name', 'Brand_Group', 'Brand', 'SKU_Tier'] + month_columns
        keep_columns = [col for col in keep_columns if col in df.columns]
        
        return df[keep_columns]
