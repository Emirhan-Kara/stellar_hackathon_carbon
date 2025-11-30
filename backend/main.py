from fastapi import FastAPI, HTTPException, Response, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
import os
import mysql.connector
from mysql.connector import Error
import jwt
import secrets
from datetime import datetime, timedelta
from stellar_sdk import Keypair, Network, StrKey
from stellar_sdk.exceptions import Ed25519PublicKeyInvalidError
import base64
import re

load_dotenv()

app = FastAPI()

# Create uploads directory if it doesn't exist
os.makedirs("uploads/projects", exist_ok=True)
os.makedirs("uploads/documents", exist_ok=True)

# Mount static files for uploaded images
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database configuration from .env
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "stellar_db"),
}

JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-this")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Stellar network configuration
STELLAR_NETWORK = os.getenv("STELLAR_NETWORK", "TESTNET")
NETWORK_PASSPHRASES = {
    "PUBLIC": Network.PUBLIC_NETWORK_PASSPHRASE,
    "TESTNET": Network.TESTNET_NETWORK_PASSPHRASE,
    "FUTURENET": Network.FUTURENET_NETWORK_PASSPHRASE,
}
NETWORK_PASSPHRASE = NETWORK_PASSPHRASES.get(STELLAR_NETWORK, Network.TESTNET_NETWORK_PASSPHRASE)


