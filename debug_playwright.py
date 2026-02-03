import asyncio
from playwright.async_api import async_playwright
import sys

async def main():
    print("Attempting to launch Playwright...")
    try:
        async with async_playwright() as p:
            print("Playwright initialized.")
            browser = await p.chromium.launch(headless=True)
            print("Chromium Launched Successfully!")
            await browser.close()
            print("Browser Closed.")
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
