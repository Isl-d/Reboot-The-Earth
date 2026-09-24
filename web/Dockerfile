FROM node:20-alpine
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
EXPOSE 5173
ENV VITE_API_BASE=http://backend:8000
CMD ["npm", "run", "dev"]
