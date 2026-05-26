"""Asset reference helpers used by Project A control-plane payloads."""

from __future__ import annotations


def blueprint_asset(object_path: str) -> str:
    asset_name = object_path.rsplit("/", 1)[-1]
    return f"BlueprintGeneratedClass'{object_path}.{asset_name}_C'"


def unwrap_asset_reference(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return raw
    if "'" in raw and raw.endswith("'"):
        _, _, raw = raw.partition("'")
        raw = raw[:-1]
    return raw


def asset_object_path(value: str) -> str:
    raw = unwrap_asset_reference(value)
    if "." in raw:
        package, object_name = raw.rsplit(".", 1)
        if object_name.endswith("_C"):
            object_name = object_name[:-2]
        return f"{package}.{object_name}"
    if raw.endswith("_C"):
        return raw[:-2]
    return raw


def asset_reference_name(value: str) -> str:
    raw = asset_object_path(value)
    if "." in raw:
        return raw.rsplit(".", 1)[-1]
    return raw.rsplit("/", 1)[-1]


def asset_class_object_path(value: str) -> str:
    raw = unwrap_asset_reference(value)
    return raw or asset_object_path(value)


def asset_class_name(value: str) -> str:
    raw = unwrap_asset_reference(value)
    if "." in raw:
        return raw.rsplit(".", 1)[-1]
    return raw.rsplit("/", 1)[-1]


def asset_default_object_name(value: str) -> str:
    return asset_reference_name(value)
