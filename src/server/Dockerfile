FROM alpine:latest

# Update package manager and install necessary dependencies
RUN apk update && \
    apk add --no-cache curl ca-certificates python3 py3-pip openssh && \
    update-ca-certificates

# Create and activate a virtual environment
RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"

# Enable and start SSH service (consider security implications)
RUN mkdir -p /var/run/sshd && \
    echo "PermitRootLogin yes" >> /etc/ssh/sshd_config && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/g' /etc/ssh/sshd_config && \
    ssh-keygen -A

# Set the working directory in the container
WORKDIR /src/server

# Copy the current directory contents into the container
COPY . .

# Install Python packages within the virtual environment
RUN pip3 install --no-cache-dir -U pip -c constraints.txt && \
    pip3 install --no-cache-dir -U wheel -c constraints.txt && \
    pip3 install --no-cache-dir -r requirements.txt

EXPOSE 80 22

# Set Flask environment variable
ENV FLASK_APP=app.py

# Start SSH and Flask app
CMD /usr/sbin/sshd && flask run --host=0.0.0.0 --port=80