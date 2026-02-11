# Minimal Dockerfile for Type Router V2 (FastAPI + Uvicorn)
FROM python:3.10-slim

# Working directory
WORKDIR /app

# Avoid installing build tools to keep image small (numpy/scikit-learn wheels available)
# If you hit wheel/build errors on your platform, add build deps (e.g. build-essential) here.

# Copy only what's needed
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app + model outputs (adjust as needed)
COPY type_router_service_v2.py .
COPY outputs/ ./outputs/

# Small example .env — replace or mount a real one in production
RUN printf "USE_DUMMY_ROUTER=false\nMODEL_PATH=outputs/ovr_rf_clip_model.joblib\nTHRESHOLD=0.5\n" > .env

# Expose port used by uvicorn
EXPOSE 8001

# Healthcheck using standard library (no extra dependency)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request, sys; \
    r = urllib.request.urlopen('http://127.0.0.1:8001/health'); \
    sys.exit(0 if r.status == 200 else 1)"

# Run with uvicorn (single worker). Use --workers >1 or gunicorn for higher loads.
CMD ["uvicorn", "type_router_service_v2:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]

# docker build -t type-router-v2 .
# docker run -p 8001:8001 --env-file .env type-router-v2

