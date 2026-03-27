FROM python:3.12-slim

ARG FUNCTION_DIR="/s3-flywheel-import"
WORKDIR ${FUNCTION_DIR}

# Copy function code and requirements
COPY requirements.txt ${FUNCTION_DIR}/
COPY *.py ${FUNCTION_DIR}/

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Set Lambda runtime
ENTRYPOINT [ "/usr/local/bin/python", "-m", "awslambdaric" ]
CMD [ "s3_flywheel_import.main" ]
