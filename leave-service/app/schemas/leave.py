from pydantic import BaseModel, Field, validator
from datetime import date
from shared.enums import LeaveType


class ApplyLeaveRequest(BaseModel):
    """Schema for leave application request with validation."""

    leave_type: LeaveType = Field(
        ...,
        description="Type of leave (CASUAL, SICK, EARNED, UNPAID)"
    )

    start_date: date = Field(..., description="Leave start date (YYYY-MM-DD)")

    end_date: date = Field(..., description="Leave end date (YYYY-MM-DD)")

    number_of_days: int = Field(..., gt=0, description="Number of days (must be > 0)")

    reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Reason for leave"
    )

    # Input validation - ensure start_date is not in past
    @validator('start_date', 'end_date')
    def date_not_in_past(cls, v):
        """Ensure dates are not in the past."""
        if v < date.today():
            raise ValueError('Cannot apply for past dates')
        return v

    # Input validation - end_date must be >= start_date
    @validator('end_date')
    def end_date_after_start(cls, v, values):
        """Ensure end date is not before start date."""
        if 'start_date' in values and v < values['start_date']:
            raise ValueError('End date cannot be before start date')
        return v
    
    # Input validation - number_of_days must match the date range
    @validator('number_of_days')
    def validate_number_of_days(cls, v, values):
        start_date = values.get('start_date')
        end_date = values.get('end_date')

        if start_date and end_date:
            expected_days = (end_date - start_date).days + 1

            if v != expected_days:
                raise ValueError(
                    f'number_of_days must be {expected_days} for the selected date range'
                )

        return v