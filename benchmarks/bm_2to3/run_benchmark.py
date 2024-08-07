import glob
import os.path
import sys
import subprocess
import warnings
# disable all warnings to avoid warnings from the 2to3 library
warnings.simplefilter("ignore")
# import pyperf



if __name__ == "__main__":
    # runner = pyperf.Runner()

    # runner.metadata['description'] = "Performance of the Python 2to3 program"
    # args = runner.parse_args()

    try:
        import lib2to3
    except ModuleNotFoundError:
        vendor = os.path.join(os.path.dirname(__file__), 'vendor')
        subprocess.run([sys.executable, "-m", "pip", "install", vendor], check=True)
    
    datadir = os.path.join(os.path.dirname(__file__), 'data', '2to3')
    pyfiles = glob.glob(os.path.join(datadir, '*.py.txt'))
    command = [sys.executable, "-m", "lib2to3", "-f", "all"] + pyfiles

    # runner.bench_command('2to3', command)
    for i in range(3):
        subprocess.run(command, check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)