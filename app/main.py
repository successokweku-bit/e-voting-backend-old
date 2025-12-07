from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException
from app.core.config import settings
from app.routes import auth, admin, elections, public
from app.models.database import engine
from app.models.models import Base
import os

# Create FastAPI app
app = FastAPI(
    title="E-Voting API",
    description="A secure e-voting system with role-based access control",
    version="2.0.0"
)

# Configure CORS - MUST be before routes and static files
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
)

# Create database tables
print("Creating database tables...")
Base.metadata.create_all(bind=engine)
print("Database tables created!")

# Create uploads directory structure
os.makedirs("uploads/profile_images", exist_ok=True)
os.makedirs("uploads/party_logos", exist_ok=True)
os.makedirs("uploads/candidate_images", exist_ok=True)

# Serve static files (AFTER CORS middleware)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(admin.router, prefix="/admin", tags=["Administration"])
app.include_router(elections.router, prefix="/api", tags=["Elections & Voting"])
app.include_router(public.router, prefix="/api", tags=["Public"])

# === CUSTOM EXCEPTION HANDLERS ===

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with structured response"""
    
    # If detail is already structured (dict), use it
    if isinstance(exc.detail, dict):
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail
        )
    
    # Otherwise, structure it
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": False,
            "data": None,
            "error": exc.detail,
            "message": get_error_message(exc.status_code)
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with structured response"""
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(x) for x in error["loc"])
        message = error["msg"]
        errors.append(f"{field}: {message}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": False,
            "data": None,
            "error": "; ".join(errors),
            "message": "Validation error"
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions with structured response"""
    print(f"Unhandled exception: {str(exc)}")  # Log for debugging
    import traceback
    traceback.print_exc()
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": False,
            "data": None,
            "error": "An unexpected error occurred",
            "message": "Internal server error"
        }
    )

def get_error_message(status_code: int) -> str:
    """Get friendly error message based on status code"""
    messages = {
        400: "Bad request",
        401: "Authentication required",
        403: "Access denied",
        404: "Resource not found",
        422: "Validation error",
        500: "Internal server error"
    }
    return messages.get(status_code, "An error occurred")

# === ENDPOINTS ===

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to E-Voting API",
        "status": "active",
        "version": "2.0.0"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "cors_enabled": True,
        "allowed_origins": settings.ALLOWED_ORIGINS
    }

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=True
    )