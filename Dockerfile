FROM python:3.11
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
RUN git clone https://github.com/tolwi/hassio-ecoflow-cloud.git /opt/ecoflow-cloud
COPY ecoflow_mqtt.py /app/
COPY /opt/ecoflow-cloud/ecoflow_cloud.py /app/
CMD ["python3", "ecoflow_mqtt.py"]
