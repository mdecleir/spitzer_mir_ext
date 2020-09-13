# plot to plot the silicate strength versus other properties of the sightlines

import argparse
import math
import os.path

import emcee
import numpy as np
import matplotlib.pyplot as pyplot
import matplotlib
import astropy.units as u
from astropy.table import Table
from astropy import uncertainty as unc

from measure_extinction.extdata import ExtData

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("filelist", help="file with list of curves to plot")
    parser.add_argument("--png", help="save figure as a png file", action="store_true")
    parser.add_argument("--pdf", help="save figure as a pdf file", action="store_true")
    args = parser.parse_args()

    filename = args.filelist

    mcmc_burnfrac = 0.4

    # data
    f = open(filename, "r")
    file_lines = list(f)
    extfnames = []
    extnames = []
    for line in file_lines:
        if (line.find("#") != 0) & (len(line) > 0):
            name = line.rstrip()
            extfnames.append(name)
            extnames.append(name.split("_")[0])

    # Amplitude of the feature when x = x_o (FM90) or lambda = lambda_o (P92)
    # FM90: I(x_o) = C3/(2*gamma**2)
    # P92: I(lambda_o) = a_i/(2 + b_i) = a_i/(gamma_i**2/lambda_i**2)
    # C3 = a_i * lambda_i**2 * 2.
    # PDRUDE2: amp is central intensity

    n_ext = len(extnames)
    sil_amp = np.full((n_ext), 0.0)
    sil_amp_unc = np.full((n_ext), 0.0)
    sil_width = np.full((n_ext), 0.0)
    sil_width_unc = np.full((n_ext), 0.0)
    sil_lambda = np.full((n_ext), 0.0)
    sil_lambda_unc = np.full((n_ext), 0.0)
    sil_asym = np.full((n_ext), 0.0)
    sil_asym_unc = np.full((n_ext), 0.0)
    sil_area = np.full((n_ext), 0.0)
    sil_area_unc = np.full((n_ext), 0.0)
    sil2_amp = np.full((n_ext), 0.0)
    sil2_amp_unc = np.full((n_ext), 0.0)
    sil_amp_ratio = np.full((n_ext), 0.0)
    sil_amp_ratio_unc = np.full((n_ext), 0.0)
    nuv_amp = np.full((n_ext), 0.0)
    nuv_amp_unc = np.full((n_ext), 0.0)
    nuv_lambda = np.full((n_ext), 0.0)
    nuv_lambda_unc = np.full((n_ext), 0.0)
    nuv_width = np.full((n_ext), 0.0)
    nuv_width_unc = np.full((n_ext), 0.0)
    nuv_area = np.full((n_ext), 0.0)
    nuv_area_unc = np.full((n_ext), 0.0)
    nuv_ceninten = np.full((n_ext), 0.0)
    nuv_ceninten_unc = np.full((2, n_ext), 0.0)
    avs = np.full((n_ext), 0.0)
    avs_unc = np.full((2, n_ext), 0.0)
    ebvs = np.full((n_ext), 0.0)
    ebvs_unc = np.full((n_ext), 0.0)
    rvs = np.full((n_ext), 0.0)
    rvs_unc = np.full((2, n_ext), 0.0)

    for k, cname in enumerate(extfnames):

        # get P92 fits
        bfile = f"fits/{cname}"
        cext = ExtData(filename=bfile)

        mcmcfile = bfile.replace(".fits", ".h5")
        reader = emcee.backends.HDFBackend(mcmcfile)
        nsteps, nwalkers = reader.get_log_prob().shape
        samples = reader.get_chain(discard=int(mcmc_burnfrac * nsteps), flat=True)

        avs_dist = unc.Distribution(samples[:, -1])
        av_per = avs_dist.pdf_percentiles([16.0, 50.0, 84.0])
        avs[k] = av_per[1]
        avs_unc[1, k] = av_per[2] - av_per[1]
        avs_unc[0, k] = av_per[1] - av_per[0]
        # print(avs_dist.pdf_percentiles([33., 50., 87.]))

        (indxs,) = np.where(
            (cext.waves["BAND"] > 0.4 * u.micron)
            & (cext.waves["BAND"] < 0.5 * u.micron)
        )
        ebvs_dist = unc.normal(
            cext.exts["BAND"][indxs[0]],
            std=cext.uncs["BAND"][indxs[0]],
            n_samples=avs_dist.n_samples,
        )
        ebvs[k] = ebvs_dist.pdf_mean()
        ebvs_unc[k] = ebvs_dist.pdf_std()

        rvs_dist = avs_dist / ebvs_dist
        rv_per = rvs_dist.pdf_percentiles([16.0, 50.0, 84.0])
        rvs[k] = rv_per[1]
        rvs_unc[1, k] = rv_per[2] - rv_per[1]
        rvs_unc[0, k] = rv_per[1] - rv_per[0]

        # print(np.corrcoef(np.stack([avs_dist.distribution, rvs_dist.distribution])))

        silamp_dist = unc.Distribution(samples[:, 2])
        sillam_dist = unc.Distribution(samples[:, 3])
        silwid_dist = unc.Distribution(samples[:, 4])
        silasm_dist = unc.Distribution(samples[:, 5])
        silamp2_dist = unc.Distribution(samples[:, 6])

        silampratio_dist = unc.Distribution(samples[:, 2] / samples[:, 6])

        sil_amp[k] = silamp_dist.pdf_mean()
        sil_amp_unc[k] = silamp_dist.pdf_std()
        sil_width[k] = silwid_dist.pdf_mean()
        sil_width_unc[k] = silwid_dist.pdf_std()
        sil_lambda[k] = sillam_dist.pdf_mean()
        sil_lambda_unc[k] = sillam_dist.pdf_std()
        sil_asym[k] = silasm_dist.pdf_mean()
        sil_asym_unc[k] = silasm_dist.pdf_std()

        # needs updating
        # using C3 = a_i * lambda_i**2 * 2 to be able to use the FM area formula
        # silarea_dist = math.pi * silamp_dist * (sillam_dist ** 2) / silwid_dist
        # sil_area[k] = silarea_dist.pdf_mean()
        # sil_area_unc[k] = silarea_dist.pdf_std()

        sil2_amp[k] = silamp2_dist.pdf_mean()
        sil2_amp_unc[k] = silamp2_dist.pdf_std()

        sil_amp_ratio[k] = silampratio_dist.pdf_mean()
        sil_amp_ratio_unc[k] = silampratio_dist.pdf_std()

        # get FM90 fits
        uvfname = bfile.replace(".fits", "_FM90.fits")
        if os.path.isfile(uvfname):
            cext_fm90 = ExtData(filename=uvfname)
            mcmcfile = uvfname.replace(".fits", ".h5")
            reader = emcee.backends.HDFBackend(mcmcfile)
            nsteps, nwalkers = reader.get_log_prob().shape
            samples = reader.get_chain(discard=int(mcmc_burnfrac * nsteps), flat=True)

            nuvamp_dist = unc.Distribution(samples[:, 2])
            nuvlam_dist = unc.Distribution(samples[:, 4])
            nuvwid_dist = unc.Distribution(samples[:, 5])

            nuv_amp[k] = nuvamp_dist.pdf_mean()
            nuv_amp_unc[k] = nuvamp_dist.pdf_std()
            nuv_width[k] = nuvwid_dist.pdf_mean()
            nuv_width_unc[k] = nuvwid_dist.pdf_std()
            nuv_lambda[k] = nuvlam_dist.pdf_mean()
            nuv_lambda_unc[k] = nuvlam_dist.pdf_std()

            nuvceninten_dist = nuvamp_dist / (nuvwid_dist ** 2)
            nuv_ci_per = nuvceninten_dist.pdf_percentiles([16.0, 50.0, 84.0])
            nuv_ceninten[k] = nuv_ci_per[1]
            nuv_ceninten_unc[1, k] = nuv_ci_per[2] - nuv_ci_per[1]
            nuv_ceninten_unc[0, k] = nuv_ci_per[1] - nuv_ci_per[0]

            # using C3 = a_i * lambda_i**2 * 2 to be able to use the FM area formula
            nuvarea_dist = math.pi * nuvamp_dist / (2.0 * nuvwid_dist)
            nuv_area[k] = nuvarea_dist.pdf_mean()
            nuv_area_unc[k] = nuvarea_dist.pdf_std()

    # output some info
    a = Table()
    a["name"] = extnames
    a["AV"] = avs
    a["RV"] = rvs
    a["Sil_amp"] = sil_amp
    a["Sil_width"] = sil_width
    a["Sil_area"] = sil_area
    # print(a)

    # plots
    fontsize = 14

    font = {"size": fontsize}

    matplotlib.rc("font", **font)

    matplotlib.rc("lines", linewidth=1)
    matplotlib.rc("axes", linewidth=2)
    matplotlib.rc("xtick.major", width=2)
    matplotlib.rc("xtick.minor", width=2)
    matplotlib.rc("ytick.major", width=2)
    matplotlib.rc("ytick.minor", width=2)

    figsize = (15.0, 9.0)
    fig, fax = pyplot.subplots(nrows=2, ncols=3, figsize=figsize)
    ax = [fax[1, 1], fax[0, 1], fax[0, 2], fax[0, 0], fax[1, 2], fax[1, 0]]

    diffuse = []
    for tname in extnames:
        if tname == "hd283809":
            diffuse.append(False)
        elif tname == "hd029647":
            diffuse.append(False)
        else:
            diffuse.append(True)
    diffuse = np.array(diffuse)
    dense = ~diffuse

    gooduv = nuv_amp > 0
    uvdiffuse = np.logical_and(diffuse, gooduv)
    uvdense = np.logical_and(dense, gooduv)

    # uncs are way over estimated as the amplitude and width are very well correlated
    # update once the samples are available
    # print(sil_amp_unc)

    # silicate1 lambda versus asymmetry
    ax[0].errorbar(
        sil_lambda[diffuse],
        sil_asym[diffuse],
        xerr=sil_lambda_unc[diffuse],
        yerr=sil_asym_unc[diffuse],
        fmt="go",
    )
    ax[0].errorbar(
        sil_lambda[dense],
        sil_asym[dense],
        xerr=sil_lambda_unc[dense],
        yerr=sil_asym_unc[dense],
        fmt="bo",
        markerfacecolor="none",
    )
    ax[0].set_xlabel(r"$\lambda_{o1}$ $[\mu m]$")
    ax[0].set_ylabel(r"$a_1$")
    ax[0].tick_params("both", length=10, width=2, which="major")
    ax[0].tick_params("both", length=5, width=1, which="minor")

    # R(V) versus silicate
    ax[1].errorbar(
        rvs[diffuse],
        sil_amp[diffuse],
        xerr=rvs_unc[:, diffuse],
        yerr=sil_amp_unc[diffuse],
        fmt="go",
    )
    ax[1].errorbar(
        rvs[dense],
        sil_amp[dense],
        xerr=rvs_unc[:, dense],
        yerr=sil_amp_unc[dense],
        fmt="bo",
        markerfacecolor="none",
    )
    ax[1].set_xlabel(r"$R(V)$")
    ax[1].set_ylabel(r"$A(S_1)/A(V)$")
    ax[1].tick_params("both", length=10, width=2, which="major")
    ax[1].tick_params("both", length=5, width=1, which="minor")

    # A(V) versus A(sil)/A(V)
    RA84_av = np.array([7.7, 7.0, 4.8, 13.0, 13.3, 4.0])
    RA84_tausil = np.array([0.32, 0.32, 0.24, 0.61, 0.69, 0.26])
    ax[3].plot(
        RA84_av,
        RA84_tausil / (1.086 * RA84_av),
        "kv",
        label="RA84",
        markerfacecolor="none",
    )

    RA85_av = np.array([30.0])
    RA85_av_unc = np.array([5.0])
    RA85_tausil = np.array([3.6])
    RA85_tausil_unc = np.array([0.3])
    RA85_tausilav = RA85_tausil / (1.086 * RA85_av)
    RA85_tausilav_unc = RA85_tausilav * np.sqrt(
        (RA85_tausil_unc / RA85_tausil) ** 2 + (RA85_av_unc / RA85_av) ** 2
    )
    ax[3].errorbar(
        RA85_av,
        RA85_tausilav,
        xerr=RA85_av_unc,
        yerr=RA85_tausilav_unc,
        fmt="k^",
        label="RA85",
        markerfacecolor="none",
    )

    RL85_rv = np.array([3.09])  # check both rv and rv_unc
    RL85_rv_unc = np.array([0.03])
    RL85_av = np.array([2.92, 9.65, 35.0, 27.5, 31.0, 29.0])
    RL85_tausil = np.array([0.17, 0.42, 2.8, 2.2, 2.5, 2.4])
    RL85_tausil_unc = np.array([0.03, 0.05, 0.5, 0.5, 0.5, 0.5])
    ax[3].errorbar(
        RL85_av,
        RL85_tausil / (1.086 * RL85_av),
        yerr=RL85_tausil_unc / (1.086 * RL85_av),
        fmt="ks",
        label="RL85",
        markerfacecolor="none",
    )
    CT06_tausil = np.array([0.78, 0.38, 0.63, 0.78])
    CT06_av = np.array([12.42, 6.50, 11.03, 11.20])
    ax[3].plot(
        CT06_av,
        CT06_tausil / (1.086 * CT06_av),
        "ko",
        label="CT06",
        markerfacecolor="none",
    )
    ax[3].errorbar(
        avs[diffuse],
        sil_amp[diffuse],
        xerr=avs_unc[:, diffuse],
        yerr=sil_amp_unc[diffuse],
        fmt="go",
        # label="diffuse",
    )
    ax[3].errorbar(
        avs[dense],
        sil_amp[dense],
        xerr=avs_unc[:, dense],
        yerr=sil_amp_unc[dense],
        fmt="bo",
        markerfacecolor="none",
        # label="dense",
    )
    ax[3].set_xlabel(r"$A(V)$")
    ax[3].set_ylabel(r"$A(S_1)/A(V)$")
    ax[3].set_xscale("log")
    ax[3].tick_params("both", length=10, width=2, which="major")
    ax[3].tick_params("both", length=5, width=1, which="minor")
    ax[3].legend(loc=[0.44, 0.62])

    # silicate verus 2175
    ax[2].errorbar(
        nuv_ceninten[uvdiffuse],
        sil_amp[uvdiffuse],
        xerr=nuv_ceninten_unc[:, uvdiffuse],
        yerr=sil_amp_unc[uvdiffuse],
        fmt="go",
        label="diffuse",
    )
    ax[2].errorbar(
        nuv_ceninten[uvdense],
        sil_amp[uvdense],
        xerr=nuv_ceninten_unc[:, uvdense],
        yerr=sil_amp_unc[uvdense],
        fmt="bo",
        markerfacecolor="none",
        label="dense",
    )
    ax[2].set_xlabel(r"$A(2175)/A(V)$")
    ax[2].set_ylabel(r"$A(S_1)/A(V)$")
    ax[2].tick_params("both", length=10, width=2, which="major")
    ax[2].tick_params("both", length=5, width=1, which="minor")
    ax[2].legend()

    # silicate1 verus silicate2
    ax[4].errorbar(
        sil_amp[diffuse],
        sil2_amp[diffuse],
        xerr=sil_amp_unc[diffuse],
        yerr=sil2_amp_unc[diffuse],
        fmt="go",
        label="diffuse",
    )
    ax[4].errorbar(
        sil_amp[dense],
        sil2_amp[dense],
        xerr=sil_amp_unc[dense],
        yerr=sil2_amp_unc[dense],
        fmt="bo",
        markerfacecolor="none",
        label="dense",
    )
    ax[4].set_xlabel(r"$A(S_1)/A(V)$")
    ax[4].set_ylabel(r"$A(S_2)/A(V)$")
    ax[4].tick_params("both", length=10, width=2, which="major")
    ax[4].tick_params("both", length=5, width=1, which="minor")
    ax[4].set_ylim(0.0, 0.05)

    # silicate1 lambda versus asymmetry
    ax[5].errorbar(
        sil_lambda[diffuse],
        sil_width[diffuse],
        xerr=sil_lambda_unc[diffuse],
        yerr=sil_width_unc[diffuse],
        fmt="go",
    )
    ax[5].errorbar(
        sil_lambda[dense],
        sil_width[dense],
        xerr=sil_lambda_unc[dense],
        yerr=sil_width_unc[dense],
        fmt="bo",
        markerfacecolor="none",
    )
    ax[5].set_xlabel(r"$\lambda_{o1}$ $[\mu m]$")
    ax[5].set_ylabel(r"$\gamma_{o1}$ $[\mu m]$")
    ax[5].tick_params("both", length=10, width=2, which="major")
    ax[5].tick_params("both", length=5, width=1, which="minor")

    fig.tight_layout()

    save_str = "_silicate"
    if args.png:
        fig.savefig(args.filelist.replace(".dat", save_str + ".png"))
    elif args.pdf:
        fig.savefig(args.filelist.replace(".dat", save_str + ".pdf"))
    else:
        pyplot.show()
