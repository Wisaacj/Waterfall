import data_source

from factories import CLOFactory
from results_writer import ResultsWriter
from clo_arg_parser import CLOArgumentParser


def main():
    parser = CLOArgumentParser(description="Simulate CLO cashflows to maturity based on provided assumptions.")
    parser.add_deal_id_argument()
    args = parser.into()
    deal_id = args.deal_id.upper()

    print(f"\nLoading deal, tranche, & loan data for {deal_id} from disk...")
    deal, loans, tranches = data_source.load_deal(deal_id)
    print(f"    > Loaded deal data")

    print(f"Loading the latest forward-rate curves from DB (US Oracle)...")
    forward_curves = data_source.load_latest_forward_curves()
    print(f"    > Loaded rate curves")

    print(f"Building a model of {deal_id}...")
    factory = CLOFactory(deal, tranches, loans, forward_curves, args)
    model = factory.build()
    print("    > Model built")

    print(f"Running scenario: Simulating cashflows for {deal_id} to maturity...")
    model.simulate()
    print("    > Cashflows simulated")

    print(f"Writing results for {deal_id} to disk...")
    writer = ResultsWriter(model, deal_id, args.output_path)
    if args.output_asset_cashflows:
        writer.include_assets()
    path = writer.include_tranches().write()
    print(f"    > Results written to '{path}'\n")


if __name__ == "__main__":
    main()
