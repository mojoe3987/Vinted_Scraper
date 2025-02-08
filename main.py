from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from google.cloud import storage
import sqlite3
import json
from datetime import datetime
import time
import random
from urllib.parse import urlparse
import os
from storage import VintedStorage
from scraper import Scraper

# Set Google credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r"C:\Users\joerling\Dropbox\0_Forschung\1_Paper\Vinted\scraping-450117-336603edb58d.json"

class VintedScraper:
    def __init__(self, bucket_name):
        # Initialize storage
        self.storage = VintedStorage(bucket_name)
        
        # Initialize Selenium
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')  # Run in headless mode
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        self.driver = webdriver.Chrome(options=options)
        self.driver.implicitly_wait(5)

    def scrape_product(self, url):
        """Scrape a single product page"""
        try:
            self.driver.get(url)
            time.sleep(random.uniform(2, 4))  # Random delay to avoid detection

            # Extract product ID from URL
            product_id = url.split('-')[-1]

            # Gather product data
            product_data = {
                'id': product_id,
                'url': url,
                'title': self._get_text('.//h1'),
                'price': self._get_price(),
                'description': self._get_text('.//div[contains(@class, "details-list__item--description")]'),
                'seller': self._get_text('.//div[contains(@class, "details-list__item--user")]'),
                'likes': self._get_number('.//div[contains(@class, "item-likes")]'),
                'views': self._get_number('.//div[contains(@class, "item-views")]'),
                'brand': self._get_text('.//div[contains(@class, "details-list__item--brand")]'),
                'size': self._get_text('.//div[contains(@class, "details-list__item--size")]'),
                'condition': self._get_text('.//div[contains(@class, "details-list__item--condition")]'),
                'location': self._get_text('.//div[contains(@class, "item-location")]'),
                'image_urls': self._get_image_urls(),
                'scraped_at': datetime.now().isoformat()
            }

            # Save to storage
            self.storage.save_product(product_data)
            print(f"Successfully scraped product {product_id}")
            return product_data

        except Exception as e:
            print(f"Error scraping {url}: {str(e)}")
            return None

    def _get_text(self, xpath, default=''):
        """Safely get text from an element"""
        try:
            element = self.driver.find_element(By.XPATH, xpath)
            return element.text.strip()
        except:
            return default

    def _get_number(self, xpath, default=0):
        """Get number from text"""
        try:
            text = self._get_text(xpath)
            return int(''.join(filter(str.isdigit, text)))
        except:
            return default

    def _get_price(self):
        """Extract price as float"""
        try:
            price_text = self._get_text('.//div[contains(@class, "item-price")]')
            return float(''.join(filter(str.isdigit, price_text)))
        except:
            return 0.0

    def _get_image_urls(self):
        """Get all product image URLs"""
        try:
            images = self.driver.find_elements(By.XPATH, '//img[contains(@class, "item-photo")]')
            return [img.get_attribute('src') for img in images if img.get_attribute('src')]
        except:
            return []

    def scrape_search_results(self, search_url, max_items=100):
        """Scrape multiple products from search results"""
        try:
            self.driver.get(search_url)
            time.sleep(random.uniform(2, 4))

            products_scraped = 0
            while products_scraped < max_items:
                # Find all product links on current page
                product_links = self.driver.find_elements(
                    By.XPATH, 
                    '//a[contains(@class, "item-link")]'
                )
                
                # Scrape each product
                for link in product_links:
                    if products_scraped >= max_items:
                        break
                    
                    product_url = link.get_attribute('href')
                    self.scrape_product(product_url)
                    products_scraped += 1
                    
                    # Random delay between products
                    time.sleep(random.uniform(1, 3))

                # Try to click next page
                try:
                    next_button = self.driver.find_element(
                        By.XPATH, 
                        '//a[contains(@class, "pagination-next")]'
                    )
                    next_button.click()
                    time.sleep(random.uniform(2, 4))
                except:
                    break  # No more pages

        except Exception as e:
            print(f"Error in search scraping: {str(e)}")

    def close(self):
        """Clean up"""
        self.driver.quit()

def main():
    # Initialize scraper with your GCS bucket name
    BUCKET_NAME = 'scrape_content'
    
    # Initialize scraper with GCS bucket
    scraper = Scraper(BUCKET_NAME)
    
    try:
        print("Starting scraper...")
        scraper.scrape_women_all()  # Use this method instead of scrape_search_results
        
    except Exception as e:
        print(f"Error in main: {e}")
    finally:
        scraper.close()

if __name__ == '__main__':
    main()