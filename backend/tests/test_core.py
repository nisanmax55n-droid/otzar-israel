from app.services.text_utils import normalize_hebrew
from app.services.sefaria_importer import is_importable_license

def test_normalize_hebrew_removes_nikud():
    assert normalize_hebrew("בְּרֵאשִׁית בָּרָא") == "בראשית ברא"

def test_license_gate():
    assert is_importable_license("Public Domain")
    assert is_importable_license("CC-BY-SA")
    assert not is_importable_license("CC-BY-NC")
    assert not is_importable_license(None)
