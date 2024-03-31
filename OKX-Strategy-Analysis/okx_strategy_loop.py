# %%
from vectorbtpro import *
import pandas as pd
import numpy as np
import os

vbt.settings.set_theme("dark")
vbt.settings.plotting["layout"]["width"] = 800
vbt.settings.plotting["layout"]["height"] = 200
vbt.settings.plotting.use_resampler = (
    True  # Need to pip install https://github.com/predict-idlab/plotly-resampler
)

SAVE_FOLDER = "OKX-Strategy-Analysis/results"
DATA_FILE = "OKX-Strategy-Analysis/price_data.pkl"
main_symbols = ["BTCUSDT", "ETHUSDT"]
# If you don't already have the data use get_data.py
data = vbt.Data.load(DATA_FILE)

######################## Custom Metrics ########################
## Usage
# Example of how to create a custom metric
# https://vectorbt.dev/api/portfolio/base/#custom-metrics

# 1. Define a function that calculates the custom metric
# 2. Create a tuple with the metric name and a dictionary containing the title and the calculation function
# 3. Add the tuple to the custom_metrics_dict
# 4. Add the metric name to the desired_order list to reorder the metrics
# 5. Run the code

# Now call the stats method with the ordered metrics
# pf.stats(metrics=ordered_metrics)

def calc_capital_weighted_time_in_market(portfolio):
    portfolio_trades = portfolio.trades.records_readable
    # Calculate trade duration and convert to seconds
    trade_duration_seconds = (portfolio_trades['Exit Index'] - portfolio_trades['Entry Index']).dt.total_seconds()
    capital_invested = portfolio_trades.Size * portfolio_trades['Avg Entry Price']
    weighted_time = (trade_duration_seconds * capital_invested).sum()
    # Calculate total time in seconds
    total_time_seconds = (portfolio.wrapper.index[-1] - portfolio.wrapper.index[0]).total_seconds()
    capital_weighted_time_pct = (weighted_time / (total_time_seconds * portfolio.value.mean())) * 100
    return capital_weighted_time_pct


# Define your custom metrics
max_winning_streak = (
    'max_winning_streak',
    dict(
        title='Max Winning Streak',
        calc_func='trades.winning_streak.max'
    )
)

max_losing_streak = (
    'max_losing_streak',
    dict(
        title='Max Losing Streak',
        calc_func='trades.losing_streak.max'
    )
)

capital_weighted_time_exposure = (
    'capital_weighted_time_exposure',
    dict(
        title='Capital Weighted Time Exposure [%]',
        calc_func=lambda self, group_by:
        calc_capital_weighted_time_in_market(self)
    )
)

custom_metrics_dict = {
    'max_winning_streak': max_winning_streak,
    'max_losing_streak': max_losing_streak,
    'capital_weighted_time_exposure': capital_weighted_time_exposure
}

# Retrieve the default metrics and convert them to a dictionary
default_metrics_dict = dict(vbt.Portfolio.metrics)


# Reorder metrics according to desired_order
desired_order = [
    'start', 'end', 'period', 'start_value', 'min_value', 'max_value', 
    'end_value', 'cash_deposits', 'cash_earnings', 'total_return', 
    'bm_return', 'total_time_exposure', 'capital_weighted_time_exposure', 
    'max_gross_exposure', 'max_dd', 'max_dd_duration', 'total_orders', 
    'total_fees_paid', 'total_trades', 'win_rate', 'max_winning_streak', 
    'max_losing_streak', 'best_trade', 'worst_trade', 'avg_winning_trade', 
    'avg_losing_trade', 'avg_winning_trade_duration', 'avg_losing_trade_duration', 
    'profit_factor', 'expectancy', 'sharpe_ratio', 'calmar_ratio', 
    'omega_ratio', 'sortino_ratio'
]

# Reorder metrics according to desired_order
ordered_metrics = []
for metric_name in desired_order:
    if metric_name in custom_metrics_dict:
        # Add custom metric
        ordered_metrics.append(custom_metrics_dict[metric_name])
    elif metric_name in default_metrics_dict:
        # Add default metric
        ordered_metrics.append(metric_name)
    else:
        print(f"Warning: Metric '{metric_name}' not found.")

######################## End Custom Metrics ########################



# %%
# Get this from the shared drive
folder = "/Users/ericervin/Library/CloudStorage/GoogleDrive-eervin@blockforcecapital.com/Shared drives/AI/data/Copy Trading/Data"

files = os.listdir(folder)
files = [f for f in files if f.endswith(".csv")]

