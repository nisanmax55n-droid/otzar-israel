FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
CMD ["/bin/sh", "-c", "sed -i \"s/listen 80;/listen ${PORT:-80};/\" /etc/nginx/conf.d/default.conf && exec nginx -g 'daemon off;'"]
