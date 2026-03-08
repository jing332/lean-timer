# Lean Timer

Lean Timer 是一个面向 Ubuntu 桌面的 GTK4 学习计时器，支持：

- 正计时
- 番茄钟
- 深度专注
- 系统通知与提示音
- 托盘后台运行

## 环境要求

- Ubuntu 桌面环境
- Python 3
- GTK4 / PyGObject 运行时

安装基础依赖：

```bash
sudo apt update
sudo apt install -y \
  python3 \
  python3-venv \
  python3-gi \
  gir1.2-gtk-4.0 \
  gir1.2-notify-0.7 \
  libcanberra-gtk3-module
```

如果你使用 Ubuntu 默认 GNOME，并希望托盘图标正常显示，额外安装：

```bash
sudo apt install -y gnome-shell-extension-appindicator
```

如果需要运行测试，再安装：

```bash
sudo apt install -y python3-pytest
```

## 运行

项目根目录执行：

```bash
./scripts/run.sh
```

`run.sh` 会自动：

- 选择可用的 Python 解释器
- 在缺少 `.venv` 时创建虚拟环境
- 先做运行时自检
- 再启动应用

## 自检

检查 GTK / PyGObject 运行环境：

```bash
./scripts/check.sh
```

也可以直接执行：

```bash
PYTHONPATH=src python3 -m lean_timer --self-check
```

## 测试

运行全部测试：

```bash
PYTHONPATH=src python3 -m pytest -q
```

运行详细输出：

```bash
PYTHONPATH=src python3 -m pytest -v
```

运行单个测试：

```bash
PYTHONPATH=src python3 -m pytest tests/test_timer_engine.py::test_countup_pause_resume_continuous -v
```

## 桌面快捷方式

如果仓库里已经生成了桌面入口文件，可以用下面的命令启动：

```bash
./scripts/run.sh
```

当前桌面快捷方式使用的入口也是：

```bash
/home/jing/Documents/Projects/lean-timer/scripts/run.sh
```

## 托盘与关闭行为

- 点击窗口关闭按钮时：
  - 有计时进行且启用了托盘收起时，窗口会收起到托盘
  - 有计时进行但未启用托盘收起时，会弹出确认框
  - 没有计时进行时，程序直接退出
- 左键托盘图标可显示或收起主窗口
- 托盘右键菜单可以显示主窗口或退出程序

## 提示音

项目内置提示音文件位于：

- `src/lean_timer/sounds/start.oga`
- `src/lean_timer/sounds/complete.oga`

当前逻辑：

- 开始计时 / 恢复到学习状态时播放 `start.oga`
- 普通提示播放 `complete.oga`

