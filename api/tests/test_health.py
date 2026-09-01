def test_healthz_returns_ok(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_reference_loads_expected_vocabulary():
    from app.reference import reference

    ref = reference()
    assert ref.sections == ["featured", "series", "minisodes", "songs"]
    assert ref.languages == ["en", "hi"]
    assert len(ref.categories) == 15
    assert ref.artwork_specs["poster"].target_w == 600
    assert ref.artwork_specs["poster"].target_h == 900
    assert ref.artwork_specs["banner"].max_kb == 200


def test_language_sort_uses_reference_order():
    from app.reference import reference

    assert reference().sort_languages(["hi", "en"]) == ["en", "hi"]
