#!/bin/bash
set -e

echo "Initialization complete. Starting supervisor..."
# Запуск supervisord, все процессы стартуют через supervisor
exec supervisord -c /etc/supervisor/conf.d/supervisord.conf