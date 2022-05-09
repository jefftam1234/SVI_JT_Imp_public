import os
import numpy as np
import pandas as pd
import requests
import datetime
import json

uri = 'https://www.deribit.com/api/v2/public/'
credentials_fname = 'credentials.json'
spec_fname = 'input_call_sept_24.json'


def authenticate(fname):
    """
        API authentication with credentials stored in fname (.json)
    """
    with open(fname, 'r') as f:
        credentials = json.loads(f.read())

    _ = requests.get(
        'https://www.deribit.com/api/v2/public/auth',
        {"grant_type": "client_credentials", **credentials}
    )


def get_option_specification(filename):
    """
    Returns the option specification given in 'input.json' as a dictionary.

    Arguments:
        filename (str): Name of .json file containing the option specification

    The following keys need to be present in the .json file:
        currency (string): Cryptocurrency, official three-letter abbreviation
        maturity (string): Maturity date of option in the format DD/MM/YYYY
        type (string): Indicator for option type, either 'put' or 'call'
        strike (number): Option strike price
    """
    # read file
    with open(filename, 'r') as f:
        specification = json.loads(f.read())
    print('Option specification: {}'.format(specification))

    # perform basic checks
    assert specification['currency'] in ['BTC', 'ETH']
    assert datetime.datetime.strptime(specification['maturity'], "%d/%m/%Y")
    assert specification['type'] in ['call', 'put']
    assert type(specification['strike']) in [int, float]

    return specification


def call_api(uri, method, params):
    """
    Returns the result JSON of a GET request's response as a dictionary

    Arguments:
        uri (str): Endpoint for the API call
        method (str): Deribit method name
        params (dict): Parameters for the API call
    """
    return requests.get(uri + method, params).json()['result']


def filter_options(option_type, options, spot):
    """
    Remove call options with downside strikes / put options with upside strikes

    Arguments:
        option_type (str): Indicator for option type, either 'put' or 'call'
        options (list of dict): List of dictionaries with information on options
        spot (float): Current price of underlying currency
    """
    # if option_type == 'call':
    #     return list(filter(lambda i: i['strike'] > spot, options))
    # else:
    #     return list(filter(lambda i: i['strike'] < spot, options))


def filter_all_options(options, spot):
    # call_list = list(filter(lambda i: i['strike'] > spot and i['option_type'] == 'call', options))
    # put_list = list(filter(lambda i: i['strike'] < spot and i['option_type'] == 'put', options))
    call_list = list(filter(lambda i: i['option_type'] == 'call', options))
    put_list = list(filter(lambda i: i['option_type'] == 'put', options))
    return put_list + call_list


def get_currency_price(uri, currency):
    """
    Returns the price of the chosen currency

    Arguments:
        uri (str): Endpoint for the API call
        currency (string): Cryptocurrency, official three-letter abbreviation
    """
    # make API call
    index_name = '{}_usd'.format(currency.lower())
    result = call_api(uri, 'get_index_price', {'index_name': index_name})

    # extract currency price
    currency_price = result['index_price']
    print('Current {} price: ${}'.format(currency, currency_price))

    return currency_price


def get_future_data(uri, currency):
    print('Fetching data for all {} futures'.format(currency))

    instr_args = {'currency': currency, 'kind': 'future', 'expired': 'false'}
    futures = call_api(uri, 'get_instruments', instr_args)

    # extract maturities
    maturities = list(map(lambda i: i['expiration_timestamp'], futures))
    instrument_names = list(map(lambda i: i['instrument_name'], futures))
    mark_price = []
    index_price = []
    last_price = []
    for name in instrument_names:
        result = call_api(uri, 'get_order_book', {'instrument_name': name})
        last_price.append(result['last_price'])
        index_price.append(result['index_price'])
        mark_price.append(result['mark_price'])
    future_data = {
        'instrument_names': instrument_names,
        'maturities': maturities,
        'mark_price': mark_price,
        'index_price': index_price,
        'last_price': last_price
    }
    return future_data


def get_implied_volatilities(options, uri):
    """
    Returns implied volatilities for a list of options

    Arguments:
        options (list of dict): List of dictionaries with information on options
        uri (str): Endpoint for the API calls
    """
    # extract the instrument names
    instrument_names = list(map(lambda i: i['instrument_name'], options))

    # map the instrument name to the marked implied volatility
    iv_mapper = lambda i: call_api(uri, 'get_order_book', {'instrument_name': i})['mark_iv']
    implied_volatilities = list(map(iv_mapper, instrument_names))

    # convert percentage to fraction values
    implied_volatilities = np.array(implied_volatilities) / 100

    return implied_volatilities


