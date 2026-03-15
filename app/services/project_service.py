from typing import List, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Project, Link, User
from app.schemas.schemas import ProjectCreate


class ProjectService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: ProjectCreate, owner: User) -> Project:
        project = Project(name=data.name, description=data.description, owner_id=owner.id)
        self.db.add(project)
        await self.db.flush()
        await self.db.refresh(project)
        return project

    async def list_for_user(self, owner: User) -> List[Project]:
        result = await self.db.execute(
            select(Project).where(Project.owner_id == owner.id)
        )
        return result.scalars().all()

    async def get(self, project_id: int, owner: User) -> Optional[Project]:
        result = await self.db.execute(
            select(Project).where(Project.id == project_id, Project.owner_id == owner.id)
        )
        return result.scalar_one_or_none()

    async def delete(self, project_id: int, owner: User) -> bool:
        project = await self.get(project_id, owner)
        if not project:
            return False
        await self.db.delete(project)
        return True

    async def get_link_count(self, project_id: int) -> int:
        result = await self.db.execute(
            select(func.count()).where(Link.project_id == project_id, Link.is_active == True)
        )
        return result.scalar_one() or 0
