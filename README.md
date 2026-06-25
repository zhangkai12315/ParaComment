# ParaComment - 摸鱼小说注释阅读器

一个专为 Windows 打工人准备的 TXT 小说摸鱼工具：把小说内容自动切分成小段，并伪装成 `//` 或 `#` 代码注释，一键粘贴到 VS Code、IDEA、PyCharm、Notepad++ 等编辑器里。  
看起来像是在读代码注释、调试说明，实际上是在低调追小说。

支持系统托盘常驻、全局快捷键翻页、浏览模式自动替换上一段、智能切分、章节跳转、阅读进度保存和剪贴板恢复，让摸鱼看小说更自然、更隐蔽、更不打断工作流。

## 功能特性

| 功能 | 说明 |
| --- | --- |
| TXT 文件读取 | 支持选择本地 TXT 文件 |
| 中文编码识别 | 支持 UTF-8、GBK、GB2312、GB18030 等常见中文文本 |
| 段落拆分 | 自动过滤空白段，并支持智能切分长段 |
| 阅读进度保存 | 同一个文件下次打开会继续上次位置 |
| 注释格式 | 支持 `//` 行注释和 `#` 脚本注释 |
| 全局快捷键 | 支持键盘组合键和鼠标侧键 |
| 快捷键提示 | 会提示常见编辑器快捷键和单键快捷键风险 |
| 浏览模式 | 默认只保留当前一段，下一段会撤销上一段再粘贴 |
| 累积模式 | 可切换为每次都追加粘贴 |
| 多文件阅读列表 | 保留最近打开的 TXT 文件，方便双击切换 |
| 章节跳转 | 自动识别常见章节标题，并可从下拉框跳转 |
| 剪贴板恢复 | 可选开启，粘贴后尽量恢复原剪贴板内容 |
| 撤销 | 优先向当前编辑器发送 `Ctrl+Z` |
| 托盘常驻 | 主窗口可最小化到系统托盘 |
| 单文件打包 | 使用 PyInstaller 打包为 exe |

## 界面预览

ParaComment 提供一个简单 GUI，用于选择 TXT 文件、查看当前文件名、查看当前片段进度、切换注释格式、设置智能切分长度、设置粘贴模式，以及自定义快捷键。

日常使用时可以把窗口最小化到托盘，主要通过快捷键操作。

## 使用场景

如果你经常在 VS Code、PyCharm、IDEA、Notepad++ 等编辑器里工作，又想顺手读一点 TXT 长文本，ParaComment 可以把文本伪装成注释块插入到当前编辑器中。默认浏览模式会尽量保证编辑器里只存在当前一段，避免内容越堆越多。

## 安装运行

建议使用 Python 3.12。

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m app
```

依赖如下：

```text
PySide6
charset-normalizer
```

开发、测试和打包时安装：

```powershell
python -m pip install -r requirements-dev.txt
```

## 打包 exe

项目内置了 `build.ps1`，可以直接打包成单文件 exe：

```powershell
.\build.ps1 -Python .\.venv\Scripts\python.exe
```

也可以手动执行 PyInstaller：

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name ParaComment app/main.py
```

打包完成后，输出文件在：

```text
dist/ParaComment.exe
```

如果打包时报 `WinError 5` 或提示文件被占用，请先从系统托盘完全退出 ParaComment，再删除旧的 `dist/ParaComment.exe` 后重新打包。

## 快速使用

1. 启动 ParaComment。
2. 点击“选择 TXT 文件”，选择一本 TXT 小说或长文本。
3. 选择注释格式：`//` 或 `#`。
4. 根据需要调整智能切分长度。
5. 把光标放到目标编辑器或 IDE 中。
6. 按“下一段并粘贴”的快捷键，当前片段会以注释形式粘贴到光标位置。
7. 如果使用浏览模式，再次按“下一段并粘贴”会尝试撤销上一段并粘贴下一段。
8. 如需连续保留多段内容，可以切换到“累积模式”。

## 快捷键建议

ParaComment 支持自定义快捷键，包括键盘快捷键和鼠标侧键。

推荐使用：

| 操作 | 推荐快捷键 |
| --- | --- |
| 下一段并粘贴 | 鼠标前进侧键，或 `Ctrl+Alt+Right` |
| 上一段 | 鼠标后退侧键，或 `Ctrl+Alt+Left` |
| 撤销上一次工具粘贴 | `Ctrl+Alt+Backspace` |

