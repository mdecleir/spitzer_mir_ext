import argparse
import warnings
import matplotlib.pyplot as plt
import matplotlib
import numpy as np

import emcee
import corner

import astropy.units as u
from astropy.modeling.fitting import LevMarLSQFitter
from astropy.modeling import Fittable1DModel, Parameter
from astropy.modeling.models import Polynomial1D, Gaussian1D

from dust_extinction.conversions import AxAvToExv
from measure_extinction.stardata import StarData
from measure_extinction.extdata import ExtData


class Drude1D(Fittable1DModel):
    """
    Drude model based one the behavior of electons in materials (esp. metals).

    Parameters
    ----------
    amplitude : float
        Peak value
    x_0 : float
        Position of the peak
    fwhm : float
        Full width at half maximum

    Model formula:

        .. math:: f(x) = A \\frac{(fwhm/x_0)^2}{((x/x_0 - x_0/x)^2 + (fwhm/x_0)^2}

    Examples
    --------

    .. plot::
        :include-source:

        import numpy as np
        import matplotlib.pyplot as plt

        from astropy.modeling.models import Drude1D

        fig, ax = plt.subplots()

        # generate the curves and plot them
        x = np.arange(7.5 , 12.5 , 0.1)

        dmodel = Drude1D(amplitude=1.0, fwhm=1.0, x_0=10.0)
        ax.plot(x, dmodel(x))

        ax.set_xlabel('x')
        ax.set_ylabel('F(x)')

        ax.legend(loc='best')
        plt.show()
    """

    amplitude = Parameter(default=1.0)
    x_0 = Parameter(default=1.0)
    fwhm = Parameter(default=1.0)

    @staticmethod
    def evaluate(x, amplitude, x_0, fwhm):
        """
        One dimensional Drude model function
        """
        return (
            amplitude
            * ((fwhm / x_0) ** 2)
            / ((x / x_0 - x_0 / x) ** 2 + (fwhm / x_0) ** 2)
        )

    @staticmethod
    def fit_deriv(x, amplitude, x_0, fwhm):
        """
        Drude1D model function derivatives.
        """
        d_amplitude = (fwhm / x_0) ** 2 / ((x / x_0 - x_0 / x) ** 2 + (fwhm / x_0) ** 2)
        d_x_0 = (
            -2
            * amplitude
            * d_amplitude
            * (
                (1 / x_0)
                + d_amplitude
                * (x_0 ** 2 / fwhm ** 2)
                * (
                    (-x / x_0 - 1 / x) * (x / x_0 - x_0 / x)
                    - (2 * fwhm ** 2 / x_0 ** 3)
                )
            )
        )
        d_fwhm = (2 * amplitude * d_amplitude / fwhm) * (1 - d_amplitude)
        return [d_amplitude, d_x_0, d_fwhm]

    @property
    def input_units(self):
        if self.x_0.unit is None:
            return None
        else:
            return {"x": self.x_0.unit}

    def _parameter_units_for_data_units(self, inputs_unit, outputs_unit):
        return {
            "x_0": inputs_unit["x"],
            "fwhm": inputs_unit["x"],
            "amplitude": outputs_unit["y"],
        }

    @property
    def return_units(self):
        if self.amplitude.unit is None:
            return None
        else:
            return {'y': self.amplitude.unit}

    @x_0.validator
    def x_0(self, val):
        if val == 0:
            raise InputParameterError("0 is not an allowed value for x_0")

    def bounding_box(self, factor=50):
        """Tuple defining the default ``bounding_box`` limits,
        ``(x_low, x_high)``.

        Parameters
        ----------
        factor : float
            The multiple of FWHM used to define the limits.
        """
        x0 = self.x_0
        dx = factor * self.fwhm

        return (x0 - dx, x0 + dx)


def lnprob(params, x, y, uncs, model, param_names):
    """
    Log likelihood

    Parameters
    ----------
    params : array of floats
        parameters for evaluting the model

    x, y, uncs : array
        x, y, and y uncertainties for the data

    model : astropy model
        model for evaluation

    param_name : array of str
        names of the model parameters to update based on params
        should not include any fixed parameters
    """
    # param_dict = dict(zip(model.param_names, model.parameters))
    for k, cname in enumerate(param_names):
        # impose the bounds
        if model.bounds[cname][0] is not None:
            if params[k] < model.bounds[cname][0]:
                return -np.inf
        if model.bounds[cname][1] is not None:
            if params[k] > model.bounds[cname][1]:
                return -np.inf
        # otherwise, set the requested value
        exec("model.{}.value = {}".format(cname, params[k]))
    return -0.5 * np.sum(((model(x) - y) / uncs) ** 2)


