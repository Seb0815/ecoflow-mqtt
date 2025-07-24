FROM python:3.11
WORKDIR /app
COPY ecoflow_mqtt.py ./
COPY requirements.txt ./

RUN pip install -r requirements.txt && \
    git clone https://github.com/tolwi/hassio-ecoflow-cloud.git /opt/ecoflow-cloud && \
    cp /opt/ecoflow-cloud/ecoflow_cloud.py /app/
CMD ["python3", "ecoflow_mqtt.py"]
