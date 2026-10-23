FROM ghcr.io/netbox-community/netbox@sha256:fa7ffa268c39fb258bed80bd256360a525f1a129ee4ee06298f10d6708578eba
USER root
RUN /usr/local/bin/uv pip install --python /opt/netbox/venv/bin/python netbox-inventory==2.7.1
COPY plugins.py /etc/netbox/config/plugins.py
RUN SECRET_KEY=build-only-not-used-at-runtime-build-only-not-used-at-runtime \
    /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py collectstatic --no-input
USER netbox
