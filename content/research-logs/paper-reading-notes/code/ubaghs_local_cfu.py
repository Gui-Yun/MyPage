"""Small, interpretable local Ca-to-BOLD model for the Ubaghs et al. data.

This is intentionally not a reimplementation of the paper's SVM analysis.  It
fits a lagged ridge observation model at the native MRI TR and uses timestamps
to avoid treating interpolated BOLD samples as independent observations.

Usage:
    python ubaghs_local_cfu.py --data-dir C:/path/to/ubaghs_figshare

Outputs are written next to this file unless --output-dir is supplied.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import scipy.io as sio
from scipy.ndimage import median_filter
from sklearn.linear_model import Ridge


def matlab_sessions(path: Path):
    obj = sio.loadmat(path, squeeze_me=True, struct_as_record=False)["data_out"]
    return {name: getattr(obj, name) for name in obj._fieldnames}


def seconds(t):
    t = np.asarray(t, dtype=float).ravel()
    # The microscopy timestamps are milliseconds; MRI timestamps are seconds.
    return t / 1000.0 if np.nanmedian(np.diff(t)) > 10 else t


def trace(x):
    x = np.asarray(x, dtype=float)
    if x.ndim == 1:
        return x
    axis = 0 if x.shape[1] >= x.shape[0] else 1
    return np.nanmean(x, axis=axis)


def zscore(x):
    x = np.asarray(x, dtype=float)
    return (x - np.nanmean(x)) / (np.nanstd(x) + 1e-12)


def interpolate_valid(t_src, x_src, t_dst, max_gap=0.65):
    """Interpolate only within recorded calcium segments, not across laser gaps."""
    order = np.argsort(t_src)
    t_src, x_src = np.asarray(t_src)[order], np.asarray(x_src)[order]
    idx = np.searchsorted(t_src, t_dst)
    valid = (idx > 0) & (idx < len(t_src))
    left = np.clip(idx - 1, 0, len(t_src) - 1)
    right = np.clip(idx, 0, len(t_src) - 1)
    valid &= (t_src[right] - t_src[left]) <= max_gap
    out = np.full(len(t_dst), np.nan)
    out[valid] = np.interp(t_dst[valid], t_src, x_src)
    return out, valid


def lag_matrix(x, n_lags):
    x = np.asarray(x, dtype=float)
    out = np.full((len(x), n_lags), np.nan)
    for lag in range(n_lags):
        if lag == 0:
            out[:, lag] = x
        else:
            out[lag:, lag] = x[:-lag]
    return out


def bold_delta(raw):
    """Approximate the paper's relative-change BOLD preprocessing."""
    raw = np.asarray(raw, dtype=float)
    # 180 s median baseline at TR=1.5 s; use an odd kernel.
    baseline = median_filter(raw, size=121, mode="nearest")
    return (raw - baseline) / (baseline + 1e-12)


def vascular_width(profile):
    """Convert vessel cross-sectional profiles to a rough width trace.

    ``vascular`` is a profile-by-time matrix, not a precomputed diameter
    vector.  A half-maximum width is a transparent proxy and is intentionally
    kept separate from the paper's full vessel-profiling pipeline.
    """
    p = np.asarray(profile, dtype=float)
    if p.ndim == 1:
        return p
    widths = np.full(p.shape[1], np.nan)
    for j in range(p.shape[1]):
        col = p[:, j]
        finite = np.isfinite(col)
        if finite.sum() < 3 or np.nanmax(col[finite]) <= 0:
            continue
        half = 0.5 * np.nanmax(col[finite])
        widths[j] = np.sum(col >= half)
    return widths


def folds(n, k=5):
    edges = np.linspace(0, n, k + 1, dtype=int)
    return [(np.arange(edges[i], edges[i + 1]), np.r_[np.arange(0, edges[i]), np.arange(edges[i + 1], n)])
            for i in range(k) if edges[i + 1] - edges[i] > 0]


def score(y, pred):
    rmse = float(np.sqrt(np.mean((y - pred) ** 2)))
    nrmse = rmse / (float(np.std(y)) + 1e-12)
    corr = float(np.corrcoef(y, pred)[0, 1]) if np.std(pred) > 1e-12 else np.nan
    return corr, nrmse


