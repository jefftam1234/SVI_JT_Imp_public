import datetime
import QuantLib as ql
import numpy as np
import pandas as pd

from dateutil import tz

def clean_up_option_data(options_df):
    tzutc = datetime.timezone.utc
    local_tz = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
    options_df['maturities_datetime'] = [datetime.datetime.fromtimestamp(T).replace(tzinfo=local_tz).astimezone(tzutc) for T in options_df['maturities']]   #maturities are in POSIX
    options_df['qlMaturities'] = [ql.Date(T.day, T.month, T.year) for T in options_df['maturities_datetime']]
    options_df['maturities_time'] = [T.time() for T in options_df['maturities_datetime']]

    options_df['T0'] = [datetime.datetime.strptime(str(T), '%Y-%m-%d %H:%M:%S.%f').replace(tzinfo=tzutc) for T in options_df['utc_T0']]
    options_df['qlT0'] = [ql.Date(T.day, T.month, T.year) for T in options_df['T0']]
    options_df['tau'] = options_df.apply(lambda x: ql.Thirty360().yearFraction(x.qlT0, x.qlMaturities), axis=1)
    options_df['tau'] = options_df.apply(
        lambda x: (x.maturities_datetime-x.T0).total_seconds()/86400/360 if abs(x.tau) < 1e-6 else x.tau, axis=1)
    options_df['daysToMaturity'] = options_df.apply(lambda x: ql.Thirty360().dayCount(x.qlT0, x.qlMaturities), axis=1)
    options_df = options_df[['tau', 'T0', 'Spot', 'strikes', 'type', 'maturities_datetime', 'daysToMaturity', 'implied_volatilities']]
    options_df = options_df.rename(columns={'strikes': 'STRIKE'})
    options_df = options_df.rename(columns={'implied_volatilities': 'IMPLIEDVOL'})
    return options_df


def compliment_futures_in_options(options_df, futures_df):
    tzutc = datetime.timezone.utc
    local_tz = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
    futures_df['maturities'] = futures_df['maturities']/1000
    futures_df = futures_df.drop(futures_df[futures_df.maturities > 30000000000.00000].index)  # drop perpetual
    futures_df['maturities_datetime'] = [datetime.datetime.fromtimestamp(T).replace(tzinfo=local_tz).astimezone(tzutc) for T in futures_df['maturities']]
    futures_df['qlMaturities'] = [ql.Date(T.day, T.month, T.year) for T in futures_df['maturities_datetime']]
    T0 = options_df['T0'][0]
    futures_df['qlT0'] = ql.Date(T0.day, T0.month, T0.year)
    futures_df['tau'] = futures_df.apply(lambda x: ql.Thirty360().yearFraction(x.qlT0, x.qlMaturities), axis=1)
    futures_df['tau'] = futures_df.apply(
        lambda x: (x.maturities_datetime - x.T0).total_seconds() / 86400 / 360 if abs(x.tau) < 1e-6 else x.tau, axis=1)
    futures_df = futures_df[['tau', 'last_price']]
    futures_df = futures_df.sort_values(by='tau')
    S0 = options_df.Spot[0]
    futures_df['imp_r'] = np.log(futures_df['last_price']/S0)/futures_df['tau']
    opt_imp_r = pd.Series(np.interp(options_df.tau, futures_df.tau, futures_df.imp_r))

    options_df = options_df[['type','tau','Spot','maturities_datetime','daysToMaturity','STRIKE','IMPLIEDVOL']]
    options_df['imp_r'] = opt_imp_r
    options_df['FUTUREPRICE'] = options_df.Spot * np.exp(options_df.imp_r * options_df.tau)
    return (options_df, futures_df)


def select_put_call(options_df):
    call_options = options_df[options_df.type == 'call']
    call_options = call_options[call_options.STRIKE >= call_options.FUTUREPRICE]
    put_options = options_df[options_df.type == 'put']
    put_options = put_options[put_options.STRIKE < put_options.FUTUREPRICE]
    ret_df = pd.concat([call_options, put_options])
    ret_df = ret_df.sort_values(['tau','STRIKE'])
    return ret_df