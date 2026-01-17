# E-Voting Backend API

> **⚠️ EDUCATIONAL PROJECT NOTICE**
> 
> This is a student project developed for educational purposes only. It is NOT intended for use in real elections or production environments. This project demonstrates concepts in web development, database management, and security practices as part of academic coursework.

A secure electronic voting system built with FastAPI, featuring encrypted vote storage, anonymous voting, and comprehensive audit trails.

## Features

- Secure user authentication with JWT tokens
- Encrypted vote storage with receipt generation
- Anonymous voting with voter verification
- Multiple election types (Federal, State, Local)
- Political party and candidate management
- Real-time election results
- Vote audit trail and verification
- Email notifications for vote receipts

## Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Authentication**: JWT (JSON Web Tokens)
- **Encryption**: Custom secure voting service
- **Email**: SMTP integration
- **File Upload**: Local storage with configurable paths

## Prerequisites

- Python 3.8+
- PostgreSQL 12+
- pip (Python package manager)
- Virtual environment (recommended)

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd evoting-backend
```

### 2. Create and activate virtual environment

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Linux/Mac:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

**Required packages include:**
- fastapi
- uvicorn
- sqlalchemy
- psycopg2-binary
- python-jose[cryptography]
- passlib[bcrypt]
- python-multipart
- cryptography
- pycryptodome

### 4. Database Setup

Create a PostgreSQL database:

```sql
CREATE DATABASE evoting_db;
CREATE USER evoting_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE evoting_db TO evoting_user;
```

### 5. Environment Configuration

Create a `.env` file in the root directory:

```env
# Database
DATABASE_URL=postgresql://evoting_user:your_password@localhost/evoting_db

# JWT Settings
SECRET_KEY=your-secret-key-here-generate-with-openssl
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Vote Encryption Keys (Generate using generate_keys.py)
VOTE_ENCRYPTION_KEY=your-generated-encryption-key
ANONYMIZATION_SALT=your-generated-salt
COMMITMENT_SECRET=your-generated-secret

# Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=noreply@evoting.com

# CORS
ALLOWED_ORIGINS=["http://localhost:3000", "http://localhost:5173"]

# App Settings
APP_NAME=E-Voting System
DEBUG=True
```

**Generate encryption keys:**

The project includes a key generation script. Run it once:

```bash
python generate_keys.py
```

This will:
- Generate a Fernet encryption key for vote data
- Generate an HMAC salt for voter anonymization
- Generate a commitment secret
- Create a `.env.example` file
- Test the encryption to ensure it works

Copy the generated keys from the terminal output into your `.env` file.

**Generate JWT secret key:**
```bash
openssl rand -hex 32
```

### 6. Run Database Migrations

```bash
# Initialize database tables
python -m app.models.database
```

Or create migration script:

```python
# migrate.py
from app.models.database import Base, engine
from app.models.models import *

