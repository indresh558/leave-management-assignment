# Leave Management System - Microservices

A comprehensive backend system for an Employee Leave Management Portal built with Python, FastAPI, PostgreSQL, RabbitMQ, and microservices architecture.

## 📋 Table of Contents
- [Overview](#overview)
- [Features](#features)
- [System Architecture](#system-architecture)
- [Technology Stack](#technology-stack)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Documentation](#api-documentation)
- [Service Details](#service-details)
- [Testing](#testing)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)
- [Notes](#notes)
- [Support](#support)

<a id="overview"></a>

## 🎯 Overview

This Leave Management System is a microservices-based backend that allows:
- **Employees** to apply for leaves, view balances, and track leave history
- **Managers** to approve/reject leave requests and view team leave status
- **Automated** leave balance deduction and notification publishing
- **Real-time** distributed tracing and observability

<a id="features"></a>

## ✨ Features

### Authentication & Authorization
- ✅ JWT-based authentication (24-hour tokens)
- ✅ Role-based access control (EMPLOYEE, MANAGER)
- ✅ Bcrypt password hashing with 12 rounds
- ✅ Token validation on all protected endpoints

### Leave Management
- ✅ Apply for leave with validations (date, overlap, balance check)
- ✅ Manager approval/rejection workflow
- ✅ Automatic leave balance deduction on approval
- ✅ Leave history with pagination and filtering
- ✅ Manager view of pending/approved/rejected requests

### Notifications
- ✅ RabbitMQ-based async notifications
- ✅ Event publishing on apply/approve/reject
- ✅ Notification history tracking
- ✅ Structured event payloads

### Infrastructure
- ✅ Service discovery via Consul
- ✅ Distributed tracing with OpenTelemetry + Jaeger
- ✅ Request logging and CORS middleware
- ✅ Health check endpoints for all services
- ✅ Docker containerization with Docker Compose

<a id="system-architecture"></a>

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Traefik Gateway                        │
│                    (Reverse Proxy)                          │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
    ┌────▼──────┐  ┌────▼──────┐  ┌────▼──────┐
    │   Auth    │  │ Employee  │  │  Leave    │
    │ Service   │  │ Service   │  │ Service   │
    │  :8001    │  │  :8002    │  │  :8003    │
    └────┬──────┘  └────┬──────┘  └────┬──────┘
         │              │              │
         └──────────────┼──────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
    ┌───▼───┐  ┌───────▼────────┐  ┌───▼──────┐
    │ Consul│  │  PostgreSQL    │  │RabbitMQ  │
    │:8500  │  │     :5432      │  │  :5672   │
    └───────┘  └────────────────┘  └─────┬────┘
                                         │
                                    ┌────▼──────────┐
                                    │ Notification  │
                                    │   Service     │
                                    │    :8004      │
                                    └───────────────┘
                                    
        ┌──────────────────────────────────┐
        │    OpenTelemetry + Jaeger        │
        │      Distributed Tracing         │
        │          :16686                  │
        └──────────────────────────────────┘
```

<a id="technology-stack"></a>

## 🛠️ Technology Stack

| Component | Technology |
|-----------|-----------|
| **Language** | Python 3.12 |
| **Framework** | FastAPI 0.104+ |
| **API Gateway** | Traefik |
| **Service Discovery** | Consul |
| **Database** | PostgreSQL 16 |
| **Message Queue** | RabbitMQ |
| **ORM** | SQLAlchemy |
| **Auth** | JWT (PyJWT) + Bcrypt |
| **Tracing** | OpenTelemetry (OTLP) + Jaeger |
| **Containerization** | Docker + Docker Compose |

<a id="prerequisites"></a>

## 📦 Prerequisites

- Docker Desktop (v20.10+)
- Docker Compose (v1.29+)
- Python 3.12+ (for local development)
- Git

<a id="quick-start"></a>

## 🚀 Quick Start

### 1. Clone Repository
```bash
cd leave_management
```

### 2. Start All Services with Docker Compose
```bash
docker-compose up -d
```

This will start:
- **PostgreSQL** - Database (port 5432)
- **RabbitMQ** - Message queue (port 5672, admin: 15672)
- **Consul** - Service discovery (port 8500)
- **Jaeger** - Distributed tracing (port 16686)
- **OTEL Collector** - Telemetry aggregator (port 4317/4318)
- **Traefik** - API Gateway (port 80)
- **Auth Service** - Port 8001
- **Employee Service** - Port 8002
- **Leave Service** - Port 8003
- **Notification Service** - Port 8004

### 3. Verify Services are Running
```bash
# Check all containers
docker-compose ps

# Check service health
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:8004/health
```

### 4. Login and Get JWT Token
```bash
curl -X POST http://localhost/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "employee",
    "password": "password123"
  }'

# Response:
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400,
  "role": "EMPLOYEE"
}
```

### 5. Use Token for Subsequent Requests
```bash
export TOKEN="<access_token_from_login>"

# Get leave balances
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:/employees/leave-balances

# Apply for leave
curl -X POST http://localhost/leaves/apply \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2026-06-15",
    "end_date": "2026-06-17",
    "leave_type": "CASUAL",
    "number_of_days": 3,
    "reason": "Personal work"
  }'
```

### 6. Stop Services
```bash
docker-compose down
```

<a id="configuration"></a>

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# Database
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/leave_management

# JWT
SECRET_KEY=your-super-secret-key-change-in-production

# RabbitMQ
RABBITMQ_URL=amqp://guest:guest@rabbitmq/

# Service Discovery
CONSUL_HOST=consul
CONSUL_PORT=8500

# Service Registration
SERVICE_HOST=auth-service
SERVICE_PORT=8001

# OpenTelemetry
OTEL_COLLECTOR_URL=http://otel-collector:4317

# Notifications
NOTIFICATION_MAX_RETRIES=3
NOTIFICATION_RETRY_DELAY=5
```

### Default Seed Users

**Employee Account:**
- Username: `employee`
- Password: `password123`
- Role: `EMPLOYEE`

**Manager Account:**
- Username: `manager`
- Password: `password123`
- Role: `MANAGER`


### Default Leave Allocations

When an employee is created, they receive:
- **Casual Leave:** 12 days
- **Sick Leave:** 10 days
- **Earned/Privilege Leave:** 15 days
- **Unpaid Leave:** 0 days

<a id="api-documentation"></a>

## 📚 API Documentation

### Authentication Endpoints

#### Login
```
POST /auth/login
Content-Type: application/json

{
  "username": "employee",
  "password": "password123"
}

Response: 200 OK
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400,
  "role": "EMPLOYEE"
}
```

### Employee Service Endpoints

#### Get Current User Info
```
GET /employees/me
Authorization: Bearer <token>

Response: 200 OK
{
  "id": 1,
  "username": "employee",
  "full_name": "John Doe",
  "role": "EMPLOYEE",
  "manager_id": 2
}
```

#### Get Leave Balances
```
GET /employees/leave-balances
Authorization: Bearer <token>

Response: 200 OK
[
  {
    "id": 1,
    "leave_type": "CASUAL",
    "allocated": 12,
    "used": 0,
    "remaining": 12
  },
  {
    "id": 2,
    "leave_type": "SICK",
    "allocated": 10,
    "used": 0,
    "remaining": 10
  }
]
```

#### Get Specific Leave Balance
```
GET /employees/{username}/leave-balance/{leave_type}

Response: 200 OK
{
  "leave_type": "CASUAL",
  "allocated": 12,
  "used": 0,
  "remaining": 12
}
```

### Leave Service Endpoints

#### Apply for Leave
```
POST /leaves/apply
Authorization: Bearer <token>
Content-Type: application/json

{
  "start_date": "2026-06-15",
  "end_date": "2026-06-17",
  "leave_type": "CASUAL",
  "number_of_days": 3,
  "reason": "Personal work"
}

Response: 200 OK
{
  "id": 1,
  "employee_username": "employee",
  "leave_type": "CASUAL",
  "start_date": "2026-06-15",
  "end_date": "2026-06-17",
  "number_of_days": 3,
  "reason": "Personal work",
  "status": "PENDING",
  "created_at": "2026-05-31T10:30:00"
}
```

#### Get Leave History
```
GET /leaves/history?skip=0&limit=10&status=PENDING
Authorization: Bearer <token>

Response: 200 OK
{
  "items": [...],
  "total": 5,
  "skip": 0,
  "limit": 10,
  "status_filter": "PENDING"
}
```

#### Get Pending Requests (Manager)
```
GET /leaves/pending?skip=0&limit=10&employee=employee&status=PENDING
Authorization: Bearer <token>

Response: 200 OK
{
  "items": [...],
  "total": 3,
  "skip": 0,
  "limit": 10,
  "filters": {
    "status": "PENDING",
    "employee": "employee",
    "start_date": null,
    "end_date": null
  }
}
```

#### Approve Leave Request
```
PUT /leaves/{leave_id}/approve
Authorization: Bearer <token>

Response: 200 OK
{
    "message": "Leave rejected successfully",
    "leave_id": 3,
    "status": "APPROVED"
}
```

#### Reject Leave Request
```
PUT /leaves/{leave_id}/reject
Authorization: Bearer <token>
Content-Type: application/json

{
  "comment": "Insufficient coverage"
}

Response: 200 OK
{
    "message": "Leave rejected successfully",
    "leave_id": 2,
    "status": "REJECTED"
}
```

<a id="service-details"></a>

## 🔧 Service Details

### Auth Service (Port 8001)
- Handles user login and JWT token generation
- Validates credentials against PostgreSQL
- Implements bcrypt password hashing
- Registers with Consul on startup

### Employee Service (Port 8002)
- Manages employee data and leave balances
- Provides endpoints for viewing/deducting leave
- Supports manager-employee relationships
- Returns team member information for managers

### Leave Service (Port 8003)
- Handles leave application and workflow
- Validates leave requests (dates, balance, overlap)
- Publishes events to RabbitMQ for approval/rejection
- Supports filtering and pagination

### Notification Service (Port 8004)
- Consumes RabbitMQ events
- Logs information related each events
- Implements retry logic for resilience

<a id="testing"></a>

## 🧪 Testing

### Using cURL

#### Scenario 1: Employee Applies for Leave
```bash
# 1. Login as employee
TOKEN=$(curl -s -X POST http://localhost/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"employee","password":"password123"}' \
  | jq -r '.access_token')

# 2. Check leave balance
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost/employees/leave-balances | jq

# 3. Apply for leave
curl -s -X POST http://localhost/leaves/apply \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2026-06-15",
    "end_date": "2026-06-17",
    "leave_type": "CASUAL",
    "number_of_days": 3,
    "reason": "Personal work"
  }' | jq
```

#### Scenario 2: Manager Approves Leave
```bash
# 1. Login as manager
MANAGER_TOKEN=$(curl -s -X POST http://localhost/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"manager","password":"password123"}' \
  | jq -r '.access_token')

# 2. Get pending requests
curl -s -H "Authorization: Bearer $MANAGER_TOKEN" \
  http://localhost/leaves/pending | jq

# 3. Approve leave (replace {leave_id} with actual ID)
curl -s -X PUT http://localhost/leaves/1/approve \
  -H "Authorization: Bearer $MANAGER_TOKEN" | jq
```

### Viewing Jaeger Traces
Open browser to `http://localhost:16686` and search for traces by service name.

### Checking RabbitMQ
Open browser to `http://localhost:15672` (credentials: guest/guest)

<a id="monitoring"></a>

## 🔍 Monitoring

### Distributed Tracing (Jaeger)
- URL: http://localhost:16686
- View request traces across services
- Identify performance bottlenecks

### Service Discovery (Consul)
- URL: http://localhost:8500
- View registered services and their health

### Logs
View service logs:
```bash
docker-compose logs -f auth-service
docker-compose logs -f employee-service
docker-compose logs -f leave-service
docker-compose logs -f notification-service
```

<a id="troubleshooting"></a>

## 🐛 Troubleshooting

### Services Won't Start
```bash
# Check logs
docker-compose logs

# Restart services
docker-compose restart

# Full rebuild
docker-compose down -v
docker-compose up --build
```

### Database Connection Issues
```bash
# Verify PostgreSQL is running
docker-compose ps postgres

# Check database exists
docker exec -it postgres psql -U postgres -l
```

### JWT Token Expired
- Tokens expire after 24 hours
- Login again to get a new token

### Service Discovery Issues
```bash
# Check Consul services
curl http://localhost:8500/v1/catalog/services

# Check service health
curl http://localhost:8500/v1/health/service/leave-service
```

<a id="notes"></a>

## 📝 Notes

- All services share a single PostgreSQL database (not production-recommended)
- Notifications are logged to console; implement real email/SMS integration for production
- RabbitMQ messages are persisted but not replicated
- Jaeger runs with in-memory storage (data lost on restart)
- For production, use environment-specific configurations

<a id="support"></a>

## 👥 Support

For issues or questions, refer to the system design documentation or check service logs.

---

**Last Updated:** May 31, 2026  
**Version:** 1.0.0
