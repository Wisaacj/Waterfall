import argparse
import data_source
import pandas as pd

from pathlib import Path
from factories import CLOFactory
from clo_arg_parser import CLOArgumentParser
from results_writer import ResultsWriter


def main():
    parser = CLOArgumentParser(description="Simulate CLO cashflows to maturity based on provided assumptions.")
    parser.add_deal_id_argument()
    args = parser.into()

    portfolio = pd.read_excel("data/Portfolio as of 22 analysis v2.xlsx", sheet_name="Summary")
    portfolio = data_source.clean_dataframe(portfolio)

    for _, row in portfolio.iterrows():
        deal_id = row['intex_id']
        real_cpr = row['realised_cpr'] / 100

        cprs = [args.cpr, real_cpr]
        print(deal_id, cprs)
        for cpr in cprs:
            print(f"\nLoading deal, tranche, & loan data for {deal_id} from disk...")
            deal, loans, tranches = data_source.load_deal(deal_id)
            print(f"    > Loaded deal data")

            print(f"Loading the latest forward-rate curves from DB (US Oracle)...")
            forward_curves = pd.read_excel("data/ForwardCurves-2022-01-01.xlsx")
            print(f"    > Loaded rate curves")

            print(f"Building a model of {deal_id}...")
            factory = CLOFactory(deal, tranches, loans, forward_curves, args)
            model = factory.build()
            print("    > Model built")

            print(f"Running scenario: Simulating cashflows for {deal_id} to maturity...")
            model.simulate()
            print("    > Cashflows simulated")

            print(f"Writing results for {deal_id} to disk...")
            writer = ResultsWriter(model, deal_id, args.output_path / deal_id / str(int(cpr * 100)))
            path = writer.include_tranches().write()
            print(f"    > Results written to '{path}'\n")


if __name__ == "__main__":
    main()



def merge_equity_sheets(base_path: Path):
    scenario_differences = {}
    for deal_dir in base_path.iterdir():
        if not deal_dir.is_dir():
            continue

        scenario_data = {}

        cpr_20_total_dist = 0
        cpr_real_total_dist = 0

        for scenario_dir in deal_dir.iterdir():
            if not scenario_dir.is_dir():
                continue

            equity_file = scenario_dir / "Equity.xlsx"
            if not equity_file.exists():
                print(f"Warning: Equity.xlsx not found in {scenario_dir}")
                continue

            df = pd.read_excel(equity_file, sheet_name="Equity")

            # Add a column for the % of the balance that has been distributed
            df['% Distribution'] = (df['interest_paid'] + df['principal_paid']) / df['balance']
            # Filter for dates between 2022-01-01 and 2024-01-01
            df = df[(df['date'] >= '2022-01-01') & (df['date'] <= '2024-02-01')]

            if scenario_dir.name == "20":
                cpr_20_total_dist = df['% Distribution'].sum()
            else:
                cpr_real_total_dist = df['% Distribution'].sum()

            scenario_data[scenario_dir.name] = df

        scenario_differences[deal_dir.name] = cpr_real_total_dist - cpr_20_total_dist
        
        if scenario_data:
            output_file = base_path / f"{deal_dir.name}_merged_equity.xlsx"
            with pd.ExcelWriter(output_file) as writer:
                for scenario, df in scenario_data.items():
                    df.to_excel(writer, sheet_name=scenario, index=False)
            print(f"Merged equity data for {deal_dir.name} saved to {output_file}")
        else:
            print(f"No equity data found for {deal_dir.name}")

    # Now, merge all individual workbooks into one big workbook
    big_merged_file = base_path / "All_Deals_Equity_Scenarios.xlsx"
    with pd.ExcelWriter(big_merged_file) as writer:
        # Write the scenario differences to a new sheet in the big merged file
        diff_df = pd.DataFrame(scenario_differences.items(), columns=['Deal ID', '% Distribution Difference'])
        diff_df.to_excel(writer, sheet_name='Scenario Differences', index=False)

        for merged_file in base_path.glob("*_merged_equity.xlsx"):
            print(f"Merging {merged_file}")
            deal_name = merged_file.stem.replace("_merged_equity", "")
            xls = pd.ExcelFile(merged_file)
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                new_sheet_name = f"{deal_name} - {sheet_name}% cpr"
                df.to_excel(writer, sheet_name=new_sheet_name, index=False)

            # Remove the individual merged file after it's been added to the big merged file
            # merged_file.unlink()

    print(f"All deals merged into {big_merged_file}")


def main():
    parser = argparse.ArgumentParser(description="Merge Equity.xlsx sheets from subdirectories.")
    parser.add_argument("path", type=Path, help="Base path containing deal directories")
    args = parser.parse_args()

    merge_equity_sheets(args.path)


if __name__ == "__main__":
    main()