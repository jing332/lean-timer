#!/usr/bin/env bash
set -euo pipefail

APP_NAME="lean-timer"
INSTALL_DIR="/opt/${APP_NAME}"
DESKTOP_FILE="/usr/share/applications/${APP_NAME}.desktop"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

run_as_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
    return
  fi

  if command -v sudo >/dev/null 2>&1; then
    sudo "$@"
    return
  fi

  echo "This script needs root privileges. Re-run with sudo." >&2
  exit 1
}

install_files() {
  mkdir -p "${INSTALL_DIR}"

  cp "${ROOT_DIR}/README.md" "${INSTALL_DIR}/README.md"
  cp "${ROOT_DIR}/lean-timer.desktop" "${INSTALL_DIR}/lean-timer.desktop"

  rm -rf "${INSTALL_DIR}/scripts" "${INSTALL_DIR}/src"
  mkdir -p "${INSTALL_DIR}/scripts" "${INSTALL_DIR}/src/lean_timer"

  cp "${ROOT_DIR}/scripts/run.sh" "${INSTALL_DIR}/scripts/run.sh"
  cp "${ROOT_DIR}/scripts/check.sh" "${INSTALL_DIR}/scripts/check.sh"
  cp "${ROOT_DIR}/src/lean_timer/__init__.py" "${INSTALL_DIR}/src/lean_timer/__init__.py"
  cp "${ROOT_DIR}/src/lean_timer/__main__.py" "${INSTALL_DIR}/src/lean_timer/__main__.py"
  cp "${ROOT_DIR}/src/lean_timer/alerts.py" "${INSTALL_DIR}/src/lean_timer/alerts.py"
  cp "${ROOT_DIR}/src/lean_timer/app.py" "${INSTALL_DIR}/src/lean_timer/app.py"
  cp "${ROOT_DIR}/src/lean_timer/bootstrap.py" "${INSTALL_DIR}/src/lean_timer/bootstrap.py"
  cp "${ROOT_DIR}/src/lean_timer/config.py" "${INSTALL_DIR}/src/lean_timer/config.py"
  cp "${ROOT_DIR}/src/lean_timer/timer_engine.py" "${INSTALL_DIR}/src/lean_timer/timer_engine.py"

  if [[ -d "${ROOT_DIR}/src/lean_timer/sounds" ]]; then
    rm -rf "${INSTALL_DIR}/src/lean_timer/sounds"
    mkdir -p "${INSTALL_DIR}/src/lean_timer/sounds"
    cp "${ROOT_DIR}/src/lean_timer/sounds/"* "${INSTALL_DIR}/src/lean_timer/sounds/" 2>/dev/null || true
  fi

  chmod +x "${INSTALL_DIR}/scripts/run.sh" "${INSTALL_DIR}/scripts/check.sh"
}

install_desktop_entry() {
  cat > "${DESKTOP_FILE}" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Lean Timer
Name[zh_CN]=学习时钟
Comment=Lean Timer GTK desktop app
Comment[zh_CN]=学习计时器
Exec=${INSTALL_DIR}/scripts/run.sh
Path=${INSTALL_DIR}
TryExec=${INSTALL_DIR}/scripts/run.sh
Icon=alarm-symbolic
Terminal=false
Categories=Utility;Education;
StartupNotify=true
X-GNOME-UsesNotifications=true
EOF

  chmod 644 "${DESKTOP_FILE}"
}

main() {
  echo "Installing ${APP_NAME} to ${INSTALL_DIR}"
  run_as_root mkdir -p "${INSTALL_DIR}"
  run_as_root bash -c "$(declare -f install_files); ROOT_DIR='${ROOT_DIR}'; INSTALL_DIR='${INSTALL_DIR}'; install_files"
  run_as_root bash -c "$(declare -f install_desktop_entry); DESKTOP_FILE='${DESKTOP_FILE}'; INSTALL_DIR='${INSTALL_DIR}'; install_desktop_entry"
  echo "Installed desktop entry to ${DESKTOP_FILE}"
  echo "You can launch it from the application menu as 'Lean Timer'."
}

main "$@"
