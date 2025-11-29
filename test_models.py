from app.schemas.schemas import UserResponse
from datetime import datetime

# Test that the model can be created without deprecated methods
test_data = {
    "id": 1,
    "nin": "12345678901",
    "email": "test@example.com",
    "full_name": "Test User",
    "state_of_residence": "Abia",
    "is_active": True,
    "is_verified": False,
    "created_at": datetime.now()
}

try:
    user = UserResponse.model_validate(test_data)
    print("✅ UserResponse model works correctly!")
    print(f"User: {user.email}, State: {user.state_of_residence}")
except Exception as e:
    print(f"❌ Error: {e}")