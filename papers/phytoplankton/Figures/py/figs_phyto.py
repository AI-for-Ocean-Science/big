""" Figs for Gordon Analyses """
import os, sys

import numpy as np

from scipy.optimize import curve_fit
import pandas


from matplotlib import pyplot as plt
import matplotlib as mpl
import matplotlib.gridspec as gridspec
mpl.rcParams['font.family'] = 'stixgeneral'

import seaborn as sns

import corner

from oceancolor.utils import plotting 
from oceancolor.water import absorption
from oceancolor.hydrolight import loisel23

from boring import plotting as boring_plot
from boring.models import utils as model_utils
#from boring.models import anw as boring_anw
#from boring.models import bbnw as boring_bbnw
#from boring import chisq_fit
#from boring import stats as boring_stats

# Local
sys.path.append(os.path.abspath("../Analysis/py"))
import anly_utils

from IPython import embed

def gen_cb(img, lbl, csz = 17.):
    cbaxes = plt.colorbar(img, pad=0., fraction=0.030)
    cbaxes.set_label(lbl, fontsize=csz)
    cbaxes.ax.tick_params(labelsize=csz)

def fig_u(outfile='fig_u.png'):
    """
    Generate a figure showing the relationship between u (backscattering ratio) and rrs (remote sensing reflectance).

    Parameters:
        outfile (str): The filename of the output figure (default: 'fig_u.png')

    """
    # Load
    ds = loisel23.load_ds(4,0)
    # Unpack
    wave = ds.Lambda.data
    Rrs = ds.Rrs.data
    a = ds.a.data
    bb = ds.bb.data
    # u
    u = bb / (a+bb)
    # rrs
    A, B = 0.52, 1.17
    rrs = Rrs / (A + B*Rrs)
    # Select wavelengths
    i370 = np.argmin(np.abs(wave-370.))
    i440 = np.argmin(np.abs(wave-440.))
    i500 = np.argmin(np.abs(wave-500.))
    i600 = np.argmin(np.abs(wave-600.))

    # Gordon
    G1, G2 = 0.0949, 0.0794  # Gordon

    def rrs_func(uval, G1, G2):
        rrs = G1*uval + G2*uval**2
        return rrs

    # GIOP
    uval = np.linspace(0., 0.25, 1000)
    rrs_GIOP = rrs_func(uval, G1, G2)
    Rrs_GIOP = A*rrs_GIOP / (1 - B*rrs_GIOP)

    # Fit
    save_ans = []
    for ii in [i370, i440, i500, i600]:
        ans, cov = curve_fit(rrs_func, u[:,ii], rrs[:,ii], p0=[0.1, 0.1], sigma=np.ones_like(u[:,ii])*0.0003)
        save_ans.append(ans)

    #
    fig = plt.figure(figsize=(8,5))

    plt.clf()
    ax = plt.gca()
    for lbl, clr, idx, ans in zip(['370nm', '440nm', '500nm', '600nm'],
                                ['purple', 'b','g', 'r'],
                                [i370, i440, i500, i600],
                                save_ans):
        ax.scatter(u[:,idx], rrs[:,idx], color=clr, s=1., label=r'$\lambda = $'+lbl)
        irrs = rrs_func(u[:,idx], ans[0], ans[1])
        usrt = np.argsort(u[:,idx])
        ax.plot(u[usrt,idx], irrs[usrt], '-', color=clr, 
                label=r'Fit: $G_1='+f'{ans[0]:0.2f},'+r'G_2='+f'{ans[1]:0.2f}'+r'$')

    # GIOP
    ax.plot(uval, rrs_GIOP, 'k--', label='Gordon')
    #
    ax.set_xlabel(r'$u(\lambda)$')
    ax.set_ylabel(r'$r_{\rm rs} (\lambda)$')
    ax.legend(fontsize=11)
    plotting.set_fontsize(ax, 15.)
    
    #
    #plt.tight_layout()#pad=0.0, h_pad=0.0, w_pad=0.3)
    plt.savefig(outfile, dpi=300)
    print(f"Saved: {outfile}")


