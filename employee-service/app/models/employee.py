from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey
)

from app.db.database import Base


class Employee(Base):

    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)

    username = Column(String, unique=True, nullable=False)

    full_name = Column(String, nullable=False)

    role = Column(String, nullable=False)

    manager_id = Column(
        Integer,
        ForeignKey("employees.id"),
        nullable=True
    )