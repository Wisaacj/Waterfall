import os
import numpy as np
import pandas as pd

from pathlib import Path
from openpyxl import Workbook
from collections import Counter
from openpyxl.utils.dataframe import dataframe_to_rows
from model import CLO, Snapshot

OUTPUT_DIR = Path("outputs")


class ResultsWriter:

    def __init__(
        self, 
        model: CLO, 
        deal_id: str,
        output_dir: Path = OUTPUT_DIR
    ):
        self.model = model
        self.deal_id = deal_id
        self.output_dir = output_dir
        output_dir.mkdir(exist_ok=True)

    @property
    def output_path(self) -> Path:
        return self.output_dir / self.deal_id

    def write_results(self) -> str:
        # Write tranche histories
        for tranche in self.model.tranches:
            self._export_history_to_excel(tranche.history, tranche.rating)

        # Write asset histories
        self._export_asset_histories()

        return self.output_dir.absolute()
    
    # def _export_asset_histories(self):
    #     """Exports histories of all assets in the portfolio to a single Excel file."""
    #     wb = Workbook()
    #     wb.remove(wb.active) # Remove the default sheet

    #     for asset in self.model.portfolio.assets:
    #         sheet_name = asset.figi
    #         ws = wb.create_sheet(sheet_name)
            
    #         data = [self._snapshot_to_dict(snapshot) for snapshot in asset.history]
    #         df = pd.DataFrame(data)
            
    #         for r in dataframe_to_rows(df, index=False, header=True):
    #             ws.append(r)

    #     output_file = self.output_path / "Asset CF.xlsx"
    #     wb.save(output_file)

    def _export_asset_histories(self):
        """Exports the history of all assets in the portfolio to a single Excel file."""
        all_asset_data = []
        figi_counter = Counter()

        for asset in self.model.portfolio.assets:
            figi_counter[asset.figi] += 1
            asset_data = [self._snapshot_to_dict(snapshot) for snapshot in asset.history]
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
            date_summary.to_excel(writer, sheet_name='Date Summary')

    def _create_summary(self, grouped: pd.DataFrame):
        """Create a summary DataFrame with weighted average interest rate."""
        sum_cols = grouped.sum()
        weighted_rate = grouped.apply(self._safe_weighted_average)
        summary = sum_cols.drop('interest_rate', axis=1)
        summary['interest_rate'] = weighted_rate
        return summary

    def _export_history_to_excel(self, snapshots: list[Snapshot], filename: str):
        """Exports a list of snapshot objects to an Excel file."""
        # Convert each snapshot object to a dictionary.
        data = [ResultsWriter._snapshot_to_dict(snapshot) for snapshot in snapshots]
        cashflows_df = pd.DataFrame(data)
        
        self.output_path.mkdir(exist_ok=True)
        cashflows_df.to_excel(self.output_path / f"{filename}.xlsx")

    @staticmethod
    def _safe_weighted_average(group):
        """Calculate weighted average, handling zero-sum weights."""
        try:
            return np.average(group['interest_rate'], weights=group['balance'])
        except ZeroDivisionError:
            return 0

    @staticmethod
    def _snapshot_to_dict(snapshot: Snapshot):
        """Convert a snapshot object into a dictionary."""
        return {field: getattr(snapshot, field) for field in snapshot.__dataclass_fields__}