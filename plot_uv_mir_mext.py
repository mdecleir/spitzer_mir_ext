#!/usr/bin/env python
#
# Program to plot a list of extinction curves
#
from __future__ import absolute_import, division, print_function, unicode_literals
import argparse

import numpy as np
import matplotlib.pyplot as pyplot
import matplotlib

# from astropy.table import Table
import astropy.units as u

from calc_ext import P92_Elv
from dust_extinction.shapes import P92
from measure_extinction.extdata import ExtData, AverageExtData


def plot_all_ext(
    ax, kxrange, kyrange, normvals=None, yoffset_factor=0.0, annotate_key=None
):
    """
    plot all the extintion info on the specified plot
    """
    # sindxs = np.argsort(avs)
    sindxs = np.arange(len(avs))

    ann_wave_range = [5.0, 10.0] * u.micron
    col_vals = ["b", "g", "r", "m", "c", "y"]
    lin_vals = ["--", ":", "-."]

    mod_x = np.logspace(-1.0, 2.0, 200) * u.micron
    for i in range(len(extnames)):
        k = sindxs[i]

        if normvals is not None:
            normval = normvals[k]
        else:
            normval = 1.0

        # plot the extinction curves
        if not args.modonly:
            extdatas[k].plot(
                ax,
                color=col_vals[i % 6],
                alax=args.alav,
                normval=normval,
                yoffset=i * yoffset_factor,
                alpha=1.0,
                rebin_fac=args.rebin_fac,
                fontsize=fontsize,
                annotate_key=annotate_key,
                annotate_yoffset=0.025,
                annotate_text=extnames[k].split("_")[0],
                annotate_wave_range=ann_wave_range,
            )

        # plot the best fit P92 model
        if args.alav:
            P92_best = P92(
                BKG_amp=extdatas[k].p92_best_fit["BKG_AMP"],
                BKG_lambda=extdatas[k].p92_best_fit["BKG_LAMBDA"],
                BKG_n=extdatas[k].p92_best_fit["BKG_N"],
                BKG_b=extdatas[k].p92_best_fit["BKG_B"],
                FUV_amp=extdatas[k].p92_best_fit["FUV_AMP"],
                FUV_lambda=extdatas[k].p92_best_fit["FUV_LAMBDA"],
                FUV_n=extdatas[k].p92_best_fit["FUV_N"],
                FUV_b=extdatas[k].p92_best_fit["FUV_B"],
                NUV_amp=extdatas[k].p92_best_fit["NUV_AMP"],
                NUV_lambda=extdatas[k].p92_best_fit["NUV_LAMBDA"],
                NUV_n=extdatas[k].p92_best_fit["NUV_N"],
                NUV_b=extdatas[k].p92_best_fit["NUV_B"],
                SIL1_amp=extdatas[k].p92_best_fit["SIL1_AMP"],
                SIL1_lambda=extdatas[k].p92_best_fit["SIL1_LAMBDA"],
                SIL1_n=extdatas[k].p92_best_fit["SIL1_N"],
                SIL1_b=extdatas[k].p92_best_fit["SIL1_B"],
                FIR_amp=extdatas[k].p92_best_fit["FIR_AMP"],
                FIR_lambda=extdatas[k].p92_best_fit["FIR_LAMBDA"],
                FIR_n=extdatas[k].p92_best_fit["FIR_N"],
                FIR_b=extdatas[k].p92_best_fit["FIR_B"],
            )
        else:
            P92_best = P92_Elv(
                BKG_amp_0=extdatas[k].p92_best_fit["BKG_AMP"],
                BKG_lambda_0=extdatas[k].p92_best_fit["BKG_LAMBDA"],
                BKG_n_0=extdatas[k].p92_best_fit["BKG_N"],
                BKG_b_0=extdatas[k].p92_best_fit["BKG_B"],
                FUV_amp_0=extdatas[k].p92_best_fit["FUV_AMP"],
                FUV_lambda_0=extdatas[k].p92_best_fit["FUV_LAMBDA"],
                FUV_n_0=extdatas[k].p92_best_fit["FUV_N"],
                FUV_b_0=extdatas[k].p92_best_fit["FUV_B"],
                NUV_amp_0=extdatas[k].p92_best_fit["NUV_AMP"],
                NUV_lambda_0=extdatas[k].p92_best_fit["NUV_LAMBDA"],
                NUV_n_0=extdatas[k].p92_best_fit["NUV_N"],
                NUV_b_0=extdatas[k].p92_best_fit["NUV_B"],
                SIL1_amp_0=extdatas[k].p92_best_fit["SIL1_AMP"],
                SIL1_lambda_0=extdatas[k].p92_best_fit["SIL1_LAMBDA"],
                SIL1_n_0=extdatas[k].p92_best_fit["SIL1_N"],
                SIL1_b_0=extdatas[k].p92_best_fit["SIL1_B"],
                FIR_amp_0=extdatas[k].p92_best_fit["FIR_AMP"],
                FIR_lambda_0=extdatas[k].p92_best_fit["FIR_LAMBDA"],
                FIR_n_0=extdatas[k].p92_best_fit["FIR_N"],
                FIR_b_0=extdatas[k].p92_best_fit["FIR_B"],
                Av_1=extdatas[k].columns["AV"][0],
            )

        if args.models:
            if args.alav:
                ltext = None
            else:
                ltext = extdatas[k].red_file.replace("DAT_files/", "")
                ltext = ltext.replace(".dat", "")
            ax.plot(
                mod_x,
                P92_best(mod_x) / normval + i * yoffset_factor,
                lin_vals[i % 3],
                color=col_vals[i % 6],
                alpha=0.5,
                label=ltext,
            )

    ax.set_yscale("linear")
    ax.set_xscale("linear")
    ax.set_xlim(kxrange)
    if args.alav:
        # ax.set_ylim(0.0, 0.25)
        ax.set_ylabel(r"$A(\lambda)/A(V)$", fontsize=1.3 * fontsize)
        # ax.legend(fontsize=fontsize)
    else:
        ax.set_xlim(kxrange)
        ax.set_ylim(kyrange)
        ax.set_ylabel(r"$E(\lambda - V)$", fontsize=1.3 * fontsize)
        # ax.legend(fontsize=12, ncol=4)

    ax.set_xlabel(r"$\lambda$ [$\mu m$]")

    ax.tick_params("both", length=10, width=2, which="major")
    ax.tick_params("both", length=5, width=1, which="minor")


