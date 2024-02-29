FROM nginx:latest

COPY ./config/nginx.conf /etc/nginx/conf.d/default.conf
COPY ./config/timeout.conf /etc/nginx/conf.d/timeout.conf