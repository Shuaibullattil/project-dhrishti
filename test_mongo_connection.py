"""
Test script to diagnose MongoDB connection issues
Run this to test your MongoDB connection independently
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.server_api import ServerApi
import certifi
import ssl

# Load environment variables
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "video_output")

if not MONGO_URI:
    print("ERROR: MONGO_URI not found in .env file")
    exit(1)

print("=" * 60)
print("MongoDB Connection Test")
print("=" * 60)
print(f"MONGO_URI: {MONGO_URI[:50]}...")  # Show first 50 chars for security
print(f"DB_NAME: {DB_NAME}")
print(f"Certifi path: {certifi.where()}")
print("=" * 60)

# Test different connection methods
methods = [
    {
        'name': 'Method 1: certifi CA bundle',
        'client': lambda: MongoClient(
            MONGO_URI,
            server_api=ServerApi('1'),
            tls=True,
            tlsCAFile=certifi.where(),
            connectTimeoutMS=30000,
            serverSelectionTimeoutMS=30000
        )
    },
    {
        'name': 'Method 2: URI-based (let URI handle TLS)',
        'client': lambda: MongoClient(
            MONGO_URI,
            server_api=ServerApi('1'),
            connectTimeoutMS=30000,
            serverSelectionTimeoutMS=30000
        )
    },
    {
        'name': 'Method 3: SSL context',
        'client': lambda: MongoClient(
            MONGO_URI,
            server_api=ServerApi('1'),
            tls=True,
            ssl_context=ssl.create_default_context(cafile=certifi.where()),
            connectTimeoutMS=30000,
            serverSelectionTimeoutMS=30000
        )
    }
]

for method in methods:
    print(f"\nTrying {method['name']}...")
    try:
        client = method['client']()
        # Test connection
        result = client.admin.command('ping')
        print(f"✓ SUCCESS with {method['name']}")
        print(f"  Ping result: {result}")
        
        # Test database access
        db = client[DB_NAME]
        collections = db.list_collection_names()
        print(f"  Collections found: {collections}")
        
        client.close()
        break
    except Exception as e:
        print(f"✗ FAILED with {method['name']}")
        print(f"  Error: {str(e)[:300]}")
        if method == methods[-1]:
            print("\n" + "=" * 60)
            print("All connection methods failed!")
            print("=" * 60)
            print("\nTroubleshooting steps:")
            print("1. Verify your MONGO_URI is correct")
            print("2. Check if your IP is whitelisted in MongoDB Atlas")
            print("3. Verify your MongoDB username and password")
            print("4. Try updating certifi: pip install --upgrade certifi")
            print("5. Check your network/firewall settings")
            print("6. Verify MongoDB Atlas cluster is running")

