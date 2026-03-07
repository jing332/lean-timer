# Lean Timer (Ubuntu 学习时钟)

面向 Ubuntu 桌面的学习时钟应用，支持：
- 正计时（开始/暂停/重置）
- 番茄钟（专注/休息循环）
- 深度专注（90/20 节律，可调随机提示音）
- 里程碑系统通知与提示音

## 运行环境

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-gi gir1.2-gtk-4.0 gir1.2-notify-0.7
```

## 启动

```bash
./scripts/run.sh
```

深度专注模式说明：
- 专注阶段默认 90 分钟，长休息默认 20 分钟
- 专注中默认每 3 到 5 分钟随机响一次提示音
- 听到提示音后会弹出 10 秒休息遮罩，结束后自动恢复

## 自检

```bash
./scripts/check.sh
```

如果提示缺少运行时，请安装：

```bash
sudo apt install -y python3-gi gir1.2-gtk-4.0 gir1.2-notify-0.7
```

## 测试（状态机）

如果安装了 pytest：

```bash
PYTHONPATH=src python3 -m pytest -q
```