def get_best_fit_params(sampler):
    """
    Get the best fit parameters from all the walkers

    Parameters
    ----------
    sample : emcee sampler object

    Returns
    -------
    fit_params_best : array of floats
        parameters of the best fit (largest likelihood sample)
    """
    max_lnp = -1e32
    nwalkers = len(sampler.lnprobability)
    fit_params_best = None
    for k in range(nwalkers):
        tmax_lnp = np.max(sampler.lnprobability[k])
        if tmax_lnp > max_lnp:
            max_lnp = tmax_lnp
            indxs, = np.where(sampler.lnprobability[k] == tmax_lnp)
            fit_params_best = sampler.chain[k, indxs[0], :]
    return fit_params_best


def p92_emcee(
    x,
    y,
    uncs,
    model,
    fit_param_names=None,
    threads=1,
    return_sampler=False,
    nburn=100,
    nsteps=500,
):
    """
    Fit the model using the emcee MCMC sampler

    Parameters
    ----------
    x, y, uncs : array
        x, y, and y uncertainties for the data

    model : astropy model
        model to fit
        starting position taken from model paramter values

    fit_param_names : list of string, optional
        list of parameters to fit
        default is to fit all non-fixed parameters

    threads : int
        number of threads to use for MCMC run

    nburn : int
        number of steps for the MCMC burn in

    nsteps : int
        number of steps for the MCMC sampling

    return_sampler: booelean
        return emcee sampler, return is now (best_fit_model, sampler)
    """

    model_copy = model.copy()

    # get a list of non-fixed parameters
    if fit_param_names is None:
        fit_param_names = []
        for cname in model_copy.param_names:
            if not model_copy.fixed[cname]:
                fit_param_names.append(cname)

    # sampler setup
    ndim = len(fit_param_names)
    nwalkers = 10 * ndim

    # needed for priors
    # model_copy.bounds

    # inital guesses at parameters
    p0_list = []
    param_dict = dict(zip(model_copy.param_names, model_copy.parameters))
    for cname in fit_param_names:
        p0_list.append(param_dict[cname])
    p0 = np.array(p0_list)

    # check if any parameters are zero and make them sligthly larger
    p0[p0 == 0.0] = 2.4e-3

    # print(fit_param_names)
    # print(p0)

    # setting up the walkers to start "near" the inital guess
    p = [p0 * (1 + 1e-4 * np.random.normal(0, 1.0, ndim)) for k in range(nwalkers)]

    # for the parameters with min/max bounds set ("good priors")
    # sample from the prior
    #    for k, cname in enumerate(fit_param_names):
    #        if ((model.bounds[cname][0] is not None)
    #                & (model.bounds[cname][1] is not None)):
    #            svals = np.random.uniform(model.bounds[cname][0],
    #                                      model.bounds[cname][1],
    #                                      nwalkers)
    #            for i in range(nwalkers):
    #                p[i][k] = svals[i]
    #            print(p)

    # ensure all the walkers start within the bounds
    param_dict = dict(zip(model.param_names, model.parameters))
    for cp in p:
        for k, cname in enumerate(fit_param_names):
            # check the bounds
            if model.bounds[cname][0] is not None:
                if cp[k] < model.bounds[cname][0]:
                    cp[k] = model.bounds[cname][0]
                    # print('min: ', cname, cp[k])
            if model.bounds[cname][1] is not None:
                if cp[k] > model.bounds[cname][1]:
                    cp[k] = model.bounds[cname][1]
                    # print('max: ', cname, cp[k])

    # setup the sampler
    sampler = emcee.EnsembleSampler(
        nwalkers,
        ndim,
        lnprob,
        threads=threads,
        args=(x, y, uncs, model_copy, fit_param_names),
    )

    if nburn is not None:
        # burn in the walkers
        pos, prob, state = sampler.run_mcmc(p, nburn)
        # rest the sampler
        sampler.reset()

    # do the full sampling
    pos, prob, state = sampler.run_mcmc(pos, nsteps, rstate0=state)

    # best fit parameters
    best_params = get_best_fit_params(sampler)

    # percentile parameters
    samples = sampler.chain.reshape((-1, ndim))
    per_params = [
        (v[1], v[2] - v[1], v[1] - v[0])
        for v in zip(*np.percentile(samples, [16, 50, 84], axis=0))
    ]

    # set the returned model parameters to the best fit values
    for k, val in enumerate(per_params):
        exec("model_copy.{}.value = {}".format(fit_param_names[k], best_params[k]))
        print(fit_param_names[k], best_params[k], val)

    clean_pnames = [pname[:-2] for pname in fit_param_names]
    model_copy.p92_emcee_param_names = clean_pnames
    model_copy.p92_emcee_per_params = per_params

    if return_sampler:
        return (model_copy, sampler)
    else:
        return model_copy


