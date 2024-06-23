
import os

import numpy as np
from scipy.interpolate import interp1d

from oceancolor.hydrolight import loisel23
try:
    from oceancolor.satellites import pace as sat_pace
except:
    pass
else:
    from oceancolor.satellites import modis as sat_modis
    from oceancolor.satellites import seawifs as sat_seawifs

from bing import rt as bing_rt
from bing.models import anw as bing_anw
from bing.models import bbnw as bing_bbnw
from bing.models import utils as model_utils
from bing import stats as bing_stats
from bing import chisq_fit


from IPython import embed

PACE_wave = np.arange(400, 701, 5)

kdict = {2: ['Cst', 'Cst'],
            3: ['Exp', 'Cst'],
            4: ['Exp', 'Pow'],
            5: ['ExpBricaud', 'Pow'],
            6: ['ExpNMF', 'Pow'],
            'GIOP': ['GIOP', 'Lee'],
            'GIOP+': ['GIOP', 'Pow'],
            'GSM': ['GSM', 'GSM'],
            'GSM+': ['GSM', 'Pow'],
}

def chain_filename(model_names:list, scl_noise, add_noise,
                       idx:int=None, MODIS:bool=False, use_LM:bool=False,
                       PACE:bool=False, SeaWiFS:bool=False): 
    outfile = f'../Analysis/Fits/BING_{model_names[0]}{model_names[1]}'

    if idx is not None:
        outfile += f'_{idx}'
        if MODIS:
            outfile += '_M'
        elif PACE:
            outfile += '_P'
        elif SeaWiFS:
            outfile += '_S'
    else:
        if MODIS:
            outfile += '_M23'
        elif PACE:
            outfile += '_P23'
        elif SeaWiFS:
            outfile += '_S23'
        else:
            outfile += '_L23'
    if add_noise:
        outfile += f'_N{int(100*scl_noise):02d}'
    else:
        if scl_noise == 'SeaWiFS':
            outfile += '_nS'
        elif scl_noise == 'MODIS_Aqua':
            outfile += '_nM'
        elif scl_noise == 'PACE':
            outfile += '_nP'
        else:
            outfile += f'_n{int(100*scl_noise):02d}'
    # LM
    if use_LM:
        outfile = outfile.replace('BING', 'BING_LM')
    outfile += '.npz'
    return outfile


def calc_ICs(ks:list, s2ns:list, use_LM:bool=False,
             MODIS:bool=False, PACE:bool=False, SeaWiFS:bool=False):

    Bdict = dict()
    Adict = dict()
    for k in ks:
        Adict[k] = []
        Bdict[k] = []

        # Model names
        model_names = kdict[k]

        chain_file = chain_filename(
            model_names, 0.02, False, use_LM=use_LM,
            MODIS=MODIS, PACE=PACE, SeaWiFS=SeaWiFS)
        d_chains = np.load(chain_file)
        print(f'Loaded: {chain_file}')
        wave = d_chains['wave']

        # Init the models
        models = model_utils.init(model_names, wave)

        # Loop on S/N
        if k == ks[0]:
            sv_s2n = []
            sv_idx = []
        for s2n in s2ns:
            if PACE and (s2n == 'PACE'):
                noise_vector = sat_pace.gen_noise_vector(
                    models[0].wave)
            elif MODIS and (s2n == 'MODIS_Aqua'):
                noise_vector = sat_modis.modis_aqua_error
            elif SeaWiFS and (s2n == 'SeaWiFS'):
                noise_vector = sat_seawifs.seawifs_error
            else:
                noise_vector = None
            # Calculate BIC
            AICs, BICs = bing_stats.calc_ICs(
                d_chains['obs_Rrs'], models, d_chains['ans'],
                            s2n, use_LM=use_LM, debug=False,
                            Chl=d_chains['Chl'],
                            bb_basis_params=d_chains['Y'], # Lee
                            noise_vector=noise_vector)
            Adict[k].append(AICs)
            Bdict[k].append(BICs)
            # 
            if k == 3:
                sv_s2n += [s2n]*BICs.size
                sv_idx += d_chains['idx'].tolist()
        #embed(header='678 of fig_all_bic')
        # Concatenate
        Bdict[k] = np.array(Bdict[k])
        Adict[k] = np.array(Adict[k])

    # Return
    return Adict, Bdict
        

