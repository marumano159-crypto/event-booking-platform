import os
import psycopg2
from psycopg2 import Error

def get_db_connection():
    try:
        # 1. Cloud Connection (Render provides this automatically)
        db_url = os.getenv("DATABASE_URL")
        
        if db_url:
            connection = psycopg2.connect(db_url)
        else:
            # 2. Local Docker Connection
            connection = psycopg2.connect(
                host='db',
                user='postgres',
                password='admin123',
                dbname='event_booking_db',
                port='5432'
            )
        return connection
    except Error as e:
        print(f"Error connecting to PostgreSQL: {e}")
        return None

# Retained in case other parts of your app rely on SQLAlchemy routing
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://postgres:admin123@db:5432/event_booking_db"
)