import json
import logging
import os
import subprocess
from pathlib import Path

import requests


CLOUD_BILLING_BASE_URL = "https://cloudbilling.googleapis.com/v1"
COMPUTE_API_BASE_URL = "https://compute.googleapis.com/compute/v1"
COMPUTE_ENGINE_SERVICE_ID = "6F81-5844-456A"
REQUEST_TIMEOUT_SECONDS = 60
PAGE_SIZE = 5000

LOGGER = logging.getLogger(__name__)

CPU_TAG_PATTERNS = [
    ("n2d amd", "n2d"),
    ("t2d amd", "t2d"),
    ("c2d amd", "c2d"),
    ("c4a arm", "c4a"),
    ("n4a", "n4a"),
    ("n4d", "n4d"),
    ("n4 ", "n4"),
    ("n2 ", "n2"),
    ("e2 ", "e2"),
    ("n1 predefined", "n1"),
    ("compute optimized", "c2"),
    ("c3d", "c3d"),
    ("c3 ", "c3"),
    ("c4d", "c4d"),
    ("c4 ", "c4"),
    ("a4 ", "a4"),
    ("a3plus", "a3"),
    ("a3ultra", "a3"),
    ("a3 ", "a3"),
    ("a2 ", "a2"),
    ("g4 ", "g4"),
    ("g2 ", "g2"),
    ("h3 ", "h3"),
    ("m4ultramem", "m4-ultramem"),
    ("m4 ", "m4"),
    ("m3 memory-optimized", "m3"),
    ("memory-optimized", "memory-optimized"),
    ("z3 ", "z3"),
]

EXCLUDED_SKU_KEYWORDS = (
    "spot",
    "preemptible",
    "commitment",
    "committed use",
    "reserved",
    "sole tenancy",
    "overcommit",
    "defined duration",
    "calendar mode",
    "upgrade premium",
    "premium for",
    "attached to dws",
    "vm state",
)


def run_command(command: list[str]) -> str:
    return subprocess.check_output(command, text=True).strip()


def get_access_token() -> str:
    token = os.getenv("GCP_ACCESS_TOKEN")
    if token:
        return token
    return run_command(["gcloud", "auth", "application-default", "print-access-token"])


def get_project_id() -> str:
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
    if project_id:
        return project_id
    project_id = run_command(["gcloud", "config", "get-value", "project"])
    if not project_id:
        raise RuntimeError("No GCP project configured. Set GOOGLE_CLOUD_PROJECT.")
    return project_id


def load_region_names(sites_path: Path) -> list[str]:
    sites = json.loads(sites_path.read_text(encoding="utf-8"))
    return [site["name"] for site in sites if "name" in site]


def to_price_usd(unit_price: dict) -> float:
    units = int(unit_price.get("units", 0))
    nanos = int(unit_price.get("nanos", 0))
    return units + (nanos / 1_000_000_000)


def extract_sku_price_usd(sku: dict) -> float | None:
    pricing_info = sku.get("pricingInfo", [])
    if not pricing_info:
        return None

    pricing_expression = pricing_info[-1].get("pricingExpression", {})
    tiered_rates = pricing_expression.get("tieredRates", [])
    if not tiered_rates:
        return None

    positive_rates = []
    for rate in tiered_rates:
        price = to_price_usd(rate.get("unitPrice", {}))
        if price > 0:
            positive_rates.append(price)

    if not positive_rates:
        return None

    return min(positive_rates)


def is_excluded_sku(description: str) -> bool:
    lower = description.lower()
    return any(keyword in lower for keyword in EXCLUDED_SKU_KEYWORDS)


def infer_cpu_ram_tag(description: str) -> str | None:
    lower = description.lower()
    for pattern, tag in CPU_TAG_PATTERNS:
        if pattern in lower:
            return tag
    return None


def infer_gpu_type(description: str) -> str | None:
    lower = description.lower()
    if "h100 mega" in lower:
        return "nvidia-h100-mega-80gb"
    if "h100 80gb" in lower:
        return "nvidia-h100-80gb"
    if "h200 141gb" in lower:
        return "nvidia-h200-141gb"
    if "a100 80gb" in lower:
        return "nvidia-a100-80gb"
    if "tesla a100" in lower:
        return "nvidia-tesla-a100"
    if "nvidia l4" in lower:
        return "nvidia-l4"
    if "tesla t4" in lower:
        return "nvidia-tesla-t4"
    if "tesla p100" in lower:
        return "nvidia-tesla-p100"
    if "b200" in lower:
        return "nvidia-b200"
    return None