def fig_Kd(outfile='fig_Kd.png'):
    """
    Generate a figure showing the relationship between Kd
    and IOPs

    Parameters:
        outfile (str): The filename of the output figure (default: 'fig_u.png')

    """
    def lee2002_func(a, bb, thetas=0.):
        Kd_lee = (1+0.005*thetas)*a + 4.18 * (1-0.52*np.exp(-10.8*a))*bb
        return Kd_lee

    # Load
    ds = loisel23.load_ds(4,0)
    ds_profile = loisel23.load_ds(4,0, profile=True)

    # Unpack
    wave = ds.Lambda.data
    Rrs = ds.Rrs.data
    a = ds.a.data
    bb = ds.bb.data
    aph = ds.aph.data

    Kd = ds_profile.KEd_z[1,:,:]
    #xscat = a[:,idx] + 4.18 * (1-0.52*np.exp(-10.8*a[:,idx]))*bb[:,idx]
    xscat = a + 4.18 * (1-0.52*np.exp(-10.8*a))*bb
    sclr = np.outer(np.ones(Rrs.shape[0]), wave)


    # Select wavelengths
    i370 = np.argmin(np.abs(wave-370.))
    i440 = np.argmin(np.abs(wave-440.))
    i500 = np.argmin(np.abs(wave-500.))
    i600 = np.argmin(np.abs(wave-600.))

    Chl = aph[:,i440] / 0.05582

    # Calculate Kd

    #
    fig = plt.figure(figsize=(7,5))

    plt.clf()
    ax = plt.gca()

    sc = ax.scatter(xscat, Kd, c=sclr, s=1., cmap='jet')
    gen_cb(sc, 'Wavelength (nm)')

    #
    ax.set_xlabel(r'Lee+2002 $K_d(a,b_b)$ ordinate')
    ax.set_ylabel(r'$K_d$')
    #ax.legend(fontsize=12)

    # Add a 1-1 line using the axis limits
    axlim = ax.get_xlim()
    ax.plot(axlim, axlim, 'k--')


    plotting.set_fontsize(ax, 15.)
    #
    plt.tight_layout()#pad=0.0, h_pad=0.0, w_pad=0.3)
    plt.savefig(outfile, dpi=300)
    print(f"Saved: {outfile}")


# ############################################################
def fig_mcmc_fit(model_names:list, idx:int=170, chain_file=None,
                 outroot='fig_BORING_fit', show_bbnw:bool=True,
                 add_noise:bool=False, log_Rrs:bool=False,
                 full_LM:bool=True,
                 MODIS:bool=False,
                 PACE:bool=False,
                 show_trueRrs:bool=False, 
                 max_wave:float=None,
                 use_LM:bool=False,
                 set_abblim:bool=True, scl_noise:float=0.02): 

    # Load the fits
    chain_file, noises, noise_lbl = anly_utils.get_chain_file(
        model_names, scl_noise, add_noise, idx, use_LM=use_LM,
        full_LM=full_LM, MODIS=MODIS, PACE=PACE)
    print(f'Loading: {chain_file}')
    d = np.load(chain_file)

    # Data
    odict = anly_utils.prep_l23_data(idx, scl_noise=scl_noise,
                                     max_wave=max_wave)
    #embed(header='figs 167')

    # Prep 
    model_wave = d['wave']
    models = model_utils.init(model_names, model_wave)

    # Outfile
    outfile = outroot + f'_{model_names[0]}{model_names[1]}_{idx}_{noise_lbl}{noises}.png'
    if use_LM:
        outfile = outfile.replace('BORING', 'BORING_LM')

    # Inputs
    params = d['ans'] if use_LM else d['chains']
    a_params = d['Chl']
    bb_params = d['Y']
    if full_LM:
        params = params[idx]
        a_params = a_params[idx]
        bb_params = bb_params[idx]
            
    axes = boring_plot.show_fit(
        models, params,
        ex_a_params=a_params, ex_bb_params=bb_params,
        Rrs_true=dict(wave=odict['wave'], spec=odict['gordon_Rrs']),
        anw_true=dict(wave=odict['true_wave'], spec=odict['anw']),
        bbnw_true=dict(wave=odict['true_wave'], spec=odict['bbnw']),
        )
    
    plt.tight_layout()#pad=0.0, h_pad=0.0, w_pad=0.3)
    plt.savefig(outfile, dpi=300)
    print(f"Saved: {outfile}")


# ############################################################
def fig_multi_fits(models:list=None, 
                   indices:list=None, 
                   min_wave:float=400.,
                   max_wave:float=700.,
                 outroot='fig_multi_fits'): 

    if models is None:
        models = [('Cst','Cst'), ('Exp','Cst'), ('Exp','Pow'), ('ExpBricaud','Pow')]
    if indices is None:
        indices = [170, 1032]
    outfile = outroot + f'_{indices[0]}_{indices[1]}.png'

    fig = plt.figure(figsize=(12,6))
    plt.clf()
    gs = gridspec.GridSpec(2,3)

    compare_models(models, indices[0], 
                   [plt.subplot(gs[0]), plt.subplot(gs[1]), 
                    plt.subplot(gs[2])],
                   lbl_wavelengths=False,
                   min_wave=min_wave, max_wave=max_wave)
    compare_models(models, indices[1], 
                   [plt.subplot(gs[3]), plt.subplot(gs[4]), 
                    plt.subplot(gs[5])],
                    min_wave=min_wave, max_wave=max_wave)

    plt.tight_layout()#pad=0.0, h_pad=0.0, w_pad=0.3)
    plt.savefig(outfile, dpi=300)
    print(f"Saved: {outfile}")

