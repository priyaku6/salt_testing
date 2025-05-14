from pyats.easypy import run # type: ignore
import os

def main():
    script_path = os.path.join(os.path.dirname(__file__), "script.py")
    run(testscript=script_path)
