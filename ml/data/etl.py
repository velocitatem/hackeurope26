import json
import os
import sys
import pandas as pd
import re
from accelerator_mappings import (
    AWS_ACCELERATOR_MAP,
    AWS_GPU_COUNT_MAP,
    AZURE_ACCELERATOR_MAP,
    AZURE_GPU_PATTERNS,
    GCP_ACCELERATOR_MAP,
    GCP_GPU_COUNT_PATTERNS,
)


def classify_aws_accelerator(instance_type: str) -> dict:
    """
    Classify AWS instance type to accelerator metadata.
    Returns: {resource_kind, vendor, family, model, count, memory_mib, cpu_arch, notes}
    """
    # Extract family prefix (e.g., g6, p5, inf2)
    match = re.match(r"^([a-z]+\d+[a-z]?)", instance_type)
    if not match:
        return {
            "resource_kind": "cpu",
            "vendor": "none",
            "family": "none",
            "model": "none",
            "count": 0,
            "memory_mib": None,
            "cpu_arch": "x86_64",
            "notes": None,
        }

    family = match.group(1)

    # Check if accelerator family
    if family not in AWS_ACCELERATOR_MAP:
        # CPU-only instance
        cpu_arch = (
            "arm64"
            if instance_type.startswith(("a1", "t4g", "m6g", "c6g", "r6g"))
            else "x86_64"
        )
        return {
            "resource_kind": "cpu",
            "vendor": "none",
            "family": "none",
            "model": "none",
            "count": 0,
            "memory_mib": None,
            "cpu_arch": cpu_arch,
            "notes": None,
        }

    # Get base accelerator info
    accel_info = AWS_ACCELERATOR_MAP[family]
    vendor = accel_info["vendor"]
    accel_family = accel_info["family"]
    model = accel_info["model"]
    memory_mib = accel_info.get("memory_mib")

    # Determine resource kind
    if vendor == "nvidia" or vendor == "amd":
        resource_kind = "gpu"
    else:
        resource_kind = "asic"

    # Get GPU count
    count = AWS_GPU_COUNT_MAP.get(instance_type, 1)  # Default to 1 if not in map

    # Handle fractional GPUs
    notes = None
    if accel_info.get("fractional") and count == 0:
        # Extract fractional count from size (e.g., g6f.large = 0.125)
        fractional_map = {
            "large": 0.125,
            "xlarge": 0.25,
            "2xlarge": 0.5,
            "4xlarge": 1.0,
        }
        size = instance_type.split(".")[-1]
        fractional_count = fractional_map.get(size, 0.125)
        notes = f"{fractional_count} GPU share"

    # CPU architecture (Graviton = ARM, others = x86)
    cpu_arch = "arm64" if family in ("g5g",) else "x86_64"

    return {
        "resource_kind": resource_kind,
        "vendor": vendor,
        "family": accel_family,
        "model": model,
        "count": count,
        "memory_mib": memory_mib,
        "cpu_arch": cpu_arch,
        "notes": notes,
    }


def classify_azure_accelerator(sku: str) -> dict:
    """
    Classify Azure SKU to accelerator metadata.
    Pattern: Standard_N{C,D,V,G,P,M}{ads,v4,v3}_{size}_{gpu_model}_v{version}
    """
    # Strip _Promo suffix
    sku_clean = sku.replace("_Promo", "")

    # Check if N-series (accelerated)
    if not sku_clean.startswith("Standard_N"):
        # CPU-only
        cpu_arch = (
            "arm64"
            if "_arm64_" in sku_clean.lower()
            or sku_clean.startswith("Standard_D")
            and "ps" in sku_clean
            else "x86_64"
        )
        return {
            "resource_kind": "cpu",
            "vendor": "none",
            "family": "none",
            "model": "none",
            "count": 0,
            "memory_mib": None,
            "cpu_arch": cpu_arch,
            "notes": None,
        }

    # Extract GPU model token from SKU name
    vendor = "nvidia"  # Default
    family = "unknown"
    model = "unknown"
    memory_mib = None
    notes = None

    for gpu_token, gpu_info in AZURE_ACCELERATOR_MAP.items():
        if f"_{gpu_token}_" in sku_clean or sku_clean.endswith(f"_{gpu_token}"):
            vendor = gpu_info["vendor"]
            family = gpu_info["family"]
            model = gpu_info["model"]
            memory_mib = gpu_info["memory_mib"]
            break

    # Infer from series if no token match
    if family == "unknown":
        if "_NC" in sku_clean:
            if "v4" in sku_clean:
                vendor, family, model = "nvidia", "A100", "A100 80GB"
                memory_mib = 81920
            elif "v3" in sku_clean:
                vendor, family, model = "nvidia", "V100", "V100"
                memory_mib = 16384
            elif "v2" in sku_clean:
                vendor, family, model = "nvidia", "P100", "P100"
                memory_mib = 16384
        elif "_ND" in sku_clean:
            if "H100" in sku_clean or "v5" in sku_clean:
                vendor, family, model = "nvidia", "H100", "H100"
                memory_mib = 81920
            elif "A100" in sku_clean or "v4" in sku_clean:
                vendor, family, model = "nvidia", "A100", "A100 40GB"
                memory_mib = 40960
        elif "_NV" in sku_clean:
            vendor, family, model = "nvidia", "M60", "M60"
            memory_mib = 8192

    # Extract GPU count from size suffix (e.g., Standard_NC6s_v3 = 1 GPU, NC24s_v3 = 4 GPUs)
    count = 1
    size_match = re.search(r"_(\d+)", sku_clean)
    if size_match:
        vcpu_count = int(size_match.group(1))
        # Heuristic: GPUs typically scale with vCPUs (6 vCPU = 1 GPU, 12 = 2, 24 = 4, etc.)
        if vcpu_count >= 96:
            count = 8
        elif vcpu_count >= 48:
            count = 4
        elif vcpu_count >= 24:
            count = 4
        elif vcpu_count >= 12:
            count = 2
        else:
            count = 1

    # Check for fractional GPU (NV series with small sizes)
    if "_NV" in sku_clean and "ads" in sku_clean:
        fractional_sizes = {"6": 0.166, "12": 0.333, "18": 0.5}
        if size_match and size_match.group(1) in fractional_sizes:
            notes = f"{fractional_sizes[size_match.group(1)]} GPU share"
            count = 0

    resource_kind = "gpu" if vendor in ("nvidia", "amd") else "asic"

    return {
        "resource_kind": resource_kind,
        "vendor": vendor,
        "family": family,
        "model": model,
        "count": count,
        "memory_mib": memory_mib,
        "cpu_arch": "x86_64",
        "notes": notes,
    }


