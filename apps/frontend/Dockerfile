FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy application code
COPY . .

# Build the application (for production)
# RUN npm run build

# Development command (for local development)
CMD ["npm", "start"]