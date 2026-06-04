import os
from datetime import datetime
from playwright.async_api import async_playwright, Page, BrowserContext, Browser

class PlaywrightManager:
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.playwright = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        
        # Ensure output directories exist
        os.makedirs("test-results/videos", exist_ok=True)
        os.makedirs("test-results/screenshots", exist_ok=True)

    async def start_browser(self):
        print("Starting Playwright browser...")
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=["--window-size=1920,1080"]
        )

    async def create_context(self, test_name: str):
        print(f"Creating browser context for test: {test_name}")
        if not self.browser:
            raise Exception("Browser not started. Call start_browser() first.")
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_dir = f"test-results/videos/{test_name}_{timestamp}"
        os.makedirs(video_dir, exist_ok=True)
        
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            record_video_dir=video_dir,
            record_video_size={'width': 1920, 'height': 1080}
        )
        
        # Inject realistic cursor for videos
        await self.context.add_init_script("""
            window.addEventListener('DOMContentLoaded', () => {
                const cursor = document.createElement('div');
                cursor.id = 'playwright-cursor';
                cursor.style.width = '20px';
                cursor.style.height = '20px';
                cursor.style.borderRadius = '50%';
                cursor.style.backgroundColor = 'rgba(239, 68, 68, 0.6)';
                cursor.style.border = '2px solid white';
                cursor.style.position = 'fixed';
                cursor.style.pointerEvents = 'none';
                cursor.style.zIndex = '2147483647';
                cursor.style.transition = 'left 0.15s ease-out, top 0.15s ease-out, transform 0.15s';
                document.body.appendChild(cursor);

                document.addEventListener('mousemove', event => {
                    cursor.style.left = event.clientX - 10 + 'px';
                    cursor.style.top = event.clientY - 10 + 'px';
                }, true);

                document.addEventListener('mousedown', event => {
                    cursor.style.transform = 'scale(0.5)';
                }, true);

                document.addEventListener('mouseup', event => {
                    cursor.style.transform = 'scale(1)';
                }, true);
            });
        """)
        self.context.set_default_timeout(60000) # 60 seconds timeout
        self.page = await self.context.new_page()
        
        return self.page, video_dir

    async def take_screenshot(self, step_number: str, step_name: str) -> str:
        if not self.page:
            return ""
            
        clean_name = step_name.replace(" ", "_").replace("/", "_").lower()
        filename = f"test-results/screenshots/{step_number}-{clean_name}.png"
        
        # Wait a bit for animations before screenshot
        await self.page.wait_for_timeout(500) 
        
        await self.page.screenshot(path=filename, full_page=True)
        print(f"Screenshot saved: {filename}")
        return filename

    def get_page(self) -> Page:
        if not self.page:
            raise Exception("Page not initialized. Call create_context() first.")
        return self.page

    async def close(self):
        print("Closing Playwright resources...")
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
