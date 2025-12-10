from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Dict, Tuple

from sqlmodel import Session, select
from PIL import Image, ImageDraw, ImageFont

from ..models import MedicalRecord

# Type alias for box coordinates: ((x1, y1), (x2, y2))
BoxCoords = Tuple[Tuple[int, int], Tuple[int, int]]
# Type alias for point coordinates: (x, y)
PointCoords = Tuple[int, int]


class SkinToneCardGenerator:
    """Simple helper to drop analysis results onto the card template."""

    # --- Content Box Coordinates (Region to fill text/image) ---
    ROSE_BOX: BoxCoords = ((45, 128), (180, 257))
    DIAGNOSIS_BOX: BoxCoords = ((220, 170), (410, 260))
    
    # Middle row boxes (Appointment info)
    APP_ID_BOX: BoxCoords = ((73, 337), (102, 371))
    APP_DATE_BOX: BoxCoords = ((198, 328), (258, 380))
    APP_CATEGORY_BOX: BoxCoords = ((334, 328), (403, 378))
    
    # Bottom box
    LLM_ADVICE_BOX: BoxCoords = ((87, 450), (420, 525))

    # --- Label Coordinates (Single point (x, y) for headers) ---
    LABEL_POS_SKIN_TONE: PointCoords = (80, 103)
    LABEL_POS_DIAGNOSIS: PointCoords = (222, 145)
    LABEL_POS_ID: PointCoords = (61, 293)
    LABEL_POS_TIME: PointCoords = (201, 293)
    LABEL_POS_TYPE: PointCoords = (343, 293)
    LABEL_POS_ADVICE: PointCoords = (47, 443)

    def __init__(self, template_path: Path, font_path: Path | None = None, session: Session | None = None) -> None:
        self.template_path = Path(template_path)
        if not self.template_path.exists():
            raise FileNotFoundError(f"Card template not found: {self.template_path}")

        self.font_path = Path(font_path) if font_path else None
        if self.font_path and not self.font_path.exists():
            self.font_path = None
        
        self.base_template = Image.open(self.template_path).convert("RGBA")
        self.session = session

    def _fetch_llm_advice(self, appointment_id: int | None) -> str:
        """
        Pull the latest LLM advice from MedicalRecord when available.
        Falls back to default text if session/record is missing.
        """
        default_text = "保持規律作息、補充水分並記得防曬，下一次回診再一起檢視膚況。"
        if not appointment_id or not self.session:
            return default_text

        try:
            # ✅ 修正：查詢整個 MedicalRecord 物件
            medical_record = self.session.exec(
                select(MedicalRecord).where(MedicalRecord.appointment_id == appointment_id)
            ).first()
            
            if medical_record and medical_record.ai_advice:
                return medical_record.ai_advice
            
            return default_text
        except Exception as e:
            print(f"❌ 查詢失敗: {e}")
            return default_text

    def _load_font(self, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        if self.font_path:
            try:
                return ImageFont.truetype(str(self.font_path), size)
            except Exception:
                pass
        
        return ImageFont.load_default()

    @staticmethod
    def _box_size(box: BoxCoords) -> Tuple[int, int]:
        (x1, y1), (x2, y2) = box
        return x2 - x1, y2 - y1

    def _paste_image(self, canvas: Image.Image, image_bytes: bytes, box: BoxCoords) -> None:
        (x1, y1), (x2, y2) = box
        target_w, target_h = self._box_size(box)
        try:
            img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
            resized = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
            canvas.paste(resized, (x1, y1), mask=resized)
        except Exception as e:
            print(f"Error pasting image: {e}")

    def _draw_label(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        pos: PointCoords,
        font_size: int = 20,
        color: Tuple[int, int, int] = (255, 255, 255),
    ) -> None:
        """Draws a single line header label at a specific position."""
        font = self._load_font(font_size)
        draw.text(pos, text, font=font, fill=color)

    def _draw_centered_text(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        box: BoxCoords,
        font_size: int = 16,
        color: Tuple[int, int, int] = (0, 0, 0),
    ) -> None:
        (x1, y1), (x2, y2) = box
        center_x = x1 + (x2 - x1) // 2
        center_y = y1 + (y2 - y1) // 2

        font = self._load_font(font_size)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        draw_x = center_x - text_w // 2
        draw_y = center_y - text_h // 2 - 2
        draw.text((draw_x, draw_y), text, font=font, fill=color)

    def _draw_multiline_text(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        box: BoxCoords,
        font_size: int = 18,
        color: Tuple[int, int, int] = (0, 0, 0),
        padding: int = 8,
        line_spacing: int = 6,
    ) -> None:
        (x1, y1), (x2, y2) = box
        max_width = (x2 - x1) - (padding * 2)
        cursor_x = x1 + padding
        cursor_y = y1 + padding

        font = self._load_font(font_size)
        lines = []
        current = ""
        for char in text:
            if draw.textlength(current + char, font=font) <= max_width:
                current += char
            else:
                lines.append(current)
                current = char
        if current:
            lines.append(current)

        for line in lines:
            if cursor_y + font_size > y2 - padding:
                break
            draw.text((cursor_x, cursor_y), line, font=font, fill=color)
            cursor_y += font_size + line_spacing

    def generate_card(
        self,
        *,
        rose_chart_bytes: bytes,
        diagnosis_text: str,
        appointment_fields: Dict[str, str],
        appointment_id: int | None = None,
        llm_advice: str | None = None,
        output_path: Path | None = None,
    ) -> str:
        """
        Build the card and return a base64-encoded PNG string.
        Optionally writes the PNG to output_path.
        """
        advice_text = llm_advice or self._fetch_llm_advice(appointment_id)

        canvas = self.base_template.copy()
        draw = ImageDraw.Draw(canvas)

        # 1. Paste Images
        self._paste_image(canvas, rose_chart_bytes, self.ROSE_BOX)

        # 2. Draw Static Headers
        header_size = 14
        self._draw_label(draw, "膚色示意", self.LABEL_POS_SKIN_TONE, header_size)
        self._draw_label(draw, "AI望診", self.LABEL_POS_DIAGNOSIS, header_size)
        self._draw_label(draw, "預約編號", self.LABEL_POS_ID, header_size)
        self._draw_label(draw, "預約時間", self.LABEL_POS_TIME, header_size)
        self._draw_label(draw, "預約類別", self.LABEL_POS_TYPE, header_size)
        self._draw_label(draw, "建議", self.LABEL_POS_ADVICE, header_size)

        # 3. Draw Dynamic Content
        self._draw_multiline_text(
            draw,
            diagnosis_text,
            self.DIAGNOSIS_BOX,
            font_size=12,
            color=(50, 30, 20),
        )

        self._draw_centered_text(
            draw,
            appointment_fields.get("app_id", "N/A"),
            self.APP_ID_BOX,
            font_size=14,
        )
        self._draw_centered_text(
            draw,
            appointment_fields.get("app_date", "N/A"),
            self.APP_DATE_BOX,
            font_size=10,
        )
        self._draw_centered_text(
            draw,
            appointment_fields.get("app_category", "N/A"),
            self.APP_CATEGORY_BOX,
            font_size=16,
        )

        self._draw_multiline_text(
            draw,
            advice_text,
            self.LLM_ADVICE_BOX,
            font_size=12,
        )

        if output_path:
            canvas.save(output_path)

        buf = io.BytesIO()
        canvas.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")