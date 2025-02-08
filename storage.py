from google.cloud import storage
import sqlite3
import json
from datetime import datetime
import tempfile

class VintedStorage:
    def __init__(self, bucket_name):
        """Initialize with a GCS bucket name"""
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)
        self.db_name = "vinted_data.db"
        self.setup_database()

    def setup_database(self):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                title TEXT,
                price REAL,
                description TEXT,
                seller TEXT,
                likes INTEGER,
                views INTEGER,
                brand TEXT,
                size TEXT,
                condition TEXT,
                location TEXT,
                original_image_urls TEXT,
                gcs_paths TEXT,
                scraped_at DATETIME,
                raw_data TEXT
            )
        ''')
        
        conn.commit()
        conn.close()

    def save_product(self, product_data):
        """Save product data to Google Cloud Storage"""
        try:
            # Create a filename using timestamp to ensure uniqueness
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"products/product_{timestamp}.json"
            
            # Create a blob
            blob = self.bucket.blob(filename)
            
            # Convert data to JSON and upload
            json_data = json.dumps(product_data, ensure_ascii=False, indent=2)
            blob.upload_from_string(
                json_data,
                content_type='application/json'
            )
            
            print(f"Saved product data to {filename}")
            
        except Exception as e:
            print(f"Error saving to storage: {e}")
            raise

    def read_json(self, filename):
        """Read JSON data from GCS bucket"""
        try:
            blob = self.bucket.blob(filename)
            if not blob.exists():
                return []
            
            # Download and parse JSON
            content = blob.download_as_string()
            return json.loads(content)
        except Exception as e:
            print(f"Error reading from GCS: {e}")
            return []

    def write_json(self, filename, data):
        """Write JSON data to GCS bucket"""
        try:
            blob = self.bucket.blob(filename)
            
            # Convert data to JSON string
            json_str = json.dumps(data, ensure_ascii=False, indent=2)
            
            # Upload to GCS
            blob.upload_from_string(json_str, content_type='application/json')
            print(f"Successfully wrote to GCS: {filename}")
        except Exception as e:
            print(f"Error writing to GCS: {e}") 