def get_db_connection():
    """Create and return a database connection"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")


def get_authenticated_user(request: Request):
    """Extract and return authenticated user from JWT cookie"""
    auth_token = request.cookies.get("auth_token")
    
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        payload = jwt.decode(auth_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        wallet_address = payload.get("wallet_address")
        
        if not user_id or not wallet_address:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        return {"user_id": user_id, "wallet_address": wallet_address}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def remove_vowels(text: str) -> str:
    """Remove all vowels (a, e, i, o, u) case-insensitively and return uppercase"""
    return re.sub(r'[aeiouAEIOU]', '', text).upper()


def generate_project_identifier(category_id: int, connection) -> str:
    """Generate unique project identifier based on category"""
    cursor = connection.cursor(dictionary=True)
    
    # Get category name
    cursor.execute("SELECT name FROM categories WHERE id = %s", (category_id,))
    category = cursor.fetchone()
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    category_name = category["name"]
    
    # Remove vowels and uppercase
    consonants = remove_vowels(category_name)
    
    # Count existing projects with same category_id
    cursor.execute("SELECT COUNT(*) as count FROM projects WHERE category_id = %s", (category_id,))
    result = cursor.fetchone()
    count = result["count"] if result else 0
    
    # Generate identifier: CONSONANTS-(count+1)
    project_identifier = f"{consonants}-{count + 1}"
    
    cursor.close()
    return project_identifier


# Pydantic models
class NonceRequest(BaseModel):
    publicKey: str


class VerifyRequest(BaseModel):
    publicKey: str
    signature: str
    nonce: str


class CheckAvailabilityRequest(BaseModel):
    username: str = None
    email: str = None


class CompleteRegistrationRequest(BaseModel):
    wallet_address: str
    username: str
    email: str = None


@app.get("/")
def read_root():
    return {"message": "Stellar Freighter Auth API"}


@app.post("/auth/nonce")
async def get_nonce(request: NonceRequest):
    """
    Generate and store a nonce for the given wallet address.
    Returns the nonce that needs to be signed.
    """
    public_key = request.publicKey.strip()
    
    # Validate Stellar public key format
    try:
        Keypair.from_public_key(public_key)
    except Ed25519PublicKeyInvalidError:
        raise HTTPException(status_code=400, detail="Invalid Stellar public key format")
    
    # Generate a random nonce
    nonce = secrets.token_urlsafe(32)
    
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Check if user exists
        cursor.execute(
            "SELECT user_id, current_nonce FROM users WHERE wallet_address = %s",
            (public_key,)
        )
        user = cursor.fetchone()
        
        if user:
            # Update existing user's nonce
            cursor.execute(
                "UPDATE users SET current_nonce = %s WHERE wallet_address = %s",
                (nonce, public_key)
            )
        else:
            # Store nonce temporarily - need to provide a temporary username since it's NOT NULL
            # Use a unique temporary username that will be replaced during registration
            # Format: temp_<timestamp>_<first8chars_of_wallet>
            import time
            temp_username = f"temp_{int(time.time())}_{public_key[:8]}"
            
            # Ensure temp username is unique (very unlikely to conflict, but check anyway)
            counter = 0
            while True:
                cursor.execute("SELECT user_id FROM users WHERE username = %s", (temp_username,))
                if not cursor.fetchone():
                    break
                temp_username = f"temp_{int(time.time())}_{public_key[:8]}_{counter}"
                counter += 1
                if counter > 1000:
                    # Fallback: use full wallet address as temp username
                    temp_username = f"temp_{public_key}"
                    break
            
            cursor.execute(
                "INSERT INTO users (wallet_address, username, current_nonce) VALUES (%s, %s, %s)",
                (public_key, temp_username, nonce)
            )
        
        connection.commit()
        return {"nonce": nonce}
        
    except Error as e:
        if connection:
            connection.rollback()
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate nonce")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


@app.post("/auth/freighter/verify")
async def verify_signature(request: VerifyRequest, response: Response):
    """
    Verify the signature, check nonce, and issue JWT token.
    Sets JWT in httpOnly cookie.
    """
    public_key = request.publicKey.strip()
    signature = request.signature.strip()
    nonce = request.nonce.strip()
    
    # Validate inputs
    if not all([public_key, signature, nonce]):
        raise HTTPException(status_code=400, detail="Missing required fields")
    
    # Validate Stellar public key format
    try:
        keypair = Keypair.from_public_key(public_key)
    except Ed25519PublicKeyInvalidError:
        raise HTTPException(status_code=400, detail="Invalid Stellar public key format")
    
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Get user and stored nonce
        cursor.execute(
            "SELECT user_id, current_nonce FROM users WHERE wallet_address = %s",
            (public_key,)
        )
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(status_code=404, detail="Nonce not found. Please request a new nonce.")
        
        stored_nonce = user.get("current_nonce")
        
        if not stored_nonce or stored_nonce != nonce:
            raise HTTPException(status_code=401, detail="Invalid or expired nonce")
        
        # Verify signature using Stellar SDK's built-in method
        # verify_message() handles the "Stellar Signed Message:\n" prefix and SHA-256 hashing internally
        try:
            # Decode the base64 signature
            signature_bytes = base64.b64decode(signature)
            
            # Use Stellar SDK's verify_message - it handles everything internally
            # Just pass the original nonce string (exactly as sent to signMessage on frontend)
            keypair.verify_message(nonce, signature_bytes)
            
            print("Signature verification successful!")
            
        except Exception as e:
            print(f"Signature verification failed: {type(e).__name__}: {e}")
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Clear the nonce after successful verification
        cursor.execute(
            "UPDATE users SET current_nonce = NULL WHERE wallet_address = %s",
            (public_key,)
        )
        connection.commit()
        
        # Get full user data including username to check registration status
        cursor.execute(
            "SELECT user_id, username, email FROM users WHERE wallet_address = %s",
            (public_key,)
        )
        full_user = cursor.fetchone()
        
        # Check if user registration is complete (has non-temporary username)
        username = full_user.get("username") if full_user else None
        is_registered = username is not None and not username.startswith("temp_")
        
        if is_registered:
            # User is fully registered, issue JWT
            payload = {
                "user_id": full_user["user_id"],
                "wallet_address": public_key,
                "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
                "iat": datetime.utcnow(),
            }
            
            token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
            
            # Set JWT in httpOnly cookie
            response.set_cookie(
                key="auth_token",
                value=token,
                httponly=True,
                secure=False,  # Set to True in production with HTTPS
                samesite="lax",
                max_age=JWT_EXPIRATION_HOURS * 3600,
            )
            
            return {
                "success": True,
                "message": "Authentication successful",
                "user_id": full_user["user_id"],
                "wallet_address": public_key,
                "username": full_user.get("username"),
                "email": full_user.get("email"),
                "registered": True,
            }
        else:
            # User needs to complete registration
            return {
                "success": True,
                "message": "Wallet verified. Please complete registration.",
                "wallet_address": public_key,
                "registered": False,
                "user_id": full_user["user_id"] if full_user else None,
            }
        
    except HTTPException:
        raise
    except Error as e:
        if connection:
            connection.rollback()
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


@app.post("/auth/check-availability")
async def check_availability(request: CheckAvailabilityRequest):
    """
    Check if username or email is available (not already taken).
    """
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        results = {}
        
        if request.username:
            cursor.execute(
                "SELECT user_id FROM users WHERE username = %s",
                (request.username.strip(),)
            )
            results["username_available"] = cursor.fetchone() is None
        
        if request.email:
            cursor.execute(
                "SELECT user_id FROM users WHERE email = %s",
                (request.email.strip(),)
            )
            results["email_available"] = cursor.fetchone() is None
        
        return results
        
    except Error as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


@app.post("/auth/complete-registration")
async def complete_registration(request: CompleteRegistrationRequest, response: Response):
    """
    Complete user registration by adding username and email.
    Verifies that the wallet_address exists and is not already registered.
    """
    wallet_address = request.wallet_address.strip()
    username = request.username.strip()
    email = request.email.strip() if request.email else None
    
    # Validate inputs
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Check if wallet exists
        cursor.execute(
            "SELECT user_id, username, email FROM users WHERE wallet_address = %s",
            (wallet_address,)
        )
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(status_code=404, detail="Wallet not found. Please connect your wallet first.")
        
        # Check if already registered (username doesn't start with "temp_")
        current_username = user.get("username", "")
        if current_username and not current_username.startswith("temp_"):
            raise HTTPException(status_code=400, detail="User is already registered")
        
        # Check if username is already taken (by another user)
        cursor.execute(
            "SELECT user_id FROM users WHERE username = %s AND wallet_address != %s",
            (username, wallet_address)
        )
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Username is already taken")
        
        # Check if email is already taken (if provided)
        if email:
            cursor.execute(
                "SELECT user_id FROM users WHERE email = %s AND wallet_address != %s",
                (email, wallet_address)
            )
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Email is already taken")
        
        # Update user with username and email
        cursor.execute(
            "UPDATE users SET username = %s, email = %s WHERE wallet_address = %s",
            (username, email, wallet_address)
        )
        connection.commit()
        
        # Generate JWT token
        payload = {
            "user_id": user["user_id"],
            "wallet_address": wallet_address,
            "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
            "iat": datetime.utcnow(),
        }
        
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        
        # Set JWT in httpOnly cookie
        response.set_cookie(
            key="auth_token",
            value=token,
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="lax",
            max_age=JWT_EXPIRATION_HOURS * 3600,
        )
        
        return {
            "success": True,
            "message": "Registration completed successfully",
            "user_id": user["user_id"],
            "wallet_address": wallet_address,
            "username": username,
            "email": email,
        }
        
    except HTTPException:
        raise
    except Error as e:
        if connection:
            connection.rollback()
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


@app.post("/auth/logout")
async def logout(response: Response):
    """
    Logout user by clearing the auth token cookie.
    """
    response.delete_cookie(
        key="auth_token",
        httponly=True,
        samesite="lax",
        path="/"
    )
    return {"success": True, "message": "Logged out successfully"}


@app.get("/auth/me")
async def get_current_user(request: Request):
    """
    Get current authenticated user from JWT token in cookie.
    """
    
    # Get auth token from cookie
    auth_token = request.cookies.get("auth_token")
    
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        # Decode and verify JWT
        payload = jwt.decode(auth_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        wallet_address = payload.get("wallet_address")
        
        if not user_id or not wallet_address:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Get user data from database
        connection = None
        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)
            
            cursor.execute(
                "SELECT user_id, wallet_address, username, email, role FROM users WHERE user_id = %s AND wallet_address = %s",
                (user_id, wallet_address)
            )
            user = cursor.fetchone()
            
            if not user:
                raise HTTPException(status_code=401, detail="User not found")
            
            return {
                "user_id": user["user_id"],
                "wallet_address": user["wallet_address"],
                "username": user.get("username"),
                "email": user.get("email"),
                "role": user.get("role", "USER"),
            }
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
                
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# Project endpoints
@app.get("/projects/categories")
async def get_categories():
    """Get all categories"""
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("SELECT id, name FROM categories ORDER BY name")
        categories = cursor.fetchall()
        
        return categories
    except Error as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


@app.get("/projects/registries")
async def get_registries():
    """Get all registries"""
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("SELECT id, name, website FROM registries ORDER BY name")
        registries = cursor.fetchall()
        
        return registries
    except Error as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


@app.post("/projects/create")
async def create_project(
    request: Request,
    category_id: int = Form(...),
    registry_id: int = Form(...),
    name: str = Form(...),
    description: str = Form(None),
    country: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    image: UploadFile = File(...)
):
    """Create a new project"""
    # Authenticate user
    user = get_authenticated_user(request)
    user_id = user["user_id"]
    
    # Validate image file
    if image.content_type not in ["image/jpeg", "image/jpg", "image/png", "image/webp"]:
        raise HTTPException(status_code=400, detail="Invalid image type. Only JPEG, PNG, and WebP are allowed.")
    
    # Check file size (5MB max)
    image.file.seek(0, 2)  # Seek to end
    file_size = image.file.tell()
    image.file.seek(0)  # Reset to beginning
    if file_size > 5 * 1024 * 1024:  # 5MB
        raise HTTPException(status_code=400, detail="Image file too large. Maximum size is 5MB.")
    
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Generate project identifier
        project_identifier = generate_project_identifier(category_id, connection)
        
        # Create uploads directory structure
        uploads_dir = os.path.join("uploads", "projects")
        os.makedirs(uploads_dir, exist_ok=True)
        
        # Save image file
        file_extension = os.path.splitext(image.filename)[1]
        # We'll use a temporary name first, then rename after getting project_id
        temp_filename = f"temp_{secrets.token_urlsafe(8)}{file_extension}"
        temp_filepath = os.path.join(uploads_dir, temp_filename)
        
        with open(temp_filepath, "wb") as buffer:
            content = await image.read()
            buffer.write(content)
        
        # Insert project into database
        # Use ST_GeomFromText for POINT type
        insert_query = """
            INSERT INTO projects (
                registry_id, category_id, project_identifier, name, issuer_id,
                description, country, location_geo, image_url
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, ST_GeomFromText(%s), %s
            )
        """
        
        point_wkt = f"POINT({longitude} {latitude})"
        image_url = ""  # Will update after getting project_id
        
        cursor.execute(
            insert_query,
            (registry_id, category_id, project_identifier, name, user_id,
             description, country, point_wkt, image_url)
        )
        connection.commit()
        
        # Get the inserted project_id
        project_id = cursor.lastrowid
        
        # Rename image file with project_id
        project_dir = os.path.join(uploads_dir, str(project_id))
        os.makedirs(project_dir, exist_ok=True)
        final_filename = f"{project_id}{file_extension}"
        final_filepath = os.path.join(project_dir, final_filename)
        os.rename(temp_filepath, final_filepath)
        
        # Update image_url in database
        image_url = f"/uploads/projects/{project_id}/{final_filename}"
        cursor.execute(
            "UPDATE projects SET image_url = %s WHERE id = %s",
            (image_url, project_id)
        )
        
        # Update user role to ISSUER if currently USER
        cursor.execute(
            "UPDATE users SET role = 'ISSUER' WHERE user_id = %s AND role = 'USER'",
            (user_id,)
        )
        connection.commit()
        
        # Fetch created project with category and registry names
        cursor.execute("""
            SELECT p.id, p.project_identifier, p.name, p.description, p.country, p.image_url,
                   c.name as category_name, r.name as registry_name
            FROM projects p
            LEFT JOIN categories c ON p.category_id = c.id
            LEFT JOIN registries r ON p.registry_id = r.id
            WHERE p.id = %s
        """, (project_id,))
        project = cursor.fetchone()
        
        return {
            "success": True,
            "message": "Project created successfully",
            "project": project
        }
        
    except HTTPException:
        raise
    except Error as e:
        if connection:
            connection.rollback()
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


@app.get("/projects/my-projects")
async def get_my_projects(request: Request):
    """Get all projects for the current authenticated user"""
    user = get_authenticated_user(request)
    user_id = user["user_id"]
    
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                p.id, 
                p.project_identifier, 
                p.name, 
                p.description, 
                p.country, 
                p.image_url,
                c.name as category_name, 
                r.name as registry_name,
                MIN(a.price_per_ton) as min_price,
                MAX(a.price_per_ton) as max_price,
                COUNT(a.id) as asset_count
            FROM projects p
            LEFT JOIN categories c ON p.category_id = c.id
            LEFT JOIN registries r ON p.registry_id = r.id
            LEFT JOIN assets a ON p.id = a.project_id AND a.is_frozen = FALSE
            WHERE p.issuer_id = %s
            GROUP BY p.id, p.project_identifier, p.name, p.description, p.country, p.image_url,
                     c.name, r.name
            ORDER BY p.id DESC
        """, (user_id,))
        
        projects = cursor.fetchall()
        
        return projects
        
    except Error as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


