# Stage 1: Build the React application
FROM node:20-alpine AS builder

WORKDIR /app

# Copy dependency definitions first
COPY package*.json ./

# Install dependencies strictly from the lockfile
RUN npm ci

# Copy the rest of the frontend source code
COPY . .

# Build the Vite project
RUN npm run build

# Stage 2: Serve the application with Nginx
FROM nginx:alpine

# Copy ONLY the built assets from the builder stage into Nginx
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose port 80 inside the container
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]