def compare_models(models:list, idx:int, axes:list, 
                   min_wave:float=None, max_wave:float=None,
                   add_noise:bool=False, scl_noise:float=None,
                   log_Rrs:bool=True, lbl_wavelengths:bool=True,
                   use_LM:bool=True, full_LM:bool=True):

    # Loop on models
    for ss, clr, model_names in zip(
        range(len(models)), ['r', 'g', 'b', 'orange'], models):


        rdict = anly_utils.recon_one(
            model_names, idx, 
            scl_noise=scl_noise, add_noise=add_noise, use_LM=use_LM,
            full_LM=full_LM, min_wave=min_wave, max_wave=max_wave)
        # Unpack what we need
        noise_lbl = rdict['noise_lbl']
        noises = rdict['noises']
        wave_true = rdict['wave_true']
        Rrs_true = rdict['Rrs_true']
        a_true = rdict['a_true']
        a_mean = rdict['a_mean']
        bb_true = rdict['bb_true']
        aw = rdict['aw']
        adg = rdict['adg']
        aph = rdict['aph']
        aw_interp = rdict['aw_interp']
        wave = rdict['wave']
        bbw = rdict['bbw']
        bbnw = rdict['bbnw']
        bb_mean = rdict['bb_mean']
        gordon_Rrs = rdict['gordon_Rrs']
        model_Rrs = rdict['model_Rrs']
        models = [rdict['anw_model'], rdict['bbnw_model']]

        nparm = models[0].nparam + models[1].nparam

        # #########################################################
        # a without water

        ax_anw = axes[1]
        if ss == 0:
            ax_anw.plot(wave_true, a_true-aw, 'ko', label='True', zorder=1)
            ax_anw.set_ylabel(r'$a_{\rm nw}(\lambda) \; [{\rm m}^{-1}]$')

        ax_anw.plot(wave, a_mean-aw, clr, label='Retreival')


        # #########################################################
        # b
        use_bbw = bbw
        ax_bb = axes[2]
        if ss == 0:
            ax_bb.plot(wave_true, bbnw, 'ko', label='True')
            ax_bb.set_ylabel(r'$b_{b,nw} (\lambda) \; [{\rm m}^{-1}]$')
        ax_bb.plot(wave, bb_mean-use_bbw, '-', color=clr, label='Retrieval')

        # #########################################################
        # Rs
        ax_R = axes[0]
        if ss == 0:
            ax_R.plot(wave, gordon_Rrs, 'k+', label='True')
            ax_R.set_ylabel(r'$R_{rs}(\lambda) \; [{\rm sr}^{-1}$]')
            lgsz = 11.
            if log_Rrs:
                ax_R.set_yscale('log')
            else:
                ax_R.set_ylim(bottom=0., top=1.1*Rrs_true.max())
        ax_R.plot(wave, model_Rrs, '-', color=clr, label=f'[k={nparm}]', zorder=10)
        ax_R.legend(fontsize=lgsz, loc='lower left')

        rel_err = np.abs(model_Rrs - gordon_Rrs) / gordon_Rrs
        print(f"Model {model_names}: {rel_err.mean():0.3f} {rel_err.max():0.3f}")
        
    # axes
    for ss, ax in enumerate(axes):
        plotting.set_fontsize(ax, 14)
        if lbl_wavelengths:
            ax.set_xlabel('Wavelength (nm)')
        else:
            ax.tick_params(labelbottom=False)  # Hide x-axis labels



def fig_corner(model, outroot:str='fig_gordon_corner', idx:int=170,
        scl_noise:float=None,
        add_noise:bool=False): 

    chain_file, noises, noise_lbl = get_chain_file(model, scl_noise, add_noise, idx)
    d_chains = inf_io.load_chains(chain_file)

    # Outfile
    outfile = outroot + f'_{model}_{idx}_{noise_lbl}{noises}.png'

    burn = 7000
    thin = 1
    chains = d_chains['chains']
    coeff = 10**(chains[burn::thin, :, :].reshape(-1, chains.shape[-1]))

    if model == 'hybpow':
        clbls = ['H0', 'g', 'H1', 'H2', 'B1', 'b']
    elif model == 'exppow':
        clbls = ['Adg', 'g', 'Bnw', 'bnw']
    elif model == 'hybnmf':
        clbls = ['H0', 'g', 'H1', 'H2', 'B1', 'B2']
    elif model == 'giop+':
        clbls = ['Adg', 'Sdg', 'Aph', 'Bnw', 'beta']
    else:
        clbls = None

    fig = corner.corner(
        coeff, labels=clbls,
        label_kwargs={'fontsize':17},
        color='k',
        #axes_scale='log',
        #truths=truths,
        show_titles=True,
        title_kwargs={"fontsize": 12},
        )

    plt.tight_layout()#pad=0.0, h_pad=0.0, w_pad=0.3)
    plt.savefig(outfile, dpi=300)
    print(f"Saved: {outfile}")

