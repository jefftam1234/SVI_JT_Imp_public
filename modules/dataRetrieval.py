import json

import pandas as pd

from modules.DeribitAPI.deribit_interface import get_deribit_data
from modules.dataCleaning import clean_up_option_data, compliment_futures_in_options, select_put_call


def retrieve_data_live():
    data = get_deribit_data()
    datetime = data["dateTime"]
    futures = data["futures"]
    options_df = data["options"]
    options_df = clean_up_option_data(options_df)
    (options_df, futures_df) = compliment_futures_in_options(options_df, futures)
    options_df = select_put_call(options_df)
    return datetime, options_df, futures_df


def retrieve_data_source(input_timestamp):
    futures = pd.read_csv(f'{input_timestamp}/Futures.csv')
    options_df = pd.read_csv(f'{input_timestamp}/Options.csv')
    options_df = clean_up_option_data(options_df)
    (options_df, futures_df) = compliment_futures_in_options(options_df, futures)
    options_df = select_put_call(options_df)
    return options_df, futures_df


def retrieve_initial_svi_param_dict(timestamp):
    with open(f'{timestamp}/svi_param_initial.json', 'r') as f:
        svi_param_initial = json.load(f)
    return svi_param_initial
