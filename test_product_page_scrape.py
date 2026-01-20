import requests
from bs4 import BeautifulSoup
import re

# Test Cookies product page
cookies_url = "https://cookiesflorida.co/bradenton/shop/prickly-pear-1-8oz/"
print(f"=== Testing Cookies Product Page ===")
print(f"URL: {cookies_url}\n")

try:
    response = requests.get(cookies_url, timeout=10, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Look for genetics/lineage keywords
    genetics_patterns = [
        r"(lineage|genetics|parents?|cross|bred from)[:\s]+([^\n<]+)",
        r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\s+[xX]\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)"
    ]
    
    page_text = soup.get_text()
    for pattern in genetics_patterns:
        matches = re.findall(pattern, page_text, re.IGNORECASE)
        if matches:
            print(f"Found genetics pattern: {matches[:3]}")
    
    # Check for specific sections
    for tag in ["p", "div", "span"]:
        for element in soup.find_all(tag, text=re.compile(r"lineage|genetics|parent", re.I)):
            print(f"\nGenetics section found in <{tag}>:")
            print(element.get_text()[:200])
            
except Exception as e:
    print(f"Error: {e}")

print("\n" + "="*50 + "\n")

# Test Flowery product page (if we can construct URL)
print("=== Flowery Product Page Structure ===")
print("Need to test with actual Flowery product URL from their site")
