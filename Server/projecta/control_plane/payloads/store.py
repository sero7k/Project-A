"""Store and purchase payload builders."""

from __future__ import annotations

from typing import Any, Callable


def store_offers_payload() -> dict[str, Any]:
    return {
        "Offers": [],
        "offers": [],
        "UpgradeCurrencyOffers": [],
        "upgradeCurrencyOffers": [],
    }


def store_v2_storefront_payload(local_bundle_id: str, local_currency_id: str) -> dict[str, Any]:
    bundle = {
        "ID": local_bundle_id,
        "id": local_bundle_id,
        "DataAssetID": local_bundle_id,
        "dataAssetID": local_bundle_id,
        "DataAssetId": local_bundle_id,
        "dataAssetId": local_bundle_id,
        "CurrencyID": local_currency_id,
        "currencyID": local_currency_id,
        "CurrencyId": local_currency_id,
        "currencyId": local_currency_id,
        "Items": [],
        "items": [],
    }
    skins_panel = {
        "SingleItemOffers": [],
        "singleItemOffers": [],
        "SingleItemStoreOffers": [],
        "singleItemStoreOffers": [],
        "SingleItemOffersRemainingDurationInSeconds": 3600,
        "singleItemOffersRemainingDurationInSeconds": 3600,
    }
    featured_bundle = {
        "Bundle": bundle,
        "bundle": bundle,
        "Bundles": [],
        "bundles": [],
        "BundleRemainingDurationInSeconds": 0,
        "bundleRemainingDurationInSeconds": 0,
    }
    return {
        "FeaturedBundle": featured_bundle,
        "featuredBundle": featured_bundle,
        "SkinsPanelLayout": skins_panel,
        "skinsPanelLayout": skins_panel,
        "BundleLayout": {"Bundles": [], "bundles": []},
        "bundleLayout": {"Bundles": [], "bundles": []},
        "PersonalizedOffers": [],
        "personalizedOffers": [],
        "UpgradeCurrencyOffers": [],
        "upgradeCurrencyOffers": [],
        "UpgradeCurrencyStore": {"UpgradeCurrencyOffers": [], "upgradeCurrencyOffers": []},
        "upgradeCurrencyStore": {"UpgradeCurrencyOffers": [], "upgradeCurrencyOffers": []},
        "BonusStore": None,
        "bonusStore": None,
        "AccessoryStore": None,
        "accessoryStore": None,
    }


def purchase_initialized_payload(local_order_id: str) -> dict[str, Any]:
    return {
        "OrderID": local_order_id,
        "orderID": local_order_id,
        "OrderId": local_order_id,
        "orderId": local_order_id,
        "Status": "SUCCEEDED",
        "status": "SUCCEEDED",
        "eventType": "OrderCompleted",
        "eventTypeId": "OrderCompleted",
        "Metadata": {},
        "metadata": {},
        "PurchasePrice": {},
        "purchasePrice": {},
        "Success": True,
        "success": True,
    }


def purchase_response_payload(
    service_uuid: Callable[[str], str],
    body: Any = None,
    route_path: str = "",
) -> dict[str, Any]:
    request_body = body if isinstance(body, dict) else {}
    xid = (
        request_body.get("XID")
        or request_body.get("xid")
        or request_body.get("Xid")
        or request_body.get("TransactionID")
        or request_body.get("transactionID")
        or request_body.get("transactionId")
        or ""
    )
    order_id = service_uuid(f"purchase-response:{route_path}:{xid}")
    return {
        "OrderID": order_id,
        "orderID": order_id,
        "OrderId": order_id,
        "orderId": order_id,
    }
