import json
import os
import sys
import pandas as pd


class ComputeLoader:
    def __init__(self):
        self.aws_sites = "./regions/aws/sites.json"
        self.azure_sites = "./regions/azure/sites.json"
        self.gcp_sites = "./regions/gcp/sites.json"
        self.aws_prices = "./regions/aws/prices.json"
        self.azure_prices = "./regions/azure/prices.json"
        self.gcp_prices = "./regions/gcp/prices.json"

        self.sites = [self.aws_sites, self.azure_sites, self.gcp_sites]
        self.prices = [self.aws_prices, self.azure_prices, self.gcp_prices]

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        S, P = self.sites.copy(), self.prices.copy()
        self.sites = {}
        for s in S:
            site_name = s.split("/")[-2]  # ex aws
            with open(s, "r") as f:
                self.sites[site_name] = json.load(f)
        self.prices = {}
        for p in P:
            price_name = p.split("/")[-2]  # ex aws
            with open(p, "r") as f:
                self.prices[price_name] = json.load(f)

        rows = []
        for cloud in self.sites:
            for site in self.sites[cloud]:
                region = site["name"]
                for instance_type, price in self.prices[cloud][region].items():
                    rows.append(
                        {
                            "cloud": cloud,
                            "region": region,
                            "instance_type": instance_type,
                            "price": price,
                        }
                    )
        return pd.DataFrame(rows)

    def fit_transform(self, X=None, y=None):
        return self.fit(X, y).transform(X)


if __name__ == "__main__":
    pipeline = [ComputeLoader()]
    last_step = None
    for step in pipeline:
        last_step = step.fit_transform(last_step)
    print(last_step)
