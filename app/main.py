from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
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