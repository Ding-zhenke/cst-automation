# -*- coding: utf-8 -*-
"""无机器路径的兼容配置入口。

发行包保持路径未配置，交由 environment 自动发现本机安装。
推荐使用 CST_INSTALL_PATH 环境变量或 CST_CONFIG_FILE 用户 JSON；
旧调用者仍可通过本文件中的同名设置覆盖自动发现。
"""

CST_INSTALL_PATH = None
CST_PYTHON_LIB = None
CST_MATERIAL_LIB = None

DEFAULT_WORK_DIR = ""
CST_START_MODE = "Interactive"
