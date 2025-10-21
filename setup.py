from setuptools import setup, find_packages
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

setup(
    name='chronomap',
    version='2.1.0',
    packages=find_packages(),
    install_requires=[],
    python_requires='>=3.8',
    extras_require={
        'pandas': ['pandas'],
    },
    entry_points={
        'console_scripts': [
            'chronomap=chronomap.cli:main',
        ],
    },
    long_description=long_description,
    long_description_content_type='text/markdown',
)
