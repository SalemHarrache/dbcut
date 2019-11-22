#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os.path as op
import re
from codecs import open

from setuptools import find_packages, setup


def read(fname):
    """ Return the file content. """
    here = op.abspath(op.dirname(__file__))
    with open(op.join(here, fname), "r", "utf-8") as fd:
        return fd.read()


readme = read("README.md")
changelog = read("CHANGES.md")

version = ""
version = re.search(
    r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]',
    read(op.join("dbcut", "__init__.py")),
    re.MULTILINE,
).group(1)

if not version:
    raise RuntimeError("Cannot find version information")

setup(
    name="dbcut",
    author="Salem Harrache",
    python_requires=">=3.4",
    author_email="salem@harrache.info",
    version=version,
    url="https://github.com/itsolutionsfactory/dbcut",
    package_dir={"dbcut": "dbcut"},
    packages=find_packages(),
    install_requires=[
        "SQLAlchemy",
        "SQLAlchemy-Utils",
        "mlalchemy",
        "marshmallow-sqlalchemy",
        "python-dotenv",
        "tabulate",
        "tqdm",
        "pptree",
        "Click",
    ],
    extras_require={
        "mysql": ["mysqlclient"],
        "postgresql": ["psycopg2"],
        "profiler": ["sqlalchemy-easy-profile", "sqlparse"],
        "fastjson": [],
        "dev": ["jedi", "pdbpp", "bumpversion", "flake8", "wheel", "twine"],
        "test": ["tox", "pytest", "pytest-cov", "pytest-sugar", "coverage"],
    },
    include_package_data=True,
    zip_safe=False,
    description="Extract a lightweight subset of your production DB for development and testing purpose.",
    long_description=readme + "\n\n" + changelog,
    keywords="dbcut",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    entry_points="""
    [console_scripts]
    dbcut=dbcut.cli.main:main
    """,
)