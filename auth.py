import bcrypt
import jwt
from datetime import datetime, timedelta

# Configuration for JWT
SECRET_KEY = "your_super_secret_key_change_this_later" 
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Checks if the provided password matches the database hash."""
    # bcrypt requires bytes, so we encode the strings
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_password_hash(password: str) -> str:
    """Converts a plain text password into a secure bcrypt hash."""
    # bcrypt.hashpw returns bytes, we decode to string for the PostgreSQL database
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def create_access_token(data: dict):
    """Generates a JWT token valid for 60 minutes."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt