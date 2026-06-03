from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    DateTime,
    UniqueConstraint
)

from app.db.database import Base


class LeaveRequest(Base):

    __tablename__ = "leave_requests"
    __table_args__ = (
        UniqueConstraint('employee_username', 'start_date', 'end_date',
                        name='uq_leave_period'),
    )

    id = Column(Integer, primary_key=True)

    employee_username = Column(String, nullable=False)

    leave_type = Column(String, nullable=False)

    start_date = Column(Date, nullable=False)

    end_date = Column(Date, nullable=False)

    number_of_days = Column(Integer)

    reason = Column(String)

    status = Column(String, default="PENDING")

    manager_comment = Column(String, nullable=True)

    approved_at = Column(DateTime, nullable=True)

    rejected_at = Column(DateTime, nullable=True)