def get_options_data(uri, currency, option_type, spot):
    """
    Returns strike, maturity and IV data for available options

    Arguments:
        uri (str): Endpoint for the API calls
        currency (string): Cryptocurrency, official three-letter abbreviation
        option_type (str): Indicator for option type, either 'put' or 'call'
        spot (float): Current index (currency) price
    """
    print('Fetching data for all {} {} options'.format(currency, option_type))
    # get list of active options on selected currency
    instr_args = {'currency': currency, 'kind': 'option', 'expired': 'false'}
    options = call_api(uri, 'get_instruments', instr_args)

    # remove options not of specified type
    # options = list(filter(lambda i: i['option_type'] == option_type, options))

    # sort by expiration
    options = sorted(options, key=lambda i: i['expiration_timestamp'])

    # remove options with downside strikes (calls) resp. upside strikes (puts)
    # options = filter_options(option_type=option_type, options=options, spot=spot)
    options = filter_all_options(options=options, spot=spot)

    # extract option type
    opt_types = list(map(lambda i: i['option_type'], options))

    # extract strikes
    strikes = np.array(list(map(lambda i: i['strike'], options)))

    # extract maturities
    maturities = list(map(lambda i: i['expiration_timestamp'], options))

    # convert maturities from unix miliseconds to seconds
    maturities = np.array(maturities) / 1000

    # get implied volatilities
    implied_volatilities = get_implied_volatilities(options=options, uri=uri)

    # compile extracted data to dictionary
    options_data = {
        'type': opt_types,
        'strikes': strikes,
        'maturities': maturities,
        'implied_volatilities': implied_volatilities
    }

    # print ranges of strikes, maturities and IVs
    print('Strikes are in range [{}, {}]'.format(min(strikes), max(strikes)))
    maturity_dates = list(map(datetime.datetime.fromtimestamp, maturities))
    print('Maturities are in range [{}, {}]'.format(
        min(maturity_dates).strftime('%d/%m/%Y'),
        max(maturity_dates).strftime('%d/%m/%Y')
    ))
    print('IVs are in range [{}, {}]'.format(
        min(implied_volatilities),
        max(implied_volatilities))
    )

    return options_data


def get_deribit_data():
    snap_dt_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")  # local time
    # authenticate with credentials
    authenticate(credentials_fname)
    # get option specification
    specification = get_option_specification(filename=spec_fname)

    # get currency price
    currency_price = get_currency_price(uri, specification['currency'])

    # get future prices
    future_price = get_future_data(uri=uri,
                                   currency=specification['currency'])
    # get options data
    options_data = get_options_data(
        uri=uri,
        currency=specification['currency'],
        option_type=specification['type'],
        spot=currency_price
    )
    folder_path = f"{snap_dt_str}"
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    futures_df = pd.DataFrame(future_price)
    option_df = pd.DataFrame(options_data)
    utc_t0 = datetime.datetime.utcnow()  # POSIX unit time

    curr_vec = pd.DataFrame(np.full(shape=futures_df.shape[0], fill_value=currency_price))
    utc_t0_vec = pd.DataFrame(np.full(shape=futures_df.shape[0], fill_value=utc_t0))
    aux_pd = pd.concat([curr_vec.rename(columns={0: 'Spot'}), utc_t0_vec.rename(columns={0: 'utc_T0'})], axis=1)
    futures_df = pd.concat([futures_df, aux_pd], axis=1)
    futures_df.to_csv(os.path.join(folder_path, f"Futures.csv"))

    curr_vec = pd.DataFrame(np.full(shape=option_df.shape[0], fill_value=currency_price))
    utc_t0_vec = pd.DataFrame(np.full(shape=option_df.shape[0], fill_value=utc_t0))
    aux_pd = pd.concat([curr_vec.rename(columns={0: 'Spot'}), utc_t0_vec.rename(columns={0: 'utc_T0'})], axis=1)
    option_df = pd.concat([option_df, aux_pd], axis=1)
    option_df.to_csv(os.path.join(folder_path, f"Options.csv"))
    print(f"Finishes fetching and saving Deribit data for local datetime: f{snap_dt_str}")
    ret = {'dateTime': snap_dt_str,
           'futures': futures_df,
           'options': option_df}
    return ret
