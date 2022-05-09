import json
import numpy as np
import scipy as sp
from matplotlib import pyplot as plt
from modules.formulas import bsdelta, calibrate, calculate_svi_vol
from modules.dataRetrieval import retrieve_initial_svi_param_dict, retrieve_calibration_hyperparameters


def initial_calibration(timestamp, options_df, bs_delta_threshold=0.1):
    # the FUTURE PRICE should be interpolated from the futures csv
    options_df['MONEYNESS'] = np.log(options_df.STRIKE / options_df.FUTUREPRICE)
    options_df['BSDELTA'] = options_df.apply(lambda x: bsdelta(x.MONEYNESS, x.IMPLIEDVOL, x.tau, x.type), axis=1)

    svi_param = {}
    mat_vec = options_df.tau.unique()

    for i in range(len(mat_vec)):
        try:
            curve = options_df[options_df.tau == mat_vec[i]].sort_values('STRIKE')
            curve = curve[['MONEYNESS', 'IMPLIEDVOL', 'tau', 'BSDELTA']]
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
            curve = options_df[options_df.tau == mat_vec[i]].sort_values('STRIKE')
            curve = curve[['MONEYNESS', 'IMPLIEDVOL', 'tau']]
            print(f'cannot calibrate for t={mat_vec[i]}, plot implied vol instead')
            curve.plot(x='MONEYNESS', y='IMPLIEDVOL', title=f"(fail to calibrate), t = {mat_vec[i]}")
            plt.savefig(f'{timestamp}/example_calibration_{i}.png')
            plt.close()
        finally:
            print(f'done for t={mat_vec[i]}')

    with open(f'{timestamp}/svi_param_initial.json', "w") as outfile:
        json.dump(svi_param, outfile)
        print(f'Saved SVI params.')


def second_calibration(timestamp, options_df, bs_delta_threshold=0.1):
    options_df['MONEYNESS'] = np.log(options_df.STRIKE / options_df.FUTUREPRICE)
    options_df['BSDELTA'] = options_df.apply(lambda x: bsdelta(x.MONEYNESS, x.IMPLIEDVOL, x.tau, x.type), axis=1)

    #get 1st round parameter
    # the first timestep might not calibrate, re-sort the parameter set
    svi_param_dict_extract = retrieve_initial_svi_param_dict(timestamp)
    svi_param_dict = {}
    for svi_param in svi_param_dict_extract:
        t = svi_param_dict_extract[svi_param].pop('t')
        svi_param_dict[t] = svi_param_dict_extract[svi_param]

    h_params = retrieve_calibration_hyperparameters()

    butarb = h_params["butarb"]
    blim = h_params["blim"]
    calarb = h_params["calarb"]
    clim = h_params["clim"]

    while butarb > blim or calarb > clim:
        (h_params, recalibrated_svi_param) = calibration_with_penalty(options_df, bs_delta_threshold, h_params, svi_param_dict)
        butarb = h_params["butarb"]
        blim = h_params["blim"]
        calarb = h_params["calarb"]
        clim = h_params["clim"]

    return recalibrated_svi_param

def calibration_with_penalty(options_df, bs_delta_threshold, h_params, previous_svi_param):
    t_prev = 0
    for t, svi_params in previous_svi_param:
        temp = sp.optimize.leastsq(residuals, x0=svi_params, args=(t, previous_svi_param, options_df, bs_delta_threshold, grid, h_params))

        t_prev = t
    #return (h_params, recalibrated_svi_param)
    pass

