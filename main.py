import numpy as np
import matplotlib.pyplot as plt
import json
import argparse
from modules.dataRetrieval import retrieve_data_live, retrieve_data_source, retrieve_initial_svi_param_dict
from modules.formulas import calibrate, calculate_svi_vol, bsdelta, svi


def restricted_float(x):
    try:
        x = float(x)
    except ValueError:
        raise argparse.ArgumentTypeError("%r not a floating-point literal" % (x,))

    if x < 0.0 or x > 1.0:
        raise argparse.ArgumentTypeError("%r not in range [0.0, 1.0]" % (x,))
    return x


def moneyness_func(options, futures, strike, t_mat):
    S0 = options.Spot.iloc[0]
    imp_r = np.interp(t_mat, futures.t, futures.imp_r)
    return np.log(strike / (S0 * np.exp(imp_r * t_mat)))


def initial_calibration(timestamp, options, bs_delta_threshold=0.1):
    # the FUTURE PRICE should be interpolated from the futures csv
    options['MONEYNESS'] = np.log(options.STRIKE / options.FUTUREPRICE)
    options['BSDELTA'] = options.apply(lambda x: bsdelta(x.MONEYNESS, x.IMPLIEDVOL, x.t, x.type), axis=1)

    svi_param = {}
    mat_vec = options.t.unique()

    for i in range(len(mat_vec)):
        try:
            curve = options[options.t == mat_vec[i]].sort_values('STRIKE')
            curve = curve[['MONEYNESS', 'IMPLIEDVOL', 't', 'BSDELTA']]
            curve['color'] = curve.BSDELTA.apply(lambda x: 'r' if x < bs_delta_threshold else 'g')
            itm_delta10_curve = curve[curve.BSDELTA > bs_delta_threshold]
            A, P, B, S, M = calibrate(itm_delta10_curve)
            curve['CALCULATEDVOL'] = curve.apply(calculate_svi_vol, A=A, P=P, B=B, S=S, M=M, axis=1)
            svi_dict = {"t": mat_vec[i], "A": A, "P": P, "B": B, "S": S, "M": M}
            svi_param[i] = svi_dict
            curve.plot(x='MONEYNESS', y=['IMPLIEDVOL', 'CALCULATEDVOL'], title=f"t = {mat_vec[i]}", style='.-')
            plt.savefig(f'{timestamp}/example_calibration_{i}.png')
            plt.close()
        except:
            curve = options[options.t == mat_vec[i]].sort_values('STRIKE')
            curve = curve[['MONEYNESS', 'IMPLIEDVOL', 't']]
            print(f'cannot calibrate for t={mat_vec[i]}, plot implied vol instead')
            curve.plot(x='MONEYNESS', y='IMPLIEDVOL', title=f"(fail to calibrate), t = {mat_vec[i]}")
            plt.savefig(f'{timestamp}/example_calibration_{i}.png')
            plt.close()
        finally:
            print(f'done for t={mat_vec[i]}')

    with open(f'{timestamp}/svi_param_initial.json', "w") as outfile:
        json.dump(svi_param, outfile)
        print(f'Saved SVI params.')


def recalibration():
    #await implementation
    return


def calculate_vol_from_svi_dicts(options, futures, svi_param_dict, t_mat, strike):

    target_index = -1000
    for i in range(len(svi_param_dict)):
        svi_param = svi_param_dict[str(i)]
        if abs(t_mat - svi_param["t"]) < 1e-8:
            target_index = i
    if target_index < 0:
        raise ValueError(f"No interpolation yet, can't find target maturity for {t_mat}")

    svi_param_t = svi_param_dict[str(target_index)]
    A = svi_param_t["A"]
    P = svi_param_t["P"]
    B = svi_param_t["B"]
    S = svi_param_t["S"]
    M = svi_param_t["M"]
    x = moneyness_func(options=options, futures=futures, strike=strike, t_mat=t_mat)
    return svi(A=A, P=P, B=B, S=S, M=M, x=x)

# initial mode
# -m initial -s deribit -bsthres 0.1
# calc mode
# -m calconly -s stored -bsthres 0.1 -t 20220303_212621

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--mode", type=str, required=True,
                        help="'initial' for initial calibration, 'recal' for further calibration (eliminate arbitrage), 'calconly' for calculation svi only")
    parser.add_argument("-s", "--source", type=str, required=True,
                        help="'deribit' or 'live' for live data, 'stored' for stored data")
    parser.add_argument("-bsthres", type=restricted_float,
                        help="bs delta cutoff threshold, default is 0.1")
    parser.add_argument("-t", "--timestamp", type=str,
                        help="timestamp for static option and future input, in yyyymmdd_hhmmss, store in the folder with string equals the local time")

    args = parser.parse_args()

    #step 0 - retrieve data (from deribit or previously stored data)
    if args.source.lower() in ['deribit', 'live']:
        datetime, options_df, futures_df = retrieve_data_live()
        localtimestamp = datetime
    elif args.source.lower() in ['stored']:
        localtimestamp = args.timestamp
        options_df, futures_df = retrieve_data_source(args.timestamp)
    else:
        raise ValueError(f'Unknown source: {args.source}')

    bs_delta_threshold = 0.1  # default BS threshold value
    if args.bsthres:
        bs_delta_threshold = args.bsthres

    if args.mode.lower() == 'initial':
        initial_calibration(timestamp=localtimestamp, options=options_df, bs_delta_threshold=bs_delta_threshold)
    elif args.mode.lower() == 'recal':
        recalibration()
    elif args.mode.lower() == 'calconly':
        pass
    else:
        raise ValueError(f'Unknown mode: {args.mode}')









    t_mat = 0.15833333333333333
    strike = 90000
    svi_param_dict = retrieve_initial_svi_param_dict(localtimestamp)
    calc_vol = calculate_vol_from_svi_dicts(options=options_df, futures=futures_df, svi_param_dict=svi_param_dict, t_mat=t_mat, strike=strike)
    print(f"For maturity =  {t_mat}, strike = {strike}, the calculated vol = {calc_vol}")

    # timestamp = '20211117_231830'
    # timestamp = '20211212_160416'
    # timestamp = '20211214_090007
    # timestamp = '20220131_230626'
    # timestamp = '20220227_154849'
    # timestamp = '20220303_212621'
