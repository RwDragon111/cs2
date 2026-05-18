from app.normalizer.item_normalizer import detect_category, detect_weapon_type, normalize_item_name


def test_normalizer_handles_stattrak_unicode_and_exterior():
    assert normalize_item_name("  stattrak™   ak-47 | redline (FT) ") == "StatTrak™ AK-47 | Redline (Field-Tested)"


def test_normalizer_detects_category_and_weapon():
    name = normalize_item_name("★ Karambit | Doppler (Factory New)")
    assert detect_category(name) == "knife"
    assert detect_weapon_type(name) == "Karambit"

