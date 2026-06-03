from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, Field

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.employee import Employee
from app.models.leave_balance import LeaveBalance

from app.core.dependencies import get_current_user, check_employee_access

router = APIRouter()


class DeductLeaveRequest(BaseModel):
    """Request model for deducting leave balance."""
    leave_type: str = Field(..., description="Type of leave (CASUAL, SICK, EARNED, UNPAID)")
    days: int = Field(..., gt=0, description="Number of days to deduct")


@router.get("/me", tags=["Employee"], summary="Get Current User Info")
def get_me(user=Depends(get_current_user)):
    """
    Get the current authenticated user's employee information.
    
    **Response:** Employee object with username, name, and manager_id
    
    **Errors:**
    - 401: Unauthorized (missing or invalid token)
    """

    db: Session = SessionLocal()

    employee = (
        db.query(Employee)
        .filter(Employee.username == user["user_id"])
        .first()
    )

    db.close()

    return employee


@router.get("/leave-balances", tags=["Leave"], summary="Get Leave Balances")
def get_leave_balances(user=Depends(get_current_user)):
    """
    Get leave balance for all leave types for the current user.
    
    **Response:** List of LeaveBalance objects with leave_type and remaining balance
    
    **Errors:**
    - 401: Unauthorized (missing or invalid token)
    """

    db: Session = SessionLocal()

    employee = (
        db.query(Employee)
        .filter(Employee.username == user["user_id"])
        .first()
    )

    balances = (
        db.query(LeaveBalance)
        .filter(LeaveBalance.employee_id == employee.id)
        .all()
    )

    db.close()

    return balances

@router.get("/team/{manager_username}", tags=["Team"], summary="Get Team Members")
def get_team_members(
    manager_username: str,
    user=Depends(get_current_user)
):
    """
    Get list of employees reporting to a manager.
    
    **Path Parameters:**
    - **manager_username**: Username of the manager
    
    **Response:** List of employee usernames
    
    **Errors:**
    - 401: Unauthorized (missing or invalid token)
    - 403: Forbidden (not allowed to view this team)
    - 404: Manager not found
    """

    db: Session = SessionLocal()

    try:
        # Authorization: Only admins or the manager themselves can view the team
        if user.get("role") != "ADMIN" and user["user_id"] != manager_username:
            raise HTTPException(
                status_code=403,
                detail="Not allowed to view this team"
            )

        manager = (
            db.query(Employee)
            .filter(Employee.username == manager_username)
            .first()
        )

        if not manager:
            raise HTTPException(
                status_code=404,
                detail="Manager not found"
            )

        employees = (
            db.query(Employee)
            .filter(Employee.manager_id == manager.id)
            .all()
        )

        return [
            employee.username
            for employee in employees
        ]
    
    finally:
        db.close()

@router.get("/{username}/manager")
def get_employee_manager(
    username: str,
    user=Depends(get_current_user)
):

    db: Session = SessionLocal()
    
    try:
        # Check authorization
        check_employee_access(user, username, db)

        employee = (
            db.query(Employee)
            .filter(Employee.username == username)
            .first()
        )

        if not employee:

            raise HTTPException(
                status_code=404,
                detail="Employee not found"
            )

        manager = (
            db.query(Employee)
            .filter(Employee.id == employee.manager_id)
            .first()
        )

        return {
            "employee": employee.username,
            "manager": manager.username if manager else None
        }
    
    finally:
        db.close()

@router.get("/{username}/leave-balance/{leave_type}")
def get_leave_balance(
    username: str,
    leave_type: str,
    user=Depends(get_current_user)
):

    db: Session = SessionLocal()
    
    try:
        # Check authorization
        check_employee_access(user, username, db)

        employee = (
            db.query(Employee)
            .filter(Employee.username == username)
            .first()
        )

        if not employee:

            raise HTTPException(
                status_code=404,
                detail="Employee not found"
            )

        balance = (
            db.query(LeaveBalance)
            .filter(
                LeaveBalance.employee_id == employee.id,
                LeaveBalance.leave_type == leave_type
            )
            .first()
        )

        if not balance:

            raise HTTPException(
                status_code=404,
                detail="Leave balance not found"
            )

        return {
            "leave_type": balance.leave_type,
            "allocated": balance.allocated,
            "used": balance.used,
            "remaining": balance.remaining
        }
    
    finally:
        db.close()

@router.put("/{username}/deduct-balance")
def deduct_leave_balance(
    username: str,
    request: DeductLeaveRequest,
    user=Depends(get_current_user)
):

    db: Session = SessionLocal()

    try:
        # Authorization: Only managers or the leave-service (via admin/service token) can deduct
        # For now, allow if user is manager of the employee or admin
        # In production, use service-to-service auth (API key or service account)
        if user.get("role") not in ["ADMIN", "MANAGER"]:
            # If not admin/manager, check if they're the employee's manager
            check_employee_access(user, username, db)
        
        employee = (
            db.query(Employee)
            .filter(Employee.username == username)
            .first()
        )

        if not employee:

            raise HTTPException(
                status_code=404,
                detail="Employee not found"
            )

        balance = (
            db.query(LeaveBalance)
            .filter(
                LeaveBalance.employee_id == employee.id,
                LeaveBalance.leave_type == request.leave_type
            )
            .first()
        )

        if not balance:

            raise HTTPException(
                status_code=404,
                detail="Leave balance not found"
            )

        if balance.remaining < request.days:

            raise HTTPException(
                status_code=400,
                detail="Insufficient leave balance"
            )

        balance.used += request.days

        balance.remaining -= request.days

        db.commit()
        
        # Store value before closing session
        remaining = balance.remaining

        return {
            "message": "Leave balance updated",
            "remaining": remaining
        }
    
    finally:
        db.close()