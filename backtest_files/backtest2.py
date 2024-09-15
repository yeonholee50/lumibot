from datetime import datetime
from lumibot.backtesting import YahooDataBacktesting
from lumibot.strategies import Strategy

class MomentumAndMeanReversion(Strategy):
    def initialize(self, symbols=None):
        self.period = 2
        self.counter = 0
        self.sleeptime = 0

        if symbols:
            self.symbols = symbols
        else:
            self.symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NFLX"]

        self.momentum_asset = ""
        self.mean_reversion_asset = ""
        self.momentum_quantity = 0
        self.mean_reversion_quantity = 0
        self.mean_reversion_threshold = 0.1

        # Moving average parameters for market trend detection
        self.short_window = 50
        self.long_window = 200

    def on_trading_iteration(self):
        if self.counter == self.period or self.counter == 0:
            self.counter = 0
            momentums = self.get_assets_momentums()
            mean_reversions = self.get_assets_mean_reversions()
            market_trend = self.get_market_trend()

            momentums.sort(key=lambda x: x.get("return"))
            best_momentum_asset_data = momentums[-1]
            best_momentum_asset = best_momentum_asset_data["symbol"]
            best_momentum_asset_return = best_momentum_asset_data["return"]

            mean_reversions.sort(key=lambda x: x.get("return"))
            best_mean_reversion_asset_data = mean_reversions[0]
            best_mean_reversion_asset = best_mean_reversion_asset_data["symbol"]
            best_mean_reversion_asset_return = best_mean_reversion_asset_data["return"]

            # Adjust trade size based on market trend
            if market_trend == "bear":
                momentum_quantity_factor = 0.7
                mean_reversion_quantity_factor = 0.7
            else:
                momentum_quantity_factor = 0.3
                mean_reversion_quantity_factor = 0.3

            if best_momentum_asset != self.momentum_asset:
                if self.momentum_asset:
                    self.log_message(f"Swapping {self.momentum_asset} for {best_momentum_asset} (Momentum)")
                    if self.get_cash() > 0:
                        order = self.create_order(self.momentum_asset, self.momentum_quantity, "sell")
                        self.submit_order(order)

                self.momentum_asset = best_momentum_asset
                best_momentum_asset_price = best_momentum_asset_data["price"]
                self.momentum_quantity = min(int(self.get_cash() * momentum_quantity_factor // best_momentum_asset_price), self.get_max_order_quantity())
                if self.momentum_quantity > 0:
                    order = self.create_order(self.momentum_asset, self.momentum_quantity, "buy")
                    self.submit_order(order)
            else:
                self.log_message(f"Keeping {self.momentum_quantity} shares of {self.momentum_asset} (Momentum)")

            if abs(best_mean_reversion_asset_return) > self.mean_reversion_threshold:
                if best_mean_reversion_asset != self.mean_reversion_asset:
                    if self.mean_reversion_asset:
                        self.log_message(f"Swapping {self.mean_reversion_asset} for {best_mean_reversion_asset} (Mean-Reversion)")
                        if self.get_cash() > 0:
                            order = self.create_order(self.mean_reversion_asset, self.mean_reversion_quantity, "sell")
                            self.submit_order(order)

                    self.mean_reversion_asset = best_mean_reversion_asset
                    best_mean_reversion_asset_price = best_mean_reversion_asset_data["price"]
                    self.mean_reversion_quantity = min(int(self.get_cash() * mean_reversion_quantity_factor // best_mean_reversion_asset_price), self.get_max_order_quantity())
                    if self.mean_reversion_quantity > 0:
                        order = self.create_order(self.mean_reversion_asset, self.mean_reversion_quantity, "buy")
                        self.submit_order(order)
                else:
                    self.log_message(f"Keeping {self.mean_reversion_quantity} shares of {self.mean_reversion_asset} (Mean-Reversion)")

        self.counter += 1
        self.await_market_to_close()

    def on_abrupt_closing(self):
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

    def get_market_trend(self):
        data = self.get_bars(self.symbols, max(self.long_window, self.short_window) + 1, timestep="day")
        market_trend = "neutral"
        
        # Calculate moving averages for trend detection
        for asset, bars_set in data.items():
            try:
                symbol = asset.symbol
                short_moving_avg = bars_set.get_moving_average(self.short_window)
                long_moving_avg = bars_set.get_moving_average(self.long_window)
                
                if short_moving_avg > long_moving_avg:
                    market_trend = "bull"
                elif short_moving_avg < long_moving_avg:
                    market_trend = "bear"
                
                self.log_message(f"{symbol}: Short MA ({self.short_window} days) = {short_moving_avg}, Long MA ({self.long_window} days) = {long_moving_avg}, Market Trend = {market_trend}")
                
            except Exception as e:
                self.log_message(f"Error processing {asset.symbol} for market trend: {str(e)}")
                
        return market_trend

    def get_max_order_quantity(self):
        # Return a reasonable order quantity based on available cash and other factors
        return 1000

    def get_cash(self):
        # Fetch available cash in the portfolio
        return self.portfolio_value * 0.2  # Example: 20% of the portfolio value

    def get_assets_momentums(self):
        momentums = []
        start_date = self.get_round_day(timeshift=self.period + 1)
        end_date = self.get_round_day(timeshift=1)
        data = self.get_bars(self.symbols, self.period + 2, timestep="day")
        for asset, bars_set in data.items():
            try:
                symbol = asset.symbol
                symbol_momentum = bars_set.get_momentum(start=start_date, end=end_date)
                self.log_message(f"{symbol} has a return value of {100 * symbol_momentum:.2f}% over the last {self.period} day(s).")
                momentums.append({"symbol": symbol, "price": bars_set.get_last_price(), "return": symbol_momentum})
            except Exception as e:
                self.log_message(f"Error processing {asset.symbol}: {str(e)}")
        return momentums

    def get_assets_mean_reversions(self):
        mean_reversions = []
        start_date = self.get_round_day(timeshift=self.period + 1)
        end_date = self.get_round_day(timeshift=1)
        data = self.get_bars(self.symbols, self.period + 2, timestep="day")
        for asset, bars_set in data.items():
            try:
                symbol = asset.symbol
                symbol_return = bars_set.get_momentum(start=start_date, end=end_date)
                self.log_message(f"{symbol} has a return value of {100 * symbol_return:.2f}% over the last {self.period} day(s) (Mean-Reversion).")
                mean_reversions.append({"symbol": symbol, "price": bars_set.get_last_price(), "return": symbol_return})
            except Exception as e:
                self.log_message(f"Error processing {asset.symbol}: {str(e)}")
        return mean_reversions

if __name__ == "__main__":
    is_live = False

    if is_live:
        from backtest_files.credentials import ALPACA_CONFIG
        from lumibot.brokers import Alpaca
        from lumibot.traders import Trader

        trader = Trader()

        broker = Alpaca(ALPACA_CONFIG)
        strategy = MomentumAndMeanReversion(broker=broker)
        trader.add_strategy(strategy)
        strategy_executors = trader.run_all()

    else:
        from lumibot.backtesting import YahooDataBacktesting

        backtesting_start = datetime(2013, 1, 1)
        backtesting_end = datetime(2023, 7, 1)

        results = MomentumAndMeanReversion.backtest(
            YahooDataBacktesting,
            backtesting_start,
            backtesting_end,
            benchmark_asset="SPY",
            budget=10000)
        