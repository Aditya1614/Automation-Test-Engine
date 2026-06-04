from bs4 import BeautifulSoup
from playwright.async_api import Page

async def capture_dom(page: Page) -> str:
    """Captures the full HTML content of the page."""
    return await page.content()

def prune_dom(html_content: str) -> str:
    """
    Reduces the size of the DOM by removing unnecessary elements and attributes,
    keeping only structural and interactive clues for the AI.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 1. Remove script, style, svg, noscript, etc.
    for tag in soup(['script', 'style', 'svg', 'noscript', 'meta', 'link', 'iframe']):
        tag.decompose()
        
    # 2. Remove comments
    from bs4 import Comment
    for comment in soup.find_all(text=lambda text: isinstance(text, Comment)):
        comment.extract()
        
    # 3. Remove non-visible or clearly irrelevant elements (basic heuristic)
    for tag in soup.find_all(attrs={"aria-hidden": "true"}):
        tag.decompose()
    for tag in soup.find_all(style=lambda value: value and "display: none" in value.lower()):
        tag.decompose()
        
    # 4. Prune attributes to keep only essential ones
    allowed_attributes = [
        'id', 'class', 'name', 'type', 'value', 'placeholder', 
        'role', 'aria-label', 'href', 'title', 'data-field', 'data-menu-xmlid'
    ]
    
    for tag in soup.find_all(True):
        attrs_to_remove = []
        for attr in tag.attrs:
            if attr not in allowed_attributes:
                attrs_to_remove.append(attr)
                
        for attr in attrs_to_remove:
            del tag[attr]

    # Return prettified HTML to help the LLM read it easily (or stripped if we want to save max tokens)
    # Using simple str() to save space instead of prettify which adds lots of whitespace
    # Let's remove excessive empty lines and spaces
    pruned_html = str(soup)
    import re
    pruned_html = re.sub(r'>\s+<', '><', pruned_html)
    return pruned_html

async def get_visible_area_dom(page: Page) -> str:
    """
    (Optional) Capture DOM only for the visible area. 
    A simple approximation is to use standard prune_dom first, 
    but we might also inject JS to remove off-screen elements.
    For this POC, we rely on prune_dom to do the heavy lifting.
    """
    html = await page.content()
    return prune_dom(html)
