from setuptools import setup, find_packages

setup(
    name="tinydb",
    version="0.2.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "tinydb=tinydb.cli:main",
        ],
    },
)
