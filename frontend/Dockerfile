FROM nginx:1.28.2-alpine
ENV API_HOST=api \
    API_PORT=8000
COPY nginx.conf.template /etc/nginx/lab.conf.template
COPY entrypoint.sh /entrypoint.sh
COPY public/ /usr/share/nginx/html/
USER 101:101
EXPOSE 8080
ENTRYPOINT ["/bin/sh", "/entrypoint.sh"]
CMD ["nginx", "-c", "/tmp/nginx.conf", "-g", "daemon off;"]
