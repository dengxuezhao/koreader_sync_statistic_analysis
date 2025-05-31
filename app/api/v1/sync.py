"""
同步API端点

实现KOReader兼容的同步API，支持阅读进度同步。
严格遵循kosync协议以确保KOReader兼容性。
"""

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, status, Form, Query
from sqlalchemy import select, and_, func
from sqlalchemy.exc import IntegrityError

from app.api.deps import DbSession, CurrentUser, CurrentDeviceUser, get_user_by_any_auth
from app.core.security import security
from app.models import User, Device, SyncProgress, Book
from app.schemas.sync import (
    SyncProgressCreate,
    SyncProgressUpdate,
    SyncProgressResponse,
    KosyncProgress,
    KosyncProgressResponse,
    KosyncErrorResponse,
    SyncProgressList
)

router = APIRouter()
logger = logging.getLogger(__name__)


# KOReader kosync兼容端点（主要API）
@router.put("/progress", response_model=KosyncProgressResponse, summary="上传同步进度")
async def upload_sync_progress(
    # 认证依赖
    current_user: CurrentUser,
    db: DbSession,
    # KOReader kosync使用Form数据格式
    document: str = Form(..., description="文档名称/路径"),
    progress: str = Form(..., description="阅读进度"),
    percentage: float = Form(..., description="百分比"),
    device: Optional[str] = Form(None, description="设备标识"),
    device_id: Optional[str] = Form(None, description="设备ID"),
    page: Optional[int] = Form(None, description="页码"),
    pos: Optional[str] = Form(None, description="位置信息"),
    chapter: Optional[str] = Form(None, description="章节信息"),
    timestamp: Optional[int] = Form(None, description="时间戳")
) -> Any:
    """
    上传同步进度 - KOReader kosync兼容
    
    接收KOReader设备上传的阅读进度数据。
    """
    try:
        # 创建同步进度数据
        sync_data = SyncProgressCreate(
            document=document,
            progress=progress,
            percentage=percentage,
            device=device,
            device_id=device_id,
            page=page,
            pos=pos,
            chapter=chapter,
            timestamp=timestamp
        )
        
        # 查找现有同步进度
        result = await db.execute(
            select(SyncProgress).where(
                and_(
                    SyncProgress.user_id == current_user.id,
                    SyncProgress.document == sync_data.document
                )
            )
        )
        existing_progress = result.scalar_one_or_none()
        
        if existing_progress:
            # 更新现有进度
            existing_progress.update_progress(
                progress=sync_data.progress,
                percentage=sync_data.percentage,
                page=sync_data.page,
                pos=sync_data.pos,
                chapter=sync_data.chapter
            )
            existing_progress.device_name = device
            existing_progress.device = device
            sync_progress = existing_progress
        else:
            # 创建新的同步进度
            sync_progress = SyncProgress(
                user_id=current_user.id,
                document=sync_data.document,
                progress=sync_data.progress,
                percentage=sync_data.percentage,
                device_name=device,
                device=device,
                page=sync_data.page,
                pos=sync_data.pos,
                chapter=sync_data.chapter
            )
            db.add(sync_progress)
        
        await db.commit()
        await db.refresh(sync_progress)
        
        logger.info(f"同步进度上传成功: {document} ({current_user.username})")
        
        # 返回kosync兼容格式
        return KosyncProgressResponse.from_sync_progress(sync_progress)
        
    except Exception as e:
        await db.rollback()
        logger.error(f"同步进度上传失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="同步进度上传失败"
        )


@router.get("/progress/{document}", response_model=KosyncProgressResponse, summary="获取文档同步进度")
async def get_document_progress(
    document: str,
    current_user: CurrentUser,
    db: DbSession
) -> Any:
    """
    获取文档同步进度 - KOReader kosync兼容
    
    根据文档名称获取用户的阅读进度。
    """
    # 查找同步进度
    result = await db.execute(
        select(SyncProgress).where(
            and_(
                SyncProgress.user_id == current_user.id,
                SyncProgress.document == document
            )
        )
    )
    sync_progress = result.scalar_one_or_none()
    
    if not sync_progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到该文档的同步进度"
        )
    
    logger.info(f"获取同步进度: {document} ({current_user.username})")
    
    # 返回kosync兼容格式
    return KosyncProgressResponse.from_sync_progress(sync_progress)


