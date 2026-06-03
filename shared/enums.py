"""Shared enums used across all microservices."""

from enum import Enum


class LeaveType(str, Enum):
    """Leave type enumeration."""
    
    CASUAL = "CASUAL"
    SICK = "SICK"
    EARNED = "EARNED"
    UNPAID = "UNPAID"


class LeaveStatus(str, Enum):
    """Leave request status enumeration."""
    
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class UserRole(str, Enum):
    """User role enumeration."""
    
    EMPLOYEE = "EMPLOYEE"
    MANAGER = "MANAGER"
    ADMIN = "ADMIN"
