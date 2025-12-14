import asyncio
import json
import os
from datetime import datetime
from urllib.parse import urlparse, parse_qs, unquote
from bot.telegram_bot import send_job_to_telegram

from playwright.async_api import async_playwright


# ================= CONFIG =================
CHANNEL_URL = "https://www.youtube.com/@ashishcode/videos"
MAX_VIDEOS = 3
DATA_FILE = "data/jobs.json"

TRUSTED_PLATFORMS = [
    "forms.gle",
    "docs.google.com",
    "notion.site",
    "airtable.com"
]

JOB_KEYWORDS = [
    "job", "career", "careers", "apply", "hiring",
    "opening", "backend", "engineer",
    "developer", "role", "position", "vacancy"
]

EXCLUDE_DOMAINS = [
    "instagram",
    "telegram",
    "whatsapp",
    "facebook",
    "discord",
    "twitter",
    "youtube.com/channel",
    "youtube.com/watch"
]

#================Extracting channel videos=================
async def get_latest_video_urls(page, max_videos=5):
    await page.goto(CHANNEL_URL)
    await page.wait_for_load_state("networkidle")

    # Scroll to trigger lazy loading
    await page.mouse.wheel(0, 2000)
    await asyncio.sleep(2)

    # NEW selector (most reliable)
    await page.wait_for_selector("ytd-rich-item-renderer", timeout=15000)

    video_elements = await page.query_selector_all(
        "ytd-rich-item-renderer a#thumbnail"
    )

    urls = []
    for el in video_elements:
        href = await el.get_attribute("href")
        if href and href.startswith("/watch"):
            urls.append("https://www.youtube.com" + href)

        if len(urls) >= max_videos:
            break

    return urls


# ================= HELPERS =================

def unwrap_youtube_redirect(url: str) -> str:
    """
    Extract real URL from youtube.com/redirect?q=...
    """
    if "youtube.com/redirect" not in url:
        return url

    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    if "q" in query:
        return unquote(query["q"][0])

    return url


def filter_job_links(links):
    """
    Apply job filtering rules
    """
    results = []

    for item in links:
        url = item["url"].lower()
        text = item["text"].lower()

        #  Exclude obvious noise
        if any(bad in url for bad in EXCLUDE_DOMAINS):
            continue

        # ✅ Always allow trusted application platforms
        if any(tp in url for tp in TRUSTED_PLATFORMS):
            results.append(item["url"])
            continue

        # ✅ Allow job intent
        if any(k in url for k in JOB_KEYWORDS) or any(k in text for k in JOB_KEYWORDS):
            results.append(item["url"])

    return list(set(results))  # remove duplicates


def load_existing_jobs():
    if not os.path.exists(DATA_FILE):
        return []

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_jobs(jobs):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2)


def video_exists(existing_jobs, video_title):
    return any(job["video_title"] == video_title for job in existing_jobs)


async def process_single_video(page, video_url):
    await page.goto(video_url)

    video_title = await page.title()

    # Channel name (safe)
    channel_name = "Unknown Channel"
    try:
        channel_name = await page.locator(
            "ytd-channel-name a, ytd-channel-name yt-formatted-string"
        ).first.inner_text(timeout=5000)
    except:
        pass

    await page.wait_for_selector("ytd-text-inline-expander")

    try:
        await page.get_by_text("Show more").click()
        await asyncio.sleep(1)
    except:
        pass

    raw_links = await page.eval_on_selector_all(
        "ytd-text-inline-expander a",
        """
        els => els.map(e => ({
            url: e.href,
            text: e.innerText
        }))
        """
    )

    clean_links = [
        {
            "url": unwrap_youtube_redirect(item["url"]),
            "text": item["text"]
        }
        for item in raw_links
    ]

    job_links = filter_job_links(clean_links)

    if not job_links:
        print("⚠️ No job links found")
        return

    existing_jobs = load_existing_jobs()

    if video_exists(existing_jobs, video_title):
        print("ℹ️ Job already exists for this video")
        return

    job_entry = {
        "source": "YouTube",
        "video_title": video_title,
        "channel": channel_name,
        "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "job_links": job_links
    }

    existing_jobs.append(job_entry)
    save_jobs(existing_jobs)

    print("✅ New job saved")
    await send_job_to_telegram(job_entry)

# ================= MAIN SCRAPER =================

async def extract_job_links():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        page.set_default_timeout(15000)

        # 1️⃣ Get latest video URLs from channel
        video_urls = await get_latest_video_urls(page, MAX_VIDEOS)

        print(f"\n📺 Found {len(video_urls)} videos")

        for video_url in video_urls:
            print(f"\n▶ Processing video: {video_url}")
            await process_single_video(page, video_url)

        await browser.close()


# ================= RUN =================

asyncio.run(extract_job_links())