# ############################################################
def fig_chi2_model(model:str, idx:int=170, chain_file=None, 
                   low_wv=500., 
                   outroot='fig_chi2_model', show_bbnw:bool=False,
                 set_abblim:bool=True, scl_noise:float=None,
                 add_noise:bool=False): 

    # Outfile
    outfile = outroot + f'_{model}_{idx}.png'

    chain_file, noises, noise_lbl = get_chain_file(model, scl_noise, add_noise, idx)
    d_chains = inf_io.load_chains(chain_file)

    # Load the data
    odict = gordon.prep_data(idx)
    wave = odict['wave']
    Rrs = odict['Rrs']
    varRrs = odict['varRrs']
    a_true = odict['a']
    bb_true = odict['bb']
    aw = odict['aw']
    bbw = odict['bbw']
    bbnw = bb_true - bbw
    wave_true = odict['true_wave']
    Rrs_true = odict['true_Rrs']

    gordon_Rrs = fgordon.calc_Rrs(odict['a'][::2], odict['bb'][::2])

    # Interpolate
    aw_interp = np.interp(wave, wave_true, aw)
    bbw_interp = np.interp(wave, wave_true, bbw)

    # Reconstruc
    pdict = fgordon.init_mcmc(model, d_chains['chains'].shape[-1], 
                              wave, Y=odict['Y'], Chl=odict['Chl'])
    a_mean, bb_mean, a_5, a_95, bb_5, bb_95,\
        model_Rrs, sigRs = gordon.reconstruct(
        model, d_chains['chains'], pdict) 

    # Low wave
    ilow = np.argmin(np.abs(wave - low_wv))

    # Calcualte chi^2
    nparm = fgordon.grab_priors(model).shape[0]
    red_chi2s = []
    red_chi2s_low = []
    sigs = [1, 2., 3, 5, 7, 10, 15, 20, 30]
    for scl_sig in sigs:
        chi2 = ((model_Rrs - gordon_Rrs) / ((scl_sig/100.) * gordon_Rrs))**2
        reduced_chi2 = np.sum(chi2) / (len(gordon_Rrs) - nparm)
        red_chi2s.append(reduced_chi2)
        # Low
        reduced_chi2_low = np.sum(chi2[:ilow]) / (ilow - nparm)
        red_chi2s_low.append(reduced_chi2_low)
        

    fig = plt.figure(figsize=(8,8))
    plt.clf()
    gs = gridspec.GridSpec(1,1)

    ax = plt.subplot(gs[0])

    ax.plot(sigs, red_chi2s, 'ko-', label='Full')

    ax.plot(sigs, red_chi2s_low, 'bo-', label=r'$\lambda < '+f'{int(low_wv)}'+r'$ nm')

    ax.set_xlabel(r'$100 \, \sigma_{R_{rs}} / R_{rs}$')
    ax.set_ylabel(r'$\chi^2_{\nu}$')

    # Horizontal line at 1.
    ax.axhline(1, color='r', linestyle='--')

    # Add model as text
    ax.text(0.1, 0.1, model+f': idx={idx}', fontsize=15, transform=ax.transAxes,
            ha='left')

    # Log scale y-axis
    ax.set_xscale('log')
    ax.set_yscale('log')

    # Vertical line at 5%
    ax.axvline(5, color='k', linestyle=':')

    # Grid me
    ax.grid(True)
    ax.legend(fontsize=14)

    plotting.set_fontsize(ax, 15)

    #plt.tight_layout()#pad=0.0, h_pad=0.0, w_pad=0.3)
    plt.savefig(outfile, dpi=300)
    print(f"Saved: {outfile}")

