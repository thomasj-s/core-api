from bs4 import BeautifulSoup as bs
import asyncio
import csv
import random
import time
from playwright.async_api import async_playwright

page_no = 1
pre = "https://tracker.gg/overwatch/leaderboards/stats/all/Eliminations?page="
post = "&plat=mouseKeyboard&gamemode=competitive"

def save_usernames_to_csv(usernames, filename="app/scraper/usernames.csv"):
    """Save usernames to CSV, checking for duplicates"""
    existing_usernames = set()

    # Read existing usernames if file exists
    try:
        with open(filename, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if row:  # Skip empty rows
                    existing_usernames.add(row[0])
    except FileNotFoundError:
        pass  # File doesn't exist yet, that's fine

    # Filter out duplicates
    new_usernames = [username for username in usernames if username not in existing_usernames]

    if new_usernames:
        # Append new usernames
        with open(filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for username in new_usernames:
                writer.writerow([username])

        print(f"Added {len(new_usernames)} new usernames to {filename} (skipped {len(usernames) - len(new_usernames)} duplicates)")
    else:
        print(f"All {len(usernames)} usernames were duplicates, nothing added to {filename}")

    return len(new_usernames)

async def scrape_page(page, page_no, browser_context):
    url = pre + str(page_no) + post

    # Rotate user agents to avoid detection
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0"
    ]

    user_agent = random.choice(user_agents)
    await page.set_extra_http_headers({
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    })


    print(f"Scraping page {page_no} with UA: {user_agent[:50]}...")

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)

        # Longer initial wait for Cloudflare
        await page.wait_for_timeout(random.randint(8000, 15000))  # 8-15 seconds

        # Check if we got the real page or still the challenge
        title = await page.title()
        challenge_count = 0
        max_challenges = 3

        while "Just a moment" in title and challenge_count < max_challenges:
            challenge_count += 1
            print(f"Still on Cloudflare challenge page (attempt {challenge_count}/{max_challenges}), waiting longer...")
            await page.wait_for_timeout(random.randint(20000, 35000))  # 20-35 seconds
            title = await page.title()

        if "Just a moment" in title:
            print(f"❌ Failed to pass Cloudflare challenge after {max_challenges} attempts")
            return []

        # Additional random delay to look human
        await page.wait_for_timeout(random.randint(3000, 8000))  # 3-8 seconds

        content = await page.content()
        soup = bs(content, "html.parser")

        player_names = soup.find_all("span", class_="trn-ign__username fit-long-username")
        player_discriminators = soup.find_all("span", class_="trn-ign__discriminator")

        print(f"  Found {len(player_names)} username elements, {len(player_discriminators)} discriminator elements")

        # Extract just the text content
        usernames = [span.text for span in player_names]
        discriminators = [span.text.replace("#", "-") for span in player_discriminators]

        # Combine usernames with discriminators
        full_usernames = [f"{username}{discriminator}" for username, discriminator in zip(usernames, discriminators)]

        print(f"  Successfully combined into {len(full_usernames)} full usernames")

        return full_usernames

    except Exception as e:
        print(f"Error scraping page {page_no}: {e}")
        return []


async def main():
    print("Starting Overwatch leaderboard scraper...")
    print("This will run until the end of the leaderboard. Press Ctrl+C to stop.")
    print("⚠️  Note: Using aggressive anti-detection with fresh browser context per page and moderate delays")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--disable-gpu'
            ]
        )

        page_no = 1
        total_usernames = 0
        consecutive_empty_pages = 0
        max_empty_pages = 5
        context_page_count = 0
        max_pages_per_context = 1  # Rotate context every page for maximum stealth

        context = await browser.new_context()
        page = await context.new_page()

        while True:
            try:
                # Rotate browser context periodically to avoid detection
                if context_page_count >= max_pages_per_context:
                    print("🔄 Rotating browser context to avoid detection...")
                    await context.close()
                    context = await browser.new_context()
                    page = await context.new_page()
                    context_page_count = 0

                # Scrape current page
                usernames = await scrape_page(page, page_no, context)
                context_page_count += 1

                if not usernames:
                    consecutive_empty_pages += 1
                    print(f"⚠️  Page {page_no} returned no usernames (empty page #{consecutive_empty_pages}/{max_empty_pages})")

                    if consecutive_empty_pages >= max_empty_pages:
                        print(f"Reached apparent end of leaderboard after {consecutive_empty_pages} consecutive empty pages.")
                        break
                else:
                    consecutive_empty_pages = 0  # Reset counter

                    # Save to CSV
                    new_count = save_usernames_to_csv(usernames)
                    total_usernames += new_count

                    print(f"✅ Page {page_no}: Found {len(usernames)} usernames, added {new_count} new ones")
                    print(f"📊 Total unique usernames collected: {total_usernames}")

                page_no += 1

                # Moderate random delay between pages (30-90 seconds)
                delay = random.randint(30000, 90000)  # 30-90 seconds
                print(f"⏱️  Waiting {delay/1000:.1f} seconds before next page...")
                await asyncio.sleep(delay / 1000)

                # Periodic save checkpoint every 5 pages
                if page_no % 5 == 0:
                    print(f"🔄 Checkpoint: Processed {page_no} pages, {total_usernames} total unique usernames")

            except KeyboardInterrupt:
                print("\n🛑 Scraping interrupted by user.")
                break
            except Exception as e:
                print(f"❌ Unexpected error on page {page_no}: {e}")
                # Wait a bit longer on errors
                await asyncio.sleep(random.randint(60, 120))
                consecutive_empty_pages += 1

        print(f"\nScraping complete! Total unique usernames saved: {total_usernames}")
        print("Data saved to usernames.csv")

asyncio.run(main())