def convert_to_satwave(wave:np.ndarray, spec:np.ndarray,
                     sat_wave:np.ndarray):
    """
    Convert the spectrum to MODIS wavelengths

    Parameters:
        wave (np.ndarray): Wavelengths of the input Rrs
        spec (np.ndarray): Spectrum. a, b, Rrs, etc. 
        sat_wave (np.ndarray): Wavelengths of the satellite

    Returns:
        np.ndarray: Rrs at MODIS wavelengths
    """
    # Interpolate
    f = interp1d(wave, spec, kind='linear', fill_value='extrapolate')
    new_spec = f(sat_wave)

    # Return
    return new_spec

def prep_l23_data(idx:int, step:int=1, scl_noise:float=0.02,
                  ds=None, max_wave:float=None, min_wave:float=None):
    """ Prepare L23 the data for the fit """

    # Load
    if ds is None:
        ds = loisel23.load_ds(4,0)

    wave = ds.Lambda.data

    gd_wave = np.ones_like(ds.Lambda.data, dtype=bool)
    if max_wave is not None:
        gd_wave &= ds.Lambda.data <= max_wave
    if min_wave is not None:
        gd_wave &= ds.Lambda.data >= min_wave
    iwave = np.where(gd_wave)[0]

    # Grab
    Rrs = ds.Rrs.data[idx,iwave]
    wave = wave[iwave]
    true_Rrs = Rrs.copy()
    true_wave = wave.copy()
    a = ds.a.data[idx,iwave]
    bb = ds.bb.data[idx,iwave]
    adg = ds.ag.data[idx,iwave] + ds.ad.data[idx,iwave]
    aph = ds.aph.data[idx,iwave]

    # For bp
    rrs = Rrs / (bing_rt.A_Rrs + bing_rt.B_Rrs*Rrs)
    i440 = np.argmin(np.abs(true_wave-440))
    i555 = np.argmin(np.abs(true_wave-555))
    Y = 2.2 * (1 - 1.2 * np.exp(-0.9 * rrs[i440]/rrs[i555]))

    # For aph
    aph = ds.aph.data[idx,iwave]
    Chl = aph[i440] / 0.05582

    # Cut down to 40 bands
    Rrs = Rrs[::step]
    wave = wave[::step]

    # Gordon
    gordon_Rrs = bing_rt.calc_Rrs(a, bb)

    # Error
    #varRrs = (scl_noise * Rrs)**2

    # Dict me
    odict = dict(wave=wave, Rrs=Rrs, a=a, bb=bb, 
                 true_wave=true_wave, true_Rrs=true_Rrs,
                 gordon_Rrs=gordon_Rrs,
                 bbw=ds.bb.data[idx,iwave]-ds.bbnw.data[idx,iwave],
                 bbnw=ds.bbnw.data[idx,iwave],
                 aw=ds.a.data[idx,iwave]-ds.anw.data[idx,iwave],
                 anw=ds.anw.data[idx,iwave],
                 adg=adg, aph=aph,
                 Y=Y, Chl=Chl)

    return odict

def save_fits(all_samples, all_idx, outfile, 
              extras:dict=None):
    """
    Save the fitting results to a file.

    Parameters:
        all_samples (numpy.ndarray): Array of fitting chains.
        all_idx (numpy.ndarray): Array of indices.
        Rs (numpy.ndarray): Array of Rs values.
        use_Rs (numpy.ndarray): Array of observed Rs values.
        outroot (str): Root name for the output file.
    """  
    # Outdict
    outdict = dict()
    outdict['chains'] = all_samples
    outdict['idx'] = all_idx
    
    # Extras
    if extras is not None:
        for key in extras.keys():
            outdict[key] = extras[key]
    np.savez(outfile, **outdict)
    print(f"Saved: {outfile}")

