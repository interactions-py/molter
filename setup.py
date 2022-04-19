from pathlib import Path

from setuptools import find_packages
from setuptools import setup

requirements = []
with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setup(
    name="interactions-molter",
    description=(
        "An extension library for interactions.py to add text-based commands! Ported"
        " from dis-snek."
    ),
    long_description=(Path(__file__).parent / "README.md").read_text(),
    long_description_content_type="text/markdown",
    author="Astrea49",
    url="https://github.com/interactions-py/molter",
    version="0.3.1",
    packages=["interactions.ext.molter"],
    python_requires=">=3.8.6",
    install_requires=requirements,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
