FROM dorowu/ubuntu-desktop-lxde-vnc
WORKDIR /jetskulls

{% set tmp_file = type + '.tmp' %}
{% set desk_dir = '/root/Desktop/' %}

{% if download.startswith('http:') or download.startswith('https:') %}
RUN wget -O {{ tmp_file }} '{{ download }}' \
{% else %}
COPY '{{ download }}' {{ tmp_file }}
RUN echo use '{{ download }}' \
{% endif %}
{% if '.tgz' in download or '.tar.gz' in download %}
    && tar xzvf {{ tmp_file }} \
{% elif '.zip' in download %}
    && unzip {{ tmp_file }} \
{% else %}
    && tar xvf {{ tmp_file }} \
{% endif %}
    && rm -f {{ tmp_file }}

RUN mkdir -p {{ desk_dir }} \
    && ln -s `find . -name {{ ide_launcher }} | xargs realpath` {{ desk_dir + ide_launcher }}

