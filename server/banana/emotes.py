"""表情系統。

自訂圖片的做法：把圖檔丟進 `server/emotes/` 資料夾就好，不需要上傳 UI。
  - 支援 .png .jpg .jpeg .gif .webp .svg
  - 檔名就是顯示名稱（`01-讚.png` 的前綴數字只用來排序，不會顯示）
  - 下次有人開房間 / 重新整理就會出現

另外內建一組純文字（emoji）表情，沒有任何圖檔也能用。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EMOTE_DIR = Path(__file__).resolve().parent.parent / "emotes"
ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
MAX_EMOTES = 60
_ORDER_PREFIX = re.compile(r"^\d+[-_.\s]*")

# 沒有圖檔時也能用的內建表情
BUILTIN: list[dict[str, str]] = [
    {"id": "t:good", "kind": "text", "text": "👍", "label": "讚"},
    {"id": "t:think", "kind": "text", "text": "🤔", "label": "讓我想想"},
    {"id": "t:cry", "kind": "text", "text": "😭", "label": "哭了"},
    {"id": "t:laugh", "kind": "text", "text": "🤣", "label": "笑死"},
    {"id": "t:angry", "kind": "text", "text": "😡", "label": "氣"},
    {"id": "t:sweat", "kind": "text", "text": "😅", "label": "尷尬"},
    {"id": "t:fire", "kind": "text", "text": "🔥", "label": "神牌"},
    {"id": "t:banana", "kind": "text", "text": "🍌", "label": "BANANA"},
    {"id": "t:hurry", "kind": "text", "text": "⏰", "label": "快點啦"},
    {"id": "t:gg", "kind": "text", "text": "GG", "label": "GG"},
    {"id": "t:nice", "kind": "text", "text": "好牌！", "label": "好牌"},
    {"id": "t:oops", "kind": "text", "text": "點砲了…", "label": "點砲了"},
]


@dataclass(frozen=True, slots=True)
class Emote:
    id: str
    kind: str          # 'text' | 'image'
    label: str
    text: str = ""
    url: str = ""

    def to_json(self) -> dict[str, Any]:
        d: dict[str, Any] = {"id": self.id, "kind": self.kind, "label": self.label}
        if self.kind == "text":
            d["text"] = self.text
        else:
            d["url"] = self.url
        return d


def _label_of(path: Path) -> str:
    return _ORDER_PREFIX.sub("", path.stem) or path.stem


def scan(directory: Path | None = None) -> list[Emote]:
    """內建表情 + emotes/ 資料夾裡的圖片。"""
    out = [
        Emote(id=e["id"], kind="text", label=e["label"], text=e["text"])
        for e in BUILTIN
    ]
    d = directory or EMOTE_DIR
    if not d.is_dir():
        return out
    files = sorted(
        (p for p in d.iterdir() if p.is_file() and p.suffix.lower() in ALLOWED_SUFFIXES),
        key=lambda p: p.name.lower(),
    )
    for p in files[:MAX_EMOTES]:
        out.append(
            Emote(
                id=f"i:{p.name}",
                kind="image",
                label=_label_of(p),
                url=f"/emotes/{p.name}",
            )
        )
    return out


def catalogue(directory: Path | None = None) -> list[dict[str, Any]]:
    return [e.to_json() for e in scan(directory)]


def is_valid(emote_id: str, directory: Path | None = None) -> bool:
    """只接受目錄裡真實存在的表情，避免客戶端塞任意字串或路徑。"""
    return any(e.id == emote_id for e in scan(directory))


def ensure_dir() -> Path:
    EMOTE_DIR.mkdir(parents=True, exist_ok=True)
    readme = EMOTE_DIR / "README.txt"
    if not readme.exists():
        readme.write_text(
            "把圖檔丟進這個資料夾，就會變成遊戲裡可以用的表情。\n"
            "\n"
            "支援格式：png / jpg / jpeg / gif / webp / svg\n"
            "檔名就是表情的名稱，開頭的數字只用來排序：\n"
            "    01-讚.png      -> 顯示為「讚」\n"
            "    02-哭.gif      -> 顯示為「哭」\n"
            "\n"
            "建議尺寸 128x128 左右，檔案越小載入越快。\n"
            "改完不用重開 server，重新整理遊戲頁面就會看到。\n",
            encoding="utf-8",
        )
    return EMOTE_DIR
