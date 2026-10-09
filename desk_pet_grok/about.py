"""About dialog copy for 桌宠grok."""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget

from desk_pet_grok.window import PRODUCT_TITLE

ABOUT_TEXT = (
    f"{PRODUCT_TITLE}\n\n"
    "本机桌宠助手。对话走 xAI API，与 Grok 网页、Grok App、Grok Bot "
    "不是同一个会话。\n"
    "非 DeepSeek、非 xAI 官方产品。立绘上的装饰标识不代表官方品牌。"
)


def show_about(parent: QWidget | None = None) -> None:
    """Show the about dialog."""
    QMessageBox.about(parent, f"关于 {PRODUCT_TITLE}", ABOUT_TEXT)
