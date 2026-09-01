"""
Scoreboard & Jersey OCR Reader Module:
Extracts player names and country codes from badminton broadcast scoreboard HUD
(Top-Left, Bottom-Left, or Top-Center) and near-player jersey back text using OCR.
"""

from typing import Dict, Any, List, Optional
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
    def __init__(self, languages: List[str] = ["en"]):
        self.reader = None
        if HAS_EASYOCR:
            try:
                # Initialize reader with English/Latin recognition
                self.reader = easyocr.Reader(languages, gpu=False, verbose=False)
                print("[ScoreboardReader] EasyOCR initialized successfully.")
            except Exception as e:
                print(f"[ScoreboardReader] EasyOCR init error: {e}")

    def extract_player_names_from_frame(
        self, frame: np.ndarray, near_player_bbox: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """
        Scans broadcast scoreboard HUD (Top-Left, Bottom-Left) and player jersey to extract athlete names.
        """
        h, w, _ = frame.shape
        extracted_names: List[str] = []

        if self.reader is not None and HAS_OPENCV:
            try:
                # Region A: Top-Left BWF Broadcast Scoreboard (e.g., China Open, Denmark Open)
                top_left_roi = frame[int(h * 0.15) : int(h * 0.42), int(w * 0.05) : int(w * 0.32)]
                if top_left_roi.size > 0:
                    results_tl = self.reader.readtext(top_left_roi)
                    for _, text, conf in results_tl:
                        clean = self._clean_player_name(text)
                        if clean and conf > 0.35 and clean not in extracted_names:
                            extracted_names.append(clean)

                # Region B: Bottom-Left HUD Scoreboard (e.g. World Tour Finals)
                if len(extracted_names) < 2:
                    bl_roi = frame[int(h * 0.68) : int(h * 0.98), int(w * 0.02) : int(w * 0.45)]
                    if bl_roi.size > 0:
                        results_bl = self.reader.readtext(bl_roi)
                        for _, text, conf in results_bl:
                            clean = self._clean_player_name(text)
                            if clean and conf > 0.35 and clean not in extracted_names:
                                extracted_names.append(clean)

                # Region C: Top-Center / Header HUD Scoreboard
                if len(extracted_names) < 2:
                    top_roi = frame[int(h * 0.02) : int(h * 0.22), int(w * 0.02) : int(w * 0.50)]
                    if top_roi.size > 0:
                        results_top = self.reader.readtext(top_roi)
                        for _, text, conf in results_top:
                            clean = self._clean_player_name(text)
                            if clean and conf > 0.35 and clean not in extracted_names:
                                extracted_names.append(clean)
            except Exception as e:
                print(f"[ScoreboardReader] Scoreboard OCR warning: {e}")

        # 2. Check Near Player Jersey Back Text
        jersey_name = None
        if self.reader is not None and HAS_OPENCV and near_player_bbox is not None:
            try:
                x1, y1, x2, y2 = [int(c) for c in near_player_bbox]
                # Crop upper back of player
                jersey_roi = frame[max(0, y1) : min(h, y1 + int((y2 - y1) * 0.45)), max(0, x1) : min(w, x2)]
                if jersey_roi.size > 0:
                    j_results = self.reader.readtext(jersey_roi)
                    for _, text, conf in j_results:
                        clean = re.sub(r"[^A-Za-z\s]", "", text).strip()
                        # Ignore brand names like YONEX, VICTOR, LI-NING
                        if len(clean) >= 3 and conf > 0.40:
                            if clean.upper() not in ["YONEX", "VICTOR", "LINING", "LI-NING", "HSBC", "BWF"]:
                                jersey_name = clean.title()
                                break
            except Exception as e:
                print(f"[ScoreboardReader] Jersey OCR warning: {e}")

        # Format Final Player Names
        p1_name = "VĐV 1 (Gần)"
        p2_name = "VĐV 2 (Xa)"
        source = "default"

        if len(extracted_names) >= 2:
            # Usually line 1 is Far Player or Near Player depending on service
            p1_name = extracted_names[1]
            p2_name = extracted_names[0]
            source = "scoreboard_ocr"
        elif len(extracted_names) == 1:
            p2_name = extracted_names[0]
            source = "scoreboard_ocr"
            if jersey_name:
                p1_name = jersey_name
        elif jersey_name:
            p1_name = jersey_name
            source = "jersey_ocr"

        return {
            "player_1_name": p1_name,
            "player_2_name": p2_name,
            "confidence": 0.88 if source != "default" else 0.50,
            "source": source,
            "extracted_list": extracted_names,
        }

    def _clean_player_name(self, raw_text: str) -> Optional[str]:
        """
        Cleans OCR text to isolate valid player names.
        Filters out sponsor brands, numbers, scores, and tournament logos.
        """
        if not raw_text:
            return None

        text = raw_text.strip()

        # Discard pure numbers, scores (e.g., "17", "21 15", "1-0")
        if re.match(r"^[\d\s\-\:\.\/]+$", text):
            return None

        # Discard common broadcast HUD keywords & sponsors
        ignore_words = [
            "HSBC", "VICTOR", "YONEX", "BWF", "WORLD", "TOUR", "SUPER",
            "GANTEN", "TOTAL", "TOTALENERGIES", "CHENGDU", "CHANGZHOU",
            "ODENSE", "DENMARK", "OPEN", "CHINA", "ALL", "ENGLAND",
            "SINGLES", "DOUBLES", "GAME", "MATCH", "SET", "LIVE", "FINAL"
        ]

        text_upper = text.upper()
        for kw in ignore_words:
            if kw in text_upper and len(text_upper) < len(kw) + 4:
                return None

        # Extract names with capital letters (e.g., "VITIDSARN K", "NARAOKA K", "AXELSEN")
        clean = re.sub(r"[^A-Za-z\s\.\-]", "", text).strip()

        # Remove single characters or noise
        if len(clean) < 3:
            return None

        # If country code at end (e.g. "VITIDSARN K THA"), clean formatting
        return clean.title()
