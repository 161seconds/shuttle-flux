from ml.ocr import scoreboard_reader as scoreboard_module


def _reader_without_model(monkeypatch):
    monkeypatch.setattr(scoreboard_module, "HAS_EASYOCR", False)
    return scoreboard_module.ScoreboardReader()


def _box(x1, y1, x2, y2):
    return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]


def test_scoreboard_parser_joins_names_and_maps_far_near_players(monkeypatch):
    reader = _reader_without_model(monkeypatch)
    results = [
        (_box(255, 263, 293, 280), "Lakshya", 0.99),
        (_box(270, 277, 293, 294), "SEN", 0.91),
        (_box(343, 262, 373, 279), "Victcr", 0.98),
        (_box(276, 298, 361, 314), "Victor LAI LEADS; 2-1", 0.31),
        (_box(420, 100, 490, 120), "HSBC BWF", 0.95),
    ]

    parsed = reader._parse_results(results, width=640, height=360)

    assert parsed["player_1_name"] == "VICTOR LAI"
    assert parsed["player_2_name"] == "LAKSHYA SEN"
    assert parsed["source"] == "scoreboard_ocr"


def test_scoreboard_parser_never_invents_default_identities(monkeypatch):
    reader = _reader_without_model(monkeypatch)
    parsed = reader._parse_results(
        [(_box(20, 20, 120, 40), "HSBC WORLD TOUR", 0.99)],
        width=640,
        height=360,
    )

    assert parsed["player_1_name"] is None
    assert parsed["player_2_name"] is None
    assert parsed["player_1_country"] is None
    assert parsed["player_2_country"] is None
    assert parsed["source"] == "unresolved"
