FROM python:3.13.7-alpine3.22
WORKDIR /app
COPY exporter.py components.json ./
USER 65534:65534
EXPOSE 9100
CMD ["python", "-B", "exporter.py"]
