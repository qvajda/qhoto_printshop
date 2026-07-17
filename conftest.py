from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _no_real_image_fetch_checks():
    """poll_until_ready HEAD-checks each Gelato image URL before declaring it ready
    (see pipeline.group_product._image_is_fetchable). Tests use fake fileUrls, not
    real ones, so this defaults the check to pass unless a test overrides it."""
    with patch("pipeline.group_product._image_is_fetchable", return_value=True):
        yield
