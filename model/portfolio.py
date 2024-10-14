import pyxirr

from datetime import date
from .asset import Asset
from .account import Account
from .forward_rate_curve import ForwardRateCurve
from .enums import LiquidationType
from pyxirr import DayCount


class Portfolio:
    """
    Class representing a Portfolio of assets.
    """
    def __init__(self, assets: list[Asset], forward_rate_curves: dict[str, ForwardRateCurve]):
        """
        Instantiates a Portfolio of Assets.
        
        :param assets: a list of assets.
        """
        self.assets = assets
        self.forward_rate_curves = forward_rate_curves
        self.last_simulation_date = self.assets[0].last_simulation_date
        self.report_date = self.assets[0].report_date
        
    def __str__(self):
        """
        Overrides the default str() method for this class.
        """
        return 'Portfolio'
    
    def simulate(self, simulate_until: date):
        """
        Simulates the entire portfolio of assets for a period of time
        ending on the simulate_until.
        
        :param simulate_until: as the name suggests.
        """
        for asset in self.assets:
            asset.simulate(simulate_until)
                
        self.last_simulation_date = simulate_until

    def liquidate(self, accrual_date: date, liquidation_type: LiquidationType):
        """
        Liquidates the entire portfolio of assets on the accrual date.
        """
        for asset in self.assets:
            asset.liquidate(accrual_date, liquidation_type)

    def backdate(self, cutoff_date: date):
        """
        Backdates the portfolio to the cutoff date.
        """
        for asset in self.assets:
            asset.backdate(cutoff_date)

    @property
    def total_interest_accrued(self):
        """
        Returns the total interest accrued, but not paid, on the portfolio.
        """
        return sum(asset.interest_accrued for asset in self.assets)
    
    @property
    def total_interest_paid(self):
        """
        Returns the total interest paid, but not swept, by assets in the portfolio.
        """
        return sum(asset.interest_paid for asset in self.assets)
    
    @property
    def total_asset_balance(self) -> float:
        """
        Returns the portfolio par.
        """
        return sum(asset.balance for asset in self.assets)
    
    @property
    def weighted_average_coupon(self) -> float:
        """
        Returns the weighted average coupon of the portfolio.
        """
        total_asset_balance = self.total_asset_balance
        
        try:
            return sum(asset.interest_rate * (asset.balance / total_asset_balance) for asset in self.assets)
        except ZeroDivisionError:
            return 0
        
    @property
    def weighted_average_spread(self) -> float:
        """
        Returns the weighted average spread of the portfolio.
        """
        total_asset_balance = self.total_asset_balance
        
        try:
            return sum(asset.spread * (asset.balance / total_asset_balance) for asset in self.assets)
        except ZeroDivisionError:
            return 0
    
    @property
    def weighted_average_price(self) -> float:
        """
        Returns the weighted average price of the portfolio.
        """
        total_asset_balance = self.total_asset_balance

        try:
            return sum(asset.price * (asset.balance / total_asset_balance) for asset in self.assets)
        except ZeroDivisionError:
            return 0
        
    @property
    def weighted_average_life(self) -> float:
        """
        Returns the weighted average life of the portfolio from the report date.
        """
        total_asset_balance = self.total_asset_balance
        
        try:
            return sum(pyxirr.year_fraction(self.report_date, asset.maturity, DayCount.ACT_360) * (asset.balance / total_asset_balance) for asset in self.assets)
        except ZeroDivisionError:
            return 0
    
    @property
    def market_value(self) -> float:
        """
        Returns the clean market value of the portfolio of assets, where clean means that
        an asset's accrued and paid interest are not included in the sum.
        """
        return sum((asset.price * asset.balance) + asset.principal_paid for asset in self.assets)
    
    @property
    def market_value_90(self) -> float:
        """
        Returns the market value of the portfolio of assets, where the price is 1.00 for
        assets with a price greater than or equal to 0.9, and the price is unchanged for
        assets with a price less than 0.9.
        """
        return sum((1.0 if asset.price >= 0.9 else asset.price) * asset.balance for asset in self.assets)

    @property
    def dirty_market_value(self) -> float:
        """
        Returns the dirty market value of the portfolio of assets, where dirty means that an
        asset's accrued and paid interest are included in the sum.
        """
        return sum((asset.price * asset.balance) + asset.principal_paid + asset.interest_paid + asset.interest_accrued for asset in self.assets)
    
    @property
    def cpr_lockout_end_date(self) -> date:
        """
        Returns the date on which the CPR lockout ends.
        """
        return self.assets[0].cpr_lockout_end_date
    
    @property
    def cdr_lockout_end_date(self) -> date: 
        """
        Returns the date on which the CDR lockout ends.
        """
        return self.assets[0].cdr_lockout_end_date

    def sweep(self, destination: Account, sweepFunc: str) -> float:
        """
        Sweeps funds using the specified sweep function into the destination account.
        
        :param destination: an Account to credit with the swept funds.
        :param sweepFunc: the name of the sweep function to call on each asset.
        :return: the total amount of monies swept.
        """    
        return sum(getattr(asset, sweepFunc)(destination) for asset in self.assets)
    
    def sweep_interest(self, destination: Account) -> float:
        """
        Sweeps all the available interest in the portfolio into the account.
        
        :param destination: an Account to credit with the swept interest.
        :return: the total amount of interest swept.
        """
        return self.sweep(destination, 'sweep_interest')
    
    def sweep_principal(self, destination: Account) -> float:
        """
        Sweeps all the available principal in the portfolio into the account.
        
        :param destination: an Account to credit with the swept principal.
        :return: the total amount of principal swept.
        """
        return self.sweep(destination, 'sweep_principal')
    
    def add_asset(self, asset: Asset):
        """
        Adds the asset to this portfolio.
        
        :param asset: an asset to add to this portfolio.
        """
        self.assets.append(asset)