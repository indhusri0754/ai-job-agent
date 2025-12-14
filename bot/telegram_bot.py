import os
import asyncio
from dotenv import load_dotenv
from telegram import Bot

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

bot = Bot(token=BOT_TOKEN)


async def send_job_to_telegram(job):
    message = f"""
🔥 *New Job Alert (YouTube)*

📌 *{job['video_title']}*
🎥 Channel: {job['channel']}

🔗 *Apply Links:*
"""

    for i, link in enumerate(job["job_links"], start=1):
        message += f"{i}️⃣ {link}\n"

    message += f"\n⏰ Added: {job['added_at']}"

    await bot.send_message(
        chat_id=CHAT_ID,
        text=message,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
