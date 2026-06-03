from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password  # Fix #1: Import verify_password
from app.db.database import SessionLocal
from app.models.user import User

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    role: str


@router.post("/login", response_model=TokenResponse, tags=["Authentication"], summary="User Login")
def login(payload: LoginRequest):
    """
    Authenticate user and return JWT token.
    
    **Request Body:**
    - **username**: Username of the user
    - **password**: Password of the user
    
    **Response:**
    - **access_token**: JWT token for authenticated requests
    - **token_type**: Token type (bearer)
    - **expires_in**: Token expiration time in seconds (86400 = 24 hours)
    - **role**: User role (EMPLOYEE or MANAGER)
    
    **Errors:**
    - 401: Invalid username or password
    """

    db: Session = SessionLocal()

    try:
        user = (
            db.query(User)
            .filter(User.username == payload.username)
            .first()
        )

        if not user:
            raise HTTPException(
                status_code=401,
                detail="Invalid username or password"
            )

        # Fix #1: Use verify_password for secure password comparison
        if not verify_password(payload.password, user.password):
            raise HTTPException(
                status_code=401,
                detail="Invalid username or password"
            )

        token = create_access_token({
            "user_id": user.username,
            "role": user.role
        })

        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": 86400,  # Fix #2: Return expiration time (24 hours)
            "role": user.role
        }
    
    finally:
        db.close()