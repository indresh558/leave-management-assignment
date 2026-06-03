import datetime
import os
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request
)

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
import httpx
import logging
from app.db.database import SessionLocal
from app.models.leave_request import LeaveRequest

from app.schemas.leave import ApplyLeaveRequest

from app.core.dependencies import get_current_user
from app.core.enums import LeaveStatus
from app.core.rabbitmq import publish_notification

router = APIRouter()
logger = logging.getLogger(__name__)

EMPLOYEE_SERVICE_URL = os.getenv("EMPLOYEE_SERVICE_URL", "http://employee-service:8002")

# Fix #4: Helper function with comprehensive error handling for inter-service calls
async def get_leave_balance(username: str, leave_type: str, auth_header: str = None) -> dict:
    """
    Fetch leave balance from Employee Service with error handling.
    
    Args:
        username: Employee username
        leave_type: Type of leave (CASUAL, SICK, EARNED, UNPAID)
        auth_header: Authorization header to pass to employee service
    
    Raises:
        HTTPException: 503 if Employee Service unavailable
    """
    try:
        headers = {}
        if auth_header:
            headers["authorization"] = auth_header
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{EMPLOYEE_SERVICE_URL}/employees/"
                f"{username}/leave-balance/"
                f"{leave_type}",
                headers=headers,
                timeout=5.0
            )
            
            # Check for successful response
            if response.status_code == 404:
                raise HTTPException(
                    status_code=400,
                    detail="Employee or leave type not found"
                )
            elif response.status_code != 200:
                logger.error(f"Employee Service error: {response.status_code}")
                raise HTTPException(
                    status_code=503,
                    detail="Employee Service temporarily unavailable"
                )
            
            return response.json()
    
    except httpx.TimeoutException as e:
        logger.error(f"Timeout fetching leave balance: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail="Employee Service unavailable (timeout)"
        )
    
    except httpx.RequestError as e:
        logger.error(f"Error communicating with Employee Service: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail="Employee Service unavailable"
        )
    
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


@router.post("/apply", tags=["Leave"], summary="Apply for Leave")
async def apply_leave(
    payload: ApplyLeaveRequest,
    request: Request,
    user=Depends(get_current_user)
):
    """
    Apply for leave.
    
    **Request Body:**
    - **start_date**: Leave start date (YYYY-MM-DD)
    - **end_date**: Leave end date (YYYY-MM-DD)
    - **leave_type**: Type of leave (SICK, CASUAL, EARNED, UNPAID)
    - **number_of_days**: Number of days for leave
    - **reason**: Reason for leave (1-500 characters)
    
    **Response:** Leave application object with leave_id and status
    
    **Errors:**
    - 400: Insufficient leave balance or invalid dates
    - 409: Overlapping leave request exists or constraint violation
    - 500: Internal server error
    - 503: Employee Service unavailable
    """

    # Get Authorization header to pass to employee service
    auth_header = request.headers.get("authorization")
    if not auth_header:
        raise HTTPException(
            status_code=401,
            detail="Authorization header required"
        )

    db: Session = SessionLocal()
    
    try:
        # Validate leave balance using error-handled helper
        balance_data = await get_leave_balance(
            user['user_id'],
            payload.leave_type.value,
            auth_header
        )

        remaining_balance = balance_data.get("remaining", 0)

        if payload.number_of_days > remaining_balance:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Insufficient leave balance. "
                    f"Remaining: {remaining_balance}"
                )
            )

        # Overlap validation
        overlap = (
            db.query(LeaveRequest)
            .filter(
                LeaveRequest.employee_username == user["user_id"],
                LeaveRequest.start_date <= payload.end_date,
                LeaveRequest.end_date >= payload.start_date,
                LeaveRequest.status.in_(["PENDING", "APPROVED"])
            )
            .first()
        )

        if overlap:
            raise HTTPException(
                status_code=409,
                detail="Overlapping leave request exists"
            )

        leave_request = LeaveRequest(
            employee_username=user["user_id"],
            leave_type=payload.leave_type.value,
            start_date=payload.start_date,
            end_date=payload.end_date,
            number_of_days=payload.number_of_days,
            reason=payload.reason,
            status="PENDING"
        )

        db.add(leave_request)
        db.commit()
        db.refresh(leave_request)

        # Publish event with error handling
        try:
            await publish_notification(
                "leave.applied",
                {
                    "leave_id": leave_request.id,
                    "employee_username": user["user_id"],
                    "leave_type": payload.leave_type,
                    "status": "PENDING"
                }
            )
        except Exception as e:
            logger.warning(f"Failed to publish notification: {str(e)}")
            # Don't fail the request if notification fails

        return {
            "message": "Leave applied successfully",
            "leave_id": leave_request.id,
            "status": "PENDING"
        }
    
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    
    except IntegrityError as e:
        # Fix #10: Handle database constraint violations
        db.rollback()
        logger.error(f"Database constraint violation: {str(e)}")
        raise HTTPException(status_code=409, detail="Leave request violates constraints")
    
    except SQLAlchemyError as e:
        # Fix #10: Handle other database errors
        db.rollback()
        logger.error(f"Database error: {str(e)}")
        raise HTTPException(status_code=500, detail="Database error")
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error applying leave: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
    
    finally:
        db.close()


