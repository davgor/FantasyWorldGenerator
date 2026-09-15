"""Compatibility shim for build frontends with pre-PEP 621 setuptools."""

from setuptools import find_packages, setup


setup(
    name="fantasy-world-generator",
    version="0.1.0",
    description="Engine-independent procedural fantasy world simulation and Unreal interchange exports",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    python_requires=">=3.9",
    package_dir={"": "Sim"},
    packages=find_packages("Sim", include=("fantasy_world_generator", "fantasy_world_generator.*", "icarus_sim", "icarus_sim.*")),
    package_data={"fantasy_world_generator": ["*.json"], "icarus_sim": ["*.json"]},
    entry_points={"console_scripts": ["fantasy-world=fantasy_world_generator.cli:main"]},
)