@router.post("/progress", response_model=KosyncProgressResponse, summary="同步进度")
async def sync_progress(
    # 认证依赖
    current_user: CurrentUser,
    db: DbSession,
    # KOReader kosync可能使用POST进行双向同步
    document: str = Form(..., description="文档名称/路径"),
    progress: Optional[str] = Form(None, description="阅读进度"),
    percentage: Optional[float] = Form(None, description="百分比"),
    device: Optional[str] = Form(None, description="设备标识"),
    device_id: Optional[str] = Form(None, description="设备ID"),
    page: Optional[int] = Form(None, description="页码"),
    pos: Optional[str] = Form(None, description="位置信息"),
    chapter: Optional[str] = Form(None, description="章节信息"),
    timestamp: Optional[int] = Form(None, description="时间戳")
) -> Any:
    """
    同步进度 - KOReader kosync兼容
    
    POST方式的进度同步，支持上传和获取。
    """
    # 查找现有同步进度
    result = await db.execute(
        select(SyncProgress).where(
            and_(
                SyncProgress.user_id == current_user.id,
                SyncProgress.document == document
            )
        )
    )
    existing_progress = result.scalar_one_or_none()
    
    # 如果提供了进度数据，执行上传操作
    if progress is not None and percentage is not None:
        try:
            sync_data = SyncProgressCreate(
                document=document,
                progress=progress,
                percentage=percentage,
                device=device,
                device_id=device_id,
                page=page,
                pos=pos,
                chapter=chapter,
                timestamp=timestamp
            )
            
            if existing_progress:
                # 更新现有进度
                existing_progress.update_progress(
                    progress=sync_data.progress,
                    percentage=sync_data.percentage,
                    page=sync_data.page,
                    pos=sync_data.pos,
                    chapter=sync_data.chapter
                )
                existing_progress.device_name = device
                existing_progress.device = device
                sync_progress = existing_progress
            else:
                # 创建新的同步进度
                sync_progress = SyncProgress(
                    user_id=current_user.id,
                    document=sync_data.document,
                    progress=sync_data.progress,
                    percentage=sync_data.percentage,
                    device_name=device,
                    device=device,
                    page=sync_data.page,
                    pos=sync_data.pos,
                    chapter=sync_data.chapter
                )
                db.add(sync_progress)
            
            await db.commit()
            await db.refresh(sync_progress)
            
            logger.info(f"POST同步进度上传: {document} ({current_user.username})")
            
        except Exception as e:
            await db.rollback()
            logger.error(f"POST同步进度失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="同步进度失败"
            )
    else:
        # 仅获取现有进度
        if not existing_progress:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="未找到该文档的同步进度"
            )
        sync_progress = existing_progress
        
        logger.info(f"POST获取同步进度: {document} ({current_user.username})")
    
    # 返回kosync兼容格式
    return KosyncProgressResponse.from_sync_progress(sync_progress)


# 现代化API端点（用于Web界面等）
@router.get("/progress", response_model=SyncProgressList, summary="获取用户同步进度列表")
async def get_user_sync_progress(
    current_user: CurrentUser,
    db: DbSession,
    page: int = Query(default=1, ge=1, description="页码"),
    size: int = Query(default=20, ge=1, le=100, description="每页大小"),
    document_filter: Optional[str] = Query(None, description="文档名称过滤")
) -> Any:
    """
    获取用户所有同步进度
    
    现代化API，支持分页和过滤。
    """
    # 构建查询
    query = select(SyncProgress).where(SyncProgress.user_id == current_user.id)
    
    # 添加文档名称过滤
    if document_filter:
        query = query.where(SyncProgress.document.ilike(f"%{document_filter}%"))
    
    # 计算总数
    count_query = select(func.count(SyncProgress.id)).where(SyncProgress.user_id == current_user.id)
    if document_filter:
        count_query = count_query.where(SyncProgress.document.ilike(f"%{document_filter}%"))
    
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()
    
    # 应用分页
    query = query.order_by(SyncProgress.last_sync_at.desc())
    query = query.offset((page - 1) * size).limit(size)
    
    # 执行查询
    result = await db.execute(query)
    sync_progress_list = result.scalars().all()
    
    # 转换为响应格式
    items = []
    for sp in sync_progress_list:
        items.append(SyncProgressResponse.model_validate(sp))
    
    logger.info(f"获取同步进度列表: {len(items)}项 ({current_user.username})")
    
    return SyncProgressList(
        total=total,
        items=items,
        page=page,
        size=size
    )


@router.get("/progress/detail/{progress_id}", response_model=SyncProgressResponse, summary="获取同步进度详情")
async def get_sync_progress_detail(
    progress_id: int,
    current_user: CurrentUser,
    db: DbSession
) -> Any:
    """
    获取同步进度详情
    """
    result = await db.execute(
        select(SyncProgress).where(
            and_(
                SyncProgress.id == progress_id,
                SyncProgress.user_id == current_user.id
            )
        )
    )
    sync_progress = result.scalar_one_or_none()
    
    if not sync_progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到同步进度记录"
        )
    
    return SyncProgressResponse.model_validate(sync_progress)


