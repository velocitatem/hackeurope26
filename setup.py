from setuptools import setup, find_packages

setup(
    name="sustain",
    version="0.1.0",
    description="Energy-aware compute scheduler - pip-installable core library",
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
        "mlflow": ["mlflow>=2.0"],
        "wandb": ["wandb>=0.15"],
        "ml": ["torch", "tensorboard"],
    },
)