Base.metadata.create_all(bind=engine)
```

Then run:
```bash
python migrate.py
```

### 7. Create Upload Directories

```bash
mkdir -p uploads/profile_images
mkdir -p uploads/party_logos
```

## Running the Application

### Development Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

### Production Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Documentation

Once the server is running, access the interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Project Structure

```
evoting-backend/
├── app/
│   ├── core/
│   │   ├── config.py           # Configuration settings
│   │   ├── security.py         # JWT and password hashing
│   │   ├── roles.py            # Role-based access control
│   │   └── file_upload.py      # File handling
│   ├── models/
│   │   ├── database.py         # Database connection
│   │   └── models.py           # SQLAlchemy models
│   ├── routes/
│   │   ├── auth.py             # Authentication endpoints
│   │   ├── election.py         # Election endpoints
│   │   └── admin.py            # Admin endpoints
│   ├── schemas/
│   │   └── schemas.py          # Pydantic models
│   ├── services/
│   │   ├── auth.py             # Auth business logic
│   │   ├── secure_voting_service.py  # Voting encryption
│   │   └── email_service.py    # Email notifications
│   └── main.py                 # Application entry point
├── uploads/                    # File storage
├── generate_keys.py            # Encryption key generator
├── .env                        # Environment variables
├── .env.example                # Environment template
├── .gitignore                  # Git ignore file
├── requirements.txt            # Python dependencies
└── README.md
```

## Key Endpoints

### Authentication
- `POST /auth/register` - User registration
- `POST /auth/token` - Login
- `POST /auth/forgot-password` - Password reset request
- `POST /auth/reset-password` - Reset password with token
- `GET /auth/me` - Get current user

### Elections
- `GET /elections/active` - List active elections
- `GET /elections/{id}` - Get election details
- `GET /elections/{id}/results` - View results
- `POST /elections/{id}/positions/{position_id}/vote-secure` - Cast vote

### Voting
- `GET /my-votes` - User's voting history
- `POST /vote/details-by-receipt` - Verify vote receipt
- `GET /elections/{id}/my-voting-status` - Check voting status

## Default User Roles

- **Super Admin**: Full system access
- **Admin**: Election management
- **User**: Voting capabilities

## Security Features

- Password hashing with bcrypt
- JWT token authentication
- Anonymous voter IDs using SHA-256 HMAC
- Encrypted vote storage with Fernet (AES-128)
- Vote receipt generation
- IP address logging
- Audit trail tracking
- Cryptographic commitments for vote integrity

**Important**: The encryption implementation in this project is for educational demonstration only. Production voting systems require professionally audited cryptographic implementations and security reviews.

## Testing

Create test users:

```python
# In Python shell or test script
from app.models.database import SessionLocal
from app.services.auth import AuthService
from app.schemas.schemas import UserCreate

db = SessionLocal()

user_data = UserCreate(
    email="test@example.com",
    password="testpassword123",
    full_name="Test User",
    phone_number="1234567890"
)

user = AuthService.create_user(db, user_data)
```

## Common Issues

### Database Connection Error
- Verify PostgreSQL is running
- Check DATABASE_URL in .env file
- Ensure database exists

### Email Not Sending
- Verify SMTP credentials
- For Gmail, use App Password instead of regular password
- Check firewall/antivirus settings

### File Upload Issues
- Ensure upload directories exist
- Check file permissions
- Verify disk space

### Encryption Key Issues
- Run `generate_keys.py` if keys are missing
- Ensure all three encryption keys are in .env
- Never share or commit encryption keys
- If keys are lost, encrypted votes cannot be recovered

## Environment Variables Reference

| Variable | Description | Example |
|----------|-------------|---------|
| DATABASE_URL | PostgreSQL connection string | postgresql://user:pass@localhost/db |
| SECRET_KEY | JWT signing key | random-32-char-hex |
| ACCESS_TOKEN_EXPIRE_MINUTES | Token expiry time | 30 |
| VOTE_ENCRYPTION_KEY | Fernet key for vote encryption | Generated by generate_keys.py |
| ANONYMIZATION_SALT | HMAC salt for voter IDs | Generated by generate_keys.py |
| COMMITMENT_SECRET | Secret for vote commitments | Generated by generate_keys.py |
| SMTP_HOST | Email server | smtp.gmail.com |
| SMTP_PORT | Email port | 587 |
| SMTP_USER | Email username | your@email.com |
| SMTP_PASSWORD | Email password | app-password |
| ALLOWED_ORIGINS | CORS origins | ["http://localhost:3000"] |

## Contributing

This is an educational project. Feel free to fork and experiment for learning purposes.

## License

MIT License - Educational Use Only

**Disclaimer**: This project is developed as part of academic coursework and is not certified or audited for use in real-world voting systems. Real electoral systems require extensive security audits, legal compliance, and professional-grade infrastructure.

## Academic Purpose

This project was created to demonstrate:
- RESTful API design with FastAPI
- Database modeling and relationships
- Authentication and authorization
- Basic cryptographic concepts
- Web security best practices
- Software development lifecycle

**Not suitable for:**
- Production deployments
- Real elections or voting
- Handling sensitive real-world data
- Mission-critical applications

## Support

For academic questions or project-related issues, please open an issue in the repository.

**Note**: This is a learning project and may contain bugs or security vulnerabilities. Use only in controlled educational environments.

## Changelog

### Version 1.0.0
- Initial release
- Core voting functionality
- Secure vote encryption
- Email notifications
- Admin panel