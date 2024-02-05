FROM nginx:latest

COPY ./config/nginx.conf /etc/nginx/conf.d/default.conf