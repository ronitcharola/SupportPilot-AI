FROM node:20-alpine

WORKDIR /app

# Install dependencies from the lockfile for reproducible builds
COPY package.json package-lock.json ./
RUN npm ci

# Copy the application source
COPY . .

# NEXT_PUBLIC_* values are inlined at build time, so they must be present here
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

EXPOSE 3000
CMD ["npm", "start"]
