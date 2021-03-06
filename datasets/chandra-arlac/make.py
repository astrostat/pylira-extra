"""Run Chandra data preparation for LIRA"""
import logging
import subprocess
from pathlib import Path
import matplotlib.pylab as plt
import numpy as np
from astropy.coordinates import SkyCoord
from astropy.table import Table
from gammapy.maps import Map
from astropy import units as u
from regions import CircleAnnulusSkyRegion
import sherpa.astro.ui as sau
from sherpa_contrib.chart import save_chart_spectrum


log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

OBS_ID = 1385

ROI = {
    "center": SkyCoord("332.17007516d", "45.74225112d", frame="icrs"),
    "npix": 128
}

PATH = Path(f"{OBS_ID}")

PATH_OUT = PATH / "lira-input"
PATH_REPRO = PATH / "repro"

PSF_IMAGE_SHAPE = (25, 25)
PSF_N_ITER = 5

INDEX_TABLE = Table.read(PATH / "oif.fits")
INDEX_TABLE.add_index("MEMBER_CONTENT")
SOURCE_NAME = INDEX_TABLE.meta["OBJECT"].strip()


def execute_command(command):
    log.info(f"Executing: {' '.join(command)}")
    subprocess.run(command)


def get_filename(member_content):
    """Get file name"""
    filename = INDEX_TABLE.loc[f"{member_content:32s}"]["MEMBER_LOCATION"]
    filename = filename.strip()
    filename = filename.replace(".fits", ".fits.gz")
    return PATH / filename


def download_data():
    """Download data"""
    if not PATH.exists():
        command = ["download_chandra_obsid", f"{OBS_ID}"]
        execute_command(command=command)
    else:
        log.info(f"Skipping download, {PATH} already exists.")



def reprocess_data():
    """Reprocess data"""
    if PATH_REPRO.exists():
        log.info(f"Skipping reprocessing, {PATH_REPRO} already exists.")
        return

    command = ["chandra_repro", f"{OBS_ID}", f"{PATH_REPRO}"]
    execute_command(command=command)


def extract_spectrum():
    """Extract spectrum"""
    path_spectrum = PATH / "spectrum"
    filename_base = path_spectrum / SOURCE_NAME

    path_spectrum.mkdir(parents=True, exist_ok=True)

    filename_out = Path(str(filename_base) + ".pi")
    if filename_out.exists():
        log.info(f"Skipping spectral extraction, {filename_out} already exists.")
        return

    command = ["specextract"]

    center = ROI["center"]
    radius = 20  # TODO: unit?
    center_str = center.icrs.to_string('hmsdms', sep=':')

    filename = str(PATH_REPRO / f"hrcf{OBS_ID:05d}_repro_evt2.fits")
    filename += f"[sky=circle({center_str.replace(' ', ',')},{radius})]"
    command += [filename]
    command += [f"{filename_base}"]
    command += ["verbose=0"]
    execute_command(command=command)


def run_sherpa_fit():
    """Run sherpa"""
    path_spectrum = PATH / "spectrum"
    filename = f"source-flux-chart-{SOURCE_NAME}.dat"
    filename = path_spectrum / filename

    if filename.exists():
        log.info(f"Skipping spectral fit, {filename} already exists.")
        return

    log.info(f"Fitting spectrum")
    filename_pha = str(path_spectrum / (SOURCE_NAME + ".pi"))
    sau.load_data(filename_pha)
    sau.group_counts(10)
    sau.notice(0.4, 6.0)
    sau.set_source(sau.bbody.bb1)
    sau.bbody.bb1.ampl.val = 3e-2
    sau.bbody.bb1.kT.val = 1

    # TODO: the fit doesn't really work right now...
    #sau.fit()
    sau.set_analysis(1, "energy", "rate", factor=1)
    sau.plot_source()

    plt.xscale("log")
    plt.yscale("log")
    plt.savefig(path_spectrum / f"spectrum-{SOURCE_NAME}.png")
    save_chart_spectrum(str(filename), elow=0.1, ehigh=10.0)


def make_counts():
    """Make counts image"""
    filename_out = PATH_OUT / "counts.fits"

    PATH_OUT.mkdir(exist_ok=True, parents=True)

    if filename_out.exists():
        log.info(f"Skipping counts image, {filename_out} already exists.")
        return

    command = ["dmcopy"]

    filename = get_filename("EVT2")

    command += [f"infile={filename}[EVENTS][bin x=16203:16331:1, y=16375:16503:1]"]
    command += [f"outfile={PATH_OUT / 'counts.fits'}"]
    command += ["option=image"]

    execute_command(command=command)

    #filename = get_filename("HIRESIMG")
    #log.info(f"Reading {filename}")

    #counts = Map.read(filename)

    #width = counts.geom.pixel_scales * ROI["npix"]
    #cutout = counts.cutout(position=ROI["center"], width=width)

    #log.info(f"Reading {filename_out}")
    #cutout.write(filename_out)


def make_psf():
    """Make PSF image"""
    # this requires running
    outroot = f"{OBS_ID}/psf/psf"
    filename_out = Path(outroot).parent / "psf.psf"

    if filename_out.exists():
        log.info(f"Skipping PSF image, {filename_out} already exists.")
        return

    command = ["simulate_psf"]

    filename = str(PATH_REPRO / f"hrcf{OBS_ID:05d}_repro_evt2.fits")
    command += [f"infile={filename}"]
    command += [f"outroot={outroot}"]

    center = ROI["center"]
    command += [f"ra={center.icrs.ra.deg}"]
    command += [f"dec={center.icrs.dec.deg}"]

    command += ["simulator=marx"]
    command += ["numsig=7"]
    command += [f"minsize={PSF_IMAGE_SHAPE[0]}"]

    path_spectrum = PATH / "spectrum"
    filename = path_spectrum / f"source-flux-chart-{SOURCE_NAME}.dat"
    command += [f"spectrum={filename}"]
    command += [f"numiter={PSF_N_ITER}"]

    #filenames = [str(_) for _ in Path("1385/psf/chart/").glob("HRMA_*.fits")]
    #command += [f"rayfile={','.join(filenames)}"]
    command += ["mode=h"]
    execute_command(command=command)


def copy_psf():
    command = ["cp", f"{OBS_ID}/psf/psf.psf", f"{PATH_OUT}"]
    execute_command(command=command)

    command = ["mv", f"{OBS_ID}/lira-input/psf.psf", f"{PATH_OUT}/psf.fits"]
    execute_command(command=command)


def make_background():
    """Make background image"""
    filename_out = PATH_OUT / "background.fits"

    if filename_out.exists():
        log.info(f"Skipping background image, {filename_out} already exists.")
        return

    filename = PATH_OUT / "counts.fits"
    log.info(f"Reading {filename}")
    counts = Map.read(filename)

    background = Map.from_geom(counts.geom)

    region = CircleAnnulusSkyRegion(
        center=ROI["center"],
        inner_radius=5 * u.arcsec,
        outer_radius=8 * u.arcsec,
    )
    mean_bkg = background.to_region_nd_map(region, func=np.mean)
    background.data[...] = mean_bkg.data

    log.info(f"Writing {filename_out}")
    background.write(filename_out, overwrite=True)



def make_exposure():
    """Make exposure image"""
    # TODO:
    pass


if __name__ == "__main__":
    download_data()
    reprocess_data()
    extract_spectrum()
    run_sherpa_fit()
    make_counts()
    make_psf()
    copy_psf()
    make_background()
    make_exposure()
