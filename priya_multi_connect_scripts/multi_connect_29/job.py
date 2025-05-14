# Copyright (c) 2024 by Cisco Systems, Inc.
# All rights reserved.

import os
from pyats.easypy import run

def main():
    # Get the path of the current script
    test_path = os.path.dirname(os.path.abspath(__file__))
    
    # Define the path to the test script
    testscript = os.path.join(test_path, 'test.py')
    
    # Run the test script
    run(testscript=testscript)
