"""Run Chandra data preparation for LIRA"""
import logging
import subprocess
from pathlib import Path
import matplotlib.pylab as plt
from astropy.coordinates import SkyCoord
from astropy.table import Table
from gammapy.maps import Map
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
    save_chart_spectrum(str(filename), elow=0.01, ehigh=10.0)


def make_counts():
    """Make counts image"""
    filename_out = PATH_OUT / "counts.fits"

    PATH_OUT.mkdir(exist_ok=True, parents=True)

    if filename_out.exists():
        log.info(f"Skipping counts image, {filename_out} already exists.")
        return

    filename = get_filename("HIRESIMG")
    log.info(f"Reading {filename}")

    counts = Map.read(filename)

    width = counts.geom.pixel_scales * ROI["npix"]
    cutout = counts.cutout(position=ROI["center"], width=width)

    log.info(f"Reading {filename_out}")
    cutout.write(filename_out)


def make_psf():
    """Make PSF image"""
    command = ["simulate_psf"]
    command += [infile]
    command += [outroot]
    command += [ra]
    command += [dec]
    command += [spectrum]
    execute_command(command=command)


def make_background():
    """Make background image"""
    # TODO:
    pass


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
    make_background()
    make_exposure()
