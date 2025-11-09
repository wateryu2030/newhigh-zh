"""
快速修复脚本：为所有数据下载函数添加自动重新登录机制
"""
import re

file_path = "fetch_extended_data.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 查找所有查询操作的模式
# 模式：rs = bs.query_xxx(...)
pattern = r'(rs = bs\.query_\w+\([^)]+\))\s*\n\s*if rs\.error_code != \'0\':'

def add_relogin_check(match):
    query_line = match.group(1)
    # 添加重新登录检查逻辑
    replacement = f"""{query_line}
                    
                    if rs.error_code != '0':
                        # 检查是否是登录错误，如果是则重新登录并重试一次
                        if check_and_relogin_on_error(rs.error_msg):
                            # 重新登录后重试一次
                            {query_line}
                            if rs.error_code != '0':
"""
    return replacement

# 替换所有匹配的模式
new_content = re.sub(pattern, add_relogin_check, content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("修复完成")

