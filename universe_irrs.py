import data_source
import pandas as pd

from tqdm import tqdm
from factories import CLOFactory
from clo_arg_parser import CLOArgumentParser, Arguments


def universe_irrs(args: Arguments) -> pd.DataFrame:
    # Load Napier holdings into memory.
    napier_holdings = data_source.load_napier_holdings()
    # Only consider deals we own equity in (for the time being).
    napier_holdings = napier_holdings[napier_holdings["orig_rtg"] == "Equity"]
    # Drop rows where intex_id is NaN.
    napier_holdings = napier_holdings.dropna(subset=["intex_id"])
    
    irrs = {}
    for deal_id in tqdm(napier_holdings["intex_id"].unique(), desc="Processing deals"):
        irrs[deal_id] = {}
        try:
            irr = deal_irrs(deal_id, args)
            irrs[deal_id]["irr"] = irr
        except Exception as e:
            print(f"Error processing deal {deal_id}: {e}")
            irrs[deal_id]["error"] = str(e)

    irrs_df = pd.DataFrame(irrs).T
    
    # Print summary statistics.
    print(f"Mean IRR: {irrs_df['irr'].mean():.2%}")
    print(f"Median IRR: {irrs_df['irr'].median():.2%}")
    print(f"Minimum IRR: {irrs_df['irr'].min():.2%}")
    print(f"Maximum IRR: {irrs_df['irr'].max():.2%}")

    # Print success rate.
    success_rate = (len(irrs) - sum(1 for irr in irrs.values() if 'error' in irr)) / len(irrs)
    print(f"Success rate: {len(irrs) - sum(1 for irr in irrs.values() if 'error' in irr)} / {len(irrs)} ({success_rate:.2%})")
    # Print a count of the number of deals with an error.
    print(f"Number of deals with an error: {sum(1 for irr in irrs.values() if 'error' in irr)}")
    
    return irrs_df


def deal_irrs(deal_id: str, args: Arguments) -> float:
    deal, loans, tranches = data_source.load_deal(deal_id)
    deal_holdings = data_source.load_deal_holdings(deal_id)
    forward_curves = data_source.load_latest_forward_curves()

    factory = CLOFactory(deal, tranches, loans, forward_curves, args)
    model = factory.build()
    model.simulate()

    equity_holdings = deal_holdings[deal_holdings['orig_rtg'] == 'Equity']
    equity_purchase_price = equity_holdings['localprice'].mean() / 100
    equity_irr = model.equity_tranche.irr(equity_purchase_price)

    return equity_irr


def main():
    parser = CLOArgumentParser(description="Simulate the IRRs of a universe of deals.")
    args = parser.into()

    irrs_df = universe_irrs(args)
    irrs_df.to_excel("outputs/Universe IRRs.xlsx")


if __name__ == "__main__":
    main()