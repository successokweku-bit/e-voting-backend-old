from fastapi import APIRouter
from app.schemas.schemas import StandardResponse

router = APIRouter()

@router.get("/states", response_model=StandardResponse[dict])
async def get_all_states():
    """Get list of all Nigerian states - Public endpoint"""
    try:
        from app.models.models import State
        
        states = [
            {
                "name": state.value,
                "code": state.name
            }
            for state in State
        ]
        
        return StandardResponse[dict](
            status=True,
            data={
                "total": len(states),
                "states": states
            },
            error=None,
            message="States retrieved successfully"
        )
        
    except Exception as e:
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Error retrieving states"
        )