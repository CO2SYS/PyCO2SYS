# PyCO2SYS: marine carbonate system calculations in Python.
# Copyright (C) 2020  Matthew Paul Humphreys et al.  (GNU GPLv3)
"""Propagate uncertainties through marine carbonate system calculations."""

from copy import deepcopy
from autograd.numpy import array, isin, log10, median, ones, size, sqrt
from autograd.numpy import abs as np_abs
from autograd.numpy import all as np_all
from autograd.numpy import any as np_any
from autograd.numpy import sum as np_sum
from .. import engine
from . import automatic

__all__ = ["automatic"]


def _get_dx_wrt(dx, var, dx_scaling, dx_func=None):
    """Scale `dx` for a particular variable `var`."""
    assert dx_scaling in [
        "none",
        "median",
        "custom",
    ], "`dx_scaling` must be 'none' or 'median'."
    if dx_scaling == "none":
        dx_wrt = dx
    elif dx_scaling == "median":
        median_var = median(var)
        if median_var == 0:
            dx_wrt = dx
        else:
            dx_wrt = dx * np_abs(median_var)
    elif dx_scaling == "custom":
        dx_wrt = dx_func(var)
    return dx_wrt


def _overridekwargs(co2dict, co2kwargs_plus, kwarg, wrt, dx, dx_scaling, dx_func):
    """Generate `co2kwargs_plus` and scale `dx` for internal override derivatives."""
    # Reformat variable names for the kwargs dicts
    ispK = wrt.startswith("pK")
    if ispK:
        wrt = wrt[1:]
    if kwarg == "equilibria_in":
        wrt_stem = wrt.replace("input", "")
    elif kwarg == "equilibria_out":
        wrt_stem = wrt.replace("output", "")
    else:
        wrt_stem = wrt
    # If there isn't yet a dict, create one
    if co2kwargs_plus[kwarg] is None:
        co2kwargs_plus[kwarg] = {wrt_stem: co2dict[wrt]}
    # If there is a dict, add the field if it's not already there
    if wrt not in co2kwargs_plus[kwarg]:
        co2kwargs_plus[kwarg].update({wrt_stem: co2dict[wrt]})
    # Scale dx and add it to the `co2kwargs_plus` dict
    if ispK:
        pKvalues = -log10(co2kwargs_plus[kwarg][wrt_stem])
        dx_wrt = _get_dx_wrt(dx, pKvalues, dx_scaling, dx_func=dx_func)
        pKvalues_plus = pKvalues + dx_wrt
        co2kwargs_plus[kwarg][wrt_stem] = 10.0 ** -pKvalues_plus
    else:
        Kvalues = co2kwargs_plus[kwarg][wrt_stem]
        dx_wrt = _get_dx_wrt(dx, Kvalues, dx_scaling, dx_func=dx_func)
        co2kwargs_plus[kwarg][wrt_stem] = Kvalues + dx_wrt
    return co2kwargs_plus, dx_wrt


