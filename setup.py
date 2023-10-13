import os

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

with open("requirements-dev.txt", "r") as fh:
    tests_require = [line for line in fh.read().split(os.linesep) if line]

with open("requirements.txt", "r") as fh:
    install_requires = [line for line in fh.read().split(os.linesep) if line]

setuptools.setup(
    name="edgerun-galileo-experiments",
    version="0.0.2.dev16",
    author="Philipp Raith, Thomas Rausch",
    author_email="p.raith@dsg.tuwien.ac.at, t.rausch@dsg.tuwien.ac.at",
    description="Galileo Experiments",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/edgerun/galileo-experiments",
    packages=setuptools.find_packages(),
    setup_requires=['wheel'],
    install_requires=install_requires,
    pyton_requires='>=3.9',
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    entry_points={
    },

)
