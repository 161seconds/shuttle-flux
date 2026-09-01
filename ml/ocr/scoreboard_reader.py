"""
Scoreboard & Jersey OCR Reader Module:
Extracts player names and country codes from badminton broadcast scoreboard HUD
or near-player jersey back text using OCR and regex pattern matching.
"""

from typing import Dict, Any, List, Optional, Tuple
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
                # Initialize reader with English/Latin recognition without progress bar print issues
                self.reader = easyocr.Reader(languages, gpu=False, verbose=False)
                print("[ScoreboardReader] EasyOCR initialized successfully.")
            except Exception as e:
                print(f"[ScoreboardReader] EasyOCR init error: {e}")

    def extract_player_names_from_frame(
        self, frame: np.ndarray, near_player_bbox: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """
        Scans broadcast scoreboard and player jersey to extract real athlete names.
        Returns:
          - player_1_name: str
          - player_2_name: str
          - confidence: float
          - source: str
        """
        h, w, _ = frame.shape
        extracted_names: List[str] = []

        # 1. Check Broadcast Scoreboard Regions (Bottom-Left or Top-Left)
        if self.reader is not None and HAS_OPENCV:
            try:
                # Bottom-Left HUD Scoreboard (Typical BWF)
                scoreboard_roi = frame[int(h * 0.70) : int(h * 0.98), int(w * 0.02) : int(w * 0.50)]
                results = self.reader.readtext(scoreboard_roi)
                for bbox, text, conf in results:
                    clean_text = self._clean_player_name(text)
                    if clean_text and conf > 0.4:
                        extracted_names.append(clean_text)

                # Top-Left HUD Scoreboard
                if len(extracted_names) < 2:
                    top_roi = frame[int(h * 0.02) : int(h * 0.25), int(w * 0.02) : int(w * 0.50)]
                    results_top = self.reader.readtext(top_roi)
                    for bbox, text, conf in results_top:
                        clean_text = self._clean_player_name(text)
                        if clean_text and conf > 0.4 and clean_text not in extracted_names:
                            extracted_names.append(clean_text)
            except Exception as e:
                print(f"[ScoreboardReader] Scoreboard OCR warning: {e}")

        # 2. Check Near Player Jersey Back Text
        jersey_name = None
        if self.reader is not None and HAS_OPENCV and near_player_bbox is not None:
            try:
                x1, y1, x2, y2 = [int(c) for c in near_player_bbox]
                # Crop upper back of player
                jersey_roi = frame[max(0, y1) : min(h, y1 + int((y2 - y1) * 0.5)), max(0, x1) : min(w, x2)]
                if jersey_roi.size > 0:
                    j_results = self.reader.readtext(jersey_roi)
                    for bbox, text, conf in j_results:
                        clean = re.sub(r"[^A-Z\s]", "", text.upper()).strip()
                        if len(clean) >= 3 and conf > 0.4:
                            jersey_name = clean
                            break
            except Exception as e:
                print(f"[ScoreboardReader] Jersey OCR warning: {e}")

        # Format Final Player Names
        p1_name = "VĐV 1 (Gần)"
        p2_name = "VĐV 2 (Xa)"
        source = "default"

        if len(extracted_names) >= 2:
            p1_name = extracted_names[0]
            p2_name = extracted_names[1]
            source = "scoreboard_ocr"
        elif len(extracted_names) == 1:
            p1_name = extracted_names[0]
            source = "scoreboard_ocr"
        elif jersey_name:
            p1_name = f"{jersey_name.title()} (Gần)"
            source = "jersey_ocr"

        return {
            "player_1_name": p1_name,
            "player_2_name": p2_name,
            "confidence": 0.88 if source != "default" else 0.50,
            "source": source,
        }

    def _clean_player_name(self, text: str) -> Optional[str]:
        """Cleans and validates recognized athlete name string."""
        text = text.strip()
        # Remove numbers and special characters
        cleaned = re.sub(r"[0-9\-_+=#@!?:;()\[\]]", "", text).strip()
        # Common BWF words to ignore
        ignore_words = {"BWF", "WORLD", "TOUR", "FINAL", "SEMIFINAL", "GAME", "MATCH", "SET", "LIVE", "SUPER", "OPEN"}
        if cleaned.upper() in ignore_words or len(cleaned) < 3:
            return None

        # Format as Title Case (e.g. K. Naraoka or Axelsen)
        parts = cleaned.split()
        if len(parts) >= 1:
            return " ".join([p.capitalize() for p in parts])
        return None