@app.get("/projects")
async def get_all_projects(request: Request):
    """Get all projects (for marketplace)"""
    get_authenticated_user(request)  # Just check authentication
    
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                p.id, 
                p.project_identifier, 
                p.name, 
                p.description, 
                p.country, 
                p.image_url,
                c.name as category_name, 
                r.name as registry_name, 
                p.issuer_id,
                MIN(a.price_per_ton) as min_price,
                MAX(a.price_per_ton) as max_price,
                COUNT(a.id) as asset_count
            FROM projects p
            LEFT JOIN categories c ON p.category_id = c.id
            LEFT JOIN registries r ON p.registry_id = r.id
            LEFT JOIN assets a ON p.id = a.project_id AND a.is_frozen = FALSE
            GROUP BY p.id, p.project_identifier, p.name, p.description, p.country, p.image_url,
                     c.name, r.name, p.issuer_id
            ORDER BY p.id DESC
        """)
        
        projects = cursor.fetchall()
        
        return projects
        
    except Error as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


@app.get("/projects/{project_id}")
async def get_project(request: Request, project_id: int):
    """Get a single project by ID with its assets"""
    get_authenticated_user(request)  # Just check authentication
    
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Get project details with latitude and longitude from POINT geometry
        cursor.execute("""
            SELECT p.id, p.project_identifier, p.name, p.description, p.country, p.image_url,
                   p.issuer_id, c.name as category_name, r.name as registry_name,
                   u.username as issuer_username,
                   ST_X(p.location_geo) as longitude,
                   ST_Y(p.location_geo) as latitude
            FROM projects p
            LEFT JOIN categories c ON p.category_id = c.id
            LEFT JOIN registries r ON p.registry_id = r.id
            LEFT JOIN users u ON p.issuer_id = u.user_id
            WHERE p.id = %s
        """, (project_id,))
        
        project = cursor.fetchone()
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Get assets for this project
        cursor.execute("""
            SELECT 
                a.id,
                a.project_id,
                a.vintage_year,
                a.asset_code,
                a.asset_issuer_address,
                a.contract_id,
                a.is_frozen,
                a.total_supply,
                a.price_per_ton,
                a.origin_request_id,
                a.created_at
            FROM assets a
            WHERE a.project_id = %s
            ORDER BY a.vintage_year DESC, a.created_at DESC
        """, (project_id,))
        
        assets = cursor.fetchall()
        
        project["assets"] = assets
        
        return project
        
    except HTTPException:
        raise
    except Error as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


# Tokenization endpoints
@app.post("/tokenization/create")
async def create_tokenization_request(
    request: Request,
    project_id: int = Form(...),
    vintage_year: int = Form(...),
    quantity: str = Form(...),
    price_per_ton: str = Form(None),
    serial_number_start: str = Form(None),
    serial_number_end: str = Form(None),
    proof_document: UploadFile = File(...)
):
    """Create a new tokenization request"""
    # Authenticate user
    user = get_authenticated_user(request)
    user_id = user["user_id"]
    
    # Validate that user is an ISSUER
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute(
            "SELECT role FROM users WHERE user_id = %s",
            (user_id,)
        )
        user_data = cursor.fetchone()
        
        if not user_data or user_data.get("role") != "ISSUER":
            raise HTTPException(status_code=403, detail="Only issuers can create tokenization requests")
        
        # Validate that project belongs to the user
        cursor.execute(
            "SELECT id FROM projects WHERE id = %s AND issuer_id = %s",
            (project_id, user_id)
        )
        project = cursor.fetchone()
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found or you don't have permission to use it")
        
        # Validate PDF file
        if proof_document.content_type != "application/pdf":
            raise HTTPException(status_code=400, detail="Invalid file type. Only PDF files are allowed.")
        
        # Check file size (10MB max)
        proof_document.file.seek(0, 2)  # Seek to end
        file_size = proof_document.file.tell()
        proof_document.file.seek(0)  # Reset to beginning
        if file_size > 10 * 1024 * 1024:  # 10MB
            raise HTTPException(status_code=400, detail="Document file too large. Maximum size is 10MB.")
        
        # Validate quantity
        try:
            quantity_decimal = float(quantity)
            if quantity_decimal <= 0:
                raise HTTPException(status_code=400, detail="Quantity must be greater than 0")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid quantity format")
        
        # Validate price_per_ton if provided
        price_per_ton_decimal = None
        if price_per_ton:
            try:
                price_per_ton_decimal = float(price_per_ton)
                if price_per_ton_decimal <= 0:
                    raise HTTPException(status_code=400, detail="Price per ton must be greater than 0")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid price per ton format")
        
        # Validate vintage year
        current_year = datetime.now().year
        if vintage_year < 2000 or vintage_year > current_year:
            raise HTTPException(status_code=400, detail=f"Vintage year must be between 2000 and {current_year}")
        
        # Create uploads directory structure
        uploads_dir = os.path.join("uploads", "documents")
        os.makedirs(uploads_dir, exist_ok=True)
        
        # Save document file
        file_extension = os.path.splitext(proof_document.filename)[1] or ".pdf"
        # Use a temporary name first, then rename after getting request_id
        temp_filename = f"temp_{secrets.token_urlsafe(8)}{file_extension}"
        temp_filepath = os.path.join(uploads_dir, temp_filename)
        
        with open(temp_filepath, "wb") as buffer:
            content = await proof_document.read()
            buffer.write(content)
        
        # Insert tokenization request into database
        proof_document_url = ""  # Will update after getting request_id
        
        insert_query = """
            INSERT INTO tokenization_requests (
                issuer_id, project_id, vintage_year, quantity, price_per_ton,
                serial_number_start, serial_number_end, proof_document_url
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        
        cursor.execute(
            insert_query,
            (user_id, project_id, vintage_year, quantity_decimal, price_per_ton_decimal,
             serial_number_start if serial_number_start else None,
             serial_number_end if serial_number_end else None,
             proof_document_url)
        )
        connection.commit()
        
        # Get the inserted request_id
        request_id = cursor.lastrowid
        
        # Rename document file with request_id
        final_filename = f"{request_id}{file_extension}"
        final_filepath = os.path.join(uploads_dir, final_filename)
        os.rename(temp_filepath, final_filepath)
        
        # Update proof_document_url in database
        proof_document_url = f"/uploads/documents/{final_filename}"
        cursor.execute(
            "UPDATE tokenization_requests SET proof_document_url = %s WHERE id = %s",
            (proof_document_url, request_id)
        )
        connection.commit()
        
        # Fetch created request
        cursor.execute("""
            SELECT tr.id, tr.vintage_year, tr.quantity, tr.status,
                   tr.serial_number_start, tr.serial_number_end,
                   p.project_identifier, p.name as project_name
            FROM tokenization_requests tr
            LEFT JOIN projects p ON tr.project_id = p.id
            WHERE tr.id = %s
        """, (request_id,))
        tokenization_request = cursor.fetchone()
        
        return {
            "success": True,
            "message": "Tokenization request created successfully",
            "request": tokenization_request
        }
        
    except HTTPException:
        raise
    except Error as e:
        if connection:
            connection.rollback()
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


# Admin endpoints
def check_admin_role(request: Request):
    """Check if user is authenticated and has ADMIN role"""
    user = get_authenticated_user(request)
    user_id = user["user_id"]
    
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute(
            "SELECT role FROM users WHERE user_id = %s",
            (user_id,)
        )
        user_data = cursor.fetchone()
        
        if not user_data or user_data.get("role") != "ADMIN":
            raise HTTPException(status_code=403, detail="Admin access required")
        
        return user
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


@app.get("/admin/tokenization-requests")
async def get_pending_tokenization_requests(request: Request):
    """Get all pending tokenization requests (admin only)"""
    check_admin_role(request)
    
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                tr.id,
                tr.issuer_id,
                tr.project_id,
                tr.vintage_year,
                tr.quantity,
                tr.serial_number_start,
                tr.serial_number_end,
                tr.proof_document_url,
                tr.status,
                tr.admin_note,
                p.project_identifier,
                p.name as project_name,
                u.username as issuer_username,
                u.wallet_address as issuer_wallet
            FROM tokenization_requests tr
            LEFT JOIN projects p ON tr.project_id = p.id
            LEFT JOIN users u ON tr.issuer_id = u.user_id
            WHERE tr.status = 'PENDING'
            ORDER BY tr.id DESC
        """)
        
        requests = cursor.fetchall()
        
        return requests
        
    except HTTPException:
        raise
    except Error as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


class ApproveRequestModel(BaseModel):
    request_id: int
    admin_note: Optional[str] = None


@app.post("/admin/tokenization-requests/approve")
async def approve_tokenization_request(request: Request, approve_data: ApproveRequestModel):
    """Approve a tokenization request and deploy the contract (admin only)"""
    admin_user = check_admin_role(request)
    
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Get the tokenization request
        cursor.execute("""
            SELECT 
                tr.*,
                p.project_identifier,
                p.name as project_name,
                u.wallet_address as issuer_wallet
            FROM tokenization_requests tr
            LEFT JOIN projects p ON tr.project_id = p.id
            LEFT JOIN users u ON tr.issuer_id = u.user_id
            WHERE tr.id = %s AND tr.status = 'PENDING'
        """, (approve_data.request_id,))
        
        tokenization_request = cursor.fetchone()
        
        if not tokenization_request:
            raise HTTPException(status_code=404, detail="Tokenization request not found or already processed")
        
        # Import soroban service
        import sys
        import os
        sys.path.append(os.path.dirname(__file__))
        from soroban_service import SorobanService
        
        try:
            # Initialize soroban service
            soroban_service = SorobanService()
            
            # Deploy contract and register in carbon controller
            project_identifier = tokenization_request["project_identifier"]
            vintage_year = tokenization_request["vintage_year"]
            project_id = tokenization_request["project_id"]
            issuer_wallet = tokenization_request["issuer_wallet"]
            quantity = tokenization_request["quantity"]  # Get quantity before using it
            
            print(f"Deploying contract for project {project_identifier}, vintage {vintage_year}")
            
            contract_address = soroban_service.deploy_and_register(
                project_identifier=project_identifier,
                vintage_year=vintage_year,
                project_id=project_id,
                admin_address=admin_user["wallet_address"],  # Admin is the contract admin
                issuer_address=issuer_wallet,  # Issuer receives the minted tokens
                quantity=float(quantity),  # Amount to mint
                decimal=7
            )
            
            # Generate asset_code: project_identifier-vintage_year
            # Replace hyphens with underscores for Soroban Symbol compatibility
            # Symbol type only accepts alphanumeric and underscore characters
            asset_code = f"{project_identifier}-{vintage_year}".replace("-", "_")
            
            # Get price_per_ton from tokenization request if available
            price_per_ton_value = tokenization_request.get("price_per_ton")
            
            # Create asset record in assets table
            cursor.execute("""
                INSERT INTO assets (
                    project_id,
                    vintage_year,
                    asset_code,
                    asset_issuer_address,
                    contract_id,
                    is_frozen,
                    total_supply,
                    price_per_ton,
                    origin_request_id
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, (
                project_id,
                vintage_year,
                asset_code,
                issuer_wallet,  # Issuer is the owner who receives the minted tokens
                contract_address,
                False,  # is_frozen
                quantity,  # total_supply
                price_per_ton_value,  # price_per_ton (can be None)
                approve_data.request_id  # origin_request_id
            ))
            
            # Update tokenization request status to MINTED and store contract address
            # Note: If contract_address column doesn't exist, you may need to add it:
            # ALTER TABLE tokenization_requests ADD COLUMN contract_address VARCHAR(255) NULL;
            try:
                cursor.execute("""
                    UPDATE tokenization_requests 
                    SET status = 'MINTED',
                        admin_note = %s,
                        contract_address = %s
                    WHERE id = %s
                """, (approve_data.admin_note, contract_address, approve_data.request_id))
            except Error as e:
                # If contract_address column doesn't exist, update without it
                if "contract_address" in str(e).lower():
                    cursor.execute("""
                        UPDATE tokenization_requests 
                        SET status = 'MINTED',
                            admin_note = %s
                        WHERE id = %s
                    """, (f"{approve_data.admin_note or ''}\nContract: {contract_address}", approve_data.request_id))
                else:
                    raise
            
            connection.commit()
            
            # Step 4: Auto-approve admin to transfer tokens on behalf of issuer
            # Since issuer is always admin in this system, this should always work
            print(f"[APPROVE] ===== STEP 4: AUTO-APPROVING ADMIN ======")
            print(f"[APPROVE] Issuer wallet: {issuer_wallet}")
            print(f"[APPROVE] Admin wallet: {admin_user['wallet_address']}")
            print(f"[APPROVE] Contract address: {contract_address}")
            print(f"[APPROVE] Quantity: {quantity}")
            
            # Verify issuer is admin
            if issuer_wallet != admin_user['wallet_address']:
                print(f"[APPROVE] WARNING: Issuer ({issuer_wallet}) is not admin ({admin_user['wallet_address']})")
                print(f"[APPROVE] This may cause approval to fail. Proceeding anyway...")
            
            try:
                # Calculate total supply in smallest units (7 decimals)
                total_supply_stroops = int(float(quantity) * 10000000)
                approval_amount = total_supply_stroops * 100  # Approve 100x the supply for safety
                
                print(f"[APPROVE] Total supply (stroops): {total_supply_stroops}")
                print(f"[APPROVE] Approval amount (stroops): {approval_amount}")
                
                # Approve admin for a very large amount
                # This allows admin to transfer any amount on behalf of the issuer
                # Since issuer is always admin, this will use admin's secret key to sign
                print(f"[APPROVE] Calling approve_admin_for_token...")
                approval_result = soroban_service.approve_admin_for_token(
                    token_contract_id=contract_address,
                    owner_address=issuer_wallet,  # This should be the same as admin
                    amount_i128=approval_amount,
                    expiration_ledger=None  # Will be calculated automatically (1 year from current ledger)
                )
                
                if approval_result:
                    print(f"[APPROVE] ✓✓✓ Admin auto-approved successfully for token transfers ✓✓✓")
                    print(f"[APPROVE] Admin can now transfer tokens on behalf of issuer")
                else:
                    print(f"[APPROVE] WARNING: Approval returned False")
                    raise Exception("Approval returned False")
                    
            except Exception as e:
                print(f"[APPROVE] ===== APPROVAL FAILED ======")
                print(f"[APPROVE] ERROR: Failed to auto-approve admin: {type(e).__name__}: {str(e)}")
                print(f"[APPROVE] This is CRITICAL - token transfers will fail without approval!")
                print(f"[APPROVE] Contract is deployed and tokens are minted, but purchases will fail.")
                import traceback
                traceback.print_exc()
                # Don't fail the whole process, but this is a serious issue
                print(f"[APPROVE] ===== APPROVAL FAILED - CONTINUING ANYWAY ======")
            
            return {
                "success": True,
                "message": "Tokenization request approved and contract deployed",
                "contract_address": contract_address,
                "request_id": approve_data.request_id
            }
            
        except Exception as e:
            # Update status to APPROVED but note the error
            error_note = f"Deployment failed: {str(e)}"
            if approve_data.admin_note:
                error_note = f"{approve_data.admin_note}\n{error_note}"
            
            cursor.execute("""
                UPDATE tokenization_requests 
                SET status = 'APPROVED',
                    admin_note = %s
                WHERE id = %s
            """, (error_note, approve_data.request_id))
            connection.commit()
            
            raise HTTPException(status_code=500, detail=f"Contract deployment failed: {str(e)}")
        
    except HTTPException:
        raise
    except Error as e:
        if connection:
            connection.rollback()
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


class RejectRequestModel(BaseModel):
    request_id: int
    admin_note: str


@app.post("/admin/tokenization-requests/reject")
async def reject_tokenization_request(request: Request, reject_data: RejectRequestModel):
    """Reject a tokenization request (admin only)"""
    check_admin_role(request)
    
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Update status to REJECTED
        cursor.execute("""
            UPDATE tokenization_requests 
            SET status = 'REJECTED',
                admin_note = %s
            WHERE id = %s AND status = 'PENDING'
        """, (reject_data.admin_note, reject_data.request_id))
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Tokenization request not found or already processed")
        
        connection.commit()
        
        return {
            "success": True,
            "message": "Tokenization request rejected",
            "request_id": reject_data.request_id
        }
        
    except HTTPException:
        raise
    except Error as e:
        if connection:
            connection.rollback()
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


# Assets endpoints
@app.get("/assets")
async def get_assets(request: Request):
    """Get all assets (authenticated users)"""
    get_authenticated_user(request)  # Just check authentication
    
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                a.id,
                a.project_id,
                a.vintage_year,
                a.asset_code,
                a.asset_issuer_address,
                a.contract_id,
                a.is_frozen,
                a.total_supply,
                a.origin_request_id,
                a.created_at,
                p.project_identifier,
                p.name as project_name
            FROM assets a
            LEFT JOIN projects p ON a.project_id = p.id
            ORDER BY a.created_at DESC
        """)
        
        assets = cursor.fetchall()
        
        return assets
        
    except Error as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


@app.get("/assets/{asset_id}")
async def get_asset(request: Request, asset_id: int):
    """Get a specific asset by ID (authenticated users)"""
    get_authenticated_user(request)  # Just check authentication
    
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                a.id,
                a.project_id,
                a.vintage_year,
                a.asset_code,
                a.asset_issuer_address,
                a.contract_id,
                a.is_frozen,
                a.total_supply,
                a.price_per_ton,
                a.origin_request_id,
                a.created_at,
                p.project_identifier,
                p.name as project_name
            FROM assets a
            LEFT JOIN projects p ON a.project_id = p.id
            WHERE a.id = %s
        """, (asset_id,))
        
        asset = cursor.fetchone()
        
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        
        return asset
        
    except HTTPException:
        raise
    except Error as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


