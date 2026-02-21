import json
import logging
from pathlib import Path

import requests


BASE_AWS_PRICING_URL = (
    "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current"
)
REQUEST_TIMEOUT_SECONDS = 45

LOGGER = logging.getLogger(__name__)


def build_region_pricing_url(region_name: str) -> str:
    return f"{BASE_AWS_PRICING_URL}/{region_name}/index.json"


def is_standard_linux_compute_product(product: dict, region_name: str) -> bool:
    attributes = product.get("attributes", {})

    if product.get("productFamily") != "Compute Instance":
        return False
    if not attributes.get("instanceType"):
        return False
    if attributes.get("regionCode") and attributes.get("regionCode") != region_name:
        return False
    if attributes.get("operatingSystem") != "Linux":
        return False
    if attributes.get("tenancy") != "Shared":
        return False
    if attributes.get("preInstalledSw") not in {None, "NA"}:
        return False
    if attributes.get("capacitystatus") not in {None, "Used"}:
        return False
    if attributes.get("licenseModel") not in {None, "No License required"}:
        return False
    if attributes.get("locationType") not in {None, "AWS Region"}:
        return False

    return True


def get_lowest_hourly_price(terms_for_sku: dict) -> float | None:
    prices = []

    for term in terms_for_sku.values():
        for dimension in term.get("priceDimensions", {}).values():
            if dimension.get("unit") != "Hrs":
                continue

            usd_price = dimension.get("pricePerUnit", {}).get("USD")
            if not usd_price:
                continue

            try:
                prices.append(float(usd_price))
            except (TypeError, ValueError):
                continue

    if not prices:
        return None

    return min(prices)


def get_prices(region_name: str, session: requests.Session) -> dict[str, float]:
    url = build_region_pricing_url(region_name)
    response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()

    data = response.json()
    products = data.get("products", {})
    ondemand_terms = data.get("terms", {}).get("OnDemand", {})
    prices = {}

    for sku, product in products.items():
        if not is_standard_linux_compute_product(product, region_name):
            continue

        instance_type = product["attributes"]["instanceType"]
        sku_terms = ondemand_terms.get(sku, {})
        lowest_price = get_lowest_hourly_price(sku_terms)
        if lowest_price is None:
            continue

        previous_price = prices.get(instance_type)
        if previous_price is None or lowest_price < previous_price:
            prices[instance_type] = lowest_price

    return dict(sorted(prices.items()))


def load_region_names(sites_path: Path) -> list[str]:
    sites = json.loads(sites_path.read_text(encoding="utf-8"))
    return [site["name"] for site in sites if "name" in site]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    base_dir = Path(__file__).resolve().parent
    sites_path = base_dir / "sites.json"
    output_path = base_dir / "prices.json"

    region_names = load_region_names(sites_path)
    all_prices = {}

    with requests.Session() as session:
        for region_name in region_names:
            LOGGER.info("Getting prices for %s...", region_name)
            try:
                all_prices[region_name] = get_prices(region_name, session)
            except requests.RequestException as exc:
                LOGGER.error("Failed to fetch prices for %s: %s", region_name, exc)
                all_prices[region_name] = {}

    output_path.write_text(
        json.dumps(all_prices, indent=2, sort_keys=True), encoding="utf-8"
    )
    LOGGER.info("Saved region price list to %s", output_path)


if __name__ == "__main__":
    main()
