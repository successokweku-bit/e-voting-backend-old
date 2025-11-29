from app.models.database import SessionLocal
from app.models.models import Election, Position, Candidate, ElectionType, State
from datetime import datetime, timedelta

def create_sample_data():
    db = SessionLocal()
    try:
        # Check if sample data already exists
        existing_elections = db.query(Election).count()
        if existing_elections > 0:
            print("✅ Sample data already exists!")
            return
        
        print("📝 Creating sample election data...")
        
        # Create a federal election
        federal_election = Election(
            title="2024 Presidential Election",
            description="Election for President and Vice President of Nigeria",
            election_type=ElectionType.FEDERAL,
            state=None,  # Federal elections have no state
            is_active=True,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30)
        )
        db.add(federal_election)
        db.commit()
        db.refresh(federal_election)
        
        # Create positions for federal election
        president_position = Position(
            title="President",
            description="President of the Federal Republic of Nigeria",
            election_id=federal_election.id
        )
        db.add(president_position)
        db.commit()
        db.refresh(president_position)
        
        # Create candidates for president
        candidate1 = Candidate(
            name="Ahmed Bello",
            bio="Experienced leader with 10 years in public service",
            position_id=president_position.id
        )
        candidate2 = Candidate(
            name="Chioma Adebayo", 
            bio="Youth advocate and technology enthusiast",
            position_id=president_position.id
        )
        db.add_all([candidate1, candidate2])
        
        # Create a state election
        lagos_election = Election(
            title="2024 Lagos State Gubernatorial Election",
            description="Election for Governor of Lagos State",
            election_type=ElectionType.STATE,
            state=State.LAGOS,
            is_active=True,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30)
        )
        db.add(lagos_election)
        db.commit()
        db.refresh(lagos_election)
        
        # Create positions for state election
        governor_position = Position(
            title="Governor",
            description="Governor of Lagos State",
            election_id=lagos_election.id
        )
        db.add(governor_position)
        db.commit()
        db.refresh(governor_position)
        
        # Create candidates for governor
        candidate3 = Candidate(
            name="Tunde Williams",
            bio="Former Commissioner for Finance",
            position_id=governor_position.id
        )
        candidate4 = Candidate(
            name="Aisha Mohammed",
            bio="Education reform advocate",
            position_id=governor_position.id
        )
        db.add_all([candidate3, candidate4])
        
        db.commit()

        # Get political parties
        parties = db.query(PoliticalParty).all()
        if not parties:
            logger.error("❌ No political parties found. Please run create_political_parties.py first!")
            return
        
        # Create Federal Positions (President, Vice President)
        federal_positions = [
            Position(title="President", level="federal", election_id=federal_election.id),
            Position(title="Vice President", level="federal", election_id=federal_election.id),
        ]
        
        # Create State Positions (Governor, Deputy Governor)
        state_positions = [
            Position(title="Governor", level="state", election_id=state_election.id),
            Position(title="Deputy Governor", level="state", election_id=state_election.id),
        ]
        
        # Add all positions
        for position in federal_positions + state_positions:
            db.add(position)
        db.commit()
        
        # Refresh to get IDs
        for position in federal_positions + state_positions:
            db.refresh(position)
        
        # Create Candidates with party affiliations
        candidates = [
            # Presidential Candidates
            Candidate(
                name="Bola Ahmed Tinubu",
                position_id=federal_positions[0].id,
                party_id=parties[0].id,  # APC
                bio="Former Governor of Lagos State",
                photo_url="https://example.com/photos/tinubu.jpg"
            ),
            Candidate(
                name="Atiku Abubakar", 
                position_id=federal_positions[0].id,
                party_id=parties[1].id,  # PDP
                bio="Former Vice President of Nigeria",
                photo_url="https://example.com/photos/atiku.jpg"
            ),
            Candidate(
                name="Peter Obi",
                position_id=federal_positions[0].id, 
                party_id=parties[2].id,  # LP
                bio="Former Governor of Anambra State",
                photo_url="https://example.com/photos/peter-obi.jpg"
            ),
            
            # Gubernatorial Candidates
            Candidate(
                name="Babajide Sanwo-Olu",
                position_id=state_positions[0].id,
                party_id=parties[0].id,  # APC
                bio="Incumbent Governor of Lagos State",
                photo_url="https://example.com/photos/sanwo-olu.jpg"
            ),
            Candidate(
                name="Abdul-Azeez Adediran",
                position_id=state_positions[0].id,
                party_id=parties[1].id,  # PDP  
                bio="PDP Gubernatorial Candidate",
                photo_url="https://example.com/photos/adediran.jpg"
            )
        ]
        
        for candidate in candidates:
            db.add(candidate)
        db.commit()
        
        print("✅ Sample data created successfully!")
        print(f"   - Federal Election: {federal_election.title}")
        print(f"   - State Election: {lagos_election.title}")
        print(f"   - Total Positions: 2")
        print(f"   - Total Candidates: 4")
        
    except Exception as e:
        print(f"❌ Error creating sample data: {e}")
        db.rollback()
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    create_sample_data()