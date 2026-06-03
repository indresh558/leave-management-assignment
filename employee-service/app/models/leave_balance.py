from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey
)

from app.db.database import Base


class LeaveBalance(Base):

    __tablename__ = "leave_balances"

    id = Column(Integer, primary_key=True)

    employee_id = Column(
        Integer,
        ForeignKey("employees.id")
    )

    leave_type = Column(String)

    allocated = Column(Integer)

    used = Column(Integer)

    remaining = Column(Integer)