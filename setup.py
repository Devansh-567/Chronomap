from setuptools import setup, find_packages
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

setup(
    name="chronomap",
    version="0.1.0",
    author="Devansh Singh",
    author_email="devansh.jay.singh@gmail.com",
    description="A time-versioned dictionary implementation for Python",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Devansh-567/chronomap",
    packages=find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Typing :: Typed",
    ],
    python_requires=">=3.7",
    keywords="temporal, versioning, time-series, history, snapshot, dictionary",
    project_urls={
        "Bug Reports": "https://github.com/Devansh-567/chronomap/issues",
        "Source": "https://github.com/Devansh-567/chronomap",
        "Documentation": "https://github.com/Devansh-567/chronomap#readme",
    },
    install_requires=[],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "mypy>=1.0.0",
            "flake8>=6.0.0",
        ],
    },
)