# ############################################################
def fig_spectra(idx:int, 
                 outroot='fig_spectra_', 
                 show_acomps:bool=False,
                 bbscl:float=20):

    # Outfile
    outfile = outroot + f'{idx}.png'

    # 
    odict = anly_utils.prep_l23_data(idx)
    wave = odict['true_wave']
    a = odict['a']
    aw = odict['aw']
    anw = odict['anw']
    aph = odict['aph']
    adg = odict['adg']
    bb = odict['bb']
    bbw = odict['bbw']
    bbnw = odict['bb'] - bbw

    #
    fig = plt.figure(figsize=(9,5))
    ax = plt.gca()
    # a
    ax.plot(wave, a, 'k-', label=r'$a$', zorder=1)

    ax.plot(wave, aw, 'b-', label=r'$a_w$', zorder=1)
    ax.plot(wave, anw, 'r-', label=r'$a_{nw}$', zorder=1)
    if show_acomps:
        ax.plot(wave, aph, 'g-', label=r'$a_{ph}$', zorder=1)
        ax.plot(wave, adg, '-', color='brown', label=r'$a_{dg}$', zorder=1)

    # bb
    ax.plot(wave, bb, ':', color='k', label=r'$b_{b}$', zorder=1)

    ax.plot(wave, bbscl*bbw, ':', color='blue', label=f'{bbscl}*'+r'$b_{b,w}$', zorder=1)
    ax.plot(wave, bbscl*bbnw, ':', color='red', label=f'{bbscl}*'+r'$b_{b,nw}$', zorder=1)

    #
    # Legend filled white
    ax.legend(fontsize=13., loc='upper right', 
              frameon=True, facecolor='white')

    ax.set_xlabel('Wavelength (nm)')
    ax.set_ylabel(r'$a, b_b \; [{\rm m}^{-1}]$')
    ymax = 0.08
    ax.set_xlim(350., 750.)
    ax.set_ylim(0., ymax)

    plotting.set_fontsize(ax, 15)

    # Fill between
    aw_to_anw = aw/anw
    bbw_to_bbnw = bbw/bbnw
    ratio = 5.
    red_idx = np.argmin(np.abs(aw_to_anw - ratio))
    blue_idx = np.argmin(np.abs(bbw_to_bbnw - ratio))

    alpha=0.3
    ax.fill_between([wave[red_idx], 750.], 0, ymax, color='red', alpha=alpha)
    ax.fill_between([350., wave[blue_idx]], 0, ymax, color='blue', alpha=alpha)

    # Red
    buff = 5.
    ax.text(wave[red_idx]+buff, 0.025, r'$a_w > '+f'{int(ratio)}'+r'a_{nw}$', fontsize=15, ha='left')
    ax.text(wave[red_idx]+buff, 0.02, r'$b_{b,nw} \approx b_{b,w}$', fontsize=15, ha='left')

    ax.text(wave[blue_idx]-buff, 0.07, r'$b_{b,w} >'+f'{int(ratio)}'+r'b_{b,nw}$', fontsize=15, ha='right')
    ax.text(wave[blue_idx]-buff, 0.075, r'$a_{nw} > a_{w}$', fontsize=15, ha='right')

    plt.tight_layout()#pad=0.0, h_pad=0.0, w_pad=0.3)
    plt.savefig(outfile, dpi=300)
    print(f"Saved: {outfile}")

def fig_all_ic(use_LM:bool=True, show_AIC:bool=False,
                outfile:str='fig_all_bic.png', MODIS:bool=False,
                comp_ks:tuple=((3,4),(4,5)),
                PACE:bool=False, log_x:bool=True):

    Bdict = {}

    s2ns = [0.05, 0.10, 0.2]
    ks = [comp_ks[0][0], comp_ks[0][1], comp_ks[1][0], comp_ks[1][1]]

    if MODIS:
        s2ns += ['MODIS_Aqua']
    elif PACE:
        s2ns += ['PACE']

    #embed(header='fig_all_ic 571')
    Adict, Bdict = anly_utils.calc_ICs(
        ks, s2ns, use_LM=use_LM, MODIS=MODIS, PACE=PACE)
        
    # Generate a pandas table
    D_BIC_A = Bdict[comp_ks[0][0]] - Bdict[comp_ks[0][1]]
    D_BIC_B = Bdict[comp_ks[1][0]] - Bdict[comp_ks[1][1]]

    # Trim junk in MODIS
    D_BIC_A = np.maximum(D_BIC_A, -5.)
    D_BIC_B = np.maximum(D_BIC_B, -5.)
    #embed(header='690 of fig_all_bic')

    #embed(header='fig_all_bic 660')

    fig = plt.figure(figsize=(14,6))
    plt.clf()
    gs = gridspec.GridSpec(1,2)

    nbins = 100
    # 34
    xlbl = 'AIC' if show_AIC else 'BIC'
    save_axes = []
    for ss in range(2):
        ax = plt.subplot(gs[ss])
        D_BIC = D_BIC_A if ss == 0 else D_BIC_B
        subset = f'{comp_ks[ss][0]},{comp_ks[ss][1]}'
        for ss, s2n in enumerate(s2ns):
            if log_x:
                xvals = np.log10(D_BIC[ss] + 6.)
            else:
                xvals = D_BIC[ss]
            # CDF
            srt = np.sort(xvals)
            yvals = np.arange(srt.size) / srt.size
            try:
                fs2n = int(1./float(s2n))
                color = None
                ls = ':'
                lw = 2
            except ValueError:
                fs2n = s2n
                color = 'k'
                ls = '-'
                lw = 3
            ax.plot(srt, yvals, label=f'S/N={fs2n}', color=color, 
                    linewidth=lw, ls=ls)
            # PDF
            #ax34.hist(xvals, bins=nbins,
            #        histtype='step', 
            #        fill=None, label=f's2n={s2n}',
            #        linewidth=3)
            # Stats
            #print(f'{s2n}: {np.sum(D_BIC_34[ss] < 0)/D_BIC_34[ss].size}')
        if log_x:
            ax.set_xlabel(r'$\log_{10}(\Delta \, \rm '+xlbl+'_{'+f'{subset}'+r'} + 6)$')
        else:
            ax.set_xlabel(r'$\Delta \, \rm '+xlbl+'_{'+f'{subset}'+r'}$')

        # Make it pretty
        # Title
        title = r'Include $\beta_{\rm nw}$?' if ss == 0 else 'Include phytoplankton?' 
        #ax.text(0.5, 1.05, title, ha='center', va='top', 
        #        fontsize=15, transform=ax.transAxes)

        ax.set_ylabel('CDF')
        ax.grid(True)
        plotting.set_fontsize(ax, 17)
        #
        xmax = 30. if MODIS else 50.
        if not log_x:
            ax.set_xlim(-5., xmax)
        else:
            ax.set_xlim(0.25, None)
        ax.legend(fontsize=17)

        # Vertical line at 0
        vline = 5. if show_AIC else 0.
        if log_x:
            vline = np.log10(vline + 6.)
        ax.axvline(vline, color='r', linestyle='--', lw=2)
        # Grab ylimits
        xl = ax.get_xlim()
        yl = ax.get_ylim()
        #ax.text(5, 0.6, 'Complex model favored', fontsize=18, ha='left')

    plt.tight_layout()#pad=0.0, h_pad=0.0, w_pad=0.3)
    plt.savefig(outfile, dpi=300)
    print(f"Saved: {outfile}")