def discover_compute_skus(session: requests.Session, headers: dict) -> list[dict]:
    skus = []
    endpoint = f"{CLOUD_BILLING_BASE_URL}/services/{COMPUTE_ENGINE_SERVICE_ID}/skus"
    page_token = None

    while True:
        params = {"currencyCode": "USD", "pageSize": PAGE_SIZE}
        if page_token:
            params["pageToken"] = page_token

        response = session.get(
            endpoint,
            headers=headers,
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()

        skus.extend(payload.get("skus", []))
        page_token = payload.get("nextPageToken")
        if not page_token:
            break

    return skus


def min_assign(target: dict[str, float], key: str, price: float) -> None:
    existing = target.get(key)
    if existing is None or price < existing:
        target[key] = price


def build_region_price_tables(skus: list[dict], region_name: str) -> dict:
    cpu_prices = {}
    ram_prices = {}
    gpu_prices = {}
    f1_micro_price = None
    g1_small_price = None

    for sku in skus:
        if region_name not in sku.get("serviceRegions", []):
            continue

        category = sku.get("category", {})
        if category.get("resourceFamily") != "Compute":
            continue
        if category.get("usageType") != "OnDemand":
            continue

        description = sku.get("description", "")
        if not description or is_excluded_sku(description):
            continue

        price = extract_sku_price_usd(sku)
        if price is None:
            continue

        resource_group = category.get("resourceGroup", "")
        description_lower = description.lower()

        if resource_group == "F1Micro" and "burstable cpu" in description_lower:
            if f1_micro_price is None or price < f1_micro_price:
                f1_micro_price = price
            continue

        if resource_group == "G1Small" and "small instance" in description_lower:
            if g1_small_price is None or price < g1_small_price:
                g1_small_price = price
            continue

        if resource_group == "GPU" and "gpu running" in description_lower:
            gpu_type = infer_gpu_type(description)
            if gpu_type:
                min_assign(gpu_prices, gpu_type, price)
            continue

        if resource_group == "CPU" and "core running" in description_lower:
            tag = infer_cpu_ram_tag(description)
            if tag:
                min_assign(cpu_prices, tag, price)
            continue

        if resource_group == "RAM" and "ram running" in description_lower:
            tag = infer_cpu_ram_tag(description)
            if tag:
                min_assign(ram_prices, tag, price)

    return {
        "cpu": cpu_prices,
        "ram": ram_prices,
        "gpu": gpu_prices,
        "f1_micro": f1_micro_price,
        "g1_small": g1_small_price,
    }


def get_region_machine_types(
    session: requests.Session, headers: dict, project_id: str, region_name: str
) -> list[dict]:
    region_url = f"{COMPUTE_API_BASE_URL}/projects/{project_id}/regions/{region_name}"
    region_response = session.get(
        region_url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS
    )
    region_response.raise_for_status()
    region_payload = region_response.json()

    zones = sorted(zone.rsplit("/", 1)[-1] for zone in region_payload.get("zones", []))
    if not zones:
        return []

    zone_name = zones[0]
    machine_types_url = (
        f"{COMPUTE_API_BASE_URL}/projects/{project_id}/zones/{zone_name}/machineTypes"
    )
    machine_types_response = session.get(
        machine_types_url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS
    )
    machine_types_response.raise_for_status()
    return machine_types_response.json().get("items", [])


def infer_machine_tag(machine_type_name: str) -> str | None:
    if machine_type_name == "f1-micro":
        return "f1-micro"
    if machine_type_name == "g1-small":
        return "g1-small"

    prefix_rules = [
        ("n2d-", "n2d"),
        ("t2d-", "t2d"),
        ("c2d-", "c2d"),
        ("c4a-", "c4a"),
        ("c4d-", "c4d"),
        ("c4-", "c4"),
        ("c3d-", "c3d"),
        ("c3-", "c3"),
        ("c2-", "c2"),
        ("n4a-", "n4a"),
        ("n4d-", "n4d"),
        ("n4-", "n4"),
        ("n2-", "n2"),
        ("e2-", "e2"),
        ("n1-", "n1"),
        ("a4x-", "a4"),
        ("a4-", "a4"),
        ("a3-", "a3"),
        ("a2-", "a2"),
        ("g4-", "g4"),
        ("g2-", "g2"),
        ("h3-", "h3"),
        ("m4-ultramem", "m4-ultramem"),
        ("m4-", "m4"),
        ("m3-", "m3"),
        ("m2-", "memory-optimized"),
        ("m1-", "memory-optimized"),
        ("z3-", "z3"),
    ]

    for prefix, tag in prefix_rules:
        if machine_type_name.startswith(prefix):
            return tag
    return None


def resolve_gpu_price(gpu_type: str, gpu_prices: dict[str, float]) -> float | None:
    if gpu_type in gpu_prices:
        return gpu_prices[gpu_type]

    fallback_map = {
        "nvidia-h100-mega-80gb": "nvidia-h100-mega-80gb",
        "nvidia-h100-80gb": "nvidia-h100-80gb",
        "nvidia-h200-141gb": "nvidia-h200-141gb",
        "nvidia-a100-80gb": "nvidia-a100-80gb",
        "nvidia-tesla-a100": "nvidia-tesla-a100",
        "nvidia-l4": "nvidia-l4",
        "nvidia-tesla-t4": "nvidia-tesla-t4",
        "nvidia-tesla-p100": "nvidia-tesla-p100",
        "nvidia-b200": "nvidia-b200",
    }

    mapped_type = fallback_map.get(gpu_type)
    if mapped_type:
        return gpu_prices.get(mapped_type)
    return None


def get_effective_vcpus(machine_type_name: str, guest_cpus: int) -> float:
    if machine_type_name == "e2-micro":
        return 0.25
    if machine_type_name == "e2-small":
        return 0.5
    if machine_type_name == "e2-medium":
        return 1.0
    return float(guest_cpus)


def calculate_machine_type_price(
    machine_type: dict, price_tables: dict
) -> float | None:
    machine_type_name = machine_type.get("name", "")
    if not machine_type_name:
        return None

    if machine_type_name == "f1-micro":
        return price_tables.get("f1_micro")
    if machine_type_name == "g1-small":
        return price_tables.get("g1_small")

    tag = infer_machine_tag(machine_type_name)
    if not tag:
        return None

    cpu_price = price_tables["cpu"].get(tag)
    ram_price = price_tables["ram"].get(tag)
    if cpu_price is None or ram_price is None:
        return None

    guest_cpus = machine_type.get("guestCpus")
    memory_mb = machine_type.get("memoryMb")
    if guest_cpus is None or memory_mb is None:
        return None

    effective_vcpus = get_effective_vcpus(machine_type_name, int(guest_cpus))
    memory_gib = float(memory_mb) / 1024
    total_price = (effective_vcpus * cpu_price) + (memory_gib * ram_price)

    accelerators = machine_type.get("accelerators", []) or []
    if accelerators:
        for accelerator in accelerators:
            gpu_type = accelerator.get("guestAcceleratorType")
            gpu_count = accelerator.get("guestAcceleratorCount", 0)
            if not gpu_type or not gpu_count:
                continue

            gpu_price = resolve_gpu_price(gpu_type, price_tables["gpu"])
            if gpu_price is None:
                return None

            total_price += float(gpu_count) * gpu_price

    return round(total_price, 6)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    base_dir = Path(__file__).resolve().parent
    sites_path = base_dir / "sites.json"
    output_path = base_dir / "prices.json"

    region_names = load_region_names(sites_path)
    project_id = get_project_id()
    access_token = get_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}

    all_prices = {}

    with requests.Session() as session:
        LOGGER.info("Loading Compute Engine SKU catalog...")
        skus = discover_compute_skus(session, headers)
        LOGGER.info("Loaded %s SKUs", len(skus))

        for region_name in region_names:
            LOGGER.info("Getting prices for %s...", region_name)
            try:
                machine_types = get_region_machine_types(
                    session, headers, project_id, region_name
                )
                price_tables = build_region_price_tables(skus, region_name)

                region_prices = {}
                for machine_type in machine_types:
                    price = calculate_machine_type_price(machine_type, price_tables)
                    if price is None:
                        continue
                    region_prices[machine_type["name"]] = price

                all_prices[region_name] = dict(sorted(region_prices.items()))
                LOGGER.info(
                    "Found %s machine prices for %s",
                    len(region_prices),
                    region_name,
                )
            except requests.RequestException as exc:
                LOGGER.error("Failed to fetch prices for %s: %s", region_name, exc)
                all_prices[region_name] = {}

    output_path.write_text(
        json.dumps(all_prices, indent=2, sort_keys=True), encoding="utf-8"
    )
    LOGGER.info("Saved region price list to %s", output_path)


if __name__ == "__main__":
    main()
