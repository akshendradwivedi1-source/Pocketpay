#!/usr/bin/env bash
# Exit immediately if a command exits with a non-zero status
set -o errexit

echo "======================================================"
echo "          PocketPay Production Build Script           "
echo "======================================================"

echo "--> Upgrading pip..."
python -m pip install --upgrade pip

echo "--> Installing project dependencies from requirements.txt..."
pip install -r requirements.txt

echo "--> Database migrations apply automatically during application startup."

echo "--> Build succeeded! Ready for Gunicorn launch."
