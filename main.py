from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from typing import List, Dict
import os
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = FastAPI()

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

logger.info(f"Attempting to connect to database with URL: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'hidden'}")

try:
    engine = create_engine(DATABASE_URL)
    # Test the connection
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    logger.info("Database connection successful")
except Exception as e:
    logger.error(f"Database connection failed: {str(e)}")
    raise

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@app.get("/")
async def root():
    return {"message": "Success! The API is working correctly."}

@app.get("/users")
async def get_users():
    try:
        db = SessionLocal()
        # Using text() for raw SQL query
        result = db.execute(text("SELECT * FROM users"))
        users = [dict(row) for row in result]
        db.close()
        return users
    except Exception as e:
        logger.error(f"Error fetching users: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Database error fetching users: {str(e)}"
        )