def classify_gcp_accelerator(machine_type: str) -> dict:
    """
    Classify GCP machine type to accelerator metadata.
    Patterns: a2-*, a3-*, g2-*, *-tpu
    """
    # Check for TPU
    if "tpu" in machine_type.lower():
        tpu_info = GCP_ACCELERATOR_MAP["tpu"]
        # Extract TPU count from suffix (e.g., ct5lp-hightpu-1t = 1 chip, 4t = 4 chips)
        count = 1
        tpu_match = re.search(r"-(\d+)t", machine_type)
        if tpu_match:
            count = int(tpu_match.group(1))

        return {
            "resource_kind": "tpu",
            "vendor": tpu_info["vendor"],
            "family": tpu_info["family"],
            "model": tpu_info["model"],
            "count": count,
            "memory_mib": tpu_info.get("memory_mib"),
            "cpu_arch": "x86_64",
            "notes": None,
        }

    # Check for GPU families (a2, a3, g2)
    gpu_family = None
    for prefix in GCP_ACCELERATOR_MAP.keys():
        if machine_type.startswith(prefix):
            gpu_family = prefix
            break

    if not gpu_family:
        # CPU-only (e.g., n1, n2, e2, c2, m1)
        cpu_arch = "arm64" if machine_type.startswith("t2a") else "x86_64"
        return {
            "resource_kind": "cpu",
            "vendor": "none",
            "family": "none",
            "model": "none",
            "count": 0,
            "memory_mib": None,
            "cpu_arch": cpu_arch,
            "notes": None,
        }

    # Get accelerator info
    accel_info = GCP_ACCELERATOR_MAP[gpu_family]
    vendor = accel_info["vendor"]
    family = accel_info["family"]
    model = accel_info["model"]
    memory_mib = accel_info.get("memory_mib")

    # Extract GPU count
    count = 1  # Default

    # Check for -Ng suffix (a2-highgpu-1g, a3-highgpu-8g)
    for suffix, gpu_count in GCP_GPU_COUNT_PATTERNS.items():
        if suffix.startswith("-") and machine_type.endswith(suffix):
            count = gpu_count
            break

    # G2 specific patterns (g2-standard-N maps to GPU count)
    if gpu_family == "g2-standard":
        for pattern, gpu_count in GCP_GPU_COUNT_PATTERNS.items():
            if pattern.startswith("g2-") and machine_type == pattern:
                count = gpu_count
                break

    return {
        "resource_kind": "gpu",
        "vendor": vendor,
        "family": family,
        "model": model,
        "count": count,
        "memory_mib": memory_mib,
        "cpu_arch": "x86_64",
        "notes": None,
    }


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
                location_name = site["location"]
                coordinates: list = site["coordinates"]
                lat, lon = coordinates[0], coordinates[1]
                for instance_type, price in self.prices[cloud][region].items():
                    # Classify accelerator based on cloud provider
                    if cloud == "aws":
                        accel = classify_aws_accelerator(instance_type)
                    elif cloud == "azure":
                        accel = classify_azure_accelerator(instance_type)
                    elif cloud == "gcp":
                        accel = classify_gcp_accelerator(instance_type)
                    else:
                        accel = {
                            "resource_kind": "cpu",
                            "vendor": "none",
                            "family": "none",
                            "model": "none",
                            "count": 0,
                            "memory_mib": None,
                            "cpu_arch": "x86_64",
                            "notes": None,
                        }

                    rows.append(
                        {
                            "provider": cloud,
                            "region": region,
                            "sku": instance_type,
                            "location_name": location_name,
                            "latitude": lat,
                            "longitude": lon,
                            "price_usd_hour": price,
                            "resource_kind": accel["resource_kind"],
                            "accelerator_vendor": accel["vendor"],
                            "accelerator_family": accel["family"],
                            "accelerator_model": accel["model"],
                            "accelerator_count": accel["count"],
                            "accelerator_memory_mib": accel["memory_mib"],
                            "cpu_arch": accel["cpu_arch"],
                            "notes": accel["notes"],
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
    df = last_step
    # filter where in france or UK
    df = df[df["location_name"].str.contains("Finland", case=False, na=False)]
    print(df)
    print(df["region"].value_counts())
