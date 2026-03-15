from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_required
from app.models.models import User
from app.schemas.schemas import ProjectCreate, ProjectOut, MessageOut
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    svc = ProjectService(db)
    project = await svc.create(data, owner=current_user)
    count = await svc.get_link_count(project.id)
    return ProjectOut(
        id=project.id,
        name=project.name,
        description=project.description,
        owner_id=project.owner_id,
        created_at=project.created_at,
        link_count=count,
    )


@router.get("", response_model=List[ProjectOut])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    svc = ProjectService(db)
    projects = await svc.list_for_user(owner=current_user)
    result = []
    for p in projects:
        count = await svc.get_link_count(p.id)
        result.append(ProjectOut(
            id=p.id, name=p.name, description=p.description,
            owner_id=p.owner_id, created_at=p.created_at, link_count=count,
        ))
    return result


@router.delete("/{project_id}", response_model=MessageOut)
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    svc = ProjectService(db)
    deleted = await svc.delete(project_id, owner=current_user)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
    return MessageOut(message=f"Project {project_id} deleted")
