from __future__ import annotations

import os

import pandas as pd
import requests


BASE_URL = "https://api.stlouisfed.org/fred"
FRED_API_KEY_ENV = "FRED_API_KEY"


def get_category_series(
    category_id: int,
    *,
    api_key: str | None = None,
) -> pd.DataFrame:
    """Return the FRED series listed under one category.

    Credentials are supplied explicitly or through ``FRED_API_KEY``. They are
    never stored in source control.
    """

    resolved_api_key = api_key or os.getenv(FRED_API_KEY_ENV)
    if not resolved_api_key:
        raise RuntimeError(
            f"Set {FRED_API_KEY_ENV} before querying the FRED API."
        )
    response = requests.get(
        f"{BASE_URL}/category/series",
        params={
            "category_id": int(category_id),
            "api_key": resolved_api_key,
            "file_type": "json",
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    if "seriess" not in data:
        raise ValueError(
            "FRED category lookup failed: "
            f"{data.get('error_message', 'missing seriess payload')}"
        )
    return pd.DataFrame(data["seriess"])


def main() -> None:
    durable_goods_series = get_category_series(32312)
    columns = [
        "id",
        "title",
        "frequency",
        "units",
        "seasonal_adjustment",
        "last_updated",
    ]
    print(durable_goods_series.loc[:, columns])


if __name__ == "__main__":
    main()
