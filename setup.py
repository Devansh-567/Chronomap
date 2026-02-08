from setuptools import setup, find_packages
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

setup(
    name='chronomap',
    version='2.2.0',
    packages=find_packages(),
    install_requires=[],
    python_requires='>=3.8',
    extras_require={
        'pandas': ['pandas>=1.0.0'],
    },
    entry_points={
        'console_scripts': [
            'chronomap=chronomap.cli:main',
        ],
    },
    author='Devansh Singh',
    author_email='devansh.jay.singh@gmail.com',
    description='Production-grade thread-safe, time-versioned key-value store with snapshots, queries, async support, and advanced performance features',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/Devansh-567/chronomap',
    license='MIT',
    keywords=['chronomap', 'timestamp', 'key-value', 'time-series', 'snapshot', 'async', 'rwlock', 'lru-cache', 'versioning'],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Operating System :: OS Independent',
        'Topic :: Database',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