def fit_cv(X, y, alpha=10.0):
    out = []
    for test, train in folds(len(y), k=min(5, max(2, len(y) // 12))):
        model = Ridge(alpha=alpha).fit(X[train], y[train])
        pred = model.predict(X[test])
        out.append(score(y[test], pred))
    return np.nanmean(out, axis=0)


def build_session(mic, vas, mri, n_lags):
    tm = seconds(getattr(mri, "timestamps"))
    tr = float(np.nanmedian(np.diff(tm)))
    y = bold_delta(trace(getattr(mri, "timeseries")))
    movement = np.asarray(getattr(mri, "movement"), dtype=float)
    movement = movement if movement.shape[1] == len(tm) else movement.T
    movement = np.nanmean(movement, axis=0)

    tc = seconds(getattr(mic, "timestamps_corrected", getattr(mic, "timestamps")))
    cells = np.asarray(getattr(mic, "cells_deconv"), dtype=float)
    n_cells = int(cells.shape[0]) if cells.ndim > 1 else 1
    ca = trace(cells)
    tv = seconds(getattr(vas, "timestamps_corrected", getattr(vas, "timestamps")))
    vascular = vascular_width(getattr(vas, "vascular"))

    ca_i, ca_ok = interpolate_valid(tc, zscore(ca), tm, max_gap=max(0.65, tr / 2))
    va_i, va_ok = interpolate_valid(tv, zscore(vascular), tm, max_gap=max(0.65, tr / 2))
    # Do not fill laser-off periods. Require both local neural and vascular data.
    ok = np.isfinite(y) & ca_ok & va_ok & np.isfinite(ca_i) & np.isfinite(va_i)
    if ok.sum() < 30:
        return None

    ca_l = lag_matrix(ca_i, n_lags)
    va_l = lag_matrix(va_i, n_lags)
    mot = zscore(movement)
    mot_l = lag_matrix(mot, min(3, n_lags))
    # Native-TR design; no BOLD interpolation is used.
    X_ca = ca_l
    X_vascular = va_l
    X_motion = mot_l
    X_local = np.c_[X_ca, X_vascular, X_motion]
    keep = ok & np.all(np.isfinite(X_local), axis=1)
    return tm[keep], y[keep], X_ca[keep], X_vascular[keep], X_motion[keep], X_local[keep], n_cells


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path)
    ap.add_argument("--lags", type=int, default=12, help="number of native-TR lags (12 = 18 s)")
    args = ap.parse_args()
    outdir = args.output_dir or Path(__file__).resolve().parent / "outputs"
    outdir.mkdir(parents=True, exist_ok=True)

    mic = matlab_sessions(args.data_dir / "microscopy.mat")
    vas = matlab_sessions(args.data_dir / "vasculature.mat")
    mri = matlab_sessions(args.data_dir / "mri.mat")
    common = sorted(set(mic) & set(vas) & set(mri))
    rows, best = [], None
    for name in common:
        built = build_session(mic[name], vas[name], mri[name], args.lags)
        if built is None:
            continue
        t, y, X_ca, X_vascular, X_motion, X_local, n_cells = built
        ca_corr, ca_nrmse = fit_cv(X_ca, y)
        vascular_corr, vascular_nrmse = fit_cv(X_vascular, y)
        motion_corr, motion_nrmse = fit_cv(X_motion, y)
        ca_vascular_corr, ca_vascular_nrmse = fit_cv(np.c_[X_ca, X_vascular], y)
        local_corr, local_nrmse = fit_cv(X_local, y)
        # Circular-shift null: preserve the autocorrelation and marginal scale
        # of Ca/vascular features while breaking their temporal relation to BOLD.
        rng = np.random.default_rng(20260902)
        null_corr = []
        for _ in range(20):
            shift = int(rng.integers(max(5, len(y) // 10), len(y) - max(5, len(y) // 10)))
            shifted = np.c_[np.roll(X_ca, shift, axis=0), np.roll(X_vascular, shift, axis=0), X_motion]
            null_corr.append(fit_cv(shifted, y)[0])
        null_corr = float(np.nanmedian(null_corr))
        rows.append({"session": name, "n_cells": n_cells, "n_native_TR": len(y),
                     "ca_corr": ca_corr, "ca_nrmse": ca_nrmse,
                     "vascular_corr": vascular_corr, "vascular_nrmse": vascular_nrmse,
                     "motion_corr": motion_corr, "motion_nrmse": motion_nrmse,
                     "ca_vascular_corr": ca_vascular_corr, "ca_vascular_nrmse": ca_vascular_nrmse,
                     "local_corr": local_corr, "local_nrmse": local_nrmse,
                     "shift_null_corr": null_corr})
        if best is None or local_corr > best["local_corr"]:
            best = {"name": name, "t": t, "y": y, "X": X_local, **rows[-1]}

    with (outdir / "results.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys() if rows else ["session"])
        writer.writeheader(); writer.writerows(rows)

    if best is not None:
        pred = np.full(len(best["y"]), np.nan)
        for test, train in folds(len(pred), k=min(5, max(2, len(pred) // 12))):
            model = Ridge(alpha=10.0).fit(best["X"][train], best["y"][train])
            pred[test] = model.predict(best["X"][test])
        # Break the display line at laser-off / missing-data gaps.
        t_plot, y_plot, p_plot = best["t"].copy(), best["y"].copy(), pred.copy()
        gaps = np.where(np.diff(t_plot) > 3.0)[0]
        if len(gaps):
            offset = 0
            for g in gaps:
                at = g + 1 + offset
                t_plot = np.insert(t_plot, at, np.nan)
                y_plot = np.insert(y_plot, at, np.nan)
                p_plot = np.insert(p_plot, at, np.nan)
                offset += 1
        fig, ax = plt.subplots(2, 1, figsize=(10, 5), sharex=True)
        ax[0].plot(t_plot, y_plot, color="#334155", label="BOLD Δ")
        ax[0].plot(t_plot, p_plot, color="#dc2626", label="local model CV")
        ax[0].set_ylabel("z-scored ΔBOLD")
        ax[0].legend(frameon=False)
        ax[0].set_title(f"Local Ca→BOLD model: {best['name']}")
        ax[1].bar([0, 1, 2], [best["ca_corr"], best["motion_corr"], best["local_corr"]],
                  color=["#94a3b8", "#f59e0b", "#2563eb"])
        ax[1].set_xticks([0, 1, 2], ["Ca only", "motion only", "Ca + vessel + motion"])
        ax[1].tick_params(axis="x", labelrotation=15)
        ax[1].set_ylabel("held-out Pearson r")
        ax[1].axhline(0, color="#64748b", lw=0.8)
        fig.tight_layout()
        fig.savefig(outdir / "local_cfu_model.png", dpi=180)
        print(f"best_session={best['name']}")
        print(f"ca_only_r={best['ca_corr']:.3f}, local_r={best['local_corr']:.3f}")
        print(f"ca_only_nrmse={best['ca_nrmse']:.3f}, local_nrmse={best['local_nrmse']:.3f}")
    print(f"sessions_fitted={len(rows)}; results={outdir / 'results.csv'}")


if __name__ == "__main__":
    main()
