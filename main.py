from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from google.oauth2 import id_token
from google.auth.transport import requests
from database import get_db_connection
import schemas
import auth
import jwt

app = FastAPI()

# --- CORS MIDDLEWARE ---
# Permits your Live Server (port 5500) to communicate with the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# --- Verify Token and Get Current User ---
def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        # Decode the JWT token
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Look up the user in the database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        
        return user[0] # Return the actual user_id
    except Exception:
        raise HTTPException(status_code=401, detail="Could not validate credentials")


@app.get("/")
def root():
    return {"message": "Event Booking API is running!"}

@app.get("/test-db")
def test_db():
    conn = get_db_connection()
    if conn:
        conn.close()
        return {"status": "success", "message": "Database connected successfully!"}
    return {"status": "error", "message": "Database connection failed."}

@app.post("/users/")
def create_user(user: schemas.UserCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        hashed_pwd = auth.get_password_hash(user.password_hash)
        insert_query = """
            INSERT INTO users (name, email, password_hash, role)
            VALUES (%s, %s, %s, %s) RETURNING id;
        """
        cursor.execute(insert_query, (user.name, user.email, hashed_pwd, user.role))
        new_user_id = cursor.fetchone()[0]
        conn.commit()
        return {"message": "User created successfully", "user_id": new_user_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, email, password_hash FROM users WHERE email = %s", (form_data.username,))
        user = cursor.fetchone()
        if not user or not auth.verify_password(form_data.password, user[2]):
            raise HTTPException(status_code=401, detail="Incorrect email or password")
        
        access_token = auth.create_access_token(data={"sub": user[1]})
        return {"access_token": access_token, "token_type": "bearer"}
    finally:
        cursor.close()
        conn.close()

@app.get("/events/")
def get_events():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, title, description, event_date, location, total_capacity, available_tickets FROM events;")
        events = cursor.fetchall()
        
        event_list = []
        for row in events:
            event_list.append({
                "id": row[0],
                "title": row[1],
                "description": row[2],
                "event_date": row[3],
                "location": row[4],
                "total_capacity": row[5],
                "available_tickets": row[6]
            })
        return event_list
    finally:
        cursor.close()
        conn.close()

# --- SECURED: Book a Ticket ---
@app.post("/bookings/")
def create_booking(booking: schemas.BookingCreate, current_user_id: int = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT available_tickets FROM events WHERE id = %s", (booking.event_id,))
        result = cursor.fetchone()
        if not result or result[0] <= 0:
            raise HTTPException(status_code=400, detail="Event is sold out or does not exist")
        
        # SECURITY: Use current_user_id from the verified token, ignore booking.user_id
        cursor.execute(
            "INSERT INTO bookings (user_id, event_id) VALUES (%s, %s) RETURNING id;",
            (current_user_id, booking.event_id)
        )
        booking_id = cursor.fetchone()[0]

        cursor.execute(
            "UPDATE events SET available_tickets = available_tickets - 1 WHERE id = %s;",
            (booking.event_id,)
        )
        
        conn.commit()
        return {"message": "Ticket booked successfully!", "booking_id": booking_id}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cursor.close()
        conn.close()

# --- Get My Bookings (User Dashboard) ---
@app.get("/my-bookings/")
def get_my_bookings(current_user_id: int = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # SQL JOIN to combine booking records with event details
        query = """
            SELECT b.id, b.booking_date, e.title, e.event_date, e.location 
            FROM bookings b
            JOIN events e ON b.event_id = e.id
            WHERE b.user_id = %s
            ORDER BY b.booking_date DESC;
        """
        cursor.execute(query, (current_user_id,))
        bookings = cursor.fetchall()
        
        booking_list = []
        for row in bookings:
            booking_list.append({
                "booking_id": row[0],
                "booked_on": row[1],
                "event_title": row[2],
                "event_date": row[3],
                "location": row[4]
            })
        return booking_list
    finally:
        cursor.close()
        conn.close()

@app.get("/init-db")
def initialize_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Create all necessary tables if they don't exist yet
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100),
            email VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(20) DEFAULT 'user'
        );
        
        CREATE TABLE IF NOT EXISTS events (
            id SERIAL PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            event_date TIMESTAMP NOT NULL,
            location VARCHAR(255),
            total_capacity INT NOT NULL,
            available_tickets INT NOT NULL
        );
        
        CREATE TABLE IF NOT EXISTS bookings (
            id SERIAL PRIMARY KEY,
            user_id INT REFERENCES users(id),
            event_id INT REFERENCES events(id),
            booking_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, event_id)
        );
        """)
        conn.commit()
        return {"message": "Database tables created successfully!"}
    except Exception as e:
        conn.rollback()
        return {"error": str(e)}
    finally:
        cursor.close()
        conn.close()

@app.get("/seed-events")
def seed_events():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check if events already exist so we don't duplicate them
        cursor.execute("SELECT COUNT(*) FROM events;")
        if cursor.fetchone()[0] > 0:
            return {"message": "Events already exist!"}

        cursor.execute("""
        INSERT INTO events (title, description, event_date, location, total_capacity, available_tickets)
        VALUES 
        ('Auto Show', 'Offroad auto show.', '2026-11-20 10:00:00', 'Coimbatore', 150, 150),
        ('Dhanush Movie Premiere', 'Exclusive 4K Dolby Atmos screening.', '2026-12-05 18:30:00', 'Miraj Cinemas, SRK Mall', 250, 250)
        RETURNING id;
        """)
        conn.commit()
        return {"message": "Test events created successfully!"}
    except Exception as e:
        conn.rollback()
        return {"error": str(e)}
    finally:
        cursor.close()
        conn.close()


# Quick schema for event creation
class NewEvent(BaseModel):
    title: str
    description: str
    event_date: str
    location: str
    total_capacity: int

@app.post("/events/create")
def create_new_event(event: NewEvent):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO events (title, description, event_date, location, total_capacity, available_tickets)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id;
        """, (event.title, event.description, event.event_date, event.location, event.total_capacity, event.total_capacity))
        conn.commit()
        return {"message": "Event created successfully!"}
    except Exception as e:
        conn.rollback()
        return {"error": str(e)}
    finally:
        cursor.close()
        conn.close()

