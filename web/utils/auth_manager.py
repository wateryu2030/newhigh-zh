"""
用户认证管理器
处理用户登录、权限验证等功能
支持前端缓存登录状态，10分钟无操作自动失效
"""

import json
import hashlib
import time
from typing import Dict, Optional, Tuple, List

import streamlit as st
from sqlalchemy import text

from tradingagents.utils.logging_manager import get_logger

from data_engine.config import DB_URL
from data_engine.utils.db_utils import get_engine

try:
    from .user_activity_logger import user_activity_logger
except ImportError:
    user_activity_logger = None

logger = get_logger("auth")

class AuthManager:
    """用户认证管理器"""
    
    DEFAULT_ROLE_PERMISSIONS = {
        "admin": ["analysis", "config", "admin"],
        "user": ["analysis"],
    }

    def __init__(self):
        self.session_timeout = 600000
        self.engine = get_engine(DB_URL)
        self._ensure_user_table()
    
    def _ensure_user_table(self):
        """确保用户表存在并初始化默认账户。"""
        create_sql = text(
            """
            CREATE TABLE IF NOT EXISTS web_users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(64) NOT NULL UNIQUE,
                password_hash VARCHAR(128) NOT NULL,
                role VARCHAR(32) NOT NULL DEFAULT 'user',
                permissions TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        with self.engine.begin() as conn:
            conn.execute(create_sql)

            existing_admin = conn.execute(
                text("SELECT COUNT(*) FROM web_users WHERE username = :username"),
                {"username": "admin"},
            ).scalar()
            if existing_admin == 0:
                conn.execute(
                    text(
                        """
                        INSERT INTO web_users (username, password_hash, role, permissions)
                        VALUES (:username, :password_hash, :role, :permissions)
                        """
                    ),
                    {
                        "username": "admin",
                        "password_hash": self._hash_password("admin123"),
                        "role": "admin",
                        "permissions": json.dumps(self.DEFAULT_ROLE_PERMISSIONS["admin"], ensure_ascii=False),
                    },
                )
                conn.execute(
                    text(
                        """
                        INSERT INTO web_users (username, password_hash, role, permissions)
                        VALUES (:username, :password_hash, :role, :permissions)
                        """
                    ),
                    {
                        "username": "user",
                        "password_hash": self._hash_password("user123"),
                        "role": "user",
                        "permissions": json.dumps(self.DEFAULT_ROLE_PERMISSIONS["user"], ensure_ascii=False),
                    },
                )
                logger.info("✅ 用户表初始化完成，已创建默认账户 admin / user")
    
    def _inject_auth_cache_js(self):
        """注入前端认证缓存JavaScript代码"""
        js_code = """
        <script>
        // 认证缓存管理
        window.AuthCache = {
            // 保存登录状态到localStorage
            saveAuth: function(userInfo) {
                const authData = {
                    userInfo: userInfo,
                    loginTime: Date.now(),
                    lastActivity: Date.now()
                };
                localStorage.setItem('tradingagents_auth', JSON.stringify(authData));
                console.log('✅ 登录状态已保存到前端缓存');
            },
            
            // 从localStorage获取登录状态
            getAuth: function() {
                try {
                    const authData = localStorage.getItem('tradingagents_auth');
                    if (!authData) return null;
                    
                    const data = JSON.parse(authData);
                    const now = Date.now();
                    const timeout = 10 * 60 * 1000; // 10分钟
                    
                    // 检查是否超时
                    if (now - data.lastActivity > timeout) {
                        this.clearAuth();
                        console.log('⏰ 登录状态已过期，自动清除');
                        return null;
                    }
                    
                    // 更新最后活动时间
                    data.lastActivity = now;
                    localStorage.setItem('tradingagents_auth', JSON.stringify(data));
                    
                    return data.userInfo;
                } catch (e) {
                    console.error('❌ 读取登录状态失败:', e);
                    this.clearAuth();
                    return null;
                }
            },
            
            // 清除登录状态
            clearAuth: function() {
                localStorage.removeItem('tradingagents_auth');
                console.log('🧹 登录状态已清除');
            },
            
            // 更新活动时间
            updateActivity: function() {
                const authData = localStorage.getItem('tradingagents_auth');
                if (authData) {
                    try {
                        const data = JSON.parse(authData);
                        data.lastActivity = Date.now();
                        localStorage.setItem('tradingagents_auth', JSON.stringify(data));
                    } catch (e) {
                        console.error('❌ 更新活动时间失败:', e);
                    }
                }
            }
        };
        
        // 监听用户活动，更新最后活动时间
        ['click', 'keypress', 'scroll', 'mousemove'].forEach(event => {
            document.addEventListener(event, function() {
                window.AuthCache.updateActivity();
            }, { passive: true });
        });
        
        // 页面加载时检查登录状态
        document.addEventListener('DOMContentLoaded', function() {
            const authInfo = window.AuthCache.getAuth();
            if (authInfo) {
                console.log('🔄 从前端缓存恢复登录状态:', authInfo.username);
                // 通知Streamlit恢复登录状态
                window.parent.postMessage({
                    type: 'restore_auth',
                    userInfo: authInfo
                }, '*');
            }
        });
        </script>
        """
        st.components.v1.html(js_code, height=0)
    
    def _hash_password(self, password: str) -> str:
        """密码哈希"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def _load_users(self) -> Dict[str, Dict]:
        """从数据库加载用户配置。"""
        users: Dict[str, Dict] = {}
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT username, password_hash, role, permissions FROM web_users")
            ).fetchall()
        for row in rows:
            permissions = []
            if row.permissions:
                try:
                    permissions = json.loads(row.permissions)
                except json.JSONDecodeError:
                    permissions = self.DEFAULT_ROLE_PERMISSIONS.get(row.role, [])
            if not permissions:
                permissions = self.DEFAULT_ROLE_PERMISSIONS.get(row.role, [])
            users[row.username] = {
                "password_hash": row.password_hash,
                "role": row.role,
                "permissions": permissions,
            }
        return users

    def register_user(self, username: str, password: str, role: str = "user") -> Tuple[bool, str]:
        """注册新用户写入数据库。"""
        username = username.strip()
        if not username or not password:
            return False, "用户名和密码不能为空"
        if role not in self.DEFAULT_ROLE_PERMISSIONS:
            return False, "不支持的角色类型"

        users = self._load_users()
        if username in users:
            return False, "用户名已存在，请更换一个"

        permissions = json.dumps(
            self.DEFAULT_ROLE_PERMISSIONS.get(role, []),
            ensure_ascii=False,
        )
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        INSERT INTO web_users (username, password_hash, role, permissions)
                        VALUES (:username, :password_hash, :role, :permissions)
                        """
                    ),
                    {
                        "username": username,
                        "password_hash": self._hash_password(password),
                        "role": role,
                        "permissions": permissions,
                    },
                )
            logger.info("✅ 新用户注册成功: %s", username)
            return True, "注册成功，请使用新账户登录"
        except Exception as exc:
            logger.error("❌ 注册用户失败: %s", exc)
            return False, "注册失败，请稍后重试"
    
    def authenticate(self, username: str, password: str) -> Tuple[bool, Optional[Dict]]:
        """
        用户认证
        
        Args:
            username: 用户名
            password: 密码
            
        Returns:
            (认证成功, 用户信息)
        """
        users = self._load_users()
        
        if username not in users:
            logger.warning(f"⚠️ 用户不存在: {username}")
            # 记录登录失败
            if user_activity_logger:
                user_activity_logger.log_login(username, False, "用户不存在")
            return False, None
        
        user_info = users[username]
        password_hash = self._hash_password(password)
        
        if password_hash == user_info["password_hash"]:
            logger.info(f"✅ 用户登录成功: {username}")
            # 记录登录成功
            if user_activity_logger:
                user_activity_logger.log_login(username, True)
            return True, {
                "username": username,
                "role": user_info["role"],
                "permissions": user_info["permissions"]
            }
        else:
            logger.warning(f"⚠️ 密码错误: {username}")
            # 记录登录失败
            if user_activity_logger:
                user_activity_logger.log_login(username, False, "密码错误")
            return False, None
    
    def check_permission(self, permission: str) -> bool:
        """
        检查当前用户权限
        
        Args:
            permission: 权限名称
            
        Returns:
            是否有权限
        """
        if not self.is_authenticated():
            return False
        
        user_info = st.session_state.get('user_info', {})
        permissions = user_info.get('permissions', [])
        
        return permission in permissions
    
    def is_authenticated(self) -> bool:
        """检查用户是否已认证"""
        # 首先检查session_state中的认证状态
        authenticated = st.session_state.get('authenticated', False)
        login_time = st.session_state.get('login_time', 0)
        current_time = time.time()
        
        logger.debug(f"🔍 [认证检查] authenticated: {authenticated}, login_time: {login_time}, current_time: {current_time}")
        
        if authenticated:
            # 检查会话超时
            time_elapsed = current_time - login_time
            logger.debug(f"🔍 [认证检查] 会话时长: {time_elapsed:.1f}秒, 超时限制: {self.session_timeout}秒")
            
            if time_elapsed > self.session_timeout:
                logger.info(f"⏰ 会话超时，自动登出 (已过时间: {time_elapsed:.1f}秒)")
                self.logout()
                return False
            
            logger.debug(f"✅ [认证检查] 用户已认证且未超时")
            return True
        
        logger.debug(f"❌ [认证检查] 用户未认证")
        return False
    
    def login(self, username: str, password: str) -> bool:
        """
        用户登录
        
        Args:
            username: 用户名
            password: 密码
            
        Returns:
            登录是否成功
        """
        success, user_info = self.authenticate(username, password)
        
        if success:
            st.session_state.authenticated = True
            st.session_state.user_info = user_info
            st.session_state.login_time = time.time()
            
            # 保存到前端缓存 - 使用与前端JavaScript兼容的格式
            current_time_ms = int(time.time() * 1000)  # 转换为毫秒
            auth_data = {
                "userInfo": user_info,  # 使用userInfo而不是user_info
                "loginTime": time.time(),
                "lastActivity": current_time_ms,  # 添加lastActivity字段
                "authenticated": True
            }
            
            save_to_cache_js = f"""
            <script>
            console.log('🔐 保存认证数据到localStorage');
            try {{
                const authData = {json.dumps(auth_data)};
                localStorage.setItem('tradingagents_auth', JSON.stringify(authData));
                console.log('✅ 认证数据已保存到localStorage:', authData);
            }} catch (e) {{
                console.error('❌ 保存认证数据失败:', e);
            }}
            </script>
            """
            st.components.v1.html(save_to_cache_js, height=0)
            
            logger.info(f"✅ 用户 {username} 登录成功，已保存到前端缓存")
            return True
        else:
            st.session_state.authenticated = False
            st.session_state.user_info = None
            return False
    
    def logout(self):
        """用户登出"""
        username = st.session_state.get('user_info', {}).get('username', 'unknown')
        st.session_state.authenticated = False
        st.session_state.user_info = None
        st.session_state.login_time = None
        
        # 清除前端缓存
        clear_cache_js = """
        <script>
        console.log('🚪 清除认证数据');
        try {
            localStorage.removeItem('tradingagents_auth');
            localStorage.removeItem('tradingagents_last_activity');
            console.log('✅ 认证数据已清除');
        } catch (e) {
            console.error('❌ 清除认证数据失败:', e);
        }
        </script>
        """
        st.components.v1.html(clear_cache_js, height=0)
        
        logger.info(f"✅ 用户 {username} 登出，已清除前端缓存")
        
        # 记录登出活动
        if user_activity_logger:
            user_activity_logger.log_logout(username)
    
    def restore_from_cache(self, user_info: Dict, login_time: float = None) -> bool:
        """
        从前端缓存恢复登录状态
        
        Args:
            user_info: 用户信息
            login_time: 原始登录时间，如果为None则使用当前时间
            
        Returns:
            恢复是否成功
        """
        try:
            # 验证用户信息的有效性
            username = user_info.get('username')
            if not username:
                logger.warning(f"⚠️ 恢复失败: 用户信息中没有用户名")
                return False
            
            # 检查用户是否仍然存在
            users = self._load_users()
            if username not in users:
                logger.warning(f"⚠️ 尝试恢复不存在的用户: {username}")
                return False
            
            # 恢复登录状态，使用原始登录时间或当前时间
            restore_time = login_time if login_time is not None else time.time()
            
            st.session_state.authenticated = True
            st.session_state.user_info = user_info
            st.session_state.login_time = restore_time
            
            logger.info(f"✅ 从前端缓存恢复用户 {username} 的登录状态")
            logger.debug(f"🔍 [恢复状态] login_time: {restore_time}, current_time: {time.time()}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 从前端缓存恢复登录状态失败: {e}")
            return False
    
    def get_current_user(self) -> Optional[Dict]:
        """获取当前用户信息"""
        if self.is_authenticated():
            return st.session_state.get('user_info')
        return None
    
    def require_permission(self, permission: str) -> bool:
        """
        要求特定权限，如果没有权限则显示错误信息
        
        Args:
            permission: 权限名称
            
        Returns:
            是否有权限
        """
        if not self.check_permission(permission):
            st.error(f"❌ 您没有 '{permission}' 权限，请联系管理员")
            return False
        return True

# 全局认证管理器实例
auth_manager = AuthManager()