class PurchaseAssetRequest(BaseModel):
    asset_id: int
    amount_xlm: float  # Amount in XLM to pay
    buyer_address: str  # Stellar address of the buyer


class AtomicSwapRequest(BaseModel):
    asset_id: int
    amount_xlm: float  # Amount in XLM to pay
    buyer_address: str  # Stellar address of the buyer


@app.post("/assets/build-payment-xdr")
async def build_payment_xdr(request: Request, purchase_data: PurchaseAssetRequest):
    """Build a payment transaction XDR for Freighter to sign"""
    print(f"[BUILD-XDR] Request received: asset_id={purchase_data.asset_id}, amount={purchase_data.amount_xlm}")
    
    user = get_authenticated_user(request)
    user_wallet = user["wallet_address"]
    print(f"[BUILD-XDR] User wallet: {user_wallet}")
    
    if purchase_data.buyer_address != user_wallet:
        print(f"[BUILD-XDR] ERROR: Buyer address mismatch")
        raise HTTPException(status_code=403, detail="Buyer address must match authenticated user")
    
    if purchase_data.amount_xlm <= 0:
        print(f"[BUILD-XDR] ERROR: Invalid amount")
        raise HTTPException(status_code=400, detail="Amount must be greater than 0")
    
    connection = None
    try:
        print(f"[BUILD-XDR] Connecting to database...")
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT a.asset_issuer_address, a.asset_code, a.contract_id
            FROM assets a
            WHERE a.id = %s
        """, (purchase_data.asset_id,))
        
        asset = cursor.fetchone()
        if not asset:
            print(f"[BUILD-XDR] ERROR: Asset not found: {purchase_data.asset_id}")
            raise HTTPException(status_code=404, detail="Asset not found")
        
        print(f"[BUILD-XDR] Asset found: {asset['asset_code']}, seller: {asset['asset_issuer_address']}")
        
        # Fetch account sequence from Horizon using Stellar SDK
        from stellar_sdk import Server, TransactionBuilder, Network, Asset, Payment
        from stellar_sdk.memo import TextMemo
        
        try:
            print(f"[BUILD-XDR] Fetching account from Horizon: {user_wallet}")
            # Use testnet server
            server = Server(horizon_url="https://horizon-testnet.stellar.org")
            source_account = server.load_account(user_wallet)
            print(f"[BUILD-XDR] Account loaded. Sequence: {source_account.sequence}")
        except Exception as e:
            print(f"[BUILD-XDR] ERROR: Failed to fetch account: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch account from Stellar network: {str(e)}")
        
        # Convert XLM to stroops
        amount_stroops = int(purchase_data.amount_xlm * 10000000)
        print(f"[BUILD-XDR] Amount: {purchase_data.amount_xlm} XLM = {amount_stroops} stroops")
        
        # Build transaction
        network_passphrase = Network.TESTNET_NETWORK_PASSPHRASE
        base_fee = 100  # Standard fee in stroops
        
        print(f"[BUILD-XDR] Building transaction...")
        transaction = (
            TransactionBuilder(
                source_account=source_account,
                network_passphrase=network_passphrase,
                base_fee=base_fee,
            )
            .add_operation(
                Payment(
                    destination=asset["asset_issuer_address"],
                    asset=Asset.native(),
                    amount=str(amount_stroops),
                )
            )
            .add_memo(TextMemo(f"Purchase {asset['asset_code']}"[:28]))  # Max 28 bytes
            .set_timeout(300)  # 5 minutes
            .build()
        )
        
        # Convert to XDR
        transaction_xdr = transaction.to_xdr()
        print(f"[BUILD-XDR] Transaction XDR built successfully. Length: {len(transaction_xdr)}")
        
        return {
            "success": True,
            "transaction_xdr": transaction_xdr,
            "network": "testnet",
            "amount_xlm": purchase_data.amount_xlm,
            "destination": asset["asset_issuer_address"],
            "memo": f"Purchase {asset['asset_code']}",
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[BUILD-XDR] ERROR: Exception occurred: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to build transaction: {str(e)}")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            print(f"[BUILD-XDR] Database connection closed")


@app.post("/assets/purchase")
async def purchase_asset(request: Request, purchase_data: PurchaseAssetRequest):
    """Purchase assets with XLM payment"""
    print(f"[PURCHASE] Request received: asset_id={purchase_data.asset_id}, amount={purchase_data.amount_xlm}")
    
    user = get_authenticated_user(request)
    user_id = user["user_id"]
    user_wallet = user["wallet_address"]
    print(f"[PURCHASE] User: {user_id}, wallet: {user_wallet}")
    
    # Verify that buyer_address matches authenticated user
    if purchase_data.buyer_address != user_wallet:
        print(f"[PURCHASE] ERROR: Buyer address mismatch")
        raise HTTPException(status_code=403, detail="Buyer address must match authenticated user")
    
    # Validate amount
    if purchase_data.amount_xlm <= 0:
        print(f"[PURCHASE] ERROR: Invalid amount")
        raise HTTPException(status_code=400, detail="Amount must be greater than 0")
    
    connection = None
    try:
        print(f"[PURCHASE] Connecting to database...")
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Get asset details
        cursor.execute("""
            SELECT 
                a.id,
                a.project_id,
                a.asset_code,
                a.contract_id,
                a.asset_issuer_address,
                a.price_per_ton,
                a.total_supply,
                a.is_frozen,
                p.issuer_id,
                p.project_identifier,
                p.name as project_name
            FROM assets a
            LEFT JOIN projects p ON a.project_id = p.id
            WHERE a.id = %s
        """, (purchase_data.asset_id,))
        
        asset = cursor.fetchone()
        
        if not asset:
            print(f"[PURCHASE] ERROR: Asset not found: {purchase_data.asset_id}")
            raise HTTPException(status_code=404, detail="Asset not found")
        
        print(f"[PURCHASE] Asset found: {asset['asset_code']}, issuer_id: {asset['issuer_id']}")
        
        if asset["is_frozen"]:
            print(f"[PURCHASE] ERROR: Asset is frozen")
            raise HTTPException(status_code=400, detail="Asset is frozen and cannot be purchased")
        
        # Check if user is trying to buy their own asset
        if asset["issuer_id"] == user_id:
            print(f"[PURCHASE] ERROR: User trying to buy own asset")
            raise HTTPException(status_code=400, detail="You cannot purchase assets from your own project")
        
        # Calculate how many tokens can be purchased
        # If price_per_ton is set, use it; otherwise, allow any amount
        # Convert decimal.Decimal to float for calculation
        price_per_ton = float(asset["price_per_ton"]) if asset["price_per_ton"] else None
        if price_per_ton and price_per_ton > 0:
            tokens_purchased = purchase_data.amount_xlm / price_per_ton
            print(f"[PURCHASE] Price per ton: {price_per_ton}, tokens: {tokens_purchased}")
        else:
            # If no price set, we'll use a 1:1 ratio (1 XLM = 1 token)
            # In production, you might want to set a default price
            tokens_purchased = purchase_data.amount_xlm
            print(f"[PURCHASE] No price set, using 1:1 ratio, tokens: {tokens_purchased}")
        
        print(f"[PURCHASE] Purchase validated successfully")
        
        # Store purchase intent in database for tracking
        # In a production system, you might want to create a purchases table
        # For now, we'll return the transaction details
        
        return {
            "success": True,
            "message": "Purchase validated. Ready for transaction.",
            "asset": {
                "id": asset["id"],
                "asset_code": asset["asset_code"],
                "contract_id": asset["contract_id"],
                "project_name": asset["project_name"],
            },
            "purchase": {
                "amount_xlm": purchase_data.amount_xlm,
                "amount_stroops": int(purchase_data.amount_xlm * 10000000),  # Convert to stroops
                "tokens_purchased": tokens_purchased,
                "tokens_purchased_stroops": int(tokens_purchased * 10000000),  # 7 decimals
                "buyer_address": purchase_data.buyer_address,
                "seller_address": asset["asset_issuer_address"],
            },
            "transaction": {
                "type": "payment",
                "network": "testnet",
                "memo": f"Purchase asset {asset['asset_code']} - ID: {asset['id']}",
            }
        }
        
    except HTTPException:
        raise
    except Error as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


@app.post("/assets/atomic-swap")
async def atomic_swap(request: Request, swap_data: AtomicSwapRequest):
    """
    Perform atomic swap: Admin transfers XLM from buyer to seller and tokens from seller to buyer.
    This requires proper authorization from both parties.
    """
    print(f"[ATOMIC-SWAP] ===== SWAP REQUEST RECEIVED ======")
    print(f"[ATOMIC-SWAP] Asset ID: {swap_data.asset_id}")
    print(f"[ATOMIC-SWAP] Amount XLM: {swap_data.amount_xlm}")
    print(f"[ATOMIC-SWAP] Buyer Address: {swap_data.buyer_address}")
    
    # Verify user is authenticated
    user = get_authenticated_user(request)
    user_wallet = user["wallet_address"]
    print(f"[ATOMIC-SWAP] Authenticated user: {user['user_id']}, wallet: {user_wallet}")
    
    if swap_data.buyer_address != user_wallet:
        print(f"[ATOMIC-SWAP] ERROR: Buyer address mismatch")
        raise HTTPException(status_code=403, detail="Buyer address must match authenticated user")
    
    if swap_data.amount_xlm <= 0:
        print(f"[ATOMIC-SWAP] ERROR: Invalid amount")
        raise HTTPException(status_code=400, detail="Amount must be greater than 0")
    
    connection = None
    try:
        print(f"[ATOMIC-SWAP] Step 1: Fetching asset and project data...")
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Get asset and project details
        cursor.execute("""
            SELECT 
                a.id,
                a.project_id,
                a.asset_code,
                a.contract_id,
                a.asset_issuer_address,
                a.price_per_ton,
                a.total_supply,
                a.is_frozen,
                p.issuer_id,
                p.project_identifier,
                p.name as project_name
            FROM assets a
            LEFT JOIN projects p ON a.project_id = p.id
            WHERE a.id = %s
        """, (swap_data.asset_id,))
        
        asset = cursor.fetchone()
        
        if not asset:
            print(f"[ATOMIC-SWAP] ERROR: Asset not found")
            raise HTTPException(status_code=404, detail="Asset not found")
        
        print(f"[ATOMIC-SWAP] Asset found: {asset['asset_code']}, contract: {asset['contract_id']}")
        print(f"[ATOMIC-SWAP] Seller address: {asset['asset_issuer_address']}")
        print(f"[ATOMIC-SWAP] Buyer address: {swap_data.buyer_address}")
        
        if asset["is_frozen"]:
            print(f"[ATOMIC-SWAP] ERROR: Asset is frozen")
            raise HTTPException(status_code=400, detail="Asset is frozen and cannot be purchased")
        
        if asset["issuer_id"] == user["user_id"]:
            print(f"[ATOMIC-SWAP] ERROR: User trying to buy own asset")
            raise HTTPException(status_code=400, detail="You cannot purchase assets from your own project")
        
        # Calculate tokens to purchase
        # Convert decimal.Decimal to float for calculation
        price_per_ton = float(asset["price_per_ton"]) if asset["price_per_ton"] else None
        if price_per_ton and price_per_ton > 0:
            tokens_purchased = swap_data.amount_xlm / price_per_ton
            print(f"[ATOMIC-SWAP] Price per ton: {price_per_ton}, tokens: {tokens_purchased}")
        else:
            tokens_purchased = swap_data.amount_xlm
            print(f"[ATOMIC-SWAP] No price set, using 1:1 ratio, tokens: {tokens_purchased}")
        
        print(f"[ATOMIC-SWAP] Step 2: Calculated tokens: {tokens_purchased} tons")
        print(f"[ATOMIC-SWAP] Price per ton: {asset['price_per_ton']}")
        
        # Convert amounts
        amount_xlm_stroops = int(swap_data.amount_xlm * 10000000)
        tokens_stroops = int(tokens_purchased * 10000000)  # 7 decimals
        
        print(f"[ATOMIC-SWAP] Amount in stroops: {amount_xlm_stroops}")
        print(f"[ATOMIC-SWAP] Tokens in stroops: {tokens_stroops}")
        
        # Import Stellar SDK and Soroban service
        from stellar_sdk import Server, Keypair, Network, TransactionBuilder, Payment, Asset
        from stellar_sdk.memo import TextMemo
        from soroban_service import SorobanService
        
        print(f"[ATOMIC-SWAP] Step 3: Initializing services...")
        soroban_service = SorobanService()
        
        # Get admin keypair
        admin_keypair = Keypair.from_secret(soroban_service.admin_secret)
        admin_address = admin_keypair.public_key
        print(f"[ATOMIC-SWAP] Admin address: {admin_address}")
        
        # Step 4: Get XLM from buyer (requires buyer to sign)
        print(f"[ATOMIC-SWAP] Step 4: Building XLM transfer from buyer to admin...")
        server = Server(horizon_url="https://horizon-testnet.stellar.org")
        
        try:
            buyer_account = server.load_account(swap_data.buyer_address)
            print(f"[ATOMIC-SWAP] Buyer account loaded. Sequence: {buyer_account.sequence}")
        except Exception as e:
            print(f"[ATOMIC-SWAP] ERROR: Failed to load buyer account: {e}")
            raise HTTPException(status_code=400, detail=f"Buyer account not found on network: {str(e)}")
        
        # Build transaction to transfer XLM from buyer to admin (escrow)
        # Note: This requires buyer signature, so we'll return XDR for frontend to sign
        print(f"[ATOMIC-SWAP] Step 5: Building buyer payment transaction...")
        buyer_payment_tx = (
            TransactionBuilder(
                source_account=buyer_account,
                network_passphrase=Network.TESTNET_NETWORK_PASSPHRASE,
                base_fee=100,
            )
            .append_operation(
                Payment(
                    destination=admin_address,  # Admin receives XLM first
                    asset=Asset.native(),
                    amount=str(amount_xlm_stroops),
                )
            )
            .add_memo(TextMemo(f"Buy {asset['asset_code']}"[:28]))  # Max 28 bytes
            .set_timeout(300)
            .build()
        )
        
        buyer_payment_xdr = buyer_payment_tx.to_xdr()
        print(f"[ATOMIC-SWAP] Buyer payment XDR built. Length: {len(buyer_payment_xdr)}")
        
        # Step 5: Prepare for token transfer
        print(f"[ATOMIC-SWAP] Step 6: Preparing token transfer details...")
        print(f"[ATOMIC-SWAP] Token contract: {asset['contract_id']}")
        print(f"[ATOMIC-SWAP] Seller: {asset['asset_issuer_address']}")
        print(f"[ATOMIC-SWAP] Buyer: {swap_data.buyer_address}")
        print(f"[ATOMIC-SWAP] Tokens to transfer: {tokens_stroops} (smallest units)")
        
        # Return XDR for buyer to sign
        # After buyer signs and XLM is received, we'll need a separate endpoint to complete the swap
        print(f"[ATOMIC-SWAP] Step 7: Preparing response...")
        return {
            "success": True,
            "message": "Atomic swap prepared. Sign the XLM payment transaction.",
            "buyer_payment_xdr": buyer_payment_xdr,
            "swap_details": {
                "asset_code": asset["asset_code"],
                "asset_id": asset["id"],
                "amount_xlm": swap_data.amount_xlm,
                "amount_stroops": amount_xlm_stroops,
                "tokens_purchased": tokens_purchased,
                "tokens_stroops": tokens_stroops,
                "buyer_address": swap_data.buyer_address,
                "seller_address": asset["asset_issuer_address"],
                "admin_address": admin_address,
                "token_contract": asset["contract_id"],
            },
            "next_steps": [
                "1. Sign the buyer_payment_xdr transaction with Freighter",
                "2. After XLM payment is confirmed, call /assets/complete-swap to transfer tokens",
                "3. Admin will transfer tokens to buyer and XLM to seller"
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ATOMIC-SWAP] ERROR: Exception occurred: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Atomic swap failed: {str(e)}")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            print(f"[ATOMIC-SWAP] Database connection closed")


@app.post("/assets/complete-swap")
async def complete_swap(request: Request, swap_data: AtomicSwapRequest):
    """
    Complete the atomic swap after XLM payment is confirmed.
    Admin transfers tokens from seller to buyer and XLM from admin to seller.
    """
    print(f"[COMPLETE-SWAP] ===== COMPLETE SWAP REQUEST RECEIVED ======")
    print(f"[COMPLETE-SWAP] Asset ID: {swap_data.asset_id}")
    print(f"[COMPLETE-SWAP] Amount XLM: {swap_data.amount_xlm}")
    print(f"[COMPLETE-SWAP] Buyer Address: {swap_data.buyer_address}")
    print(f"[COMPLETE-SWAP] Request body: {swap_data}")
    
    user = get_authenticated_user(request)
    if swap_data.buyer_address != user["wallet_address"]:
        print(f"[COMPLETE-SWAP] ERROR: Buyer address mismatch")
        raise HTTPException(status_code=403, detail="Buyer address must match authenticated user")
    
    connection = None
    try:
        print(f"[COMPLETE-SWAP] Step 1: Fetching asset data...")
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT a.asset_code, a.contract_id, a.asset_issuer_address, a.price_per_ton, p.project_identifier, a.vintage_year
            FROM assets a
            LEFT JOIN projects p ON a.project_id = p.id
            WHERE a.id = %s
        """, (swap_data.asset_id,))
        
        asset = cursor.fetchone()
        if not asset:
            print(f"[COMPLETE-SWAP] ERROR: Asset not found")
            raise HTTPException(status_code=404, detail="Asset not found")
        
        print(f"[COMPLETE-SWAP] Asset: {asset['asset_code']}, Contract: {asset['contract_id']}")
        
        # Calculate tokens
        # Convert decimal.Decimal to float for calculation
        price_per_ton = float(asset["price_per_ton"]) if asset["price_per_ton"] else None
        if price_per_ton and price_per_ton > 0:
            tokens_purchased = swap_data.amount_xlm / price_per_ton
            print(f"[COMPLETE-SWAP] Price per ton: {price_per_ton}, tokens: {tokens_purchased}")
        else:
            tokens_purchased = swap_data.amount_xlm
            print(f"[COMPLETE-SWAP] No price set, using 1:1 ratio, tokens: {tokens_purchased}")
        
        tokens_stroops = int(tokens_purchased * 10000000)
        amount_xlm_stroops = int(swap_data.amount_xlm * 10000000)
        
        print(f"[COMPLETE-SWAP] Step 2: Tokens to transfer: {tokens_stroops}")
        print(f"[COMPLETE-SWAP] XLM to transfer to seller: {amount_xlm_stroops}")
        
        # Import services
        from stellar_sdk import Server, Keypair, Network, TransactionBuilder, Payment, Asset
        from stellar_sdk.memo import TextMemo
        from soroban_service import SorobanService
        
        soroban_service = SorobanService()
        admin_keypair = Keypair.from_secret(soroban_service.admin_secret)
        admin_address = admin_keypair.public_key
        
        print(f"[COMPLETE-SWAP] Step 3: Admin address: {admin_address}")
        
        # Step 3: Mint tokens directly to buyer
        print(f"[COMPLETE-SWAP] Step 4: Minting tokens directly to buyer...")
        print(f"[COMPLETE-SWAP] Buyer: {swap_data.buyer_address}")
        print(f"[COMPLETE-SWAP] Amount: {tokens_purchased} tons ({tokens_stroops} stroops)")
        
        try:
            # Get asset_code for carbon controller mint call
            asset_code = asset['asset_code']
            if not asset_code:
                # Generate asset_code from project_identifier and vintage_year if not set
                project_identifier = asset.get('project_identifier', '')
                vintage_year = asset.get('vintage_year', '')
                if project_identifier and vintage_year:
                    asset_code = f"{project_identifier}-{vintage_year}".replace("-", "_")
                else:
                    raise Exception("Cannot determine asset_code for minting")
            
            print(f"[COMPLETE-SWAP] Asset code: {asset_code}")
            print(f"[COMPLETE-SWAP] Minting {tokens_purchased} tokens to buyer {swap_data.buyer_address}")
            
            # Mint tokens directly to buyer using carbon controller
            soroban_service.mint_to_issuer(
                asset_code=asset_code,
                issuer_address=swap_data.buyer_address,  # Mint to buyer instead of issuer
                amount=float(tokens_purchased)
            )
            print(f"[COMPLETE-SWAP] ✓ Tokens minted successfully to buyer")
        except Exception as e:
            error_msg = str(e)
            print(f"[COMPLETE-SWAP] ERROR: Token minting failed: {error_msg}")
            print(f"[COMPLETE-SWAP] DETAILED ERROR: {type(e).__name__}: {error_msg}")
            raise HTTPException(status_code=500, detail=f"Token minting failed: {error_msg}")
        
        # Step 4: Transfer XLM from admin to seller
        print(f"[COMPLETE-SWAP] Step 5: Transferring XLM from admin to seller...")
        print(f"[COMPLETE-SWAP] From: {admin_address}, To: {asset['asset_issuer_address']}")
        
        server = Server(horizon_url="https://horizon-testnet.stellar.org")
        admin_account = server.load_account(admin_address)
        
        seller_payment_tx = (
            TransactionBuilder(
                source_account=admin_account,
                network_passphrase=Network.TESTNET_NETWORK_PASSPHRASE,
                base_fee=100,
            )
            .append_operation(
                Payment(
                    destination=asset["asset_issuer_address"],
                    asset=Asset.native(),
                    amount=str(amount_xlm_stroops),
                )
            )
            .add_memo(TextMemo(f"Pay {asset['asset_code']}"[:28]))  # Max 28 bytes
            .set_timeout(300)
            .build()
        )
        
        seller_payment_tx.sign(admin_keypair)
        print(f"[COMPLETE-SWAP] XLM payment transaction built and signed")
        
        try:
            response = server.submit_transaction(seller_payment_tx)
            print(f"[COMPLETE-SWAP] ✓ XLM transferred successfully. Hash: {response['hash']}")
        except Exception as e:
            print(f"[COMPLETE-SWAP] ERROR: XLM transfer failed: {e}")
            raise HTTPException(status_code=500, detail=f"XLM transfer failed: {str(e)}")
        
        print(f"[COMPLETE-SWAP] ===== SWAP COMPLETED SUCCESSFULLY ======")
        
        # Step 5: Record purchase in database
        print(f"[COMPLETE-SWAP] Step 6: Recording purchase in database...")
        try:
            # Get asset details for purchase record
            cursor.execute("""
                SELECT a.id, a.project_id, p.issuer_id as seller_id
                FROM assets a
                LEFT JOIN projects p ON a.project_id = p.id
                WHERE a.id = %s
            """, (swap_data.asset_id,))
            asset_details = cursor.fetchone()
            
            # Create purchases table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS purchases (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    asset_id INT NOT NULL,
                    buyer_id INT NOT NULL,
                    seller_id INT NOT NULL,
                    amount_xlm DECIMAL(20, 7) NOT NULL,
                    tokens_purchased DECIMAL(20, 7) NOT NULL,
                    xlm_payment_hash VARCHAR(255),
                    token_transfer_hash VARCHAR(255),
                    seller_payment_hash VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (asset_id) REFERENCES assets(id),
                    FOREIGN KEY (buyer_id) REFERENCES users(user_id),
                    FOREIGN KEY (seller_id) REFERENCES users(user_id),
                    INDEX idx_buyer (buyer_id),
                    INDEX idx_seller (seller_id),
                    INDEX idx_asset (asset_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # Get buyer user_id
            cursor.execute("SELECT user_id FROM users WHERE wallet_address = %s", (swap_data.buyer_address,))
            buyer_record = cursor.fetchone()
            buyer_id = buyer_record["user_id"] if buyer_record else None
            
            if not buyer_id:
                print(f"[COMPLETE-SWAP] WARNING: Could not find buyer user_id for address {swap_data.buyer_address}")
            else:
                # Insert purchase record
                cursor.execute("""
                    INSERT INTO purchases (
                        asset_id, buyer_id, seller_id, amount_xlm, tokens_purchased,
                        seller_payment_hash
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    swap_data.asset_id,
                    buyer_id,
                    asset_details["seller_id"],
                    swap_data.amount_xlm,
                    tokens_purchased,
                    response.get('hash')
                ))
                connection.commit()
                print(f"[COMPLETE-SWAP] ✓ Purchase recorded in database. Purchase ID: {cursor.lastrowid}")
        except Exception as e:
            print(f"[COMPLETE-SWAP] WARNING: Failed to record purchase in database: {e}")
            import traceback
            traceback.print_exc()
            # Don't fail the whole transaction if DB recording fails
        
        return {
            "success": True,
            "message": "Atomic swap completed successfully",
            "transaction_hash": response.get('hash'),
            "tokens_purchased": tokens_purchased,
            "amount_xlm": swap_data.amount_xlm,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[COMPLETE-SWAP] ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Swap completion failed: {str(e)}")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


@app.get("/issuer/assets")
async def get_issuer_assets(request: Request):
    """
    Get all assets for the current authenticated issuer.
    """
    user = get_authenticated_user(request)
    user_id = user["user_id"]
    
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Verify user is an ISSUER
        cursor.execute("SELECT role FROM users WHERE user_id = %s", (user_id,))
        user_data = cursor.fetchone()
        
        if not user_data or user_data.get("role") != "ISSUER":
            raise HTTPException(status_code=403, detail="Only issuers can access this endpoint")
        
        # Get all assets for projects owned by this issuer
        cursor.execute("""
            SELECT 
                a.id,
                a.asset_code,
                a.contract_id,
                a.asset_issuer_address,
                a.total_supply,
                a.is_frozen,
                p.project_identifier,
                p.name as project_name,
                a.vintage_year
            FROM assets a
            LEFT JOIN projects p ON a.project_id = p.id
            WHERE p.issuer_id = %s
            ORDER BY a.created_at DESC
        """, (user_id,))
        
        assets = cursor.fetchall()
        
        return assets
        
    except HTTPException:
        raise
    except Error as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


class ApproveAdminRequest(BaseModel):
    secret_key: Optional[str] = None  # Seller's secret key (optional, for server-side approval)


@app.post("/issuer/approve-admin-all")
async def approve_admin_for_all_assets(request: Request, approve_data: ApproveAdminRequest = None):
    """
    Approve admin to transfer tokens for all assets owned by the current issuer.
    This allows admin to act as middleman without requiring seller signature during purchase.
    
    If secret_key is provided, will approve server-side. Otherwise, returns approval commands.
    WARNING: Providing secret key in request is insecure - only use in development!
    """
    user = get_authenticated_user(request)
    user_id = user["user_id"]
    user_wallet = user["wallet_address"]
    
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Verify user is an ISSUER
        cursor.execute("SELECT role FROM users WHERE user_id = %s", (user_id,))
        user_data = cursor.fetchone()
        
        if not user_data or user_data.get("role") != "ISSUER":
            raise HTTPException(status_code=403, detail="Only issuers can approve admin")
        
        # Get all assets for projects owned by this issuer
        cursor.execute("""
            SELECT 
                a.id,
                a.asset_code,
                a.contract_id,
                a.asset_issuer_address,
                a.total_supply
            FROM assets a
            LEFT JOIN projects p ON a.project_id = p.id
            WHERE p.issuer_id = %s AND a.contract_id IS NOT NULL
                AND a.asset_issuer_address = %s
        """, (user_id, user_wallet))
        
        assets = cursor.fetchall()
        
        if not assets:
            return {
                "success": True,
                "message": "No assets found to approve",
                "approved_count": 0
            }
        
        # Import soroban service
        from soroban_service import SorobanService
        soroban_service = SorobanService()
        admin_address = soroban_service.get_admin_address()
        
        # If secret key provided, try to approve server-side
        if approve_data and approve_data.secret_key:
            approved_count = 0
            failed_assets = []
            
            for asset in assets:
                try:
                    # Calculate approval amount (100x total supply for safety)
                    total_supply_stroops = int(float(asset['total_supply']) * 10000000)
                    approval_amount = total_supply_stroops * 100
                    
                    print(f"[PRE-APPROVE] Approving admin for asset {asset['asset_code']}")
                    
                    # Approve admin using seller's secret key
                    # expiration_ledger will be calculated automatically (1 year from current)
                    soroban_service.approve_admin_for_token(
                        token_contract_id=asset['contract_id'],
                        owner_address=user_wallet,
                        amount_i128=approval_amount,
                        expiration_ledger=None,  # Will be calculated automatically
                        owner_secret_key=approve_data.secret_key
                    )
                    
                    approved_count += 1
                    print(f"[PRE-APPROVE] ✓ Approved for {asset['asset_code']}")
                    
                except Exception as e:
                    print(f"[PRE-APPROVE] ERROR: Failed to approve for {asset['asset_code']}: {e}")
                    failed_assets.append({
                        "asset_code": asset['asset_code'],
                        "error": str(e)
                    })
            
            return {
                "success": True,
                "message": f"Approved admin for {approved_count} out of {len(assets)} assets",
                "approved_count": approved_count,
                "total_count": len(assets),
                "failed_assets": failed_assets
            }
        else:
            # Return approval commands for manual execution
            approval_commands = []
            
            for asset in assets:
                # Calculate approval amount (100x total supply for safety)
                total_supply_stroops = int(float(asset['total_supply']) * 10000000)
                approval_amount = total_supply_stroops * 100
                
                # Build the approval command
                # Note: Users need to get current ledger first and add 518400 for 30 days expiration
                # Command: stellar ledger current --network <network>
                network = soroban_service.network
                cmd_parts = [
                    "stellar contract invoke",
                    f"--id {asset['contract_id']}",
                    f"--source {user_wallet}",
                    f"--network {network}",
                    "--",
                    "approve",
                    f"--from {user_wallet}",
                    f"--spender {admin_address}",
                    f"--amount {approval_amount}",
                    "--expiration-ledger <CURRENT_LEDGER + 120960>"  # Replace with actual value (7 days from current)
                ]
                
                approval_commands.append({
                    "asset_code": asset['asset_code'],
                    "contract_id": asset['contract_id'],
                    "command": " ".join(cmd_parts),
                    "approval_amount": approval_amount
                })
            
            return {
                "success": True,
                "message": f"Found {len(assets)} assets that need approval",
                "total_count": len(assets),
                "approval_commands": approval_commands,
                "instructions": "Set your STELLAR_SECRET_KEY environment variable and run these commands, or provide your secret key in the request body (insecure - development only)."
            }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[PRE-APPROVE] ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Pre-approval failed: {str(e)}")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


@app.post("/admin/assets/{asset_id}/approve-admin")
async def approve_admin_for_asset(request: Request, asset_id: int):
    """
    Manually approve admin to transfer tokens for an existing asset.
    This is useful if auto-approval failed during asset creation.
    """
    admin_user = check_admin_role(request)
    
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Get asset details
        cursor.execute("""
            SELECT a.contract_id, a.asset_issuer_address, a.total_supply, a.asset_code
            FROM assets a
            WHERE a.id = %s
        """, (asset_id,))
        
        asset = cursor.fetchone()
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        
        print(f"[MANUAL-APPROVE] ===== MANUAL APPROVAL REQUEST ======")
        print(f"[MANUAL-APPROVE] Asset ID: {asset_id}")
        print(f"[MANUAL-APPROVE] Contract: {asset['contract_id']}")
        print(f"[MANUAL-APPROVE] Issuer: {asset['asset_issuer_address']}")
        
        from soroban_service import SorobanService
        soroban_service = SorobanService()
        
        # Calculate approval amount (100x total supply)
        total_supply_stroops = int(float(asset['total_supply']) * 10000000)
        approval_amount = total_supply_stroops * 100
        
        print(f"[MANUAL-APPROVE] Total supply: {asset['total_supply']} tons = {total_supply_stroops} stroops")
        print(f"[MANUAL-APPROVE] Approval amount: {approval_amount} stroops")
        
        try:
            soroban_service.approve_admin_for_token(
                token_contract_id=asset['contract_id'],
                owner_address=asset['asset_issuer_address'],
                amount_i128=approval_amount,
                expiration_ledger=None  # Will be calculated automatically (1 year from current ledger)
            )
            
            print(f"[MANUAL-APPROVE] ✓✓✓ Admin approved successfully ✓✓✓")
            
            return {
                "success": True,
                "message": f"Admin approved successfully for asset {asset['asset_code']}",
                "asset_id": asset_id,
                "approval_amount": approval_amount
            }
        except Exception as e:
            print(f"[MANUAL-APPROVE] ERROR: Approval failed: {e}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Failed to approve admin: {str(e)}")
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[MANUAL-APPROVE] ERROR: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Approval failed: {str(e)}")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

