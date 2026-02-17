# 图片资源目录说明

本目录按**场景**组织截图资源，便于在不同分辨率下调试。

## 目录结构

```
resources/
├── call/      # 场景：拨打（你好豆包）
│   └── *.png  # 可放多张图，程序会依次尝试直到匹配
├── hangup/    # 场景：挂断（再见吧）
│   └── *.png
└── README.md
```

## 多分辨率兼容

- 每个场景目录下可放**多张**截图（如 `call.png`、`call_1080p.png`、`call_1440p.png`）。
- 程序会**遍历**该目录下所有 `.png` / `.jpg` 图片，依次尝试识别，直到某张匹配成功。
- 建议：在不同分辨率电脑上截取对应按钮图，放入对应场景目录，即可自动适配。

## 开发与打包

- **开发时**：使用与 `main.py` 同级的 `resources/` 目录。
- **打包后**：必须存在与 exe 同级的 `resources/` 目录（resources 不再打包进 exe）。
- 分发建议：将 `DoubaoAssistant.exe` 与 `resources/` 放在同一目录（本项目提供 `package.ps1` 会将两者打到一个 zip 里）。
- **旧版迁移**：如果你之前把 `call.png`、`hangup.png` 放在项目根目录，请手动移动到 `resources/call/`、`resources/hangup/`，逻辑更统一。
