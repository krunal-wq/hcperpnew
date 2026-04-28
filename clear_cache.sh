#!/bin/bash
# clear_cache.sh — wipe all server-side caches and restart Flask
# Run from your project root:  bash clear_cache.sh

set -e

echo "=== HCP ERP — Cache Clear ==="

# 1. Python bytecode cache
echo ""
echo "[1/4] Removing __pycache__ folders and .pyc files..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
echo "    ✓ Done"

# 2. Flask sessions (optional — only if you want to log out all users)
# echo "[2/4] Clearing Flask session files..."
# rm -rf flask_session/* 2>/dev/null || true

# 3. Restart Flask
echo ""
echo "[2/4] Restarting Flask app..."
RESTARTED=0

# Try systemd service names (in order of likelihood)
for SERVICE in gunicorn hcp-erp erp flask-erp; do
    if systemctl list-units --type=service 2>/dev/null | grep -q "^.*$SERVICE.service"; then
        sudo systemctl restart "$SERVICE" 2>&1 && {
            echo "    ✓ Restarted systemd service: $SERVICE"
            RESTARTED=1
            break
        }
    fi
done

# Fallback: kill python index.py and restart
if [ "$RESTARTED" = "0" ]; then
    if pgrep -f "python.*index.py" > /dev/null; then
        echo "    Found python index.py running — sending HUP..."
        pkill -HUP -f "python.*index.py" || true
        echo "    ✓ Sent HUP signal"
        RESTARTED=1
    fi
fi

if [ "$RESTARTED" = "0" ]; then
    echo "    ⚠ Could not auto-restart. Restart your Flask service manually:"
    echo "       sudo systemctl restart <your-service-name>"
    echo "       — or —"
    echo "       pkill -f 'python index.py' && nohup python index.py > app.log 2>&1 &"
fi

# 4. Reload nginx if present
echo ""
echo "[3/4] Reloading nginx (if present)..."
if command -v nginx > /dev/null 2>&1; then
    sudo nginx -t 2>/dev/null && sudo systemctl reload nginx 2>/dev/null && echo "    ✓ Nginx reloaded" || echo "    (nginx skipped — not running or no permission)"
else
    echo "    (nginx not installed — skipped)"
fi

# 5. Done
echo ""
echo "[4/4] All clear."
echo ""
echo "Now open the site in your browser and do a HARD REFRESH:"
echo "    Windows:  Ctrl + Shift + R"
echo "    Mac:      Cmd + Shift + R"
echo ""
echo "Open DevTools (F12) → Console tab. You should see:"
echo "    [PACKING] PAGINATION v2 LOADED"
echo ""