@router.get("/history", tags=["Leave"], summary="Get Leave History")
def leave_history(
    user=Depends(get_current_user),
    skip: int = 0,
    limit: int = 10,
    status: str = None
):
    """
    Get leave request history for the current user with pagination and filtering.
    
    **Query Parameters:**
    - **skip**: Number of records to skip (default: 0)
    - **limit**: Number of records to return (default: 10)
    - **status**: Filter by status (PENDING/APPROVED/REJECTED/CANCELLED - optional)
    
    **Response:** List of LeaveRequest objects with pagination metadata
    
    **Errors:**
    - 401: Unauthorized (missing or invalid token)
    - 400: Invalid status filter
    """
    
    valid_statuses = ["PENDING", "APPROVED", "REJECTED", "CANCELLED"]
    
    if status and status.upper() not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        )

    db: Session = SessionLocal()

    query = db.query(LeaveRequest).filter(
        LeaveRequest.employee_username == user["user_id"]
    )
    
    if status:
        query = query.filter(LeaveRequest.status == status.upper())
    
    total = query.count()
    
    requests = query.offset(skip).limit(limit).all()

    db.close()

    return {
        "items": requests,
        "total": total,
        "skip": skip,
        "limit": limit,
        "status_filter": status
    }

@router.get("/pending", tags=["Leave"], summary="Get Pending Leave Requests")
async def get_pending_requests(
    request: Request,
    user=Depends(get_current_user),
    skip: int = 0,
    limit: int = 10,
    employee: str = None,
    status: str = "PENDING",
    start_date: str = None,
    end_date: str = None
):
    """
    Get leave requests for the manager's team with filtering and pagination.
    
    **Query Parameters:**
    - **skip**: Number of records to skip (default: 0)
    - **limit**: Number of records to return (default: 10)
    - **employee**: Filter by employee username (optional)
    - **status**: Filter by status (default: PENDING, can be APPROVED/REJECTED)
    - **start_date**: Filter by leave start date (YYYY-MM-DD, optional)
    - **end_date**: Filter by leave end date (YYYY-MM-DD, optional)
    
    **Response:** List of LeaveRequest objects with pagination metadata
    
    **Errors:**
    - 403: Forbidden (only managers allowed)
    - 401: Unauthorized (missing or invalid token)
    - 503: Employee Service unavailable
    - 400: Invalid date format
    """

    if user["role"] != "MANAGER":

        raise HTTPException(
            status_code=403,
            detail="Managers only"
        )

    # Get Authorization header to pass to employee service
    auth_header = request.headers.get("authorization")
    if not auth_header:
        raise HTTPException(
            status_code=401,
            detail="Authorization header required"
        )

    # Fetch manager's team
    try:
        headers = {"authorization": auth_header}
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{EMPLOYEE_SERVICE_URL}/employees/team/{user['user_id']}",
                headers=headers
            )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=503,
                    detail="Employee Service unavailable"
                )
    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Employee Service unavailable"
        )

    team_members = response.json()

    db: Session = SessionLocal()

    query = db.query(LeaveRequest).filter(
        LeaveRequest.employee_username.in_(team_members),
        LeaveRequest.status == status
    )
    
    # Filter by employee if provided
    if employee:
        if employee not in team_members:
            db.close()
            raise HTTPException(
                status_code=400,
                detail="Employee not in your team"
            )
        query = query.filter(LeaveRequest.employee_username == employee)
    
    # Filter by date range if provided
    if start_date:
        try:
            from datetime import datetime as dt
            parsed_start = dt.strptime(start_date, "%Y-%m-%d").date()
            query = query.filter(LeaveRequest.start_date >= parsed_start)
        except ValueError:
            db.close()
            raise HTTPException(
                status_code=400,
                detail="Invalid start_date format. Use YYYY-MM-DD"
            )
    
    if end_date:
        try:
            from datetime import datetime as dt
            parsed_end = dt.strptime(end_date, "%Y-%m-%d").date()
            query = query.filter(LeaveRequest.end_date <= parsed_end)
        except ValueError:
            db.close()
            raise HTTPException(
                status_code=400,
                detail="Invalid end_date format. Use YYYY-MM-DD"
            )
    
    total = query.count()
    
    requests = query.order_by(
    LeaveRequest.id.desc()
    ).offset(skip).limit(limit).all()
    

    db.close()

    return {
        "items": requests,
        "total": total,
        "skip": skip,
        "limit": limit,
        "filters": {
            "status": status,
            "employee": employee,
            "start_date": start_date,
            "end_date": end_date
        }
    }