不太建议把快捷键设置成单独的 `Up`、`Down`、字母键或数字键，因为它们会抢占编辑器原本的输入和光标移动行为。更推荐使用鼠标侧键，或者带 `Ctrl` / `Alt` / `Shift` 的组合键。

## 粘贴模式

### 浏览模式

默认模式。适合“只看当前一段”的场景。

当你按下一段时，ParaComment 会尝试向当前编辑器发送 `Ctrl+Z` 撤销上一段工具粘贴，再发送 `Ctrl+V` 粘贴新段落。

### 累积模式

适合想保留多段文本的场景。

每次按下一段都会追加粘贴，不会主动撤销上一段。

## 智能切分

有些小说段落非常长，如果按原始段落输出，会一次粘贴太多内容。ParaComment 支持智能切分，可以把长段按默认长度拆成更小片段。

智能切分长度可以在界面中调整。长度越小，每次输出越短；长度越大，阅读连续性越强。

## 状态保存

ParaComment 会保存：

| 状态 | 说明 |
| --- | --- |
| 最近打开文件 | 下次启动自动恢复 |
| 多文件阅读列表 | 最近阅读过的 TXT 会显示在主窗口中 |
| 文件阅读位置 | 同一个 TXT 可以继续上次位置 |
| 注释格式 | 每个文件可保存当前格式 |
| 智能切分长度 | 保留用户设置 |
| 快捷键配置 | 支持自定义后持久化 |
| 粘贴模式 | 浏览模式或累积模式 |
| 剪贴板恢复开关 | 保存是否在粘贴后恢复剪贴板 |

状态文件位于：

```text
%APPDATA%\ParaComment\state.json
```

调试日志位于：

```text
%APPDATA%\ParaComment\logs\debug.log
```

## 项目结构

```text
ParaComment/
  app/
    main.py                  # 应用入口与主控制器
    config.py                # 常量和路径配置
    hotkeys.py               # 快捷键构建、序列化、校验
    models.py                # 数据模型
    services/
      text_loader.py         # 文本读取、编码识别、段落/智能切分
      state_store.py         # 状态持久化
      hotkey_service.py      # 全局快捷键监听
      paste_service.py       # 剪贴板粘贴与撤销
      tray_service.py        # 系统托盘
      debug_logger.py        # JSON Lines 调试日志
    ui/
      main_window.py         # 主窗口
      hotkey_edit.py         # 快捷键录入控件
      theme.py               # UI 样式
  tests/                     # 单元测试
  requirements.txt           # Python 依赖
  build.ps1                  # PyInstaller 打包脚本
  ParaComment.spec           # PyInstaller 配置
```

## 测试

```powershell
python -m unittest discover -s tests -v
```

运行静态检查：

```powershell
python -m ruff check app tests
```

## 兼容性说明

主要面向 Windows，常见目标编辑器包括：

| 编辑器 / IDE | 说明 |
| --- | --- |
| VS Code | 支持 |
| PyCharm | 支持 |
| IDEA | 支持 |
| Notepad++ | 支持 |
| 其他 Windows 编辑器 | 理论上只要支持剪贴板和 `Ctrl+V` 即可 |

## 已知限制

- ParaComment 使用剪贴板加 `Ctrl+V` 实现粘贴。可以开启“粘贴后恢复剪贴板”，但目标编辑器响应较慢时仍建议留意。
- 浏览模式依赖当前编辑器自己的 `Ctrl+Z` 撤销栈。如果你在两次工具输出之间手动输入或修改代码，下一次浏览模式替换可能会先撤销你的手动修改。
- 如果目标编辑器以管理员权限运行，ParaComment 也可能需要以管理员权限运行，快捷键和输入注入才更稳定。
- 不建议使用单独的方向键或字母键作为全局快捷键，容易影响正常编辑体验。
- 当前仍是 MVP，后续可以继续扩展为更精确的“定位上一段并替换”，减少对编辑器撤销栈的依赖。

## 后续计划

- 继续优化浏览模式的定位替换，让它更少依赖编辑器撤销栈。
- 增加更细的章节规则配置，例如自定义正则。
- 增加阅读列表管理，例如移除不存在的文件或手动清空列表。
- 增加发布用 GitHub Actions 打包流程。

## 免责声明

ParaComment 是一个本地文本辅助工具，主要用于个人阅读、测试和学习场景。请遵守所在环境的工作规范、软件使用规则以及文本内容的版权要求。
