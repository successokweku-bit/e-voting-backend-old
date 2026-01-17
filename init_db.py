from app.models.database import engine
from app.models.models import Base

def init_database():
    """Initialize the database with all tables"""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")
    print("Database file: evoting.db")

if __name__ == "__main__":
    init_database()