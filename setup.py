from setuptools import setup, find_packages
from cm_deployer import __version__

setup(
    name="cm-deployer",
    version=__version__,
    packages=find_packages(),
    package_data={
        "cm_deployer": ["templates/*.yaml", "templates/argocd/*.yaml"],
    },
    install_requires=[
        "pyyaml>=6.0",
        "pytest>=7.0",
        "cryptography>=39.0.0",
        "authlib>=1.2.0",
        "kubernetes>=28.1.0"
    ],
    entry_points={
        'console_scripts': [
            'cm-deploy=cm_deployer.cli:main',
        ],
    },
    python_requires='>=3.12',
)