def forward(
    co2dict,
    grads_of,
    grads_wrt,
    totals=None,
    equilibria_in=None,
    equilibria_out=None,
    dx=1e-6,
    dx_scaling="median",
    dx_func=None,
):
    """Get forward finite-difference derivatives of CO2SYS outputs w.r.t. inputs.

    Arguments:
    co2dict -- output generated by `PyCO2SYS.CO2SYS`.
    grads_of -- list of keys from `co2dict` that you want to calculate the derivatives
        of, or a single key as a string, or "all".
    grads_wrt -- list of `PyCO2SYS.CO2SYS` input variable names that you want to
        calculate the derivatives with respect to, or a single name as a string, or
        "all".

    Keyword arguments:
    totals -- dict of internal override total salt concentrations identical to that used
        to generate the `co2dict` (default None).
    equilibria_in -- dict of internal override equilibrium constants at input conditions
        identical to that used to generate the `co2dict` (default None).
    equilibria_out -- dict of internal override equilibrium constants at output
        conditions identical to that used to generate the `co2dict` (default None).
    dx -- the forward difference for the derivative estimation (default 1e-6).
    dx_scaling -- method for scaling `dx` for each variable, can be one of: "median"
        (default), "none", or "custom".
    dx_func -- function of each variable to scale `dx` with if dx_scaling="custom".
    """
    # Derivatives can be calculated w.r.t. these inputs only
    inputs_wrt = [
        "PAR1",
        "PAR2",
        "SAL",
        "TEMPIN",
        "TEMPOUT",
        "PRESIN",
        "PRESOUT",
        "SI",
        "PO4",
        "NH3",
        "H2S",
    ]
    totals_wrt = ["TB", "TF", "TSO4", "TCa"]
    Ks_wrt = [
        "KSO4",
        "KF",
        "fH",
        "KB",
        "KW",
        "KP1",
        "KP2",
        "KP3",
        "KSi",
        "K1",
        "K2",
        "KH2S",
        "KNH3",
        "K0",
        "FugFac",
    ]
    Kis_wrt = ["{}input".format(K) for K in Ks_wrt]
    Kos_wrt = ["{}output".format(K) for K in Ks_wrt]
    pKis_wrt = ["p{}input".format(K) for K in Ks_wrt if K.startswith("K")]
    pKos_wrt = ["p{}output".format(K) for K in Ks_wrt if K.startswith("K")]
    # If only a single `grads_wrt` is requested, check it's allowed & convert to list
    groups_wrt = ["all", "measurements", "totals", "equilibria_in", "equilibria_out"]
    all_wrt = inputs_wrt + totals_wrt + Kis_wrt + Kos_wrt + pKis_wrt + pKos_wrt
    if isinstance(grads_wrt, str):
        assert grads_wrt in (all_wrt + groups_wrt)
        if grads_wrt == "all":
            grads_wrt = all_wrt
        elif grads_wrt == "measurements":
            grads_wrt = inputs_wrt
        elif grads_wrt == "totals":
            grads_wrt = totals_wrt
        elif grads_wrt == "equilibria_in":
            grads_wrt = Kis_wrt
        elif grads_wrt == "equilibria_out":
            grads_wrt = Kos_wrt
        else:
            grads_wrt = [grads_wrt]
    # Make sure all requested `grads_wrt` are allowed
    assert np_all(isin(list(grads_wrt), all_wrt)), "Invalid `grads_wrt` requested."
    # If only a single `grads_of` is requested, check it's allowed & convert to list
    if isinstance(grads_of, str):
        assert grads_of in ["all"] + list(engine.gradables)
        if grads_of == "all":
            grads_of = engine.gradables
        else:
            grads_of = [grads_of]
    # Final validity checks
    assert np_all(isin(grads_of, engine.gradables)), "Invalid `grads_of` requested."
    assert dx > 0, "`dx` must be positive."
    # Assemble input arguments for engine._CO2SYS()
    co2args = {
        arg: co2dict[arg]
        for arg in [
            "PAR1",
            "PAR2",
            "PAR1TYPE",
            "PAR2TYPE",
            "SAL",
            "TEMPIN",
            "TEMPOUT",
            "PRESIN",
            "PRESOUT",
            "SI",
            "PO4",
            "NH3",
            "H2S",
            "pHSCALEIN",
            "K1K2CONSTANTS",
            "KSO4CONSTANT",
            "KFCONSTANT",
            "BORON",
            "buffers_mode",
        ]
    }
    co2kwargs = {
        "KSO4CONSTANTS": co2dict["KSO4CONSTANTS"],
        "totals": totals,
        "equilibria_in": equilibria_in,
        "equilibria_out": equilibria_out,
    }
    # Preallocate output dict to store the gradients
    co2derivs = {of: {wrt: None for wrt in grads_wrt} for of in grads_of}
    dxs = {wrt: None for wrt in grads_wrt}
    # Estimate the gradients with central differences
    for wrt in grads_wrt:
        # Make copies of input args to modify
        co2args_plus = deepcopy(co2args)
        co2kwargs_plus = deepcopy(co2kwargs)
        # Perturb if `wrt` is one of the main inputs to CO2SYS
        if wrt in inputs_wrt:
            dx_wrt = _get_dx_wrt(
                dx, median(co2args_plus[wrt]), dx_scaling, dx_func=dx_func
            )
            co2args_plus[wrt] = co2args_plus[wrt] + dx_wrt
        # Perturb if `wrt` is one of the `totals` internal overrides
        elif wrt in totals_wrt:
            co2kwargs_plus, dx_wrt = _overridekwargs(
                co2dict, co2kwargs_plus, "totals", wrt, dx, dx_scaling, dx_func=dx_func
            )
        # Perturb if `wrt` is one of the `equilibria_in` internal overrides
        elif wrt in Kis_wrt:
            co2kwargs_plus, dx_wrt = _overridekwargs(
                co2dict,
                co2kwargs_plus,
                "equilibria_in",
                wrt,
                dx,
                dx_scaling,
                dx_func=dx_func,
            )
        # Perturb if `wrt` is one of the `equilibria_in` internal overrides and the pK
        # derivative is requested
        elif wrt in pKis_wrt:
            co2kwargs_plus, dx_wrt = _overridekwargs(
                co2dict,
                co2kwargs_plus,
                "equilibria_in",
                wrt,
                dx,
                dx_scaling,
                dx_func=dx_func,
            )
        # Perturb if `wrt` is one of the `equilibria_out` internal overrides
        elif wrt in Kos_wrt:
            co2kwargs_plus, dx_wrt = _overridekwargs(
                co2dict,
                co2kwargs_plus,
                "equilibria_out",
                wrt,
                dx,
                dx_scaling,
                dx_func=dx_func,
            )
        # Solve CO2SYS with the perturbation applied
        co2dict_plus = engine._CO2SYS(**co2args_plus, **co2kwargs_plus)
        dxs[wrt] = dx_wrt
        # Extract results and calculate forward finite difference derivatives
        for of in grads_of:
            if co2derivs[of][wrt] is None:  # don't overwrite existing derivatives
                co2derivs[of][wrt] = (co2dict_plus[of] - co2dict[of]) / dx_wrt
    return co2derivs, dxs


def propagate(
    co2dict,
    uncertainties_into,
    uncertainties_from,
    totals=None,
    equilibria_in=None,
    equilibria_out=None,
    dx=1e-6,
    dx_scaling="median",
    dx_func=None,
):
    """Propagate uncertainties from requested inputs to outputs."""
    co2derivs = forward(
        co2dict,
        uncertainties_into,
        uncertainties_from,
        totals=totals,
        equilibria_in=equilibria_in,
        equilibria_out=equilibria_out,
        dx=dx,
        dx_scaling=dx_scaling,
        dx_func=dx_func,
    )[0]
    npts = size(co2dict["PAR1"])
    uncertainties_from = engine.condition(uncertainties_from, npts=npts)[0]
    components = {
        u_into: {
            u_from: np_abs(co2derivs[u_into][u_from]) * v_from
            for u_from, v_from in uncertainties_from.items()
        }
        for u_into in uncertainties_into
    }
    uncertainties = {
        u_into: sqrt(
            np_sum(
                array([component for component in components[u_into].values()]) ** 2,
                axis=0,
            )
        )
        for u_into in uncertainties_into
    }
    return uncertainties, components