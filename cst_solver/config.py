# -*- coding: utf-8 -*-
"""
CST Studio Suite 本地配置文件
==============================
⚠ 本文件已加入 .gitignore，不会同步到 GitHub
请修改 CST_INSTALL_PATH 为本机 CST 安装路径

所有从属路径（Python库、材料库）均自动从 CST_INSTALL_PATH 推导。
    → CST_PYTHON_LIB   = {CST_INSTALL_PATH}\\AMD64\\python_cst_libraries
    → CST_MATERIAL_LIB = {CST_INSTALL_PATH}\\Library\\Materials
"""

import os

# ============================================================
# ★ 唯一需要配置的项 —— 请修改为本机 CST 安装路径
# ============================================================

CST_INSTALL_PATH = r"C:\SOFTWARE\CST Studio Suite 2026"

# ============================================================
# 以下为自动推导（从 CST_INSTALL_PATH），请勿手动修改
# ============================================================

CST_PYTHON_LIB = os.path.join(CST_INSTALL_PATH, "AMD64", "python_cst_libraries")
CST_MATERIAL_LIB = os.path.join(CST_INSTALL_PATH, "Library", "Materials")

# 可选配置
DEFAULT_WORK_DIR = ""
CST_START_MODE = "Interactive"
