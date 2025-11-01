#!/usr/bin/env python3
"""
LLM提供商检查工具
用于检测和验证LLM配置，并在遇到问题时建议切换
"""

import os
from typing import Dict, List, Tuple, Optional
from tradingagents.utils.logging_init import get_logger

logger = get_logger('web.llm_provider_checker')


class LLMProviderChecker:
    """LLM提供商检查和切换助手"""
    
    @staticmethod
    def get_available_providers() -> List[Dict[str, str]]:
        """
        获取所有可用的LLM提供商
        
        Returns:
            提供商列表，每个包含name, key, configured等字段
        """
        providers = []
        
        # Dashscope
        dashscope_key = os.getenv("DASHSCOPE_API_KEY")
        providers.append({
            'id': 'dashscope',
            'name': '🇨🇳 阿里百炼',
            'display_name': '阿里百炼 (Dashscope)',
            'api_key': dashscope_key,
            'configured': bool(dashscope_key and dashscope_key != 'your_dashscope_api_key_here'),
            'recommended': True,
            'models': ['qwen-plus-latest', 'qwen-max', 'qwen-turbo']
        })
        
        # Anthropic
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        providers.append({
            'id': 'anthropic',
            'name': '🤖 Anthropic Claude',
            'display_name': 'Anthropic Claude',
            'api_key': anthropic_key,
            'configured': bool(anthropic_key and anthropic_key != 'your_anthropic_api_key_here'),
            'recommended': False,
            'models': ['claude-3-5-sonnet-latest']
        })
        
        # DeepSeek
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        providers.append({
            'id': 'deepseek',
            'name': '🚀 DeepSeek',
            'display_name': 'DeepSeek',
            'api_key': deepseek_key,
            'configured': bool(deepseek_key and deepseek_key != 'your_deepseek_api_key_here'),
            'recommended': False,
            'models': ['deepseek-chat']
        })
        
        # OpenAI
        openai_key = os.getenv("OPENAI_API_KEY")
        providers.append({
            'id': 'openai',
            'name': '🤖 OpenAI',
            'display_name': 'OpenAI',
            'api_key': openai_key,
            'configured': bool(openai_key and openai_key not in ['your_openai_api_key_here', '']),
            'recommended': False,
            'models': ['gpt-4o', 'gpt-4o-mini']
        })
        
        return providers
    
    @staticmethod
    def get_recommended_provider() -> Optional[Dict[str, str]]:
        """
        获取推荐的LLM提供商（优先Dashscope）
        
        Returns:
            推荐的提供商信息，如果没有则返回None
        """
        providers = LLMProviderChecker.get_available_providers()
        
        # 优先返回已配置的推荐提供商
        for provider in providers:
            if provider['recommended'] and provider['configured']:
                return provider
        
        # 如果没有推荐提供商，返回第一个已配置的
        for provider in providers:
            if provider['configured']:
                return provider
        
        return None
    
    @staticmethod
    def check_provider_status(provider_id: str) -> Tuple[bool, str]:
        """
        检查特定提供商的状态
        
        Args:
            provider_id: 提供商ID（dashscope/openai/anthropic/deepseek）
        
        Returns:
            (是否可用, 状态消息)
        """
        providers = LLMProviderChecker.get_available_providers()
        
        for provider in providers:
            if provider['id'] == provider_id:
                if provider['configured']:
                    return True, f"✅ {provider['display_name']}: 已配置"
                else:
                    return False, f"❌ {provider['display_name']}: 未配置API密钥"
        
        return False, f"❌ 未知的提供商: {provider_id}"
    
    @staticmethod
    def suggest_switch(current_provider: str, error_code: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        根据当前提供商和错误代码建议切换到其他提供商
        
        Args:
            current_provider: 当前使用的提供商
            error_code: 错误代码（402/401/429等）
        
        Returns:
            建议切换到的提供商信息，如果没有则返回None
        """
        # 402错误：余额不足，强烈建议切换
        if error_code == "402" and current_provider == "openai":
            recommended = LLMProviderChecker.get_recommended_provider()
            if recommended and recommended['id'] != 'openai':
                return recommended
        
        # 其他错误：也建议切换到推荐提供商
        if current_provider not in ["dashscope"]:
            recommended = LLMProviderChecker.get_recommended_provider()
            if recommended:
                return recommended
        
        return None
    
    @staticmethod
    def format_provider_list(providers: List[Dict[str, str]], show_all: bool = False) -> str:
        """
        格式化提供商列表用于显示
        
        Args:
            providers: 提供商列表
            show_all: 是否显示所有提供商（包括未配置的）
        
        Returns:
            格式化后的文本
        """
        lines = []
        for provider in providers:
            if provider['configured'] or show_all:
                status = "✅" if provider['configured'] else "❌"
                recommend = "⭐推荐" if provider['recommended'] else ""
                lines.append(f"{status} {provider['display_name']} {recommend}")
        
        return "\n".join(lines) if lines else "未找到可用的提供商"


def get_current_provider_info() -> Dict[str, any]:
    """
    获取当前LLM提供商信息（从session state）
    
    Returns:
        当前提供商信息
    """
    try:
        import streamlit as st
        provider_id = st.session_state.get('llm_provider', 'dashscope')
        model = st.session_state.get('llm_model', 'qwen-plus-latest')
        
        return {
            'provider': provider_id,
            'model': model,
            'configured': LLMProviderChecker.check_provider_status(provider_id)[0]
        }
    except:
        return {
            'provider': 'unknown',
            'model': 'unknown',
            'configured': False
        }

