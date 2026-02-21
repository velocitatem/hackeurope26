import json
import logging
from pathlib import Path

import requests


AZURE_RETAIL_PRICES_URL = "https://prices.azure.com/api/retail/prices"
AZURE_API_VERSION = "2023-01-01-preview"
REQUEST_TIMEOUT_SECONDS = 45

LOGGER = logging.getLogger(__name__)


def build_region_filter(region_name: str) -> str:
    return (
        "serviceName eq 'Virtual Machines' "
        f"and armRegionName eq '{region_name}' "
        "and type eq 'Consumption'"
    )


def is_payg_linux_vm_item(item: dict, region_name: str) -> bool:
    product_name = item.get("productName", "")
    sku_name = item.get("skuName", "")
    meter_name = item.get("meterName", "")
    instance_type = item.get("armSkuName", "")

    if item.get("serviceName") != "Virtual Machines":
        return False
    if item.get("armRegionName") != region_name:
        return False
    if item.get("type") != "Consumption":
        return False
    if item.get("currencyCode") != "USD":
        return False
    if item.get("unitOfMeasure") != "1 Hour":
        return False
    if not instance_type.startswith("Standard_"):
        return False
    if not product_name.startswith("Virtual Machines"):
        return False
    if "Windows" in product_name:
        return False
    if any(token in sku_name for token in ("Spot", "Low Priority", "Promo")):
        return False
    if any(token in meter_name for token in ("Spot", "Low Priority", "Promo")):
        return False

    return True


def get_region_prices(region_name: str, session: requests.Session) -> dict[str, float]:
    prices = {}
    next_page_url = AZURE_RETAIL_PRICES_URL
    params = {
        "api-version": AZURE_API_VERSION,
        "$filter": build_region_filter(region_name),
    }

    while next_page_url:
        response = session.get(
            next_page_url, params=params, timeout=REQUEST_TIMEOUT_SECONDS
        )
        response.raise_for_status()

        payload = response.json()
        for item in payload.get("Items", []):
            if not is_payg_linux_vm_item(item, region_name):
                continue

            instance_type = item["armSkuName"]
            retail_price = item.get("retailPrice")
            if retail_price is None:
                continue

            try:
                price = float(retail_price)
            except (TypeError, ValueError):
                continue

            if price <= 0:
                continue

            previous_price = prices.get(instance_type)
            if previous_price is None or price < previous_price:
                prices[instance_type] = price

        next_page_url = payload.get("NextPageLink")
        params = None

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
                region_prices = get_region_prices(region_name, session)
                all_prices[region_name] = region_prices
                LOGGER.info(
                    "Found %s VM prices for %s", len(region_prices), region_name
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
