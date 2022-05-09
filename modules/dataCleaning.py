import datetime

import QuantLib as ql
import numpy as np
import pandas as pd


def clean_up_option_data(options_df):
    # Use a flat yield curve for simplicity
    options_df['maturities_dates'] = [datetime.date.fromtimestamp(T) for T in options_df['maturities']]   #maturities are in POSIX
    options_df['qlMaturities'] = [ql.Date(T.day, T.month, T.year) for T in options_df['maturities_dates']]

    t0 = datetime.datetime.utcnow()
    initial_date_vec = pd.DataFrame(np.full(shape=options_df.shape[0], fill_value=t0))
    aux_pd = initial_date_vec.rename(columns={0: 'T0'})
    options_df = pd.concat([options_df, aux_pd], axis =1)
    options_df['T0'] = [datetime.datetime.strptime(str(T), '%Y-%m-%d %H:%M:%S.%f') for T in options_df['T0']]
    options_df['qlT0'] = [ql.Date(T.day, T.month, T.year) for T in options_df['T0']]
    options_df['tau'] = options_df.apply(lambda x: ql.Thirty360().yearFraction(x.qlT0, x.qlMaturities), axis=1)
    #options_df['tau'] = options_df['t']+1/360   # artificially inflated the t-to-maturity due to time-zone difference (need to refine)
    options_df['daysToMaturity'] = options_df.apply(lambda x: ql.Thirty360().dayCount(x.qlT0, x.qlMaturities), axis=1)
    options_df = options_df[['tau', 'T0', 'Spot', 'strikes', 'type', 'maturities_dates', 'daysToMaturity', 'implied_volatilities']]
    options_df = options_df.rename(columns={'strikes': 'STRIKE'})
    options_df = options_df.rename(columns={'implied_volatilities': 'IMPLIEDVOL'})
    return options_df


def compliment_futures_in_options(options_df, futures_df):

    #futures_df['maturities'] = futures_df['maturities']/1000
    futures_df = futures_df.drop(futures_df[futures_df.maturities / 1000 > 30000000000.00000].index)  # drop perpetual
    futures_df['maturities_dates'] = [datetime.date.fromtimestamp(T) for T in futures_df['maturities']]
    futures_df['qlMaturities'] = [ql.Date(T.day, T.month, T.year) for T in futures_df['maturities']]
    T0 = options_df['T0'][0]
    futures_df['qlT0'] = ql.Date(T0.day, T0.month, T0.year)
    futures_df['tau'] = futures_df.apply(lambda x: ql.Thirty360().yearFraction(x.T0, x.maturities), axis=1)
    futures_df = futures_df[['tau', 'last_price']]
    futures_df = futures_df.sort_values(by='tau')
    S0 = options_df.Spot[0]
    futures_df['imp_r'] = np.log(futures_df['last_price']/S0)/futures_df['tau']
    opt_imp_r = pd.Series(np.interp(options_df.tau, futures_df.tau, futures_df.imp_r))

    options_df = options_df[['type','tau','Spot','maturities_dates','daysToMaturity','STRIKE','IMPLIEDVOL']]
    options_df['imp_r'] = opt_imp_r
    options_df['FUTUREPRICE'] = options_df.Spot * np.exp(options_df.imp_r * options_df.t)
    return (options_df, futures_df)


def select_put_call(options_df):
    call_options = options_df[options_df.type == 'call']
    call_options = call_options[call_options.STRIKE >= call_options.FUTUREPRICE]
    put_options = options_df[options_df.type == 'put']
    put_options = put_options[put_options.STRIKE < put_options.FUTUREPRICE]
    ret_df = pd.concat([call_options, put_options])
    ret_df = ret_df.sort_values(['t','STRIKE'])
    return ret_df