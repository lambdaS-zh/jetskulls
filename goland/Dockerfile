FROM dorowu/ubuntu-desktop-lxde-vnc
WORKDIR /jetskulls

RUN wget -O goland.tgz 'https://download.jetbrains.com/go/goland-2021.2.tar.gz' \
    && tar xzvf goland.tgz \
    && rm -f goland.tgz
RUN mkdir -p /root/Desktop \
    && ln -s `find . -name goland.sh | xargs realpath` /root/Desktop/goland.sh

