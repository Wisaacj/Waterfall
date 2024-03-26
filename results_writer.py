import os
import pandas as pd

from model import CLO, Snapshot

OUTPUT_DIR = "./outputs"


class ResultsWriter:

    def __init__(
        self, 
        model: CLO, 
        deal_id: str,
        output_dir: str = OUTPUT_DIR
    ):
        self.model = model
        self.deal_id = deal_id
        self.output_dir = output_dir

        if not os.path.exists(output_dir):
            os.mkdir(output_dir)

    @property
    def output_path(self) -> str:
        return os.path.join(self.output_dir, self.deal_id)

    def write_results(self) -> str:
        for tranche in self.model.tranches:
            self._export_history_to_excel(tranche.history, tranche.rating)

        return os.path.abspath(self.output_path)

    def _export_history_to_excel(self, snapshots: list[Snapshot], filename: str):
        """Exports a list of snapshot objects to an Excel file."""
        # Convert each snapshot object to a dictionary.
        data = [ResultsWriter._snapshot_to_dict(snapshot) for snapshot in snapshots]
        cashflows_df = pd.DataFrame(data)
        
        if not os.path.exists(self.output_path):
            os.mkdir(self.output_path)

        cashflows_df.to_csv(os.path.join(self.output_path, f"{filename}.csv"))

    @staticmethod
    def _snapshot_to_dict(snapshot: Snapshot):
        """Convert a snapshot object into a dictionary."""
        return {field: getattr(snapshot, field) for field in snapshot.__dataclass_fields__}