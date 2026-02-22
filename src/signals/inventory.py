from __future__ import annotations

import os
import sys
import json
from pathlib import Path

from src.models import InventoryNode


COUNTRY_TO_GEO = {
    "Austria": "AT",
    "Belgium": "BE",
    "Denmark": "DK",
    "Finland": "FI",
    "France": "FR",
    "Germany": "DE",
    "Ireland": "IE",
    "Italy": "IT",
    "Netherlands": "NL",
    "Poland": "PL",
    "Spain": "ES",
    "Sweden": "SE",
    "Switzerland": "CH",
    "United Kingdom": "GB",
}


def _build_geo_to_regions() -> dict[str, set[str]]:
    root = Path(__file__).resolve().parents[2]
    base = root / "ml" / "data" / "regions"
    mapping: dict[str, set[str]] = {}
    for provider in ("aws", "azure", "gcp"):
        sites_path = base / provider / "sites.json"
        if not sites_path.exists():
            continue
        sites = json.loads(sites_path.read_text(encoding="utf-8"))
        for site in sites:
            region = str(site.get("name", ""))
            location = str(site.get("location", ""))
            if not region or not location:
                continue
            country = location.split(",")[-1].strip()
            geo = COUNTRY_TO_GEO.get(country)
            if not geo:
                continue
            mapping.setdefault(geo, set()).add(region)

    if mapping:
        return mapping

    return {
        "FR": {"eu-west-3", "francecentral", "europe-west9"},
        "DE": {"eu-central-1", "germanywestcentral", "europe-west3"},
        "ES": {"eu-south-2", "spaincentral"},
    }


GEO_TO_REGIONS = _build_geo_to_regions()


def _geo_from_region(region: str) -> str | None:
    for geo, regions in GEO_TO_REGIONS.items():
        if region in regions:
            return geo
    return None


class InventoryClient:
    def __init__(self):
        self._cache: list[InventoryNode] | None = None

    def load(self) -> list[InventoryNode]:
        if self._cache is not None:
            return self._cache

        root = Path(__file__).resolve().parents[2]
        data_dir = root / "ml" / "data"
        sys.path.append(str(data_dir))

        from etl import ComputeLoader  # type: ignore

        loader = ComputeLoader()
        loader.aws_sites = str(data_dir / "regions" / "aws" / "sites.json")
        loader.azure_sites = str(data_dir / "regions" / "azure" / "sites.json")
        loader.gcp_sites = str(data_dir / "regions" / "gcp" / "sites.json")
        loader.aws_prices = str(data_dir / "regions" / "aws" / "prices.json")
        loader.azure_prices = str(data_dir / "regions" / "azure" / "prices.json")
        loader.gcp_prices = str(data_dir / "regions" / "gcp" / "prices.json")
        loader.sites = [loader.aws_sites, loader.azure_sites, loader.gcp_sites]
        loader.prices = [loader.aws_prices, loader.azure_prices, loader.gcp_prices]

        old_cwd = os.getcwd()
        try:
            os.chdir(str(data_dir))
            df = loader.fit_transform()
        finally:
            os.chdir(old_cwd)

        nodes: list[InventoryNode] = []
        gpu_df = df[(df["resource_kind"] == "gpu") & (df["accelerator_count"] > 0)]
        for _, row in gpu_df.iterrows():
            region = str(row["region"])
            geo = _geo_from_region(region)
            if geo is None:
                continue
            memory = row["accelerator_memory_mib"]
            if memory != memory:  # NaN check
                memory = None
            nodes.append(
                InventoryNode(
                    provider=str(row["provider"]).upper(),
                    region=region,
                    geo=geo,
                    sku=str(row["sku"]),
                    price_usd_hour=float(row["price_usd_hour"]),
                    gpu_count=int(row["accelerator_count"]),
                    gpu_memory_mib=int(memory) if memory is not None else None,
                )
            )

        self._cache = nodes
        return nodes

    def feasible_nodes(
        self,
        geo: str,
        gpu_count: int,
        min_gpu_memory_mib: int,
        max_price_usd_hour: float | None,
    ) -> list[InventoryNode]:
        nodes = []
        for node in self.load():
            if node.geo != geo:
                continue
            if node.gpu_count < gpu_count:
                continue
            if (
                node.gpu_memory_mib is not None
                and node.gpu_memory_mib < min_gpu_memory_mib
            ):
                continue
            if (
                max_price_usd_hour is not None
                and node.price_usd_hour > max_price_usd_hour
            ):
                continue
            nodes.append(node)
        return nodes
