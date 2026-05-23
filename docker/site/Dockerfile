FROM nginx:1.27-alpine

COPY docker/site/nginx.conf /etc/nginx/conf.d/default.conf

COPY frontend /usr/share/nginx/html/frontend
COPY shared /usr/share/nginx/html/shared
COPY ./*.html /usr/share/nginx/html/