def plot_emcee_results(sampler, fit_param_names, filebase=""):
    """
    Plot the standard triangle and diagnostic walker plots
    """

    # plot the walker chains for all parameters
    nwalkers, nsteps, ndim = sampler.chain.shape
    fig, ax = plt.subplots(ndim, sharex=True, figsize=(13, 13))
    walk_val = np.arange(nsteps)
    for i in range(ndim):
        for k in range(nwalkers):
            ax[i].plot(walk_val, sampler.chain[k, :, i], "-")
            ax[i].set_ylabel(fit_param_names[i])
    fig.savefig("%s_walker_param_values.png" % filebase)
    plt.close(fig)

    # plot the 1D and 2D likelihood functions in a traditional triangle plot
    samples = sampler.chain.reshape((-1, ndim))
    fig = corner.corner(
        samples,
        labels=fit_param_names,
        show_titles=True,
        title_fmt=".3f",
        use_math_text=True,
    )
    fig.savefig("%s_param_triangle.png" % filebase)
    plt.close(fig)


if __name__ == "__main__":

    # commandline parser
    parser = argparse.ArgumentParser()
    parser.add_argument("redstarname", help="name of reddened star")
    parser.add_argument("compstarname", help="name of comparision star")
    parser.add_argument(
        "--path",
        help="base path to observed data",
        default="/home/kgordon/Python_git/extstar_data/",
    )
    parser.add_argument("--emcee", help="run EMCEE fit", action="store_true")
    parser.add_argument(
        "--nburn", type=int, default=100, help="# of burn steps in MCMC chain"
    )
    parser.add_argument(
        "--nsteps", type=int, default=500, help="# of steps in MCMC chain"
    )
    parser.add_argument(
        "--threads", type=int, default=1, help="number of threads for EMCEE run"
    )
    parser.add_argument("--png", help="save figure as a png file", action="store_true")
    parser.add_argument("--pdf", help="save figure as a pdf file", action="store_true")
    args = parser.parse_args()

    # read in the observed data for both stars
    redstarobs = StarData("DAT_files/%s.dat" % args.redstarname, path=args.path)
    compstarobs = StarData("DAT_files/%s.dat" % args.compstarname, path=args.path)

    # output filebase
    filebase = "fits/%s_%s" % (args.redstarname, args.compstarname)

    # calculate the extinction curve
    extdata = ExtData()
    extdata.calc_elx(redstarobs, compstarobs)

    # get an observed extinction curve to fit
    (wave, y, y_unc) = extdata.get_fitdata(
        ["BAND", "IUE", "IRS"], remove_uvwind_region=True, remove_lya_region=True
    )
    # remove units as fitting routines often cannot take numbers with units
    x = wave.to(1.0 / u.micron, equivalencies=u.spectral()).value

    # determine the initial guess at the A(V) values
    #  just use the average at wavelengths > 5
    #  limit as lambda -> inf, E(lamda-V) -> -A(V)
    indxs, = np.where(1.0 / x > 5.0)
    av_guess = -1.0 * np.average(y[indxs])
    if not np.isfinite(av_guess):
        av_guess = 1.0

    # initialize the model
    #    a few tweaks to the starting parameters helps find the solution

    ponly = (
        Polynomial1D(degree=5, c0=0.0, fixed={"c0": True})
        + Drude1D(amplitude=30.0, x_0=13.5, fwhm=2.0,
                  fixed={"x_0": True, "fwhm": True},
                  bounds={"amplitude": [10.0, None], "x_0": [13.0, 14.0], "fwhm": [0.5, 40.5]})
        + Drude1D(amplitude=1.0, x_0=4.6, fwhm=1.0,
                  bounds={"amplitude": [0.0, 10.0], "x_0": [4.4, 4.8], "fwhm": [0.5, 1.5]})
        + Drude1D(amplitude=0.1, x_0=0.1, fwhm=0.1,
                  bounds={"amplitude": [0.01, None], "x_0": [1./12., 1./8.], "fwhm": [0.01, 0.5]})
        + Drude1D(amplitude=1.0, x_0=1.0/20.0, fwhm=0.05,
                  bounds={"amplitude": [0.01, None], "x_0": [1.0/22., 1.0/17.], "fwhm": [0.001, 0.05]})
    #    + Gaussian1D(amplitude=1.0, mean=4.6, stddev=1.0,
    #        bounds={"amplitude": [0.0, 10.0], "mean": [4.5, 4.7], "stddev": [0.5, 1.5]})
    ) | AxAvToExv(Av=av_guess)

    ponly.c1_0 = 2.0
    ponly.c2_0 = 3.0

    # pick the fitter
    fit = LevMarLSQFitter()

    # fit the data to the P92 model using the fitter
    # p92_fit = fit(p92_init, x, y, weights=1.0 / y_unc, maxiter=1000)
    p92_fit = fit(ponly, x, y, weights=1.0 / y_unc, maxiter=1000)

    for k, cur_pname in enumerate(p92_fit.param_names):
        print("{:12} {:6.4e}".format(cur_pname, p92_fit.parameters[k]))

    best_fit_Av = p92_fit.parameters[-1]
    print(best_fit_Av)

    # plotting setup for easier to read plots
    fontsize = 18
    font = {"size": fontsize}
    matplotlib.rc("font", **font)
    matplotlib.rc("lines", linewidth=1)
    matplotlib.rc("axes", linewidth=2)
    matplotlib.rc("xtick.major", width=2)
    matplotlib.rc("xtick.minor", width=2)
    matplotlib.rc("ytick.major", width=2)
    matplotlib.rc("ytick.minor", width=2)

    # setup the plot
    fig, ax = plt.subplots(figsize=(12, 8))

    # subplot
    ax2 = plt.axes([0.60, 0.35, 0.35, 0.35])

    # plot the bands and all spectra for this star
    extdata.plot(ax, color="k", alpha=0.5)
    extdata.plot(ax2, color="k", alpha=0.5)

    # ax.plot(1.0 / x, p92_init(x), "r--", label="P92 Init")
    ax.plot(1.0 / x, p92_fit(x), "r-", label="P92 Best Fit")
    ax2.plot(1.0 / x, p92_fit(x), "r-")

    # finish configuring the plot
    ax.set_yscale("linear")
    ax.set_xscale("log")
    ax.set_xlabel(r"$\lambda$ [$\mu m$]", fontsize=1.3 * fontsize)
    ax.set_ylabel(extdata._get_ext_ytitle(extdata.type), fontsize=1.3 * fontsize)
    ax.tick_params("both", length=10, width=2, which="major")
    ax.tick_params("both", length=5, width=1, which="minor")
    ax.legend()

    # finish configuring the subplot
    sp_xlim = [2.0, 35.0]
    ax2.set_xlim(sp_xlim)
    # ax2.set_ylim(-best_fit_Av-0.1, -best_fit_Av+0.5)
    indxs, = np.where((x > 1.0 / sp_xlim[1]) & (x < 1.0 / sp_xlim[0]))
    ax2.set_ylim(
        min([min(p92_fit(x)[indxs]), -best_fit_Av]) - 0.1, max(p92_fit(x)[indxs]) + 0.1
    )

    # use the whitespace better
    warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")
    fig.tight_layout()

    # plot or save to a file
    outname = "%s_ext" % filebase
    if args.png:
        fig.savefig(outname + ".png")
    elif args.pdf:
        fig.savefig(outname + ".pdf")
    else:
        plt.show()