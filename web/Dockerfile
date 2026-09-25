FROM nginx:1.27-alpine

COPY web/nginx.conf /etc/nginx/nginx.conf
COPY app/static /usr/share/nginx/html

HEALTHCHECK --interval=10s --timeout=3s --retries=5 --start-period=3s \
    CMD wget -q -O- http://127.0.0.1/health >/dev/null || exit 1