# ################################
def fig_bic_modis_pace(use_LM:bool=True, 
                outfile:str='fig_bic_modis_pace.png', 
                log_x:bool=False):


    r_s2ns = [0.05, 0.10, 0.2]
    ks = [3,5]

    fig = plt.figure(figsize=(14,6))
    plt.clf()
    gs = gridspec.GridSpec(1,2)

    xlbl = 'BIC'
    for ss in range(2):

        if ss==0:
            s2ns = r_s2ns + ['MODIS_Aqua']
            MODIS = True
            PACE = False
            dataset = '(a) Multi-spectral'
        else:
            s2ns = r_s2ns + ['PACE']
            MODIS = False
            PACE = True
            dataset = '(b) Hyperspectral'

        #embed(header='fig_all_ic 571')
        Adict, Bdict = anly_utils.calc_ICs(
            ks, s2ns, use_LM=use_LM, MODIS=MODIS, PACE=PACE)
            
        # Generate a pandas table
        D_BIC_A = Bdict[ks[0]] - Bdict[ks[1]]


    #embed(header='fig_all_bic 660')

        ax = plt.subplot(gs[ss])
        D_BIC = D_BIC_A #if ss == 0 else D_BIC_B
        subset = f'{ks[0]},{ks[1]}'
        for ss, s2n in enumerate(s2ns):
            if log_x:
                xvals = np.log10(D_BIC[ss] + 6.)
            else:
                xvals = D_BIC[ss]
            # CDF
            srt = np.sort(xvals)
            yvals = np.arange(srt.size) / srt.size
            try:
                fs2n = int(1./float(s2n))
                color = None
                ls = ':'
                lw = 1
            except ValueError:
                fs2n = s2n
                color = 'k'
                ls = '-'
                lw = 3
            ax.plot(srt, yvals, label=f'S/N={fs2n}', color=color, linewidth=lw, ls=ls)
        if log_x:
            ax.set_xlabel(r'$\log_{10}(\Delta \, \rm '+xlbl+'_{'+f'{subset}'+r'} + 6)$')
        else:
            ax.set_xlabel(r'$\Delta \, \rm '+xlbl+'_{'+f'{subset}'+r'}$')

        # Make it pretty
        # Title
        ax.text(0.9, 0.7, dataset, ha='right', va='top', 
                fontsize=19, transform=ax.transAxes)

        ax.set_ylabel('CDF')
        ax.grid(True)
        plotting.set_fontsize(ax, 17)
        #
        xmax = 30. #if MODIS else 50.
        if not log_x:
            ax.set_xlim(-5., xmax)
        else:
            ax.set_xlim(0.25, None)
        ax.set_ylim(0.,1)
        ax.legend(fontsize=17)

        # Vertical line at 0
        vline = 0.
        if log_x:
            vline = np.log10(vline + 6.)
        ax.axvline(vline, color='r', linestyle='--', lw=2)
        # Grab ylimits
        xl = ax.get_xlim()
        yl = ax.get_ylim()
        #ax.text(5, 0.6, 'Complex model favored', fontsize=18, ha='left')

    plt.tight_layout()#pad=0.0, h_pad=0.0, w_pad=0.3)
    plt.savefig(outfile, dpi=300)
    print(f"Saved: {outfile}")







