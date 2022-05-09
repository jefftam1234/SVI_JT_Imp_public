from scipy import optimize
from py_vollib.black import implied_volatility
import numpy as np
# We'll convert the option prices into implied volatities using the Black's model implementation
# in vollib (http://www.vollib.org/html/apidoc/vollib.black.html), dropping any prices that fail:
from scipy.stats import norm


def calc_iv(row):
    return implied_volatility.implied_volatility_of_discounted_option_price(
        row.PRICE,
        row.FUTUREPRICE,
        row.STRIKE,
        row.RISKFREERATE,
        row.t,
        row.PC.lower())


# Do the parameters fall inside Zeniade's compact and convex domain D?
import sys
def acceptable(S, a, d, c, vT):
    eps = sys.float_info.epsilon
    return -eps <= c and c <= 4 * S + eps and abs(d) <= min(c, 4 * S - c) + eps and -eps <= a and a <= vT.max() + eps and c>0


# The error function from the optimizer, in terms of a, d and c so we don't need to keep dividing by T:
def sum_of_squares(x, a, d, c, vT):
    diff = a + d * x + c * np.sqrt(x * x + 1) - vT
    return (diff * diff).sum()


# The key part of the Zeliade paper - identify the values of `a`, `d` and `c` that produce
# the lowest sum-of-squares error when the gradient of the `f` function is zero,
# ensuring that the parameters remain in the domain `D` identified in the paper.

def solve_grad(S, M, x, vT):
    ys = (x - M) / S

    y = ys.sum()
    y2 = (ys * ys).sum()
    y2one = (ys * ys + 1).sum()
    ysqrt = np.sqrt(ys * ys + 1).sum()
    y2sqrt = (ys * np.sqrt(ys * ys + 1)).sum()
    v = vT.sum()
    vy = (vT * ys).sum()
    vsqrt = (vT * np.sqrt(ys * ys + 1)).sum()

    matrix = [
        [1, y, ysqrt],
        [y, y2, y2sqrt],
        [ysqrt, y2sqrt, y2one]
    ]
    vector = [v, vy, vsqrt]
    _a, _d, _c = np.linalg.solve(np.array(matrix), np.array(vector))

    if acceptable(S, _a, _d, _c, vT):
        return _a, _d, _c, sum_of_squares(ys, _a, _d, _c, vT)

    _a, _d, _c, _cost = None, None, None, None
    for matrix, vector, clamp_params in [
        ([[1, 0, 0], [y, y2, y2sqrt], [ysqrt, y2sqrt, y2one]], [0, vy, vsqrt], False),  # a = 0
        ([[1, 0, 0], [y, y2, y2sqrt], [ysqrt, y2sqrt, y2one]], [vT.max(), vy, vsqrt], False),  # a = _vT.max()
        ([[1, y, ysqrt], [0, -1, 1], [ysqrt, y2sqrt, y2one]], [v, 0, vsqrt], False),  # d = c
        ([[1, y, ysqrt], [0, 1, 1], [ysqrt, y2sqrt, y2one]], [v, 0, vsqrt], False),  # d = -c
        ([[1, y, ysqrt], [0, 1, 1], [ysqrt, y2sqrt, y2one]], [v, 4 * S, vsqrt], False),  # d <= 4*s-c
        ([[1, y, ysqrt], [0, -1, 1], [ysqrt, y2sqrt, y2one]], [v, 4 * S, vsqrt], False),  # -d <= 4*s-c
        ([[1, y, ysqrt], [y, y2, y2sqrt], [0, 0, 1]], [v, vy, 0], False),  # c = 0
        ([[1, y, ysqrt], [y, y2, y2sqrt], [0, 0, 1]], [v, vy, 4 * S], False),  # c = 4*S

        ([[1, y, ysqrt], [0, 1, 0], [0, 0, 1]], [v, 0, 0], True),  # c = 0, implies d = 0, find optimal a
        ([[1, y, ysqrt], [0, 1, 0], [0, 0, 1]], [v, 0, 4 * S], True),  # c = 4s, implied d = 0, find optimal a
        ([[1, 0, 0], [0, -1, 1], [ysqrt, y2sqrt, y2one]], [0, 0, vsqrt], True),  # a = 0, d = c, find optimal c
        ([[1, 0, 0], [0, 1, 1], [ysqrt, y2sqrt, y2one]], [0, 0, vsqrt], True),  # a = 0, d = -c, find optimal c
        ([[1, 0, 0], [0, 1, 1], [ysqrt, y2sqrt, y2one]], [0, 4 * S, vsqrt], True),  # a = 0, d = 4s-c, find optimal c
        ([[1, 0, 0], [0, -1, 1], [ysqrt, y2sqrt, y2one]], [0, 4 * S, vsqrt], True)  # a = 0, d = c-4s, find optimal c
    ]:
        a, d, c = np.linalg.solve(np.array(matrix), np.array(vector))
        if clamp_params:
            dmax = min(c, 4 * S - c)
            a = min(max(a, 0), vT.max())
            d = min(max(d, -dmax), dmax)
            c = min(max(c, 0), 4 * S)
        cost = sum_of_squares(ys, a, d, c, vT)
        if acceptable(S, a, d, c, vT) and (_cost is None or cost < _cost):
            _a, _d, _c, _cost = a, d, c, cost

    assert _cost is not None, "S=%s, M=%s" % (S, M)
    return _a, _d, _c, _cost

# Use scipy's optimizer to minimize the error function
def solve_grad_get_score(S_M, x_vT):
    S, M = S_M
    x, vT = x_vT
    return solve_grad(S, M, x, vT)[3]

def calibrate(df):
    vT = df.IMPLIEDVOL * df.IMPLIEDVOL * df.t
    res = optimize.minimize(solve_grad_get_score, [.1, .0], args=[df.MONEYNESS, vT], bounds=[(0.001, None), (None, None)])
    assert res.success
    S, M = res.x
    a, d, c, _ = solve_grad(S, M, df.MONEYNESS, vT)
    T = df.t.max() # should be the same for all rows
    A, P, B = a / T, d / c, c / (S * T)
    # assert T >= 0 and S >= 0 and abs(P) <= 1
    return A, P, B, S, M

# SVI formula for the volatility (not variance):
def svi(A, P, B, S, M, x):
    return np.sqrt(A + B * (P * (x - M) + np.sqrt((x - M) * (x - M) + S * S)))

def calculate_svi_vol(row, A, P, B, S, M):
    return svi(A, P, B, S, M, row.MONEYNESS)

def volsurface(slices, t, moneyness):
    ts = []
    if t >= slices.index.min():
        ts.append(slices.index.get_loc(t, method='ffill'))
    if t <= slices.index.max():
        ts.append(slices.index.get_loc(t, method='bfill'))
    if len(ts) == 1:
        return slices.iat[ts[0]](moneyness)
    period = slices.index[ts[1]] - slices.index[ts[0]]
    fraction = (t - slices.index[ts[0]]) / period
    return (1 - fraction) * slices.iat[ts[0]](moneyness) + fraction * slices.iat[ts[1]](moneyness)


def bsdelta(moneyness, vol, maturity, opt_type):
    if maturity < 1e-10: maturity = 0.002 # less than a day
    d1 = 1 / vol / np.sqrt(maturity) * (-moneyness + 0.5 * vol * vol * maturity)
    if opt_type.lower() == 'call':
        return norm.cdf(d1)
    elif opt_type.lower() == 'put':
        return 1 - norm.cdf(d1)
    else:
        raise ValueError(f"Unknown option type: {opt_type}")