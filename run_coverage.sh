#!/bin/bash

python3-coverage run -m unittest discover -s tests -p "test_*.py"
python3-coverage html
#python3-coverage report -m
#zip -r htmlcov.zip htmlcov