# ############################################################
def fig_one_bic(models:list=None, idx:int=170, 
            scl_noises:list=None,
            low_wv=500., 
            outroot='fig_bic_', show_bbnw:bool=False,
            set_abblim:bool=True, 
            add_noise:bool=False): 


    # Outfile
    outfile = outroot + f'{idx}.png'

    if scl_noises is None:
        scl_noises = [0.02, 0.03, 0.05, 0.07, 0.10]

    if models is None:
        models = ['expcst', 'exppow', 'giop+']

    # Load the data
    odict = gordon.prep_data(idx)
    wave = odict['wave']
    Rrs = odict['Rrs']
    varRrs = odict['varRrs']
    a_true = odict['a']
    bb_true = odict['bb']
    aw = odict['aw']
    bbw = odict['bbw']
    bbnw = bb_true - bbw
    wave_true = odict['true_wave']
    Rrs_true = odict['true_Rrs']

    gordon_Rrs = fgordon.calc_Rrs(odict['a'][::2], odict['bb'][::2])

    # Calculate BIC
    BICs = {}
    nparms = []
    for model in models:
        nparm = fgordon.grab_priors(model).shape[0]
        nparms.append(nparm)
        if model not in BICs.keys():
            BICs[model] = []
        # Load noiseless (should not matter) 
        chain_file, noises, noise_lbl = get_chain_file(
            model, 0.02, False, idx)
        d_chains = inf_io.load_chains(chain_file)

        # Reconstruct
        pdict = fgordon.init_mcmc(model, d_chains['chains'].shape[-1], 
                                wave, Y=odict['Y'], Chl=odict['Chl'])
        a_mean, bb_mean, a_5, a_95, bb_5, bb_95,\
            model_Rrs, sigRs = gordon.reconstruct(
            model, d_chains['chains'], pdict) 

        for scl_noise in scl_noises:
            # Calcualte chi^2
            chi2 = ((model_Rrs - gordon_Rrs) / ((scl_noise) * gordon_Rrs))**2
            Bic = nparm * np.log(len(model_Rrs)) + np.sum(chi2) 
            # Save
            BICs[model].append(Bic)
        
    # Plot em

    fig = plt.figure(figsize=(8,8))
    plt.clf()
    gs = gridspec.GridSpec(1,1)

    ax = plt.subplot(gs[0])

    for kk, scl_noise in enumerate(scl_noises):
        these_BICs = []
        for model in models:
            these_BICs.append(BICs[model][kk])
        ax.plot(nparms, these_BICs, '-', label=f'{int(100*scl_noise):02d}')

    ax.set_xlabel('N parameters')
    ax.set_ylabel('BIC')

    # Add model as text
    ax.text(0.1, 0.1, f'idx={idx}', fontsize=15, transform=ax.transAxes,
            ha='left')

    # Log scale y-axis
    #ax.set_xscale('log')
    #ax.set_yscale('log')

    ax.set_ylim(0., 100.)

    # Grid me
    ax.grid(True)
    ax.legend(fontsize=14)

    plotting.set_fontsize(ax, 15)

    #plt.tight_layout()#pad=0.0, h_pad=0.0, w_pad=0.3)
    plt.savefig(outfile, dpi=300)
    print(f"Saved: {outfile}")

def fig_Sexp(outfile='fig_Sexp.png', kmodel:int=4):


    # Load
    ds = loisel23.load_ds(4,0)
    l23_wave = ds.Lambda.data
    l23_Rrs = ds.Rrs.data
    a = ds.a.data
    bb = ds.bb.data
    adg = ds.ag.data + ds.ad.data
    aph = ds.aph.data
    anw = ds.anw.data

    ks = [3,4,5]
    pdict = {}
    for k in ks:
        pdict[k] = {}
        # Model names
        if k == 3:
            model_names = ['Exp', 'Cst']
        elif k == 4:
            model_names = ['Exp', 'Pow']
        elif k == 5:
            model_names = ['ExpBricaud', 'Pow']
        else:
            raise ValueError("Bad k")

        chain_file, noises, noise_lbl = anly_utils.get_chain_file(
            model_names, 0.02, False, 'L23', use_LM=True,
            PACE=True)
        # Load up
        d = np.load(chain_file)
        # Parse
        pdict[k]['params'] = d['ans']
        if k == ks[0]:
            pdict['Rrs'] = d['obs_Rrs']
            pdict['idx'] = d['idx']

    Sexp = pdict[kmodel]['params'][:,1]
    i440 = np.argmin(np.abs(l23_wave-440.))
    aph_anw = aph[:,i440]/anw[:,i440]

    xmin, xmax = 0.08, 0.9
    #
    cut = Sexp > -6.
    fig = plt.figure(figsize=(10,6))
    ax = plt.gca()
    #
    ax.scatter(aph_anw[cut], 10**Sexp[cut], s=1, color='k')
    # Sg
    #ax.fill_between([xmin, xmax], [np.log10(0.01)]*2, [np.log10(0.02)]*2, color='cyan', alpha=0.3, label=r'$S_g$')
    ax.fill_between([xmin, xmax], [0.01]*2, [0.02]*2, color='cyan', alpha=0.3, label=r'$S_g$')
    # Sd
    ax.fill_between([xmin, xmax], [0.007]*2, [0.015]*2, color='yellow', alpha=0.3, label=r'$S_d$')
    #ax.fill_between([xmin, xmax], [np.log10(0.007)]*2, [np.log10(0.015)]*2, color='brown', alpha=0.3, label=r'$S_d$')
    # Fit to a_dg
    #ax.fill_between([xmin, xmax], [np.log10(adg_fits[:,1].min())]*2, [np.log10(adg_fits[:,1].max())]*2, color='yellow', alpha=0.3, label=r'$S_{dg}$')
    # Werdell2013
    #ax.axhline(np.log10(0.018), color='k', ls='--', label='GIOP')
    #ax.axhline(np.log10(0.0206), color='k', ls=':', label='GSM')
    ax.axhline(0.018, color='k', ls='--', label='GIOP')
    ax.axhline(0.0206, color='k', ls=':', label='GSM')
    # Tara extreme
    #ax.axhline(np.log10(0.004746), color='r', ls='-', label='Tara')
    ax.axhline(0.004746, color='r', ls='-', label='Tara')
    #
    #ax.set_ylabel(r'$\log_{10} \, S_{\rm exp}$')
    ax.set_ylabel(r'$S_{\rm exp} \rm \; [nm^{-1}]$')
    ax.set_xlabel(r'$[a_{\rm ph}/a_{\rm nw}] (440)$')
    ax.set_xlim(xmin, xmax)
    #
    #ax.set_ylim(-3., None)
    ax.set_ylim(0, 0.022)
    ax.legend(fontsize=15.)
    #
    plotting.set_fontsize(ax, 17.)
    
    plt.tight_layout()#pad=0.0, h_pad=0.0, w_pad=0.3)
    plt.savefig(outfile, dpi=300)
    print(f"Saved: {outfile}")


