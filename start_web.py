#!/usr/bin/env python3
"""
TradingAgents-CN 简化启动脚本
解决模块导入问题的最简单方案
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    """主函数"""
    print("🚀 TradingAgents-CN Web应用启动器")
    print("=" * 50)
    
    # 获取项目根目录
    project_root = Path(__file__).parent
    web_dir = project_root / "web"
    app_file = web_dir / "app.py"
    
    # 检查文件是否存在
    if not app_file.exists():
        print(f"❌ 找不到应用文件: {app_file}")
        return
    
    # 检查虚拟环境
    in_venv = (
        hasattr(sys, 'real_prefix') or 
        (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    )
    
    if not in_venv:
        print("⚠️ 建议在虚拟环境中运行:")
        print("   Windows: .\\env\\Scripts\\activate")
        print("   Linux/macOS: source env/bin/activate")
        print()
    
    # 检查streamlit是否安装
    try:
        import streamlit
        print("✅ Streamlit已安装")
    except ImportError:
        print("❌ Streamlit未安装，正在安装...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "streamlit", "plotly"], check=True)
            print("✅ Streamlit安装成功")
        except subprocess.CalledProcessError:
            print("❌ Streamlit安装失败，请手动安装: pip install streamlit plotly")
            return
    
    # 设置环境变量，添加项目根目录到Python路径
    env = os.environ.copy()
    current_path = env.get('PYTHONPATH', '')
    if current_path:
        env['PYTHONPATH'] = f"{project_root}{os.pathsep}{current_path}"
    else:
        env['PYTHONPATH'] = str(project_root)
    
    # 添加Homebrew到PATH（pandoc需要）
    homebrew_bin = "/opt/homebrew/bin"
    homebrew_sbin = "/opt/homebrew/sbin"
    current_path_env = env.get('PATH', '')
    if homebrew_bin not in current_path_env:
        env['PATH'] = f"{homebrew_bin}:{homebrew_sbin}:{current_path_env}"
        print(f"✅ 已添加Homebrew到PATH: {homebrew_bin}")
    
    # 添加LaTeX到PATH（PDF生成需要）
    tex_paths = [
        "/Library/TeX/texbin",  # basictex/mactex标准路径
        "/usr/local/texlive/*/bin/*/",  # 备用路径
    ]
    for tex_path in tex_paths:
        if os.path.exists(tex_path.replace('/*', '').split('/')[0] + '/' + tex_path.split('/')[1] if '*' in tex_path else tex_path):
            if tex_path not in current_path_env:
                env['PATH'] = f"{tex_path}:{env.get('PATH', '')}"
                print(f"✅ 已添加LaTeX到PATH: {tex_path}")
                break
    
    # 尝试使用path_helper更新PATH（包含LaTeX）
    try:
        path_helper_result = subprocess.run(
            ['/usr/libexec/path_helper'],
            capture_output=True,
            text=True,
            timeout=2
        )
        if path_helper_result.returncode == 0:
            # 解析path_helper的输出并合并到PATH
            for line in path_helper_result.stdout.split('\n'):
                if 'PATH=' in line:
                    new_path = line.split("PATH=")[1].split('"')[1] if '"' in line else line.split("PATH=")[1].split("'")[1]
                    if new_path:
                        env['PATH'] = f"{new_path}:{env.get('PATH', '')}"
                        print(f"✅ 已通过path_helper更新PATH（包含LaTeX）")
                        break
    except:
        pass
    
    # 设置Homebrew bottle镜像（加速下载）
    if 'HOMEBREW_BOTTLE_DOMAIN' not in env:
        env['HOMEBREW_BOTTLE_DOMAIN'] = 'https://mirrors.tuna.tsinghua.edu.cn/homebrew-bottles'
    
    # 构建启动命令
    cmd = [
        sys.executable, "-m", "streamlit", "run",
        str(app_file),
        "--server.port", "8501",
        "--server.address", "localhost",
        "--browser.gatherUsageStats", "false",
        "--server.fileWatcherType", "none",
        "--server.runOnSave", "false"
    ]
    
    print("🌐 启动Web应用...")
    print("📱 浏览器将自动打开 http://localhost:8501")
    print("⏹️  按 Ctrl+C 停止应用")
    print("=" * 50)
    
    try:
        # 启动应用，传递修改后的环境变量
        subprocess.run(cmd, cwd=project_root, env=env)
    except KeyboardInterrupt:
        print("\n⏹️ Web应用已停止")
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        print("\n💡 如果遇到模块导入问题，请尝试:")
        print("   1. 激活虚拟环境")
        print("   2. 运行: pip install -e .")
        print("   3. 再次启动Web应用")

if __name__ == "__main__":
    main()
