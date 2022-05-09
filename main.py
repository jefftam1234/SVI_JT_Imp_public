import argparse

from modules.calibration import initial_calibration, second_calibration
from modules.dataRetrieval import retrieve_data_live, retrieve_data_source
from modules.calc_svi import test_calc_svi


def restricted_float(x):
    try:
        x = float(x)
    except ValueError:
        raise argparse.ArgumentTypeError("%r not a floating-point literal" % (x,))

    if x < 0.0 or x > 1.0:
        raise argparse.ArgumentTypeError("%r not in range [0.0, 1.0]" % (x,))
    return x


# initial calibration mode from live data
# -m initial -s deribit -bsthres 0.1

# initial calibration mode from live data
# -m initial -s stored -t 20220416_143702 -bsthres 0.1

# re-calibration mode
# -m recal -s stored -t 20220416_143702 -bsthres 0.1

# calc mode
# -m calconly -s stored -t 20220416_143702 -bsthres 0.1


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

    # stage 0 - retrieve data (from deribit or previously stored data)
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

    # stage 1 - from the data received calibrate the model

    if args.mode.lower() == 'initial':
        initial_calibration(timestamp=localtimestamp, options_df=options_df, bs_delta_threshold=bs_delta_threshold)
    elif args.mode.lower() == 'recal':
        second_calibration(timestamp=localtimestamp, options_df=options_df, bs_delta_threshold=bs_delta_threshold)
    elif args.mode.lower() == 'calconly':
        test_calc_svi(t_mat=0.0027888, strike=90000, localtimestamp=localtimestamp, options_df=options_df,
                      futures_df=futures_df)
    else:
        raise ValueError(f'Unknown mode: {args.mode}')