def main(flg):
    if flg== 'all':
        flg= np.sum(np.array([2 ** ii for ii in range(25)]))
    else:
        flg= int(flg)

    # Spectra
    if flg == 1:
        fig_spectra(170, bbscl=20)

    if flg == 2:
        fig_multi_fits()#[('Cst','Cst'), ('Exp','Cst'), ('Exp','Pow'), ('ExpBricaud','Pow')], 
                       #[170, 1032])

    if flg == 3:
        fig_bic_modis_pace()

    # BIC/AIC for MODIS+L23
    if flg == 4:
        fig_all_ic(MODIS=True, outfile='fig_all_bic_MODIS.png',
                   log_x=False,
                   comp_ks=((2,3), (3,4)))
        #fig_all_ic(MODIS=True, show_AIC=True, 
        #           outfile='fig_all_aic_MODIS.png')
        #fig_all_ic(MODIS=True, outfile='fig_all_bic_MODIS_GIOP.png',
        #           comp_ks=((2,3), (3,9)))

    # BIC/AIC for PACE
    if flg == 5:
        fig_all_ic(PACE=True, outfile='fig_all_bic_PACE.png',
                   log_x=False)

    # BIC/AIC for 70 + fixed relative error
    if flg == 6:
        fig_all_ic(outfile='fig_all_bic_46.png',
                   comp_ks=((3,4), (4,6)))
        #fig_all_ic(show_AIC=True, outfile='fig_all_aic.png')

    # ########################################
    # Supp
    if flg == 10:
        fig_u()

    if flg == 11:
        fig_Kd()

    if flg == 12:
        fig_Sexp()

    # LM fits
    if flg == 30:
        #fig_mcmc_fit(['Exp', 'Pow'], idx=170, log_Rrs=True)
        #fig_mcmc_fit(['Exp', 'Pow'], idx=170, log_Rrs=True, use_LM=True)
        #fig_mcmc_fit(['Exp', 'Cst'], idx=170, log_Rrs=True, use_LM=True)
        #fig_mcmc_fit(['Exp', 'Cst'], idx=3315, log_Rrs=True, use_LM=True)
        #fig_mcmc_fit(['Exp', 'Pow'], idx=3315, log_Rrs=True, use_LM=True)
        #fig_mcmc_fit(['Cst', 'Cst'], idx=170, log_Rrs=True, use_LM=True)
        #fig_mcmc_fit(['Exp', 'Pow'], idx=170, 
        #             log_Rrs=True, use_LM=True, max_wave=700.)#, full_LM=False)
        #fig_mcmc_fit(['ExpBricaud', 'Pow'], idx=170, 
        #             log_Rrs=True, use_LM=True, max_wave=700.)#, full_LM=False)
        #fig_mcmc_fit(['ExpNMF', 'Pow'], idx=170, full_LM=False,
        #             log_Rrs=True, use_LM=True, max_wave=700.)#, full_LM=False)
        #fig_mcmc_fit(['ExpBricaud', 'Pow'], idx=170, full_LM=True,
        #fig_mcmc_fit(['GIOP', 'Lee'], idx=170, full_LM=True,
        #fig_mcmc_fit(['GIOP', 'Pow'], idx=170, full_LM=True,
        #    PACE=True, log_Rrs=True, use_LM=True)#, full_LM=False)
        fig_mcmc_fit(['GSM', 'GSM'], idx=170, full_LM=False,
            PACE=True, log_Rrs=True, use_LM=False)#, full_LM=False)



# Command line execution
if __name__ == '__main__':
    import sys

    if len(sys.argv) == 1:
        flg = 0

        #flg = 1
        
    else:
        flg = sys.argv[1]

    main(flg)