@router.put("/{leave_id}/approve", tags=["Leave"], summary="Approve Leave Request")
async def approve_leave(
    leave_id: int,
    request: Request,
    user=Depends(get_current_user)
):
    """
    Approve a pending leave request.
    
    **Path Parameters:**
    - **leave_id**: ID of the leave request to approve
    
    **Response:** Approval status and message
    
    **Errors:**
    - 400: Leave already processed or manager cannot approve own leave
    - 403: Forbidden (only managers allowed)
    - 404: Leave request not found
    - 401: Unauthorized (missing or invalid token)
    - 503: Employee Service unavailable
    """

    # Get Authorization header to pass to employee service
    auth_header = request.headers.get("authorization")
    if not auth_header:
        raise HTTPException(
            status_code=401,
            detail="Authorization header required"
        )

    # Only managers allowed
    if user["role"] != "MANAGER":

        raise HTTPException(
            status_code=403,
            detail="Managers only"
        )

    db: Session = SessionLocal()

    leave = (
        db.query(LeaveRequest)
        .filter(LeaveRequest.id == leave_id)
        .first()
    )

    # Leave existence validation
    if not leave:

        db.close()

        raise HTTPException(
            status_code=404,
            detail="Leave request not found"
        )

    # Prevent self approval
    if leave.employee_username == user["user_id"]:

        db.close()

        raise HTTPException(
            status_code=400,
            detail="Managers cannot approve their own leave"
        )

    # Only pending requests allowed
    if leave.status != LeaveStatus.PENDING.value:

        db.close()

        raise HTTPException(
            status_code=400,
            detail="Only pending requests can be approved"
        )

    # Validate reporting manager
    try:

        async with httpx.AsyncClient(timeout=5.0) as client:

            response = await client.get(
                f"{EMPLOYEE_SERVICE_URL}/employees/"
                f"{leave.employee_username}/manager",
                headers={"authorization": auth_header}
            )

    except httpx.RequestError:

        db.close()

        raise HTTPException(
            status_code=503,
            detail="Employee Service unavailable"
        )

    if response.status_code != 200:

        db.close()

        raise HTTPException(
            status_code=500,
            detail="Unable to validate reporting manager"
        )

    manager_data = response.json()

    actual_manager = manager_data["manager"]

    # Validate manager ownership
    if actual_manager != user["user_id"]:

        db.close()

        raise HTTPException(
            status_code=403,
            detail="You cannot approve this employee's leave"
        )

    # Fix #14: Use database transaction for atomic approval
    # Important: Deduct balance first, then update leave status in single transaction
    try:
        # Deduct leave balance via service call
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                deduct_response = await client.put(
                    f"{EMPLOYEE_SERVICE_URL}/employees/"
                    f"{leave.employee_username}/deduct-balance",
                    json={
                        "leave_type": leave.leave_type,
                        "days": leave.number_of_days
                    },
                    headers={"authorization": auth_header},
                    timeout=5.0
                )

        except httpx.RequestError:
            db.rollback()
            db.close()
            raise HTTPException(
                status_code=503,
                detail="Employee Service unavailable"
            )

        if deduct_response.status_code != 200:
            db.rollback()
            db.close()
            raise HTTPException(
                status_code=400,
                detail="Failed to deduct leave balance"
            )

        # Update leave status in same transaction
        # Both operations commit together, or both rollback on error
        leave.status = LeaveStatus.APPROVED.value
        leave.approved_at = datetime.datetime.now(datetime.timezone.utc)
        
        db.add(leave)  # Ensure leave is tracked
        db.commit()  # Atomic commit: balance deduction + status update
        db.refresh(leave)
        
        # Store values before closing session to avoid detached instance errors
        leave_id = leave.id
        employee_username = leave.employee_username
        approval_status = leave.status
        
        logger.info(f"Leave {leave.id} approved successfully by {user['user_id']}")

    except HTTPException:
        db.rollback()
        raise
    
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database constraint violation during approval: {str(e)}")
        raise HTTPException(status_code=409, detail="Failed to approve leave due to constraint")
    
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during approval: {str(e)}")
        raise HTTPException(status_code=500, detail="Database error during approval")
    
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during approval: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
    
    finally:
        db.close()

    # Publish event with stored values
    await publish_notification(
        "leave.approved",
        {
            "leave_id": leave_id,
            "employee_username": employee_username,
            "approved_by": user["user_id"],
            "status": approval_status
        }
    )

    return {
        "message": "Leave approved successfully",
        "leave_id": leave_id,
        "status": approval_status
    }

