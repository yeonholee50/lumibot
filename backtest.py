from datetime import datetime, timedelta
from lumibot.backtesting import YahooDataBacktesting
from lumibot.strategies import Strategy

class MomentumAndMeanReversion(Strategy):
    def initialize(self, symbols=None):
        self.period = 20  # period in minutes
        self.symbols = symbols or [
            "AAPL", "MSFT", "GOOGL", "META", "TSLA", "NVDA", "NFLX"
        ]
        self.stop_loss_pct = 0.1
        self.take_profit_pct = 0.2
        self.mean_reversion_threshold = 0.05
        self.decay_factor = 0.01  # Adjust this value based on your strategy
        self.portfolio_allocation = 0.5

    def on_trading_iteration(self):
        momentums = self.get_assets_momentums()
        mean_reversions = self.get_assets_mean_reversions()

        combined_scores = self.combine_momentum_mean_reversion(momentums, mean_reversions)

        combined_scores.sort(key=lambda x: x["score"], reverse=True)
        best_asset_data = combined_scores[0]
        best_asset = best_asset_data["symbol"]
        best_asset_score = best_asset_data["score"]
        best_asset_price = best_asset_data["price"]

        self.log_message(f"Best asset based on combined score: {best_asset} with score: {best_asset_score:.2f}")

        order_quantity = self.calculate_order_quantity(best_asset_price, best_asset_score)

        if self.portfolio_value >= best_asset_price * order_quantity:
            order = self.create_order(best_asset, order_quantity, "buy")
            self.submit_order(order)
            self.set_stop_loss_take_profit(best_asset, self.stop_loss_pct, self.take_profit_pct)

    def calculate_order_quantity(self, price, score):
        base_quantity = int(self.portfolio_value * self.portfolio_allocation // price)
        decay_adjustment = 1 - self.decay_factor * score
        adjusted_quantity = int(base_quantity * decay_adjustment)
        return max(adjusted_quantity, 1)  # Ensure at least 1 share is bought

    def combine_momentum_mean_reversion(self, momentums, mean_reversions):
        combined_scores = []
        for momentum in momentums:
            for mean_reversion in mean_reversions:
                if momentum["symbol"] == mean_reversion["symbol"]:
                    combined_score = (momentum["return"] + mean_reversion["return"]) / 2
                    combined_scores.append({
                        "symbol": momentum["symbol"],
                        "price": momentum["price"],
                        "score": combined_score
                    })
                    break
        return combined_scores

    def get_assets_momentums(self):
        momentums = []
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=self.period)
        data = self.get_bars(self.symbols, start=start_time, end=end_time, timestep="minute")
        for asset, bars_set in data.items():
            symbol = asset.symbol
            symbol_momentum = bars_set.get_momentum(start=start_time, end=end_time)
            self.log_message(f"{symbol} has a momentum return value of {100 * symbol_momentum:.2f}% over the last {self.period} minutes.")

            momentums.append({"symbol": symbol, "price": bars_set.get_last_price(), "return": symbol_momentum})

        return momentums

    def get_assets_mean_reversions(self):
        mean_reversions = []
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=self.period)
        data = self.get_bars(self.symbols, start=start_time, end=end_time, timestep="minute")
        for asset, bars_set in data.items():
            symbol = asset.symbol
            symbol_return = bars_set.get_momentum(start=start_time, end=end_time)
            self.log_message(f"{symbol} has a mean reversion return value of {100 * symbol_return:.2f}% over the last {self.period} minutes.")

            mean_reversions.append({"symbol": symbol, "price": bars_set.get_last_price(), "return": symbol_return})

        return mean_reversions

    def set_stop_loss_take_profit(self, symbol, stop_loss_pct, take_profit_pct):
        current_price = self.get_last_price(symbol)
        stop_loss_price = current_price * (1 - stop_loss_pct)
        take_profit_price = current_price * (1 + take_profit_pct)
        self.create_order(symbol, self.portfolio_allocation, "sell", stop_price=stop_loss_price, take_profit_price=take_profit_price)

if __name__ == "__main__":
    is_live = False

    if is_live:
        from credentials import ALPACA_CONFIG
        from lumibot.brokers import Alpaca
        from lumibot.traders import Trader

        trader = Trader()
        broker = Alpaca(ALPACA_CONFIG)
        strategy = MomentumAndMeanReversion(broker=broker)
        trader.add_strategy(strategy)
        trader.run_all()
    else:
        from lumibot.backtesting import YahooDataBacktesting

        backtesting_start = datetime(2013, 1, 1)
        backtesting_end = datetime(2023, 1, 1)

        results = MomentumAndMeanReversion.backtest(
            YahooDataBacktesting,
            backtesting_start,
            backtesting_end,
            benchmark_asset="SPY",
        )
