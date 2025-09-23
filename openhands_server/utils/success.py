from pydantic import BaseModel


class Success(BaseModel):
    success: bool = True
