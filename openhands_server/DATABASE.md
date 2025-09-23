# Database Configuration

This document describes the database setup and usage in OpenHands Server.

## Overview

The OpenHands Server uses SQLAlchemy with async support for database operations. The database configuration is centralized in `openhands_server/database.py`.

## Configuration

### Environment Variables

- `DATABASE_URL`: Database connection string (default: `sqlite+aiosqlite:///./openhands.db`)
- `DATABASE_ECHO`: Enable SQL query logging (default: `false`)

### Supported Databases

- SQLite (default, using aiosqlite)
- PostgreSQL (using asyncpg)
- MySQL (using aiomysql)

## Usage

### In FastAPI Routes

Use the `get_async_session` dependency function:

```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from openhands_server.database import get_async_session

@app.get("/example")
async def example_route(session: AsyncSession = Depends(get_async_session)):
    # Your database operations here
    result = await session.execute(select(SomeModel))
    return result.scalars().all()
```

### Direct Usage

For operations outside of FastAPI routes:

```python
from openhands_server.database import AsyncSessionLocal

async def some_function():
    async with AsyncSessionLocal() as session:
        try:
            # Your database operations here
            result = await session.execute(select(SomeModel))
            await session.commit()
            return result.scalars().all()
        except Exception:
            await session.rollback()
            raise
```

## Models

All database models should inherit from the `Base` class defined in `database.py`:

```python
from openhands_server.database import Base
from sqlalchemy import Column, Integer, String

class MyModel(Base):
    __tablename__ = 'my_table'
    
    id = Column(Integer, primary_key=True)
    name = Column(String)
```

## Database Management

### Create Tables

```python
from openhands_server.database import create_tables

await create_tables()
```

### Drop Tables

```python
from openhands_server.database import drop_tables

await drop_tables()
```

## Migration

The project uses Alembic for database migrations. Migration files should be created and managed using standard Alembic commands.