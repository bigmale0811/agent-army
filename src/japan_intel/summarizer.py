# -*- coding: utf-8 -*-
"""日本博弈資訊蒐集 Agent — Gemini 摘要翻譯模組

使用 Google Gemini API（新版 google-genai SDK）將蒐集到的文章做重點整理，
並將日文/英文內容翻譯為繁體中文，產生精煉的情報摘要。
"""

import asyncio
import logging
from typing import Optional

from google import genai

from .config import GEMINI_API_KEY, CATEGORIES
from .models import Article, Report

logger = logging.getLogger(__name__)

# Gemini 每次處理的文章上限（避免超出 token 限制）
_BATCH_SIZE = 15


def _init_client() -> genai.Client:
    """初始化 Gemini 客戶端"""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY 未設定，請檢查 .env 檔案")
    return genai.Client(api_key=GEMINI_API_KEY)


def _build_summary_prompt(articles: list[Article], category_name: str) -> str:
    """建構摘要翻譯的 prompt

    要求 Gemini 做三件事：
    1. 從文章中提取重點趨勢
    2. 翻譯標題為繁體中文
    3. 產生該分類的綜合分析
    """
    article_texts = []
    for i, a in enumerate(articles[:_BATCH_SIZE], 1):
        article_texts.append(
            f"{i}. 標題: {a.title}\n"
            f"   來源: {a.source}\n"
            f"   日期: {a.published_at[:10]}\n"
            f"   摘要: {a.summary[:200]}"
        )
    articles_block = "\n\n".join(article_texts)

    return f"""你是一位專業的日本博弈產業分析師。以下是本週蒐集到的「{category_name}」類別新聞。

請完成以下工作：

1. 趨勢總結：用 2-3 句繁體中文總結本週該領域的重要趨勢和發展方向。
2. 重點新聞：挑選最重要的 3-5 則新聞，每則用繁體中文寫出：
   - 繁體中文標題（翻譯自原文）
   - 一句話重點摘要
   - 原文來源名稱
3. 分析觀點：用 1-2 句繁體中文提供你的專業觀點或建議。

格式要求：
- 全部使用繁體中文輸出
- 簡潔有力，適合在 Telegram 閱讀
- 不要使用 Markdown 格式符號（如 ** 或 #）
- 用數字編號列出重點新聞

===== 本週新聞 =====
{articles_block}
"""


async def summarize_category(
    client: genai.Client,
    articles: list[Article],
    category_code: str,
) -> str:
    """用 Gemini 摘要翻譯單一分類的文章

    Args:
        client: Gemini 客戶端實例
        articles: 該分類的文章列表
        category_code: 分類代碼

    Returns:
        繁體中文摘要文字
    """
    if not articles:
        return ""

    cat_info = CATEGORIES.get(category_code, {"name": category_code, "icon": "📰"})
    category_name = cat_info["name"]

    prompt = _build_summary_prompt(articles, category_name)

    try:
        # 使用新版 SDK 呼叫（同步，用 asyncio.to_thread 避免阻塞）
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
        )
        result = response.text.strip()
        logger.info("Gemini 摘要完成 [%s]: %d 字", category_name, len(result))
        return result

    except Exception as e:
        logger.error("Gemini 摘要失敗 [%s]: %s", category_name, e)
        # 失敗時回傳基本的原文標題列表作為降級方案
        fallback_lines = ["（Gemini 摘要暫時無法使用，以下為原文標題）"]
        for i, a in enumerate(articles[:5], 1):
            fallback_lines.append(f"{i}. {a.title}")
            fallback_lines.append(f"   {a.source} | {a.published_at[:10]}")
        return "\n".join(fallback_lines)


async def summarize_report(report: Report) -> dict[str, str]:
    """對整份報告的各分類進行摘要翻譯

    Args:
        report: 蒐集報告

    Returns:
        dict，key 為分類代碼，value 為繁體中文摘要
    """
    client = _init_client()
    summaries: dict[str, str] = {}

    for cat_code in CATEGORIES:
        articles = report.get_articles_by_category(cat_code)
        if not articles:
            continue

        logger.info(
            "正在用 Gemini 處理 [%s]：%d 篇文章...",
            CATEGORIES[cat_code]["name"], len(articles),
        )
        summary = await summarize_category(client, articles, cat_code)
        if summary:
            summaries[cat_code] = summary

        # 間隔避免 API 限速
        await asyncio.sleep(1.0)

    logger.info("Gemini 摘要全部完成：%d 個分類", len(summaries))
    return summaries
