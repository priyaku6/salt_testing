import os

from pyats.easypy import run  # type: ignore

def main():
    """
    Main function to execute the test script.
    """
    # Define the path to the test script
    script_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "script.py"
    )
    
    # Run the test script
    run(testscript=script_path)

