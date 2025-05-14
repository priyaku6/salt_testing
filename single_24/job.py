import os
from pyats.easypy import run # type: ignore

script_name = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "script.py"
)

def main():
    run(testscript=script_name)
