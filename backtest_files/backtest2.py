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

        

    def on_trading_iteration(self):
        for symbol in self.symbols:
            if self.get_cash() > 0:
                """
                we can buy. we decide whether to buy or sell
                """
                recent_price = self.get_last_price(asset=symbol)
                bars = self.get_historical_prices(asset=symbol, length=4, timestep="day")
                df = bars.df
                last_ohlc = df.iloc[-1]
                
                if recent_price < last_ohlc['close']:
                    self.log_message(f"Buying {symbol}")
                    order = self.create_order(symbol, 1, "buy")
                    self.submit_order(order)
                elif self.get_position(symbol) == None or self.get_position(symbol).quantity > 1:
                    self.log_message(f"Selling{symbol}")
                    order = self.create_order(symbol, 0.1, "sell")
                    self.submit_order(order)
            

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
        