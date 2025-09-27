# Use an official Python runtime as a parent image, slim version for smaller size
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# --- Environment Variable for Dynamic Configuration ---
# Set the environment variable to 'docker'. This tells settings.py to use
# the Docker-specific configurations (e.g., host='0.0.0.0' and service URLs).
ENV ENV_TYPE=docker

# --- Optimize Layer Caching for Dependencies ---
# Copy only the requirements file first to leverage Docker's layer caching.
# This layer will only be rebuilt if requirements.txt changes.
COPY ./requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# --- Copy Application Code ---
# Now, copy the rest of your application code into the container.
COPY . /app/

# --- Expose Port for Documentation and Tooling ---
# Inform Docker that the container listens on port 8000 at runtime.
# Note: This does NOT publish the port. You still need to use the -p flag.
EXPOSE 8000

# --- Command to Run the Application ---
# Start the Uvicorn server. It will listen on 0.0.0.0:8000 inside the container,
# which is the correct way to accept connections from outside the container.
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]