if __name__ == "__main__":

    # commandline parser
    parser = argparse.ArgumentParser()
    parser.add_argument("filelist", help="file with list of curves to plot")
    parser.add_argument(
        "--rebin_fac", type=int, default=None, help="rebin factor for spectra"
    )
    parser.add_argument("--alav", help="plot A(lambda)/A(V)", action="store_true")
    parser.add_argument("--ave", help="plot the average", action="store_true")
    parser.add_argument(
        "--models", help="plot the best fit models", action="store_true"
    )
    parser.add_argument(
        "--modonly", help="only plot the best fit models", action="store_true"
    )
    parser.add_argument(
        "--prevobs", help="plot previous observations", action="store_true"
    )
    parser.add_argument(
        "--dg_models", help="plot dust grain models", action="store_true"
    )
    parser.add_argument(
        "-p", "--png", help="save figure as a png file", action="store_true"
    )
    parser.add_argument("--pdf", help="save figure as a pdf file", action="store_true")
    args = parser.parse_args()

    filename = args.filelist

    f = open(filename, "r")
    file_lines = list(f)
    extnames = []
    extdatas = []
    avs = []

    normtype = "IUE"
    norm_wave_range = [0.25, 0.30] * u.micron
    normvals = []

    for line in file_lines:
        if (line.find("#") != 0) & (len(line) > 0):
            name = line.rstrip()
            extnames.append(name)
            text = ExtData(filename="fits/%s" % name)
            extdatas.append(text)
            avs.append(text.columns["AV"][0])

            # determine the extinction in the near-UV
            # useful for sorting to make a pretty plot
            if "IUE" in text.exts.keys():
                gindxs, = np.where(
                    (text.npts[normtype] > 0)
                    & (
                        (text.waves[normtype] >= norm_wave_range[0])
                        & (text.waves[normtype] <= norm_wave_range[1])
                    )
                )
                normvals.append(
                    np.average(
                        (text.exts[normtype][gindxs]) / float(text.columns["AV"][0])
                        + 1.0
                    )
                )
            else:
                normvals.append(1.0)
        else:
            normvals.append(1.0)

    normvals = np.array(normvals)
    sindxs = np.flip(np.argsort(normvals))
    normvals = normvals[sindxs]
    extnames = np.array(extnames)[sindxs]

    extdatas = []
    avs = []

    for extname in extnames:
        text = ExtData(filename="fits/%s" % extname)
        extdatas.append(text)
        avs.append(text.columns["AV"][0])

    fontsize = 18

    font = {"size": fontsize}

    matplotlib.rc("font", **font)

    matplotlib.rc("lines", linewidth=1)
    matplotlib.rc("axes", linewidth=2)
    matplotlib.rc("xtick.major", width=2)
    matplotlib.rc("xtick.minor", width=2)
    matplotlib.rc("ytick.major", width=2)
    matplotlib.rc("ytick.minor", width=2)

    if args.alav:
        figsize = (12, 10)
    else:
        figsize = (20, 10)
    fig, ax = pyplot.subplots(nrows=1, ncols=2, figsize=figsize)

    plot_all_ext(
        ax[1],
        kxrange=[1.0, 25.0],
        kyrange=[-6.0, -0.5],
        yoffset_factor=0.1,
        annotate_key="IRS",
    )
    plot_all_ext(
        ax[0],
        kxrange=[0.115, 0.33],
        kyrange=[1.0, 10.0],
        normvals=normvals,
        yoffset_factor=0.5,
    )

    ax[1].set_ylim(-0.1, 1.75)
    ax[0].set_ylim(0.0, 9.5)
    ax[1].set_ylabel(r"$A(\lambda)/A(V) + constant$")
    ax[0].set_ylabel(r"$A(\lambda)/A(0.27~\mu m) + constant$")

    ax[1].yaxis.set_label_position("right")
    ax[1].yaxis.tick_right()

    fig.tight_layout()

    save_str = "_mext_uv_mir"
    if args.png:
        fig.savefig(args.filelist.replace(".dat", save_str + ".png"))
    elif args.pdf:
        fig.savefig(args.filelist.replace(".dat", save_str + ".pdf"))
    else:
        pyplot.show()
