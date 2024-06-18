FROM nginx:latest

COPY ./config/default.conf /etc/nginx/conf.d/default.conf
COPY ./config/nginx.conf /etc/nginx/nginx.conf
COPY ./config/timeout.conf /etc/nginx/conf.d/timeout.conf