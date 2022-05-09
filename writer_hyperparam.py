import json

if __name__ == '__main__':
    h_params = {
        "butarb": float("Inf"),
        "calarb": float("Inf"),
        "bpen": 128,  # initial butterfly penalty factor
        "cpen": 128,  # initial calendar penalty factor
        "blim": 0.001,  # target butterfly arbitrage bound
        "clim": 0.001,  # target calendar arbitrage bound
    }

    with open(f'calib_hyperparameter.json', "w") as outfile:
        json.dump(h_params, outfile)
        print(f'Saved calibration hyperparameters.')
