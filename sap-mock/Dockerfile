# The mock SAP service (OData v2 shape). Build context is the repo root:
#   docker build -f sap-mock/Dockerfile -t create-design-sap .
FROM python:3.11-slim
WORKDIR /srv
COPY sap-mock/requirements.txt sap-mock/requirements.txt
RUN pip install --no-cache-dir -r sap-mock/requirements.txt
COPY sap-mock/app sap-mock/app
COPY sap-mock/seed sap-mock/seed
RUN useradd --create-home sap && mkdir -p /data && chown sap /data
ENV DATA_DIR=/data
VOLUME /data
USER sap
WORKDIR /srv/sap-mock
EXPOSE 8100
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8100/docs')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]
