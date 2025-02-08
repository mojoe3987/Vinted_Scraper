from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import time
import random
from datetime import datetime
import sys
import os
import pandas as pd
import json
from storage import VintedStorage
import uuid  # Add this import for generating unique IDs
import requests  # Added for image downloading

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class Scraper:
    def __init__(self, bucket_name="scrape_content"):
        """Initialize the scraper with Chrome driver and GCS storage"""
        self.driver = webdriver.Chrome()
        self.storage = VintedStorage(bucket_name)  # Initialize storage with your bucket
        
        # Initialize Selenium with additional options
        options = webdriver.ChromeOptions()
        #options.add_argument('--headless')  # Run in headless mode
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        # Add these new options
        options.add_argument('--disable-gpu')  # Disable GPU hardware acceleration
        options.add_argument('--disable-software-rasterizer')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-logging')  # Reduce console logging
        
        # Update this path to where your chromedriver is located
        self.driver = webdriver.Chrome(options=options)  # Modern selenium doesn't need executable_path
        self.driver.implicitly_wait(5)

    def handle_popups(self):
        """Handle both country selection and cookie popups using recorded selectors"""
        try:
            print("Handling initial popups...")
            
            # Close country selection using recorded selector
            print("Attempting to close country selection popup...")
            country_close = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((
                    By.CSS_SELECTOR, 
                    ".web_ui__Navigation__right > .web_ui__Button__button"
                ))
            )
            country_close.click()
            time.sleep(2)
            
            # Handle cookie popup using recorded ID
            print("Attempting to reject cookies...")
            cookie_reject = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((
                    By.ID, 
                    "onetrust-reject-all-handler"
                ))
            )
            cookie_reject.click()
            print("Rejected cookies")
            time.sleep(2)
            
        except Exception as e:
            print(f"Error handling popups: {str(e)}")

    def scrape_search_results(self, search_term, max_items=100):
        """Scrape multiple products from search results"""
        try:
            # First go to main page
            print("Navigating to main page...")
            self.driver.get("https://www.vinted.com")
            time.sleep(3)
            
            # Handle popups using recorded selectors
            self.handle_popups()
            
            # Navigate to Women's section (as per recording)
            women_link = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.LINK_TEXT, "Women"))
            )
            women_link.click()
            time.sleep(2)
            
            # Click "All" in Women's section
            all_items = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((
                    By.CSS_SELECTOR, 
                    ".web_ui__Cell__default:nth-child(1) .web_ui__Cell__body > .web_ui__Text__body"
                ))
            )
            all_items.click()
            time.sleep(2)
            
            # Now look for search field
            print(f"Looking for search field...")
            try:
                search_input = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='search']"))
                )
                
                print(f"Found search field, entering search term: {search_term}")
                search_input.click()
                time.sleep(1)
                search_input.send_keys(search_term)
                time.sleep(1)
                search_input.send_keys(Keys.RETURN)
                
                print("Search submitted, waiting for results...")
                time.sleep(3)
                
            except Exception as e:
                print(f"Error with search: {str(e)}")
                raise
            
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
            print(f"Error scraping search results: {e}")

    def _get_text(self, xpath, default=''):
        """Safely get text from an element"""
        try:
            element = self.driver.find_element(By.XPATH, xpath)
            return element.text.strip()
        except:
            return default

    def _get_likes(self):
        """Get number of likes"""
        try:
            likes_element = self.driver.find_element(By.CSS_SELECTOR, "[data-testid='item-likes']")
            likes_text = likes_element.text
            return int(''.join(filter(str.isdigit, likes_text)))
        except Exception as e:
            print(f"Error getting likes: {e}")
            return 0

    def _get_views(self):
        """Get number of views"""
        try:
            views_element = self.driver.find_element(By.CSS_SELECTOR, "[data-testid='item-views']")
            views_text = views_element.text
            return int(''.join(filter(str.isdigit, views_text)))
        except Exception as e:
            print(f"Error getting views: {e}")
            return 0

    def _get_product_details(self):
        """Get all product details from the details list"""
        details = {}
        try:
            # Find all detail items
            detail_items = self.driver.find_elements(By.CSS_SELECTOR, ".details-list__item")
            
            for item in detail_items:
                try:
                    # Get the label and value
                    label = item.find_element(By.CSS_SELECTOR, ".details-list__item-title").text.strip().lower()
                    value = item.find_element(By.CSS_SELECTOR, ".details-list__item-value").text.strip()
                    details[label] = value
                except:
                    continue
                    
        except Exception as e:
            print(f"Error getting product details: {e}")
        
        return details

    def _extract_details_from_container(self, container):
        """Extract all details from a container element"""
        details = {}
        
        try:
            # Get all details-list sections
            details_lists = container.find_elements(By.CLASS_NAME, "details-list")
            
            for details_list in details_lists:
                # Check the class name to identify the section type
                class_name = details_list.get_attribute('class')
                
                if 'details-list--main-info' in class_name:
                    # Extract main info (title, condition, brand)
                    try:
                        title = details_list.find_element(By.CLASS_NAME, "web_ui__Text__title").text.strip()
                        details['title'] = title
                    except: pass
                    
                    try:
                        condition_brand = details_list.find_element(By.CLASS_NAME, "summary-max-lines-4")
                        texts = condition_brand.find_elements(By.CLASS_NAME, "web_ui__Text__text")
                        for text in texts:
                            if 'Very good' in text.text:  # or any other condition text
                                details['condition'] = text.text.strip()
                            elif text.get_attribute('class').find('clickable') > -1:
                                details['brand'] = text.text.strip()
                    except: pass

                elif 'details-list--pricing' in class_name:
                    # Extract pricing information
                    try:
                        price = details_list.find_element(By.CSS_SELECTOR, "[data-testid='item-price'] p").text.strip()
                        details['price'] = price
                        
                        buyer_protection = details_list.find_element(By.CSS_SELECTOR, "[data-testid='service-fee-included-title']").text.strip()
                        details['buyer_protection'] = buyer_protection
                    except: pass

                else:
                    # Extract all other details
                    try:
                        items = details_list.find_elements(By.CLASS_NAME, "details-list__item")
                        for item in items:
                            try:
                                # Get label and value
                                label = item.find_element(By.CSS_SELECTOR, ".details-list__item-value:first-child").text.strip()
                                value = item.find_element(By.CSS_SELECTOR, ".details-list__item-value:last-child").text.strip()
                                
                                # Clean up the label (remove any trailing colon and convert to lowercase for consistency)
                                label = label.rstrip(':').lower()
                                
                                if label and value:  # Only add if both exist
                                    details[label] = value
                            except: continue
                    except: pass
                    
        except Exception as e:
            print(f"Error extracting details from container: {e}")
            
        return details

    def _save_images(self, unique_id, image_urls):
        """Save product images to GCS"""
        try:
            image_paths = []
            for idx, img_url in enumerate(image_urls, 1):
                # Create image filename with product ID and sequence number
                image_filename = f"scrape_images/{unique_id}_image_{idx}.jpg"
                
                # Download image and upload to GCS
                blob = self.storage.bucket.blob(image_filename)
                
                # Use requests to download the image
                response = requests.get(img_url)
                if response.status_code == 200:
                    # Upload image content directly to GCS
                    blob.upload_from_string(
                        response.content,
                        content_type='image/jpeg'
                    )
                    image_paths.append(image_filename)
                    print(f"Saved image {idx} to GCS: {image_filename}")
                
                # Add small delay between image downloads
                time.sleep(random.uniform(0.5, 1))
            
            return image_paths
        except Exception as e:
            print(f"Error saving images: {e}")
            return []

    def scrape_product(self, product_url):
        """Scrape a single product page"""
        try:
            print("\n=== PRODUCT DATA ===")
            print(f"URL: {product_url}")
            self.driver.get(product_url)
            time.sleep(random.uniform(2, 4))

            # Generate unique ID
            unique_id = str(uuid.uuid4())

            product_data = {
                'id': unique_id,
                'scrape_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'url': product_url
            }

            try:
                main_container = self.driver.find_element(By.CLASS_NAME, "details-list--main-info").find_element(By.XPATH, '..')
                details = self._extract_details_from_container(main_container)
                product_data.update(details)

                # Get all image URLs from the item-photos container
                image_urls = []
                try:
                    image_elements = self.driver.find_elements(
                        By.CSS_SELECTOR,
                        ".item-photos img.web_ui__Image__content"
                    )
                    image_urls = [img.get_attribute('src') for img in image_elements if img.get_attribute('src')]
                    
                    # Save images to GCS and get their paths
                    if image_urls:
                        image_paths = self._save_images(unique_id, image_urls)
                        product_data['image_paths'] = image_paths
                        product_data['image_count'] = len(image_paths)
                except Exception as e:
                    print(f"Error getting images: {e}")
                    product_data['image_paths'] = []
                    product_data['image_count'] = 0

                # Get description separately as it might be in a different location
                description = self._get_text('/html/body/div[1]/div/main/div/div[1]/div/div[2]/div/div/main/div[1]/aside/div[2]/div[1]/div/div/div/div/div/div[2]/div[3]/div/div/div[1]/div/span/span')
                if description:
                    product_data['description'] = description

                # Get seller information
                seller_data = {
                    'seller_name': self._get_text('//*[@id="sidebar"]/div[2]/div[3]/div/a/div[2]/div[1]/div/div/span'),
                    'seller_image': self.driver.find_element(By.XPATH, '//*[@id="sidebar"]/div[2]/div[3]/div/a/div[2]/div[1]/div/div/span').get_attribute('src'),
                    'seller_ratings': self._get_text('//*[@id="sidebar"]/div[2]/div[3]/div/a/div[2]/div[2]/div/div[6]/h4'),
                    'seller_rating': self._get_text('//*[@id="sidebar"]/div[2]/div[3]/div/a/div[2]/div[2]/div'),
                    'upload_frequency': self._get_text('//*[@id="sidebar"]/div[2]/div[3]/div/div[2]/div/div[2]/div[1]/div'),
                    'seller_location': self._get_text('//*[@id="sidebar"]/div[2]/div[3]/div/div[4]/div/div/div[1]/div[2]')
                }
                product_data['seller_info'] = seller_data

                # Save to GCS
                filename = f'vinted_products_{datetime.now().strftime("%Y%m%d")}.json'
                
                # Get existing data from GCS
                existing_data = self.storage.read_json(filename)
                if not existing_data:
                    existing_data = []
                
                # Append new data and save back to GCS
                existing_data.append(product_data)
                self.storage.write_json(filename, existing_data)
                
                print(f"\nSaved data to GCS bucket: scrape_content/{filename}")
                print("\nData collected:")
                print(json.dumps(product_data, indent=2, ensure_ascii=False))

            except Exception as e:
                print(f"Error getting specific details: {e}")

            print("\n=== END PRODUCT DATA ===")
            return product_data

        except Exception as e:
            print(f"Error scraping product {product_url}: {str(e)}")
            return None

    def _get_shipping_cost(self):
        """Get shipping cost"""
        try:
            shipping_element = self.driver.find_element(By.CSS_SELECTOR, "[data-testid='shipping-price']")
            shipping_text = shipping_element.text
            return float(''.join(filter(str.isdigit, shipping_text))) / 100  # Convert cents to dollars
        except Exception as e:
            print(f"Error getting shipping cost: {e}")
            return 0.0

    def _get_image_urls(self):
        """Get all product image URLs"""
        try:
            # Look for the image gallery
            images = self.driver.find_elements(By.CSS_SELECTOR, ".item-photos img")
            return [img.get_attribute('src') for img in images if img.get_attribute('src')]
        except Exception as e:
            print(f"Error getting image URLs: {e}")
            return []

    def close(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()

    def scrape_women_all(self):
        """Follow the exact navigation steps from Vinted.side and scrape results"""
        try:
            # Step 1: Open main page
            print("Navigating to main page...")
            self.driver.get("https://www.vinted.com")
            time.sleep(3)
            
            # Step 2: Close country selection popup
            print("Closing country selection...")
            country_close = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((
                    By.CSS_SELECTOR, 
                    ".web_ui__Navigation__right > .web_ui__Button__button"
                ))
            )
            country_close.click()
            time.sleep(2)
            
            # Step 3: Handle cookie popup
            print("Handling cookie popup...")
            cookie_reject = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((
                    By.ID, 
                    "onetrust-reject-all-handler"
                ))
            )
            cookie_reject.click()
            time.sleep(2)
            
            # Step 4: Click Women link
            print("Clicking Women category...")
            women_link = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.LINK_TEXT, "Women"))
            )
            women_link.click()
            time.sleep(2)
            
            # Step 5: Click All in Women's section
            print("Clicking All items...")
            all_items = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((
                    By.CSS_SELECTOR, 
                    ".web_ui__Cell__default:nth-child(1) .web_ui__Cell__body > .web_ui__Text__body"
                ))
            )
            all_items.click()
            time.sleep(2)
            
            # Now scrape the products on the page
            print("Starting to scrape products...")
            self.scrape_current_page_products()
            
        except Exception as e:
            print(f"Error during navigation: {str(e)}")
            raise

    def scrape_current_page_products(self):
        """Scrape all products visible on the current page"""
        try:
            # Find all product links using the content section selector
            product_links = self.driver.find_elements(
                By.CSS_SELECTOR, 
                "#content div.new-item-box__image-container > a"
            )
            
            if product_links:
                # Just get the first product
                first_product = product_links[0]
                product_url = first_product.get_attribute('href')
                print(f"Found first product URL: {product_url}")
                self.scrape_product(product_url)
                print("Finished scraping first product")
            else:
                print("No products found on page")
                    
        except Exception as e:
            print(f"Error scraping page: {str(e)}")

# Remove or comment out these lines if they exist
# scraper = Scraper(bucket_name='scrape_content')
# try:
#     search_url = "https://www.vinted.de/catalog?search_text=nike&brand_id[]=53"
#     scraper.scrape_search_results(search_url, max_items=100)
#     another_search = "https://www.vinted.de/catalog?search_text=adidas"
#     scraper.scrape_search_results(another_search, max_items=50)
# finally:
#     scraper.close()

# Add this at the bottom of the file
if __name__ == "__main__":
    scraper = Scraper(bucket_name='scrape_content')
    
    try:
        print("Starting scraper...")
        scraper.scrape_women_all()  # Use this method instead of scrape_search_results
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        import traceback
        print(traceback.format_exc())
        
    finally:
        print("Closing scraper...")
        scraper.close()
        print("Scraper closed.") 