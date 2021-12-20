"""Run Chandra data preparation for LIRA"""
import subprocess
from pathlib import Path
from astropy.coordinates import SkyCoord
from astropy import units as u
from astropy.nddata import Cutout2D
import sherpa.astro.ui as sau
from sherpa_contrib.chart import save_chart_spectrum


OBS_ID = 1385

ROI = {
    "center": SkyCoord("332.17007516d", "45.74225112d", frame="icrs"),
    "width": (128, 128),
}

PATH = Path(f"{OBS_ID}")

PATH_OUT = "lira-input"
PATH_REPRO = PATH / "repro"


INDEX_TABLE = Table.read(PATH / "oif.fits")
INDEX_TABLE.add_index("MEMBER_CONTENT")
SOURCE_NAME = INDEX_TABLE.meta["OBJECT"].strip()


def get_filename(member_content):
    """Get file name"""
    filename = INDEX_TABLE.loc[f"{member_content:32s}"]["MEMBER_LOCATION"]
    filename = filename.strip()
    filename = filename.replace(".fits", ".fits.gz")
    return PATH / filename



def download_data():
    """Download data"""
    if not Path(str(OBS_ID)).exist():
        command = ["download_chandra_obsid", f"{OBS_ID}"]
        subprocess.call(*command)

        
def reprocess_data():
    """Reprocess data"""
    command = ["chandra_repro",   f"{OBSID}", f"{PATH_REPRO}"]
    subprocess.call(*command)

    
def extract_spectrum():
    """Extract spectrum"""
    command = ["specextract"]
    command += ["acisf00942_repro_evt2.fits"]
    command += [f"[sky=circle(12:16:56.990,+37:43:35.69,20)]"]
    command += [f"{SOURCE_NAME}"]
    command += ["verbose=0"]
    subprocess.call(*command)
    

def run_sherpa_fit():
    """Run sherpa"""
    filename = "ngc4244.pi"
    sau.load_data(filename)
    sau.group_counts(10)
    sau.notice(0.4, 6.0)
    # TODO: use black body here...
    sau.set_source(sau.xsphabs.abs1 * sau.powlaw1d.p1)
    sau.abs1.nh = 0.5
    sau.guess(p1)
    sau.fit()
    sau.set_analysis(1, "energy", "rate", factor=1)

    filename = "source_flux_chart.dat"
    save_chart_spectrum(PATH / filename, elow=0.4, ehigh=6.0)


def make_counts():
    """Make counts image"""
    filename = get_filename()
    

def make_psf():
    """Make PSF image"""
    pass


def make_background():
    """Make background image"""
    pass


def make_exposure():
    """Make exposure image"""
    pass


if __name__ == "__main__":
    download_data()
    reprocess_data()
    make_psf()
    make_background()
    make_exposure()