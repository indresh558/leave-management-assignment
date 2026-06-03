from sqlalchemy.orm import Session

from app.models.user import User
from app.core.security import hash_password  # Fix #1: Import hash_password


def seed_users(db: Session):

    existing = db.query(User).first()

    if existing:
        return

    users = [
        # Manager 1
        User(
            username="manager",
            password=hash_password("password"),
            role="MANAGER"
        ),

        # Manager 2
        User(
            username="manager2",
            password=hash_password("password"),
            role="MANAGER"
        ),

        # Employee 1 (under manager)
        User(
            username="employee",
            password=hash_password("password"),
            role="EMPLOYEE"
        ),

        # Employees under manager2
        User(
            username="employee2",
            password=hash_password("password"),
            role="EMPLOYEE"
        ),
        User(
            username="employee3",
            password=hash_password("password"),
            role="EMPLOYEE"
        ),
        User(
            username="employee4",
            password=hash_password("password"),
            role="EMPLOYEE"
        )
    ]

    db.add_all(users)
    db.commit()

    print("Users password seeded successfully with hashed passwords in the database.")