@router.put("/progress/detail/{progress_id}", response_model=SyncProgressResponse, summary="更新同步进度")
async def update_sync_progress_detail(
    progress_id: int,
    update_data: SyncProgressUpdate,
    current_user: CurrentUser,
    db: DbSession
) -> Any:
    """
    更新同步进度详情
    """
    result = await db.execute(
        select(SyncProgress).where(
            and_(
                SyncProgress.id == progress_id,
                SyncProgress.user_id == current_user.id
            )
        )
    )
    sync_progress = result.scalar_one_or_none()
    
    if not sync_progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到同步进度记录"
        )
    
    try:
        # 更新字段
        if update_data.progress is not None:
            sync_progress.progress = update_data.progress
        if update_data.percentage is not None:
            sync_progress.percentage = update_data.percentage
        if update_data.page is not None:
            sync_progress.page = update_data.page
        if update_data.pos is not None:
            sync_progress.pos = update_data.pos
        if update_data.chapter is not None:
            sync_progress.chapter = update_data.chapter
        
        sync_progress.last_sync_at = datetime.utcnow()
        sync_progress.sync_count += 1
        sync_progress.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(sync_progress)
        
        logger.info(f"更新同步进度: {progress_id} ({current_user.username})")
        
        return SyncProgressResponse.model_validate(sync_progress)
        
    except Exception as e:
        await db.rollback()
        logger.error(f"更新同步进度失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新同步进度失败"
        )


@router.delete("/progress/detail/{progress_id}", summary="删除同步进度")
async def delete_sync_progress(
    progress_id: int,
    current_user: CurrentUser,
    db: DbSession
) -> Any:
    """
    删除同步进度记录
    """
    result = await db.execute(
        select(SyncProgress).where(
            and_(
                SyncProgress.id == progress_id,
                SyncProgress.user_id == current_user.id
            )
        )
    )
    sync_progress = result.scalar_one_or_none()
    
    if not sync_progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到同步进度记录"
        )
    
    try:
        await db.delete(sync_progress)
        await db.commit()
        
        logger.info(f"删除同步进度: {progress_id} ({current_user.username})")
        
        return {"message": "同步进度删除成功"}
        
    except Exception as e:
        await db.rollback()
        logger.error(f"删除同步进度失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除同步进度失败"
        )


# 设备同步状态端点
@router.get("/devices/status", summary="获取设备同步状态")
async def get_device_sync_status(
    current_user: CurrentUser,
    db: DbSession
) -> Any:
    """
    获取用户所有设备的同步状态
    """
    # 获取用户设备
    result = await db.execute(
        select(Device).where(Device.user_id == current_user.id)
    )
    devices = result.scalars().all()
    
    device_status = []
    for device in devices:
        # 统计设备同步进度数量
        progress_count_result = await db.execute(
            select(func.count(SyncProgress.id)).where(
                and_(
                    SyncProgress.user_id == current_user.id,
                    SyncProgress.device_name == device.device_name
                )
            )
        )
        progress_count = progress_count_result.scalar_one()
        
        device_status.append({
            "device_id": device.id,
            "device_name": device.device_name,
            "model": device.model,
            "last_sync_at": device.last_sync_at.isoformat() if device.last_sync_at else None,
            "sync_count": device.sync_count,
            "progress_count": progress_count,
            "is_recently_active": device.is_recently_active,
            "sync_enabled": device.sync_enabled
        })
    
    return {
        "user_id": current_user.id,
        "username": current_user.username,
        "devices": device_status,
        "total_devices": len(devices)
    }


# 批量操作端点
@router.post("/progress/batch", summary="批量上传同步进度")
async def batch_upload_sync_progress(
    progress_list: list[SyncProgressCreate],
    current_user: CurrentUser,
    db: DbSession
) -> Any:
    """
    批量上传同步进度
    
    支持一次性上传多个文档的阅读进度。
    """
    results = []
    errors = []
    
    for i, sync_data in enumerate(progress_list):
        try:
            # 查找现有同步进度
            result = await db.execute(
                select(SyncProgress).where(
                    and_(
                        SyncProgress.user_id == current_user.id,
                        SyncProgress.document == sync_data.document
                    )
                )
            )
            existing_progress = result.scalar_one_or_none()
            
            if existing_progress:
                # 更新现有进度
                existing_progress.update_progress(
                    progress=sync_data.progress,
                    percentage=sync_data.percentage,
                    page=sync_data.page,
                    pos=sync_data.pos,
                    chapter=sync_data.chapter
                )
                existing_progress.device_name = sync_data.device
                existing_progress.device = sync_data.device
                sync_progress = existing_progress
            else:
                # 创建新的同步进度
                sync_progress = SyncProgress(
                    user_id=current_user.id,
                    document=sync_data.document,
                    progress=sync_data.progress,
                    percentage=sync_data.percentage,
                    device_name=sync_data.device,
                    device=sync_data.device,
                    page=sync_data.page,
                    pos=sync_data.pos,
                    chapter=sync_data.chapter
                )
                db.add(sync_progress)
            
            await db.flush()  # 刷新但不提交
            results.append({
                "index": i,
                "document": sync_data.document,
                "status": "success"
            })
            
        except Exception as e:
            logger.error(f"批量上传第{i}项失败: {e}")
            errors.append({
                "index": i,
                "document": sync_data.document,
                "error": str(e)
            })
    
    try:
        await db.commit()
        logger.info(f"批量上传同步进度: {len(results)}成功, {len(errors)}失败 ({current_user.username})")
        
        return {
            "total": len(progress_list),
            "success": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors
        }
        
    except Exception as e:
        await db.rollback()
        logger.error(f"批量上传提交失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="批量上传提交失败"
        ) 