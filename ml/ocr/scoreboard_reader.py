"""Extract athlete names, country codes, and scores from broadcast graphics."""

from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Sequence, Tuple
import re

import numpy as np

try:
    import easyocr

    HAS_EASYOCR = True
except ImportError:
    HAS_EASYOCR = False

try:
    import cv2

    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False


class ScoreboardReader:
    """Reads real broadcast text without substituting demo athlete names."""

    COUNTRY_CODES = {
        "AUS", "BRA", "CAN", "CHN", "DEN", "ESP", "FRA", "GBR", "GER",
        "HKG", "INA", "IND", "IRL", "ITA", "JPN", "KOR", "MAS", "NED",
        "NZL", "PHI", "POL", "SGP", "SRI", "SUI", "SWE", "THA", "TPE",
        "TUR", "USA", "VIE",
    }

    def __init__(self, languages: Optional[List[str]] = None):
        self.reader = None
        if HAS_EASYOCR:
            try:
                self.reader = easyocr.Reader(
                    languages or ["en"], gpu=False, verbose=False
                )
                print("[ScoreboardReader] EasyOCR initialized successfully.")
            except Exception as exc:
                print(f"[ScoreboardReader] EasyOCR init error: {exc}")

        self.blacklist_words = {
            "ALL", "BADMINTON", "BWF", "CHAMPIONSHIP", "CHANGZHOU", "CHINA",
            "COURT", "DAIHATSU", "DENMARK", "DOUBLES", "ENGLAND", "FINAL",
            "FINALS", "FRENCH", "GAME", "GANTEN", "GERMAN", "HEAD", "HSBC",
            "INDONESIA", "JAPAN", "KOREA", "LEADS", "LINING", "LI-NING",
            "LIVE", "MALAYSIA", "MASTERS", "MATCH", "MEETING", "MEN",
            "OPEN", "PARIS", "PERODUA", "PETRONAS", "QUARTER", "ROUND",
            "SERIES", "SET", "SHENZHEN", "SINGLES", "SPORT", "SUPER",
            "SWISS", "TANGKIS", "THAILAND", "TO", "TOTAL", "TOTALENERGIES",
            "TOUR", "VIETNAM", "WOMEN", "WON", "WORLD", "YONEX",
        }

    @property
    def available(self) -> bool:
        return self.reader is not None and HAS_OPENCV

    @staticmethod
    def _bbox_metrics(bbox: Sequence[Sequence[float]]) -> Tuple[float, float, float, float]:
        xs = [float(point[0]) for point in bbox]
        ys = [float(point[1]) for point in bbox]
        return min(xs), min(ys), max(xs), max(ys)

    @staticmethod
    def _token_similarity(first: str, second: str) -> float:
        return SequenceMatcher(None, first.upper(), second.upper()).ratio()

    def _clean_player_name(self, raw_text: str) -> Optional[str]:
        if not raw_text:
            return None
        text = raw_text.strip()
        if re.fullmatch(r"[\d\s\-:\./\[\]\(\)]+", text):
            return None

        clean = re.sub(r"[^A-Za-z\s\.\-']", " ", text)
        words = [word for word in clean.split() if len(word.replace(".", "")) >= 2]
        if not words or len(words) > 4:
            return None

        normalized = []
        for word in words:
            upper = re.sub(r"[^A-Z]", "", word.upper())
            looks_blacklisted = any(
                len(upper) >= 4
                and len(blocked) >= 4
                and self._token_similarity(upper, re.sub(r"[^A-Z]", "", blocked))
                >= 0.72
                for blocked in self.blacklist_words
            )
            if upper in self.COUNTRY_CODES or looks_blacklisted:
                return None
            normalized.append(word.upper())

        name = " ".join(normalized)
        return name if len(name.replace(" ", "")) >= 3 else None

    def _narrative_name(self, raw_text: str) -> Optional[str]:
        match = re.search(
            r"([A-Za-z][A-Za-z .'-]{2,36}?)\s+(?:LEADS?|WON)\b",
            raw_text,
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        value = re.sub(r"\s+", " ", match.group(1)).strip(" .:-")
        words = value.split()
        if len(words) > 3:
            words = words[-3:]
        return " ".join(word.upper() for word in words) or None

    def _combine_name_tokens(
        self, items: List[Dict[str, Any]], width: int, height: int
    ) -> List[Dict[str, Any]]:
        combined: List[Dict[str, Any]] = []
        single_words = [item for item in items if len(item["name"].split()) == 1]
        for index, first in enumerate(single_words):
            for second in single_words[index + 1 :]:
                dx = abs(first["x"] - second["x"])
                dy = abs(first["y"] - second["y"])
                vertical = (
                    height * 0.012 <= dy <= height * 0.09
                    and dx <= width * 0.075
                )
                horizontal_gap = max(
                    0.0,
                    max(first["x1"], second["x1"])
                    - min(first["x2"], second["x2"]),
                )
                horizontal = dy <= height * 0.025 and horizontal_gap <= width * 0.025
                if not vertical and not horizontal:
                    continue

                ordered = (
                    sorted((first, second), key=lambda item: item["y"])
                    if vertical
                    else sorted((first, second), key=lambda item: item["x"])
                )
                combined.append(
                    {
                        "name": f"{ordered[0]['name']} {ordered[1]['name']}",
                        "confidence": min(
                            1.0,
                            (first["confidence"] + second["confidence"]) / 2.0 + 0.18,
                        ),
                        "x": (first["x"] + second["x"]) / 2.0,
                        "y": (first["y"] + second["y"]) / 2.0,
                        "x1": min(first["x1"], second["x1"]),
                        "x2": max(first["x2"], second["x2"]),
                        "source": "joined_tokens",
                    }
                )
        return combined

    def _deduplicate_names(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        def rank(item: Dict[str, Any]) -> float:
            return float(item["confidence"]) + (
                0.24 if len(item["name"].split()) > 1 else 0.0
            ) + (0.28 if item.get("source") == "narrative" else 0.0)

        for item in items:
            item["rank"] = rank(item)
        ranked = sorted(
            items,
            key=lambda item: item["rank"],
            reverse=True,
        )
        selected: List[Dict[str, Any]] = []
        for item in ranked:
            item_tokens = item["name"].split()
            duplicate = False
            for existing in selected:
                existing_tokens = existing["name"].split()
                token_match = max(
                    self._token_similarity(first, second)
                    for first in item_tokens
                    for second in existing_tokens
                )
                if (
                    item["name"] == existing["name"]
                    or item["name"] in existing["name"]
                    or existing["name"] in item["name"]
                    or token_match >= 0.78
                ):
                    duplicate = True
                    break
            if not duplicate:
                selected.append(item)
        return selected

    def _parse_results(
        self,
        results: Sequence[Tuple[Any, str, float]],
        width: int,
        height: int,
    ) -> Dict[str, Any]:
        name_items: List[Dict[str, Any]] = []
        countries: List[Dict[str, Any]] = []
        scores: List[Dict[str, Any]] = []

        for bbox, raw_text, confidence in results:
            x1, y1, x2, y2 = self._bbox_metrics(bbox)
            x, y = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            text = raw_text.strip()
            upper = re.sub(r"[^A-Z]", "", text.upper())

            if upper in self.COUNTRY_CODES:
                countries.append({"code": upper, "x": x, "y": y})
            if (
                x < width * 0.48
                and y < height * 0.35
                and re.fullmatch(r"\d{1,2}", text)
            ):
                value = int(text)
                if 0 <= value <= 30:
                    scores.append({"value": value, "y": y})

            narrative = self._narrative_name(text)
            if narrative:
                name_items.append(
                    {
                        "name": narrative,
                        "confidence": min(1.0, float(confidence) + 0.40),
                        "x": x,
                        "y": y,
                        "x1": x1,
                        "x2": x2,
                        "source": "narrative",
                    }
                )

            cleaned = self._clean_player_name(text)
            if cleaned and float(confidence) >= 0.08:
                name_items.append(
                    {
                        "name": cleaned,
                        "confidence": float(confidence),
                        "x": x,
                        "y": y,
                        "x1": x1,
                        "x2": x2,
                        "source": "ocr",
                    }
                )

        name_items.extend(self._combine_name_tokens(name_items, width, height))
        candidates = self._deduplicate_names(name_items)
        candidates.sort(key=lambda item: item["rank"], reverse=True)

        near = None
        far = None
        if len(candidates) >= 2 and candidates[1]["rank"] >= 0.58:
            pair = sorted(candidates[:2], key=lambda item: item["y"])
            far, near = pair[0], pair[1]
        elif candidates and candidates[0]["rank"] >= 0.68:
            candidate = candidates[0]
            if candidate["y"] <= height * 0.42:
                far = candidate
            elif candidate["y"] >= height * 0.58:
                near = candidate

        def closest_country(candidate: Optional[Dict[str, Any]]) -> Optional[str]:
            if candidate is None or not countries:
                return None
            closest = min(
                countries,
                key=lambda country: abs(country["x"] - candidate["x"])
                + abs(country["y"] - candidate["y"]),
            )
            return closest["code"]

        scores.sort(key=lambda item: item["y"])
        confidence = 0.0
        if near and far:
            confidence = min(near["confidence"], far["confidence"])
        elif near or far:
            confidence = (near or far)["confidence"]
        return {
            "player_1_name": near["name"] if near else None,
            "player_2_name": far["name"] if far else None,
            "player_1_country": closest_country(near),
            "player_2_country": closest_country(far),
            "score_player_1": scores[1]["value"] if len(scores) >= 2 else None,
            "score_player_2": scores[0]["value"] if scores else None,
            "serving_player_id": None,
            "confidence": round(float(confidence), 3),
            "source": "scoreboard_ocr" if near or far else "unresolved",
            "extracted_list": [item["name"] for item in candidates],
        }

    def extract_player_names_from_frame(
        self, frame: np.ndarray, near_player_bbox: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """Scans the whole frame so scoreboards and lower-thirds are both covered."""
        if not self.available:
            return {
                "player_1_name": None,
                "player_2_name": None,
                "source": "unavailable",
                "confidence": 0.0,
                "extracted_list": [],
            }

        height, width = frame.shape[:2]
        try:
            results = self.reader.readtext(
                frame,
                detail=1,
                paragraph=False,
                text_threshold=0.45,
                low_text=0.25,
                link_threshold=0.25,
                canvas_size=2560,
                mag_ratio=1.5,
            )
        except Exception as exc:
            print(f"[ScoreboardReader] OCR warning: {exc}")
            results = []

        parsed = self._parse_results(results, width, height)
        if parsed["player_1_name"] or near_player_bbox is None:
            return parsed

        try:
            x1, y1, x2, y2 = [int(value) for value in near_player_bbox]
            player_height = max(1, y2 - y1)
            jersey = frame[
                max(0, y1) : min(height, y1 + int(player_height * 0.58)),
                max(0, x1) : min(width, x2),
            ]
            if jersey.size:
                jersey = cv2.resize(
                    jersey, None, fx=4.0, fy=4.0, interpolation=cv2.INTER_CUBIC
                )
                jersey_results = self.reader.readtext(
                    jersey,
                    detail=1,
                    paragraph=False,
                    allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz -.'",
                    text_threshold=0.35,
                    low_text=0.15,
                    link_threshold=0.15,
                )
                jersey_candidates = []
                for _, text, confidence in jersey_results:
                    cleaned = self._clean_player_name(text)
                    if cleaned and confidence >= 0.25:
                        jersey_candidates.append((float(confidence), cleaned))
                if jersey_candidates:
                    jersey_candidates.sort(reverse=True)
                    parsed["player_1_name"] = jersey_candidates[0][1]
                    parsed["confidence"] = max(
                        parsed["confidence"], round(jersey_candidates[0][0], 3)
                    )
                    parsed["source"] = "scoreboard_and_jersey_ocr"
        except Exception as exc:
            print(f"[ScoreboardReader] Jersey OCR warning: {exc}")
        return parsed
