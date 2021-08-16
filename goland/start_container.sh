#!/bin/sh

# --- configs ---
HOST_WORK_DIR=`pwd`
CONTAINER_WORK_DIR=/myapp
HOST_PORT=6080
VERSION=v1

docker run -d --name jetskulls-goland-container \
    -p $HOST_PORT:80 \
    -v /dev/shm:/dev/shm \
    -v $HOST_WORK_DIR:$CONTAINER_WORK_DIR \
    -w $CONTAINER_WORK_DIR \
    jetskulls-goland:$VERSION \
    && echo "view http://{host_ip}:$HOST_PORT to use the IDE."

