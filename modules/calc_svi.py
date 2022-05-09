from modules.dataRetrieval import retrieve_initial_svi_param_dict
from modules.formulas import svi, moneyness_func


def test_calc_svi(t_mat, strike, localtimestamp, options_df, futures_df):
    svi_param_dict = retrieve_initial_svi_param_dict(localtimestamp)
    calc_vol = calculate_vol_from_svi_dicts(options=options_df, futures=futures_df, svi_param_dict=svi_param_dict,
                                            t_mat=t_mat, strike=strike)
    print(f"For maturity =  {t_mat}, strike = {strike}, the calculated vol = {calc_vol}")


def calculate_vol_from_svi_dicts(options, futures, svi_param_dict, t_mat, strike):

    target_index = -1000
    for index in svi_param_dict:
        svi_param = svi_param_dict[index]
        if abs(t_mat - svi_param["t"]) < 1e-8:
            target_index = index
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