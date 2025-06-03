import os
from pyats.easypy import run

def main():
    # Get the directory path of the current job file
    test_path = os.path.dirname(os.path.abspath(__file__))
    
    # Define the path to the test script
    testscript = os.path.join(test_path, 'script.py')  # Updated to use 'script.py'
    
    # Run the test script
    run(testscript=testscript)
