from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

# Load MongoDB URI from environment variable
MONGO_URI = os.getenv('MONGO_URI')

# Connect to the MongoDB cluster
client = MongoClient(MONGO_URI)

# List all databases
databases = client.list_database_names()
print("Databases in MongoDB cluster:", databases)
