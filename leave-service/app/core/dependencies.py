from fastapi import Header, HTTPException
from jose import jwt, JWTError
import os
import logging

logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key")
ALGORITHM = "HS256"


def get_current_user(authorization: str = Header(None)):
    """
    Extract and validate user from JWT token in Authorization header.
    
    Expected format: Authorization: Bearer <token>
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization header"
        )
    
    try:
        # Extract token from "Bearer <token>"
        parts = authorization.split()
        
        if len(parts) != 2:
            logger.error(f"Invalid authorization header format: {len(parts)} parts")
            raise HTTPException(
                status_code=401,
                detail="Invalid authorization header format"
            )
        
        scheme, token = parts
        
        if scheme.lower() != "bearer":
            logger.error(f"Invalid auth scheme: {scheme}")
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication scheme"
            )
        
        # Decode JWT token
        logger.debug(f"Decoding token with SECRET_KEY")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        user_id = payload.get("user_id")
        role = payload.get("role")
        
        if not user_id:
            logger.error("Invalid token: missing user_id")
            raise HTTPException(
                status_code=401,
                detail="Invalid token: missing user_id"
            )
        
        logger.info(f"User authenticated: {user_id} with role {role}")
        
        return {
            "user_id": user_id,
            "role": role or "EMPLOYEE"
        }
    
    except HTTPException:
        raise
    
    except JWTError as e:
        logger.error(f"JWT decode error: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )
    
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=401,
            detail="Authentication failed"
        )