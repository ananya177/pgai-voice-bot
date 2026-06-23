from dataclasses import replace

import pytest

from config import OFFICIAL_TEST_NUMBER, normalize_phone


def test_normalize_phone() -> None:
    assert normalize_phone("+1 (805) 439-8008") == OFFICIAL_TEST_NUMBER


def test_target_number_guard(settings) -> None:
    settings.validate_target_number()
    unsafe = replace(settings, target_number="12125551212")
    with pytest.raises(ValueError):
        unsafe.validate_target_number()
