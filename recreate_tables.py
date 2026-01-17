from app.models.database import engine
from app.models.models import Base

def recreate_tables():
    print("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    
    print("Creating tables with new schema...")
    Base.metadata.create_all(bind=engine)
    
    print("Database schema updated successfully!")

if __name__ == "__main__":
    recreate_tables()