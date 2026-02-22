from setuptools import setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="tot-engine-memory",
    version="1.0.0",
    author="Thunderbolt AI",
    description="Pure in-memory Tree of Thought Engine - zero dependencies",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/gaharivatsa/tot-engine-memory",
    py_modules=["tot_engine_memory", "enforcement", "config"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.8",
    install_requires=[],  # No dependencies!
)
