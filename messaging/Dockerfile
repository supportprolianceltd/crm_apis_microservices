# Use an official Node.js runtime as a parent image
FROM node:18-alpine

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy package.json and package-lock.json to the working directory
COPY package*.json ./

# Install any needed packages
RUN npm install

# Copy the rest of the application's source code
COPY . .

# Generate Prisma Client
RUN npx prisma generate

# Make ports available to the world outside this container
EXPOSE 3500
EXPOSE 3501

# Define the command to run the app
# Run migrations and then start the application
CMD ["sh", "-c", "npx prisma migrate deploy && npm start"]

