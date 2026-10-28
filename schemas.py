from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# Schema for creating a new user
class UserCreate(BaseModel):
    name: str
    email: str
    password_hash: str
    role: str = "organizer"

# Schema for creating a new event
class EventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    event_date: datetime
    location: str
    total_capacity: int
    organizer_id: int
# Schema for booking a ticket
class BookingCreate(BaseModel):
    user_id: int
    event_id: int
# --- NEW: Auth Schemas ---
class UserLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    
class TokenData(BaseModel):
    email: Optional[str] = None