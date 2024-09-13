import os
import pandas as pd

from pathlib import Path
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
        for tranche in self.model.tranches:
            self._export_history_to_excel(tranche.history, tranche.rating)

        return self.output_dir.absolute()

    def _export_history_to_excel(self, snapshots: list[Snapshot], filename: str):
        """Exports a list of snapshot objects to an Excel file."""
        # Convert each snapshot object to a dictionary.
        data = [ResultsWriter._snapshot_to_dict(snapshot) for snapshot in snapshots]
        cashflows_df = pd.DataFrame(data)
        
        self.output_path.mkdir(exist_ok=True)
        cashflows_df.to_excel(self.output_path / f"{filename}.xlsx")

    @staticmethod
    def _snapshot_to_dict(snapshot: Snapshot):
        """Convert a snapshot object into a dictionary."""
        return {field: getattr(snapshot, field) for field in snapshot.__dataclass_fields__}