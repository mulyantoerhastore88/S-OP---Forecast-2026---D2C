import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

class GSheetConnector:
    def __init__(self, sheet_id):
        self.sheet_id = sheet_id
        self.client = None
        self.connect()
    
    def connect(self):
        # Setup credentials
        scope = ['https://www.googleapis.com/auth/spreadsheets']
        creds = Credentials.from_service_account_file(
            'config/credentials.json', scopes=scope)
        self.client = gspread.authorize(creds)
        self.sheet = self.client.open_by_key(self.sheet_id)
    
    def get_sheet_data(self, sheet_name):
        """Read sheet as DataFrame"""
        worksheet = self.sheet.worksheet(sheet_name)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    
    def update_sheet(self, sheet_name, df):
        """Update sheet with DataFrame"""
        worksheet = self.sheet.worksheet(sheet_name)
        worksheet.clear()
        
        # Update headers
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
    
    def append_to_sheet(self, sheet_name, data_dict):
        """Append single row to sheet"""
        worksheet = self.sheet.worksheet(sheet_name)
        worksheet.append_row(list(data_dict.values()))
