from fastapi import Header, HTTPException
from jose import jwt, JWTError
import os
import logging
from sqlalchemy.orm import Session

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


def check_employee_access(
    current_user: dict,
    target_username: str,
    db: Session
) -> bool:
    """
    Check if current user can access data for target_username.
    
    Access granted if:
    - User is accessing their own data (user_id == target_username)
    - User is a manager of the target employee
    - User is ADMIN
    
    Args:
        current_user: Current authenticated user dict with user_id and role
        target_username: Username of employee whose data is being accessed
        db: Database session
        
    Returns:
        True if access allowed
        
    Raises:
        HTTPException(403): If access is denied
    """
    # Allow access to own data
    if current_user["user_id"] == target_username:
        return True
    
    # ADMIN can access any employee's data
    if current_user.get("role") == "ADMIN":
        return True
    
    # Check if user is a manager of the target employee
    from app.models.employee import Employee
    
    try:
        manager = (
            db.query(Employee)
            .filter(Employee.username == current_user["user_id"])
            .first()
        )
        
        target_employee = (
            db.query(Employee)
            .filter(Employee.username == target_username)
            .first()
        )
        
        if not target_employee:
            raise HTTPException(
                status_code=404,
                detail="Employee not found"
            )
        
        # Check if current user is a manager of target employee
        if manager and target_employee.manager_id == manager.id:
            return True
        
        # Access denied
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to access this employee's data"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authorization check error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Authorization check failed"
        )