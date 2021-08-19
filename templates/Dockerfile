FROM dorowu/ubuntu-desktop-lxde-vnc
WORKDIR /jetskulls

{%- set tmp_file = type + '.tmp' %}
{%- set desk_dir = '/root/Desktop/' %}

COPY '{{ cache_file }}' {{ tmp_file }}
RUN echo use '{{ download }}' \
{%- if '.tgz' in download or '.tar.gz' in download %}
    && tar xzvf {{ tmp_file }} \
{%- elif '.zip' in download %}
    && unzip {{ tmp_file }} \
{%- else %}
    && tar xvf {{ tmp_file }} \
{%- endif %}
    && rm -f {{ tmp_file }}

RUN mkdir -p {{ desk_dir }} \
    && ln -s `find . -name {{ ide_launcher }} | xargs realpath` {{ desk_dir + ide_launcher }}

