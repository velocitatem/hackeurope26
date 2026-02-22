from setuptools import setup, find_packages

setup(
    name="lib",
    version="0.1.0",
    packages=find_packages(exclude=["apps*", "ml*", "tests*"]),
    install_requires=[
        "python-logging-loki",
        "python-dotenv",
        "beautifulsoup4",
        "requests",
    ],
    extras_require={
        "scraper": ["seleniumbase"],
        "ai": ["anthropic"],
    },
)
