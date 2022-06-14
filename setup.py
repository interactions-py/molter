from pathlib import Path

from setuptools import setup

requirements = []
with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setup(
    name="interactions-molter",
    description=(
        "An extension library for interactions.py to add prefixed commands. A"
        " demonstration of molter-core."
    ),
    long_description=(Path(__file__).parent / "README.md").read_text(),
    long_description_content_type="text/markdown",
    author="Astrea49",
    url="https://github.com/interactions-py/molter",
    version="0.5.0",
    packages=["interactions.ext.molter"],
    include_package_data=True,
    python_requires=">=3.8.6",
    install_requires=requirements,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
