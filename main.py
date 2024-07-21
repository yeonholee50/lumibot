from lumibot.brokers import Alpaca
from lumibot.strategies.strategy import Strategy
from lumibot.traders import Trader
from credentials import ALPACA_CONFIG
from flask import Flask
import os

app = Flask(__name__)
@app.route('/')
class MyStrategy(Strategy):
    def initialize(self, symbols=None):
        # Setting the waiting period (in days) for both strategies
        self.period = 2

        # The counter for the number of days we have been holding the current asset
        self.counter = 0

        # No need to sleep between iterations as there's only one trading operation per day
        self.sleeptime = 0

        # Set the symbols that we will be monitoring
        if symbols:
            self.symbols = symbols
        else:
            self.symbols = ["AAPL", "MSFT", "GOOGL", "META", "TSLA", "NVDA", "NFLX"]

        # Initialize variables for momentum and mean-reversion strategies
        self.momentum_asset = ""
        self.mean_reversion_asset = ""
        self.momentum_quantity = 0
        self.mean_reversion_quantity = 0
        self.mean_reversion_threshold = 0.03  # Example threshold for mean-reversion

    def on_trading_iteration(self):
        if self.broker.is_market_open() and (self.counter == self.period or self.counter == 0):
            self.counter = 0
            momentums = self.get_assets_momentums()
            mean_reversions = self.get_assets_mean_reversions()

            # Momentum strategy: Get the asset with the highest return in our period
            momentums.sort(key=lambda x: x.get("return"))
            best_momentum_asset_data = momentums[-1]
            best_momentum_asset = best_momentum_asset_data["symbol"]
            best_momentum_asset_return = best_momentum_asset_data["return"]

            # Mean-reversion strategy: Get the asset with the lowest return in our period
            mean_reversions.sort(key=lambda x: x.get("return"))
            best_mean_reversion_asset_data = mean_reversions[0]
            best_mean_reversion_asset = best_mean_reversion_asset_data["symbol"]
            best_mean_reversion_asset_return = best_mean_reversion_asset_data["return"]

            available_cash = self.broker._get_balances_at_broker(None)[0]
            

            # Momentum strategy: Check if we need to swap the asset
            if best_momentum_asset != self.momentum_asset:
                if self.momentum_asset:
                    self.log_message(f"Swapping {self.momentum_asset} for {best_momentum_asset} (Momentum)")
                    order = self.create_order(self.momentum_asset, self.momentum_quantity, "sell")
                    self.submit_order(order)

                best_momentum_asset_price = best_momentum_asset_data["price"]
                self.momentum_quantity = int(self.portfolio_value * 0.5 // best_momentum_asset_price)

                if available_cash > 0 and available_cash >= best_momentum_asset_price * self.momentum_quantity:
                    self.momentum_asset = best_momentum_asset
                    order = self.create_order(self.momentum_asset, self.momentum_quantity, "buy")
                    self.submit_order(order)
                else:
                    self.log_message(f"Not enough cash to buy {self.momentum_quantity} shares of {best_momentum_asset} (Momentum)")
            else:
                self.log_message(f"Keeping {self.momentum_quantity} shares of {self.momentum_asset} (Momentum)")

            available_cash = self.broker._get_balances_at_broker(None)[0]


            # Mean-reversion strategy: Check if we need to swap the asset
            if abs(best_mean_reversion_asset_return) > self.mean_reversion_threshold:
                if best_mean_reversion_asset != self.mean_reversion_asset:
                    if self.mean_reversion_asset:
                        self.log_message(f"Swapping {self.mean_reversion_asset} for {best_mean_reversion_asset} (Mean-Reversion)")
                        order = self.create_order(self.mean_reversion_asset, self.mean_reversion_quantity, "sell")
                        self.submit_order(order)

                    best_mean_reversion_asset_price = best_mean_reversion_asset_data["price"]
                    self.mean_reversion_quantity = int(self.portfolio_value * 0.5 // best_mean_reversion_asset_price)

                    if available_cash > 0 and available_cash >= best_mean_reversion_asset_price * self.mean_reversion_quantity:
                        self.mean_reversion_asset = best_mean_reversion_asset
                        order = self.create_order(self.mean_reversion_asset, self.mean_reversion_quantity, "buy")
                        self.submit_order(order)
                    else:
                        self.log_message(f"Not enough cash to buy {self.mean_reversion_quantity} shares of {best_mean_reversion_asset} (Mean-Reversion)")
                else:
                    self.log_message(f"Keeping {self.mean_reversion_quantity} shares of {self.mean_reversion_asset} (Mean-Reversion)")

        self.counter += 1
        self.await_market_to_close()

    def on_abrupt_closing(self):
        #self.sell_all()
        return

    def trace_stats(self, context, snapshot_before):
        row = {
            "old_momentum_asset": snapshot_before.get("momentum_asset"),
            "old_mean_reversion_asset": snapshot_before.get("mean_reversion_asset"),
            "old_momentum_quantity": snapshot_before.get("momentum_quantity"),
            "old_mean_reversion_quantity": snapshot_before.get("mean_reversion_quantity"),
            "old_cash": snapshot_before.get("cash"),
            "new_momentum_asset": self.momentum_asset,
            "new_mean_reversion_asset": self.mean_reversion_asset,
            "new_momentum_quantity": self.momentum_quantity,
            "new_mean_reversion_quantity": self.mean_reversion_quantity,
        }

        momentums = context.get("momentums")
        mean_reversions = context.get("mean_reversions")
        if momentums is not None and len(momentums) != 0:
            for item in momentums:
                symbol = item.get("symbol")
                for key in item:
                    if key != "symbol":
                        row[f"{symbol}_momentum_{key}"] = item[key]

        if mean_reversions is not None and len(mean_reversions) != 0:
            for item in mean_reversions:
                symbol = item.get("symbol")
                for key in item:
                    if key != "symbol":
                        row[f"{symbol}_mean_reversion_{key}"] = item[key]

        return row

    def get_assets_momentums(self):
        momentums = []
        start_date = self.get_round_day(timeshift=self.period + 1)
        end_date = self.get_round_day(timeshift=1)
        data = self.get_historical_prices_for_assets(self.symbols, self.period + 2, timestep="day")
        for asset, bars_set in data.items():
            symbol = asset.symbol
            symbol_momentum = bars_set.get_momentum(start=start_date, end=end_date)
            self.log_message(f"{symbol} has a return value of {100 * symbol_momentum:.2f}% over the last {self.period} day(s).")

            momentums.append({"symbol": symbol, "price": bars_set.get_last_price(), "return": symbol_momentum})

        return momentums

    def get_assets_mean_reversions(self):
        mean_reversions = []
        start_date = self.get_round_day(timeshift=self.period + 1)
        end_date = self.get_round_day(timeshift=1)
        data = self.get_historical_prices_for_assets(self.symbols, self.period + 2, timestep="day")
        for asset, bars_set in data.items():
            symbol = asset.symbol
            symbol_return = bars_set.get_momentum(start=start_date, end=end_date)
            self.log_message(f"{symbol} has a return value of {100 * symbol_return:.2f}% over the last {self.period} day(s) (Mean-Reversion).")

            mean_reversions.append({"symbol": symbol, "price": bars_set.get_last_price(), "return": symbol_return})

        return mean_reversions



if __name__ == "__main__":
    is_live = True

    port = int(os.environ.get('PORT', 4000))
    app.run(host='0.0.0.0', port=port)
    if is_live:
        trader = Trader()
        broker = Alpaca(ALPACA_CONFIG)
        strategy = MyStrategy(broker=broker)

        # Run the strategy live
        trader.add_strategy(strategy)
        trader.run_all()
    else:
        from lumibot.backtesting import YahooDataBacktesting
        from datetime import datetime

        backtesting_start = datetime(2013, 1, 1)
        backtesting_end = datetime(2023, 5, 15)

        results = MyStrategy.backtest(
            YahooDataBacktesting,
            backtesting_start,
            backtesting_end,
            benchmark_asset="SPY",
        )