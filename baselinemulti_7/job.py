import os
from pyats.easypy import run  # type: ignore

def main():
    script_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "script.py"
    )
    run(testscript=script_path)
