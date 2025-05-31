"""
同步API测试

测试KOReader kosync协议兼容性、进度同步和设备管理功能。
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import User, Device, SyncProgress


class TestKOReaderSyncCompatibility:
    """KOReader同步兼容性测试"""
    
    @pytest.mark.asyncio
    async def test_kosync_progress_upload_form_data(self, client: AsyncClient, test_user: User, test_device: Device):
        """测试kosync进度上传（Form数据格式）"""
        # 模拟KOReader的kosync插件请求
        form_data = {
            "document": "test_book.epub",
            "progress": "0.15",
            "percentage": "15.0",
            "device": test_device.device_name,
            "device_id": test_device.device_id,
            "user": test_user.username
        }
        
        response = await client.put("/api/v1/syncs/progress", data=form_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["document"] == "test_book.epub"
        assert float(data["progress"]) == 0.15
        assert float(data["percentage"]) == 15.0
        assert data["device"] == test_device.device_name
    
    @pytest.mark.asyncio
    async def test_kosync_progress_get(self, client: AsyncClient, test_user: User, test_device: Device, test_db: AsyncSession):
        """测试kosync进度获取"""
        # 先创建一个同步进度记录
        sync_progress = SyncProgress(
            user_id=test_user.id,
            device_id=test_device.id,
            document="test_book.epub",
            progress=0.25,
            percentage=25.0,
            timestamp=1640995200  # 固定时间戳
        )
        test_db.add(sync_progress)
        await test_db.commit()
        
        # 使用kosync格式的查询参数
        params = {
            "user": test_user.username,
            "device": test_device.device_name
        }
        
        response = await client.get("/api/v1/syncs/progress/test_book.epub", params=params)
        
        assert response.status_code == 200
        data = response.json()
        assert data["document"] == "test_book.epub"
        assert float(data["progress"]) == 0.25
        assert float(data["percentage"]) == 25.0
        assert data["timestamp"] == 1640995200
    
    @pytest.mark.asyncio
    async def test_kosync_progress_post_sync(self, client: AsyncClient, test_user: User, test_device: Device):
        """测试kosync双向同步"""
        form_data = {
            "document": "sync_book.epub",
            "progress": "0.35",
            "percentage": "35.0",
            "device": test_device.device_name,
            "device_id": test_device.device_id,
            "user": test_user.username,
            "timestamp": "1640995300"
        }
        
        response = await client.post("/api/v1/syncs/progress", data=form_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["document"] == "sync_book.epub"
        assert float(data["progress"]) == 0.35
        assert data["sync_status"] == "updated"
    
    @pytest.mark.asyncio
    async def test_kosync_device_validation(self, client: AsyncClient):
        """测试kosync设备验证"""
        # 没有device参数的请求应该失败
        form_data = {
            "document": "test_book.epub",
            "progress": "0.15",
            "user": "testuser"
        }
        
        response = await client.put("/api/v1/syncs/progress", data=form_data)
        
        assert response.status_code == 400
        assert "device" in response.json()["detail"].lower()


class TestModernSyncAPI:
    """现代同步API测试"""
    
    @pytest.mark.asyncio
    async def test_get_user_sync_progress_list(self, client: AsyncClient, auth_headers: dict, test_user: User, test_device: Device, test_db: AsyncSession):
        """测试获取用户同步进度列表"""
        # 创建多个同步进度记录
        progresses = []
        for i in range(3):
            progress = SyncProgress(
                user_id=test_user.id,
                device_id=test_device.id,
                document=f"book_{i}.epub",
                progress=0.1 * (i + 1),
                percentage=10.0 * (i + 1)
            )
            progresses.append(progress)
            test_db.add(progress)
        
        await test_db.commit()
        
        response = await client.get("/api/v1/syncs/progress", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3
        assert "pagination" in data
    
    @pytest.mark.asyncio
    async def test_get_sync_progress_detail(self, client: AsyncClient, auth_headers: dict, test_user: User, test_device: Device, test_db: AsyncSession):
        """测试获取同步进度详情"""
        sync_progress = SyncProgress(
            user_id=test_user.id,
            device_id=test_device.id,
            document="detail_book.epub",
            progress=0.5,
            percentage=50.0
        )
        test_db.add(sync_progress)
        await test_db.commit()
        await test_db.refresh(sync_progress)
        
        response = await client.get(f"/api/v1/syncs/progress/detail/{sync_progress.id}", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["document"] == "detail_book.epub"
        assert float(data["progress"]) == 0.5
        assert data["device"]["device_name"] == test_device.device_name
    
    @pytest.mark.asyncio
    async def test_update_sync_progress(self, client: AsyncClient, auth_headers: dict, test_user: User, test_device: Device, test_db: AsyncSession):
        """测试更新同步进度"""
        sync_progress = SyncProgress(
            user_id=test_user.id,
            device_id=test_device.id,
            document="update_book.epub",
            progress=0.3,
            percentage=30.0
        )
        test_db.add(sync_progress)
        await test_db.commit()
        await test_db.refresh(sync_progress)
        
        update_data = {
            "progress": 0.6,
            "percentage": 60.0
        }
        
        response = await client.put(
            f"/api/v1/syncs/progress/detail/{sync_progress.id}", 
            json=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert float(data["progress"]) == 0.6
        assert float(data["percentage"]) == 60.0
    
    @pytest.mark.asyncio
    async def test_delete_sync_progress(self, client: AsyncClient, auth_headers: dict, test_user: User, test_device: Device, test_db: AsyncSession):
        """测试删除同步进度"""
        sync_progress = SyncProgress(
            user_id=test_user.id,
            device_id=test_device.id,
            document="delete_book.epub",
            progress=0.2,
            percentage=20.0
        )
        test_db.add(sync_progress)
        await test_db.commit()
        await test_db.refresh(sync_progress)
        
        response = await client.delete(f"/api/v1/syncs/progress/detail/{sync_progress.id}", headers=auth_headers)
        
        assert response.status_code == 200
        
        # 验证记录已删除
        result = await test_db.execute(select(SyncProgress).where(SyncProgress.id == sync_progress.id))
        deleted_progress = result.scalar_one_or_none()
        assert deleted_progress is None
    
    @pytest.mark.asyncio
    async def test_batch_upload_progress(self, client: AsyncClient, auth_headers: dict, test_device: Device):
        """测试批量上传同步进度"""
        batch_data = {
            "device_id": test_device.device_id,
            "progresses": [
                {
                    "document": "batch_book_1.epub",
                    "progress": 0.1,
                    "percentage": 10.0
                },
                {
                    "document": "batch_book_2.epub", 
                    "progress": 0.2,
                    "percentage": 20.0
                }
            ]
        }
        
        response = await client.post("/api/v1/syncs/progress/batch", json=batch_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["uploaded_count"] == 2
        assert len(data["results"]) == 2


class TestDeviceSyncStatus:
    """设备同步状态测试"""
    
    @pytest.mark.asyncio
    async def test_get_device_sync_status(self, client: AsyncClient, auth_headers: dict, test_user: User, test_device: Device, test_db: AsyncSession):
        """测试获取设备同步状态"""
        # 创建一些同步记录
        sync_progress = SyncProgress(
            user_id=test_user.id,
            device_id=test_device.id,
            document="status_book.epub",
            progress=0.4,
            percentage=40.0
        )
        test_db.add(sync_progress)
        await test_db.commit()
        
        response = await client.get("/api/v1/syncs/devices/status", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["devices"]) >= 1
        
        device_status = next((d for d in data["devices"] if d["device_id"] == test_device.device_id), None)
        assert device_status is not None
        assert device_status["sync_count"] >= 1
        assert device_status["last_sync"] is not None


class TestSyncPermissions:
    """同步权限测试"""
    
    @pytest.mark.asyncio
    async def test_unauthorized_sync_access(self, client: AsyncClient):
        """测试未认证的同步访问"""
        response = await client.get("/api/v1/syncs/progress")
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_cross_user_sync_access(self, client: AsyncClient, test_db: AsyncSession, auth_headers: dict):
        """测试跨用户同步访问"""
        # 创建另一个用户和他们的同步进度
        other_user = User(
            username="otheruser",
            hashed_password="5d41402abc4b2a76b9719d911017c592",
            is_active=True
        )
        test_db.add(other_user)
        await test_db.commit()
        await test_db.refresh(other_user)
        
        other_device = Device(
            device_id="other-device",
            device_name="Other Device",
            user_id=other_user.id
        )
        test_db.add(other_device)
        await test_db.commit()
        await test_db.refresh(other_device)
        
        other_progress = SyncProgress(
            user_id=other_user.id,
            device_id=other_device.id,
            document="other_book.epub",
            progress=0.5
        )
        test_db.add(other_progress)
        await test_db.commit()
        await test_db.refresh(other_progress)
        
        # 尝试访问其他用户的同步进度
        response = await client.get(f"/api/v1/syncs/progress/detail/{other_progress.id}", headers=auth_headers)
        
        assert response.status_code == 404  # 应该找不到，因为不属于当前用户


class TestSyncDataValidation:
    """同步数据验证测试"""
    
    @pytest.mark.asyncio
    async def test_invalid_progress_value(self, client: AsyncClient, test_user: User, test_device: Device):
        """测试无效的进度值"""
        form_data = {
            "document": "test_book.epub",
            "progress": "1.5",  # 无效：大于1
            "device": test_device.device_name,
            "user": test_user.username
        }
        
        response = await client.put("/api/v1/syncs/progress", data=form_data)
        
        assert response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_invalid_percentage_value(self, client: AsyncClient, test_user: User, test_device: Device):
        """测试无效的百分比值"""
        form_data = {
            "document": "test_book.epub",
            "progress": "0.5",
            "percentage": "150.0",  # 无效：大于100
            "device": test_device.device_name,
            "user": test_user.username
        }
        
        response = await client.put("/api/v1/syncs/progress", data=form_data)
        
        assert response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_missing_required_fields(self, client: AsyncClient):
        """测试缺少必需字段"""
        form_data = {
            "document": "test_book.epub"
            # 缺少其他必需字段
        }
        
        response = await client.put("/api/v1/syncs/progress", data=form_data)
        
        assert response.status_code == 400


class TestSyncConflictResolution:
    """同步冲突解决测试"""
    
    @pytest.mark.asyncio
    async def test_timestamp_based_conflict_resolution(self, client: AsyncClient, test_user: User, test_device: Device, test_db: AsyncSession):
        """测试基于时间戳的冲突解决"""
        # 创建一个旧的同步记录
        old_progress = SyncProgress(
            user_id=test_user.id,
            device_id=test_device.id,
            document="conflict_book.epub",
            progress=0.3,
            percentage=30.0,
            timestamp=1640995200  # 较早时间
        )
        test_db.add(old_progress)
        await test_db.commit()
        
        # 上传更新的进度（更晚时间戳）
        form_data = {
            "document": "conflict_book.epub",
            "progress": "0.6",
            "percentage": "60.0",
            "device": test_device.device_name,
            "user": test_user.username,
            "timestamp": "1640995300"  # 更晚时间
        }
        
        response = await client.put("/api/v1/syncs/progress", data=form_data)
        
        assert response.status_code == 200
        data = response.json()
        assert float(data["progress"]) == 0.6  # 应该更新为新值
        assert data["sync_status"] == "updated"
    
    @pytest.mark.asyncio
    async def test_older_timestamp_rejection(self, client: AsyncClient, test_user: User, test_device: Device, test_db: AsyncSession):
        """测试拒绝较旧的时间戳"""
        # 创建一个新的同步记录
        new_progress = SyncProgress(
            user_id=test_user.id,
            device_id=test_device.id,
            document="newer_book.epub",
            progress=0.7,
            percentage=70.0,
            timestamp=1640995300  # 较新时间
        )
        test_db.add(new_progress)
        await test_db.commit()
        
        # 尝试上传更旧的进度
        form_data = {
            "document": "newer_book.epub",
            "progress": "0.5",
            "percentage": "50.0",
            "device": test_device.device_name,
            "user": test_user.username,
            "timestamp": "1640995200"  # 更旧时间
        }
        
        response = await client.put("/api/v1/syncs/progress", data=form_data)
        
        assert response.status_code == 200
        data = response.json()
        assert float(data["progress"]) == 0.7  # 应该保持原值
        assert data["sync_status"] == "ignored" 