# --- NEW GOOGLE AUTH ROUTE ---
class GoogleToken(BaseModel):
    token: str

@app.post("/auth/google")
def google_login(req: GoogleToken):
    # 👇 PASTE YOUR GOOGLE CLIENT ID INSIDE THESE QUOTES 👇
    CLIENT_ID = "421196198288-o5jdi7s68t18tm6jmfliqm4oso3uuluo.apps.googleusercontent.com"
    
    try:
        # 1. Verify the token with Google's servers
        idinfo = id_token.verify_oauth2_token(req.token, requests.Request(), CLIENT_ID)
        email = idinfo['email']
        name = idinfo.get('name', 'Google User')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 2. Check if this user already exists in your PostgreSQL database
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        if not user:
            # 3. Auto-register them if it's their first time
            cursor.execute("""
                INSERT INTO users (name, email, password_hash, role) 
                VALUES (%s, %s, %s, 'user') RETURNING id;
            """, (name, email, "google_sso_no_password"))
            conn.commit()
        
        cursor.close()
        conn.close()
        
        # 4. NEW: Generate a REAL access token for the Google user
        real_access_token = auth.create_access_token(data={"sub": email})
        
        return {"message": "Google Login Successful", "email": email, "access_token": real_access_token}
        
    except ValueError:
        return {"error": "Invalid Google token"}
    except Exception as e:
        return {"error": str(e)}
# --- SECURED: Cancel a Booking ---
@app.delete("/bookings/{booking_id}")
def cancel_booking(booking_id: int, current_user_id: int = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 1. Verify the booking exists AND belongs to the logged-in user
        cursor.execute("SELECT event_id FROM bookings WHERE id = %s AND user_id = %s", (booking_id, current_user_id))
        result = cursor.fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Booking not found or not authorized to cancel")
        
        event_id = result[0]

        # 2. Delete the booking record
        cursor.execute("DELETE FROM bookings WHERE id = %s;", (booking_id,))

        # 3. Add the ticket back to the event's available capacity
        cursor.execute("UPDATE events SET available_tickets = available_tickets + 1 WHERE id = %s;", (event_id,))
        
        conn.commit()
        return {"message": "Booking cancelled successfully!"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cursor.close()
        conn.close()