# #############################################################################
def recon_one(model_names:list, idx:int, 
              min_wave:float=None, max_wave:float=None,
              scl_noise:float=None, add_noise:bool=False, 
              use_LM:bool=False,
              full_LM:bool=False, MODIS=False, PACE=False,
              limit_wave_to_fit:bool=True):

    # Load up the chains or parameters
    chain_file, noises, noise_lbl = get_chain_file(
        model_names, scl_noise, add_noise, idx, use_LM=use_LM,
        full_LM=full_LM, MODIS=MODIS)
    print(f'Loading: {chain_file}')
    d_chains = np.load(chain_file)

    # Load the data
    odict = prep_l23_data(idx, min_wave=min_wave, max_wave=max_wave)
    model_wave = odict['wave']
    Rrs = odict['Rrs']
    varRrs = odict['varRrs']
    a_true = odict['a']
    bb_true = odict['bb']
    aw = odict['aw']
    adg = odict['adg']
    aph = odict['aph']
    bbw = odict['bbw']
    bbnw = bb_true - bbw
    wave_true = odict['true_wave']
    Rrs_true = odict['true_Rrs']

    gordon_Rrs = bing_rt.calc_Rrs(odict['a'], odict['bb'])

    # MODIS?
    if MODIS:
        model_wave = bing_modis.modis_wave
        model_Rrs = bing_modis.convert_to_modis(wave_true, gordon_Rrs)
    elif PACE:
        model_wave = bing_pace.pace_wave
    else:
        model_wave = wave_true

    # Init the models
    models = model_utils.init(model_names, model_wave)

    # Extras?
    if models[0].uses_Chl:
        models[0].set_aph(odict['Chl'])
    if models[1].uses_basis_params:  # Lee
        models[1].set_basis_func(odict['Y'])

    # Interpolate
    aw_interp = np.interp(model_wave, wave_true, aw)

    #embed(header='figs 167')

    # Reconstruct
    if use_LM:
        if full_LM:
            params = d_chains['ans'][idx]
        else:
            params = d_chains['ans']
        model_Rrs, a_mean, bb_mean = chisq_fit.fit_func(
            model_wave, *params, models=models, return_full=True)
    else:
        raise ValueError("Need to implement")
        #a_mean, bb_mean, a_5, a_95, bb_5, bb_95,\
        #    model_Rrs, sigRs = anly_utils.reconstruct(
        #    models, d_chains['chains']) 

    # Return as a dict
    rdict = dict(wave=model_wave, Rrs=Rrs, varRrs=varRrs, noise_lbl=noise_lbl,
                 noises=noises, idx=idx,
                 a_true=a_true, bb_true=bb_true,
                 aw=aw, adg=adg, aph=aph,
                 anw_model=models[0], bbnw_model=models[1],
                 aw_interp=aw_interp, 
                 bbw=bbw, bbnw=bbnw,
                 wave_true=wave_true, Rrs_true=Rrs_true,
                 gordon_Rrs=gordon_Rrs,
                 model_Rrs=model_Rrs, a_mean=a_mean, bb_mean=bb_mean)
    # Return
    return rdict


def scale_noise(scl_noise, model_Rrs, model_wave):

    if scl_noise == 'SeaWiFS':
        model_varRrs = sat_seawifs.seawifs_error**2
    elif scl_noise == 'MODIS_Aqua':
        model_varRrs = sat_modis.modis_aqua_error**2
    elif scl_noise == 'PACE':
        PACE_error = sat_pace.gen_noise_vector(model_wave)
        model_varRrs = PACE_error**2
    else:
        model_varRrs = (scl_noise * model_Rrs)**2

    # Return
    return model_varRrs