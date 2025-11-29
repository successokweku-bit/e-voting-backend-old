#!/usr/bin/env python3
"""
Script to create political parties for the e-voting system
"""

import sys
import os

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
from models import PoliticalParty
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_political_parties():
    """Create sample political parties"""
    db = SessionLocal()
    try:
        # Check if parties already exist
        existing_parties = db.query(PoliticalParty).count()
        if existing_parties > 0:
            logger.info("✅ Political parties already exist!")
            return
        
        # Define major political parties in Nigeria
        political_parties = [
            {
                "name": "All Progressives Congress",
                "abbreviation": "APC",
                "logo_url": "https://example.com/logos/apc.png",
                "founding_year": 2013,
                "ideology": "Progressivism, Conservatism",
                "description": "A major political party in Nigeria formed by the merger of several opposition parties.",
                "color_code": "#00A859"  # Green
            },
            {
                "name": "People's Democratic Party",
                "abbreviation": "PDP",
                "logo_url": "https://example.com/logos/pdp.png",
                "founding_year": 1998,
                "ideology": "Neoliberalism, Social democracy",
                "description": "One of the two major political parties in Nigeria, formerly the ruling party.",
                "color_code": "#D21034"  # Red
            },
            {
                "name": "Labour Party",
                "abbreviation": "LP",
                "logo_url": "https://example.com/logos/lp.png",
                "founding_year": 2002,
                "ideology": "Social democracy, Progressivism",
                "description": "A social democratic political party in Nigeria.",
                "color_code": "#FF0000"  # Bright Red
            },
            {
                "name": "All Progressives Grand Alliance",
                "abbreviation": "APGA",
                "logo_url": "https://example.com/logos/apga.png",
                "founding_year": 2002,
                "ideology": "Progressivism, Igbo interests",
                "description": "A political party in Nigeria with strong support in the Southeast.",
                "color_code": "#FFD700"  # Gold
            },
            {
                "name": "New Nigeria Peoples Party",
                "abbreviation": "NNPP",
                "logo_url": "https://example.com/logos/nnpp.png",
                "founding_year": 2022,
                "ideology": "Progressivism, Reformism",
                "description": "A political party in Nigeria focused on national rebirth and development.",
                "color_code": "#00CED1"  # Dark Turquoise
            },
            {
                "name": "Young Progressive Party",
                "abbreviation": "YPP",
                "logo_url": "https://example.com/logos/ypp.png",
                "founding_year": 2017,
                "ideology": "Progressivism, Youth empowerment",
                "description": "A youth-focused political party in Nigeria.",
                "color_code": "#800080"  # Purple
            }
        ]
        
        # Create party objects
        for party_data in political_parties:
            party = PoliticalParty(**party_data)
            db.add(party)
        
        # Commit to database
        db.commit()
        logger.info(f"✅ Created {len(political_parties)} political parties successfully!")
        
        # Display created parties
        parties = db.query(PoliticalParty).all()
        for party in parties:
            logger.info(f"   - {party.abbreviation}: {party.name}")
            
    except Exception as e:
        logger.error(f"❌ Error creating political parties: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_political_parties()