@router.put("/{leave_id}/reject")
async def reject_leave(
    leave_id: int,
    comment: str,
    request: Request,
    user=Depends(get_current_user)
):

    # Get Authorization header to pass to employee service
    auth_header = request.headers.get("authorization")
    if not auth_header:
        raise HTTPException(
            status_code=401,
            detail="Authorization header required"
        )

    # Only managers allowed
    if user["role"] != "MANAGER":

        raise HTTPException(
            status_code=403,
            detail="Managers only"
        )

    db: Session = SessionLocal()

    leave = (
        db.query(LeaveRequest)
        .filter(LeaveRequest.id == leave_id)
        .first()
    )

    # Leave existence validation
    if not leave:

        db.close()

        raise HTTPException(
            status_code=404,
            detail="Leave request not found"
        )

    # Prevent self rejection
    if leave.employee_username == user["user_id"]:

        db.close()

        raise HTTPException(
            status_code=400,
            detail="Managers cannot reject their own leave"
        )

    # Only pending requests allowed
    if leave.status != LeaveStatus.PENDING.value:

        db.close()

        raise HTTPException(
            status_code=400,
            detail="Only pending requests can be rejected"
        )

    # Validate reporting manager
    try:

        async with httpx.AsyncClient(timeout=5.0) as client:

            response = await client.get(
                f"{EMPLOYEE_SERVICE_URL}/employees/"
                f"{leave.employee_username}/manager",
                headers={"authorization": auth_header}
            )

    except httpx.RequestError:

        db.close()

        raise HTTPException(
            status_code=503,
            detail="Employee Service unavailable"
        )

    if response.status_code != 200:

        db.close()

        raise HTTPException(
            status_code=500,
            detail="Unable to validate reporting manager"
        )

    manager_data = response.json()

    actual_manager = manager_data["manager"]

    # Validate manager ownership
    if actual_manager != user["user_id"]:

        db.close()

        raise HTTPException(
            status_code=403,
            detail="You cannot reject this employee's leave"
        )

    # Update leave status
    leave.status = LeaveStatus.REJECTED.value

    leave.manager_comment = comment

    leave.rejected_at = datetime.datetime.now(datetime.timezone.utc)

    db.commit()
    
    # Store values before closing session
    leave_id = leave.id
    employee_username = leave.employee_username
    rejection_status = leave.status

    db.close()

    await publish_notification(
        "leave.rejected",
        {
            "leave_id": leave_id,
            "employee_username": employee_username,
            "rejected_by": user["user_id"],
            "status": rejection_status,
            "comment": comment
        }
    )

    return {
        "message": "Leave rejected successfully",
        "leave_id": leave_id,
        "status": rejection_status
    }