master_results = pd.DataFrame()
for file in files:
    filename = f"{folder}/{file}"
    # Choose a symbol to analyze
    abreviated_filename = filename.split("/")[-1].split(".")[0]
    results = pd.DataFrame()

    trades = pd.read_csv(filename)
    # Drop rows where closed_date is '--' currently open trades
    print(f'Processing {abreviated_filename}')
    # Check to see if the file has any data
    if trades.empty:
        print(f"No data for {abreviated_filename}")
        continue
    trades = trades[trades["closed_date"] != "--"]
    trades["open_date"] = pd.to_datetime(trades["open_date"], errors="coerce")
    trades["close_date"] = pd.to_datetime(trades["closed_date"], errors="coerce")
    min_date = trades.open_date.min().floor("D")
    max_date = trades.close_date.max().ceil("D")

    trades["symbol"] = trades["title"].str.extract(r"(\w+)")
    # Change USDT to -USDT
    trades["okx_symbol"] = trades["symbol"].str.replace("USDT", "-USDT")
    trades["trade_type"] = trades["leverage"].apply(
        lambda x: (
            "open_long"
            if "Long" in x
            else (
                "close_long"
                if "Long" in x
                else "open_short" if "Short" in x else "close_short"
            )
        )
    )
    trades = trades.drop(columns=["Unnamed: 0"])

    # Function to clean and convert currency columns
    def clean_currency_column(column):
        # Convert the column to string type first
        column = column.astype(str)
        return pd.to_numeric(
            column.str.replace(",", "").str.replace(" USDT", ""), errors="coerce"
        )

    # Clean the currency columns
    trades["entry_price"] = clean_currency_column(trades["entry_price"])
    trades["pnl"] = clean_currency_column(trades["pnl"])
    trades["fill_price"] = clean_currency_column(trades["fill_price"])

    # Extracting the number of contracts
    trades["num_contracts"] = (
        trades["closed"]
        .str.extract("(\d+,?\d*)")
        .replace(",", "", regex=True)
        .astype(int)
    )

    # Get a list of all unique symbols
    symbols = trades["symbol"].unique()
    okx_symbols = trades["okx_symbol"].unique()
    # Look up the contract multiplier for each symbol from the exchange website https://www.okx.com/trade-market/info/swap
    symbols_dict_contract_multiplier = {
        "ETH-USDT": 0.1,
        "BTC-USDT": 0.01,
        "PEOPLE-USDT": 100,
        "ORDI-USDT": 0.1,
        "SOL-USDT": 1,
        "DOGE-USDT": 1000,
        "USTC-USDT": 100,
        "BNB-USDT": 0.01,
    }
    trades["contract_multiplier"] = trades["okx_symbol"].map(
        symbols_dict_contract_multiplier
    )
    trades["quantity"] = trades["num_contracts"] * trades["contract_multiplier"]

    # Now separate out the orders into open and closing orders and sort by date
    # Open Orders
    open_orders = trades[
        [
            "open_date",
            "title",
            "direction",
            "leverage",
            "entry_price",
            "symbol",
            "okx_symbol",
            "num_contracts",
            "quantity",
        ]
    ].copy()
    open_orders.rename(columns={"open_date": "date"}, inplace=True)
    open_orders["price"] = open_orders["entry_price"]
    open_orders["trade_type"] = open_orders["leverage"].apply(
        lambda x: "open_long" if "Long" in x else "open_short"
    )

    # Closing Orders
    closing_orders = trades[
        [
            "closed_date",
            "title",
            "direction",
            "leverage",
            "fill_price",
            "pnl",
            "pnl_percent",
            "symbol",
            "okx_symbol",
            "num_contracts",
            "quantity",
        ]
    ].copy()
    closing_orders.rename(
        columns={"closed_date": "date", "fill_price": "close_price"}, inplace=True
    )
    closing_orders["price"] = closing_orders["close_price"]
    closing_orders["trade_type"] = closing_orders["leverage"].apply(
        lambda x: "close_long" if "Long" in x else "close_short"
    )

    # Combine the two dataframes
    orders = pd.concat([open_orders, closing_orders])
    # Convert date columns to datetime for sorting
    orders["date"] = pd.to_datetime(orders["date"], errors="coerce")

    # Sorting by date
    orders = orders.sort_values(by="date")
    orders.set_index("date", inplace=True)
    # Localize the index to Central Standard Time (CST) first
    orders.index = orders.index.tz_localize("America/Chicago")
    # Then convert the timezone from CST to UTC
    orders.index = orders.index.tz_convert("UTC")

    # Revised approach to handle duplicate timestamps by adding milliseconds
    def add_milliseconds_to_duplicates(df):
        # Create a new Series to hold adjusted timestamps
        adjusted_timestamps = []

        # Create a dictionary to track the count of each timestamp
        timestamp_count = {}

        # Iterate through each timestamp in the index
        for timestamp in df.index:
            # If the timestamp is not in the dictionary, add it with a count of 0
            if timestamp not in timestamp_count:
                timestamp_count[timestamp] = 0
                adjusted_timestamps.append(timestamp)
            else:
                # If the timestamp is already in the dictionary, increment the count
                timestamp_count[timestamp] += 1
                # Add milliseconds to the timestamp based on its count
                new_timestamp = timestamp + pd.Timedelta(
                    milliseconds=timestamp_count[timestamp]
                )
                adjusted_timestamps.append(new_timestamp)

        return pd.Series(adjusted_timestamps, index=df.index)

    # Apply the function to adjust the index
    adjusted_index = add_milliseconds_to_duplicates(orders)
    orders.index = adjusted_index
    orders = orders.sort_index()
    # If open-short and close-long then quantity should be negative else positive
    orders["trade_direction"] = orders.apply(
        lambda x: (
            -1
            if (x["trade_type"] == "open_short" or x["trade_type"] == "close_long")
            else 1
        ),
        axis=1,
    )
    orders["trade_quantity"] = orders["trade_direction"] * orders["quantity"]

    for symbol in main_symbols:
        if symbol not in trades.symbol.unique():
            print(f"No data for {abreviated_filename} for {symbol}")
            temp_results_created = False
            continue
        else:
            # print(f'Processing {abreviated_filename} for {symbol}')
            symbol_data = data["Close"].get(symbol=symbol)
            symbol_orders = orders[orders["symbol"] == symbol]

            # Identify duplicates in the index
            symbol_orders.index[symbol_orders.index.duplicated()]
            # Throw an error if there are duplicates
            if symbol_orders.index.duplicated().any():
                raise ValueError("Duplicate timestamps found in the orders dataframe")

            # Change Floor and Ceiling based on your preference to zoom in or out. This is just rounding the date to the nearest hour/day/etc.
            min_date = symbol_orders.index.min().floor("D")
            max_date = symbol_orders.index.max().ceil("D")
            # print(f"Minimum date: {min_date}")
            # print(f"Maximum date: {max_date}")

            unlevered_pf = vbt.Portfolio.from_orders(
                close=symbol_data.loc[
                    min_date:max_date
                ],  # Note, here we are using the minutely data for ETH
                size=symbol_orders["trade_quantity"],
                price=symbol_orders["price"],
                size_type="amount",
                # fixed_fees = trades['fees'],
                init_cash="auto",  # 40000,
                # leverage=10,
                leverage_mode=vbt.pf_enums.LeverageMode.Eager,
                freq="15T",
            )
            # print(f'Unlevered Portfolio Sim Sharpe Ratio for {abreviated_filename} for {symbol}: {unlevered_pf.sharpe_ratio}')
            init_cash = unlevered_pf.init_cash
            leverage = 3
            pf = vbt.Portfolio.from_orders(
                close=symbol_data.loc[
                    min_date:max_date
                ],  # Note, here we are using the minutely data for ETH
                size=symbol_orders["trade_quantity"],
                price=symbol_orders["price"],
                size_type="amount",
                # fixed_fees = trades['fees'],
                init_cash=init_cash / leverage,
                leverage=leverage,
                leverage_mode=vbt.pf_enums.LeverageMode.Eager,
                freq="15T",
            )
            # print(type(pf.stats()))
            pf.save(f"{SAVE_FOLDER}/{abreviated_filename}_{symbol}_pf.pkl")
            unlevered_pf.save(f"{SAVE_FOLDER}/{abreviated_filename}_{symbol}_unlevered_pf.pkl") 
            
            # Leveraged portfolio stats
            temp_results = pd.DataFrame([pf.stats(metrics=ordered_metrics)])
            temp_results["file_symbol"] = f"{abreviated_filename}_{symbol}"
            temp_results["symbol"] = symbol
            master_results = pd.concat([master_results, temp_results])

            # Unlevered portfolio stats
            temp_unlevered_results = pd.DataFrame([unlevered_pf.stats(metrics=ordered_metrics)])
            temp_unlevered_results["file_symbol"] = f"{abreviated_filename}_{symbol}_unlevered"
            temp_unlevered_results["symbol"] = f"{symbol}"
            master_results = pd.concat([master_results, temp_unlevered_results])


# Save to CSV
master_results.set_index("file_symbol", inplace=True)
master_results.to_csv(f"{SAVE_FOLDER}/master_stats.csv")

