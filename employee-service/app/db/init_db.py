from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.leave_balance import LeaveBalance
from shared.enums import LeaveType


def seed_data(db: Session):

    existing = db.query(Employee).filter(Employee.username == "manager").first()

    if not existing:
        # Manager 1
        manager1 = Employee(
            username="manager",
            full_name="Manager User",
            role="MANAGER"
        )

        db.add(manager1)
        db.commit()
        db.refresh(manager1)

        employee1 = Employee(
            username="employee",
            full_name="Employee User",
            role="EMPLOYEE",
            manager_id=manager1.id
        )

        db.add(employee1)

        # Manager 2
        manager2 = Employee(
            username="manager2",
            full_name="Manager Two",
            role="MANAGER"
        )

        db.add(manager2)
        db.commit()
        db.refresh(manager2)

        # Employees under Manager 2
        employees = [
            Employee(
                username="employee2",
                full_name="Employee Two",
                role="EMPLOYEE",
                manager_id=manager2.id
            ),
            Employee(
                username="employee3",
                full_name="Employee Three",
                role="EMPLOYEE",
                manager_id=manager2.id
            ),
            Employee(
                username="employee4",
                full_name="Employee Four",
                role="EMPLOYEE",
                manager_id=manager2.id
            )
        ]

        db.add_all(employees)
        db.commit()

        # Create leave balances for all employees
        leave_types = [
            (LeaveType.CASUAL, 12),
            (LeaveType.SICK, 10),
            (LeaveType.EARNED, 15),
            (LeaveType.UNPAID, 0)
        ]

        all_employees = [employee1] + employees

        for emp in all_employees:
            db.refresh(emp)

            for leave_type, count in leave_types:
                balance = LeaveBalance(
                    employee_id=emp.id,
                    leave_type=leave_type.value,
                    allocated=count,
                    used=0,
                    remaining=count
                )
                db.add(balance)

        db.commit()

        print("Seed data created successfully")
    else:
        # Ensure all required leave types exist for all employees
        employee = db.query(Employee).filter(Employee.username == "employee").first()
        if employee:
            required_leave_types = [
                (LeaveType.CASUAL, 12),
                (LeaveType.SICK, 10),
                (LeaveType.EARNED, 15),
                (LeaveType.UNPAID, 0)
            ]

            for leave_type, count in required_leave_types:
                existing_balance = (
                    db.query(LeaveBalance)
                    .filter(
                        LeaveBalance.employee_id == employee.id,
                        LeaveBalance.leave_type == leave_type.value
                    )
                    .first()
                )

                if not existing_balance:
                    balance = LeaveBalance(
                        employee_id=employee.id,
                        leave_type=leave_type.value,
                        allocated=count if count != float('inf') else 0,
                        used=0,
                        remaining=count
                    )
                    db.add(balance)

            db.commit()
            print("Employee leave types ensured")