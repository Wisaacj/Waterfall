import numpy as np
import pandas as pd

from tqdm import tqdm
from pathlib import Path
from collections import Counter
from model import CLO, Snapshot


class ResultsWriter:

    def __init__(
        self, 
        model: CLO, 
        deal_id: str,
        output_dir: Path = Path("outputs")
    ):
        self.model = model
        self.deal_id = deal_id
        self.output_dir = output_dir
        self.requested_results = []
        output_dir.mkdir(exist_ok=True)

    @property
    def output_path(self) -> Path:
        return self.output_dir / self.deal_id
    
    def include_assets(self) -> 'ResultsWriter':
        self.requested_results.append(self._write_asset_cashflows)
        return self

    def include_tranches(self) -> 'ResultsWriter':
        self.requested_results.append(self._write_tranche_cashflows)
        return self
    
    def include_fees(self) -> 'ResultsWriter':
        self.requested_results.append(self._write_fee_cashflows)
        return self
    
    def include_clo(self) -> 'ResultsWriter':
        self.requested_results.append(self._write_clo_cashflows)
        return self
    
    def include_all_liabilities(self) -> 'ResultsWriter':
        self.include_clo()
        self.include_fees()
        self.include_tranches()
        return self

    def write(self) -> str:
        self.output_path.mkdir(exist_ok=True)
        cashflow_path = self.output_path / "Cashflows.xlsx"

        with pd.ExcelWriter(cashflow_path, engine='openpyxl') as writer:
            for write_func in self.requested_results:
                write_func(writer)

        return self.output_path.absolute()
    
    def _write_tranche_cashflows(self, writer: pd.ExcelWriter) -> str:
        """Exports the history of all tranches in the CLO to a single Excel file."""
        for tranche in tqdm(self.model.tranches, desc="Exporting tranche histories"):
            self._export_history_to_excel(tranche.history, tranche.rating, writer)

    def _write_fee_cashflows(self, writer: pd.ExcelWriter) -> str:
        """Exports the history of all fees in the CLO to a single Excel file."""
        for fee in tqdm(self.model.fees, desc="Exporting fee histories"):
            self._export_history_to_excel(fee.history, fee.name, writer)
        self._export_history_to_excel(self.model.incentive_fee.history, self.model.incentive_fee.name, writer)

    def _write_clo_cashflows(self, writer: pd.ExcelWriter) -> str:
        """Exports the history of the CLO to a single Excel file."""
        self._export_history_to_excel(self.model.history, "CLO", writer)
    
    def _write_asset_cashflows(self, _: pd.ExcelWriter) -> str:
        """Exports the history of all assets in the portfolio to a single Excel file."""
        all_asset_data = []
        figi_counter = Counter()

        for asset in tqdm(self.model.portfolio.assets, desc="Exporting asset histories"):
            figi_counter[asset.figi] += 1
            asset_data = [vars(snapshot) for snapshot in asset.history]
            for row in asset_data:
                row['figi'] = asset.figi
                row['figi_instance'] = figi_counter[asset.figi]
            all_asset_data.extend(asset_data)

        df = pd.DataFrame(all_asset_data)
        df.set_index(['figi', 'figi_instance', 'date'], inplace=True)
        df.sort_index(inplace=True)

        excel_path = self.output_path / "Asset CF.xlsx"
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Asset Cashflows')

            # Create summary sheet
            date_summary = self._create_summary(df.groupby('date'))
            date_summary.to_excel(writer, sheet_name='Portfolio Summary')

            # Access the workbook and apply formatting
            workbook = writer.book
            self._apply_formatting(workbook['Asset Cashflows'])
            self._apply_formatting(workbook['Portfolio Summary'])

    def _create_summary(self, grouped: pd.DataFrame):
        """Create a summary DataFrame with weighted average interest rate."""
        sum_cols = grouped.sum()
        weighted_coupon = grouped.apply(lambda x: self._safe_weighted_average(x, 'coupon'))
        weighted_spread = grouped.apply(lambda x: self._safe_weighted_average(x, 'spread'))
        weighted_base_rate = grouped.apply(lambda x: self._safe_weighted_average(x, 'base_rate'))   
        weighted_price = grouped.apply(lambda x: self._safe_weighted_average(x, 'price'))
        summary = sum_cols.drop(['coupon', 'spread', 'base_rate', 'price'], axis=1)
        summary['coupon'] = weighted_coupon
        summary['spread'] = weighted_spread
        summary['base_rate'] = weighted_base_rate
        summary['price'] = weighted_price
        return summary

    def _export_history_to_excel(self, snapshots: list[Snapshot], filename: str, writer: pd.ExcelWriter):
        """Exports a list of snapshot objects to an Excel file."""
        # Convert each snapshot object to a dictionary.
        data = [vars(snapshot) for snapshot in snapshots]
        cashflows_df = pd.DataFrame(data)
        
        cashflows_df.to_excel(writer, sheet_name=filename)
        self._apply_formatting(writer.sheets[filename])

    @staticmethod
    def _safe_weighted_average(group: pd.DataFrame, column: str) -> float:
        """Calculate weighted average, handling zero-sum weights."""
        try:
            return np.average(group[column], weights=group['balance'])
        except ZeroDivisionError:
            return 0
        
    @staticmethod
    def _apply_formatting(sheet):
        """Apply formatting to the Excel sheet."""
        for row in sheet.iter_rows():
            for cell in row:
                if isinstance(cell.value, (int, float)):
                    cell.number_format = '#,##0'

        # Adjust column widths
        for col in sheet.columns:
            column = col[0].column_letter
            max_length = len(column)
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = (max_length)
            sheet.column_dimensions[column].width = adjusted_width