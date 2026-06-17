"""合同 OCR 识别模块

支持 PaddleOCR（优先）和 Tesseract（备选），以及纯文本输入。
自动降级：PaddleOCR → Tesseract → 返回提示安装。
"""
import io
import re
import logging
from typing import Union

logger = logging.getLogger(__name__)


class ContractOCR:
    """合同 OCR 识别"""

    # 合同高频词纠错表
    CORRECTIONS = {
        "用方": "甲方",
        "用方": "甲方",
        "乙方": "乙方",
        "租房": "租房",
        "出租方": "出租方",
        "承租方": "承租方",
        "出租人": "出租人",
        "承租人": "承租人",
        "租赁": "租赁",
        "押金": "押金",
        "违约": "违约",
        "解约": "解约",
        "续租": "续租",
        "转租": "转租",
        "退租": "退租",
        "租金": "租金",
        "物业": "物业",
        "水费": "水费",
        "电费": "电费",
        "燃气": "燃气",
        "宽带": "宽带",
    }

    # OCR 常见数字/符号混淆
    CHAR_FIXES = {
        "O": "0",
        "o": "0",
        "l": "1",
        "I": "1",
        "S": "5",
        "Z": "2",
        "B": "8",
    }

    def __init__(self):
        self.engine = None  # 延迟初始化
        self.engine_name = "none"
        self._init_attempted = False

    def _ensure_engine(self) -> bool:
        """确保引擎已初始化，尝试降级链"""
        if self.engine is not None:
            return True
        if self._init_attempted:
            return False
        self._init_attempted = True
        if self._init_paddleocr():
            return True
        if self._init_tesseract():
            return True
        logger.warning("OCR: PaddleOCR 和 Tesseract 均不可用")
        return False

    def _init_paddleocr(self) -> bool:
        """尝试初始化 PaddleOCR，返回是否成功"""
        try:
            from paddleocr import PaddleOCR
            self.engine = PaddleOCR(
                use_angle_cls=True,
                lang='ch',
                show_log=False,
                use_gpu=False,  # CPU 模式，有 GPU 自动检测
            )
            self.engine_name = "paddleocr"
            logger.info("OCR: PaddleOCR 初始化成功")
            return True
        except ImportError:
            logger.debug("OCR: PaddleOCR 未安装")
            return False
        except Exception as e:
            logger.warning("OCR: PaddleOCR 初始化失败: %s", e)
            return False

    def _init_tesseract(self) -> bool:
        """尝试初始化 Tesseract"""
        try:
            import pytesseract
            from PIL import Image  # noqa: F401
            self.engine = pytesseract
            self.engine_name = "tesseract"
            logger.info("OCR: Tesseract 初始化成功")
            return True
        except ImportError:
            logger.debug("OCR: Tesseract/pytesseract 未安装")
            return False

    def recognize_image(self, image_input, page_num: int = 1) -> dict:
        """
        识别单张图片

        Args:
            image_input: 文件路径(str) 或 bytes 或 PIL.Image
            page_num: 页码

        Returns:
            {
                "full_text": str,
                "regions": [{"type": str, "bbox": list, "text": str, "confidence": float}],
                "confidence_avg": float,
                "low_confidence_regions": list,
                "page_num": int,
            }
        """
        if not self._ensure_engine():
            return {
                "full_text": "",
                "regions": [],
                "confidence_avg": 0.0,
                "low_confidence_regions": [],
                "page_num": page_num,
                "error": "OCR 引擎不可用，请安装 PaddleOCR (pip install paddleocr paddlepaddle) 或 Tesseract",
            }

        try:
            if self.engine_name == "paddleocr":
                return self._recognize_paddleocr(image_input, page_num)
            elif self.engine_name == "tesseract":
                return self._recognize_tesseract(image_input, page_num)
        except Exception as e:
            logger.error("OCR 识别失败: %s", e)
            return {
                "full_text": "",
                "regions": [],
                "confidence_avg": 0.0,
                "low_confidence_regions": [],
                "page_num": page_num,
                "error": str(e),
            }

    def _recognize_paddleocr(self, image_input, page_num: int) -> dict:
        """使用 PaddleOCR 识别"""
        # 准备输入
        img = self._prepare_image_input(image_input)

        result = self.engine.ocr(img, cls=True)

        regions = []
        all_text_parts = []
        confidences = []

        if result and result[0]:
            for line in result[0]:
                bbox_points = line[0]  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
                text = line[1][0]
                confidence = line[1][1]

                # 转换 bbox 为 [x1, y1, x2, y2]
                x_coords = [p[0] for p in bbox_points]
                y_coords = [p[1] for p in bbox_points]
                bbox = [min(x_coords), min(y_coords), max(x_coords), max(y_coords)]

                # 后处理纠错
                text = self._post_process(text)

                region_type = self._classify_region(text, bbox, regions)
                regions.append({
                    "type": region_type,
                    "bbox": bbox,
                    "text": text,
                    "confidence": round(confidence, 4),
                })
                all_text_parts.append(text)
                confidences.append(confidence)

        full_text = "\n".join(all_text_parts)
        confidence_avg = round(sum(confidences) / len(confidences), 4) if confidences else 0.0
        low_confidence = [r for r in regions if r["confidence"] < 0.7]

        return {
            "full_text": full_text,
            "regions": regions,
            "confidence_avg": confidence_avg,
            "low_confidence_regions": low_confidence,
            "page_num": page_num,
        }

    def _recognize_tesseract(self, image_input, page_num: int) -> dict:
        """使用 Tesseract 识别"""
        from PIL import Image

        if isinstance(image_input, bytes):
            img = Image.open(io.BytesIO(image_input))
        elif isinstance(image_input, str):
            img = Image.open(image_input)
        elif hasattr(image_input, 'read'):
            img = Image.open(image_input)
        else:
            img = image_input  # PIL.Image

        # Tesseract 中文识别
        text = self.engine.image_to_string(img, lang='chi_sim')
        text = self._post_process(text)

        # Tesseract 无置信度信息，使用简单估算
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        regions = []
        for i, line in enumerate(lines):
            region_type = self._classify_region(line, [0, i * 30, 800, (i + 1) * 30], regions)
            regions.append({
                "type": region_type,
                "bbox": [0, i * 30, 800, (i + 1) * 30],
                "text": line,
                "confidence": 0.8,  # Tesseract 无精确置信度
            })

        return {
            "full_text": text,
            "regions": regions,
            "confidence_avg": 0.8,
            "low_confidence_regions": [],
            "page_num": page_num,
        }

    def recognize_images(self, images: list) -> dict:
        """
        识别多张图片（多页合同）

        Args:
            images: 图片列表，每项可以是文件路径(str)、bytes 或 PIL.Image

        Returns:
            {
                "pages": [OCRResult, ...],
                "full_text": str,
                "total_pages": int,
                "engine": str,
            }
        """
        pages = []
        all_texts = []

        for i, img in enumerate(images):
            page_result = self.recognize_image(img, page_num=i + 1)
            pages.append(page_result)
            if page_result.get("full_text"):
                all_texts.append(page_result["full_text"])

        return {
            "pages": pages,
            "full_text": "\n\n".join(all_texts),
            "total_pages": len(pages),
            "engine": self.engine_name,
        }

    def _prepare_image_input(self, image_input):
        """准备图片输入，PaddleOCR 支持路径和 numpy 数组"""
        if isinstance(image_input, str):
            # 文件路径，PaddleOCR 直接支持
            return image_input
        elif isinstance(image_input, bytes):
            # bytes 需要转为 numpy 数组
            import numpy as np
            from PIL import Image
            img = Image.open(io.BytesIO(image_input))
            return np.array(img)
        elif hasattr(image_input, 'read'):
            # 文件类对象
            import numpy as np
            from PIL import Image
            img = Image.open(image_input)
            return np.array(img)
        else:
            # 假设是 PIL.Image 或 numpy 数组
            try:
                import numpy as np
                return np.array(image_input)
            except Exception:
                return image_input

    def _classify_region(self, text: str, bbox: list, all_regions: list) -> str:
        """
        分类区域类型：title/paragraph/table/signature

        规则：
        - 包含"签名"/"盖章"/"签字"/"印章" → signature
        - 文字少(<=20字)且居中(y坐标在页面上部1/4或行数<=3) → title
        - 其余 → paragraph
        """
        # 签名区
        sig_keywords = ["签名", "盖章", "签字", "印章", "签章", "甲方签", "乙方签"]
        for kw in sig_keywords:
            if kw in text:
                return "signature"

        # 标题：文字短且在页面顶部
        text_len = len(text.strip())
        if text_len <= 20:
            # 判断是否居中/在页面上部
            if len(bbox) >= 4:
                y_center = (bbox[1] + bbox[3]) / 2
                # 假设页面高度约 1000（A4 常见像素高度）
                if y_center < 250 or (len(all_regions) <= 2 and text_len <= 15):
                    return "title"
            elif len(all_regions) <= 2 and text_len <= 15:
                return "title"

        return "paragraph"

    def _post_process(self, text: str) -> str:
        """后处理：合同专用纠错"""
        if not text:
            return text

        # 高频词强制修正
        for wrong, right in self.CORRECTIONS.items():
            if wrong != right:
                text = text.replace(wrong, right)

        # 数字上下文中的 OCR 字符修正
        # 在数字语境中修正 O→0, l→1 等
        text = self._fix_numbers_in_context(text)

        # 清理多余空白
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def _fix_numbers_in_context(self, text: str) -> str:
        """在数字上下文中修正 OCR 常见字符混淆"""
        # 匹配数字上下文：前后有数字或单位
        # 例如："2O24年" → "2024年"，"l5OO元" → "1500元"
        result = []
        i = 0
        while i < len(text):
            ch = text[i]
            # 如果前后字符是数字，尝试修正
            prev_is_digit = (i > 0 and text[i - 1].isdigit())
            next_is_digit = (i + 1 < len(text) and text[i + 1].isdigit())

            if ch in self.CHAR_FIXES and (prev_is_digit or next_is_digit):
                result.append(self.CHAR_FIXES[ch])
            else:
                # 数字+单位常见组合：元/月/年/天/m²/㎡
                if ch in self.CHAR_FIXES:
                    # 检查后面是否跟数字单位
                    remaining = text[i + 1:i + 3] if i + 1 < len(text) else ""
                    unit_patterns = ["元", "月", "年", "天", "m", "平"]
                    if any(remaining.startswith(p) for p in unit_patterns):
                        result.append(self.CHAR_FIXES[ch])
                    else:
                        result.append(ch)
                else:
                    result.append(ch)
            i += 1

        return "".join(result)
