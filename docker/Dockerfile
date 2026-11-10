FROM python:3.12-slim
RUN pip install --no-cache-dir pandas==2.3.3 numpy==2.5.4
COPY worker.py /worker.py
LABEL org.tabular-agent.worker-contract="3"
ENV PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
WORKDIR /output
ENTRYPOINT ["python", "-I", "/worker.py"]
