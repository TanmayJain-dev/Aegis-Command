# frontend/Dockerfile
FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm install

# Copy frontend source code
COPY . .

# Expose Next.js port
EXPOSE 3000

# Run Next.js in development mode
CMD ["npm", "run", "dev"]