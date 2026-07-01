FROM python:3.14.3

# Upgrade pip
RUN pip install --upgrade pip

# Get curl for healthchecks
RUN apt-get update && apt-get install -y curl git && rm -rf /var/lib/apt/lists/*


# Permissions and nonroot user for tightened security
RUN adduser --disabled-password --gecos '' nonroot
RUN mkdir /home/app/ && chown -R nonroot:nonroot /home/app
RUN mkdir -p /var/log/streamlit-app && touch /var/log/streamlit-app/streamlit-app.err.log && touch /var/log/streamlit-app/streamlit-app.out.log
RUN chown -R nonroot:nonroot /var/log/streamlit-app
WORKDIR /home/app
USER nonroot

# Copy all the files to the container
COPY --chown=nonroot:nonroot . .

# venv
ENV VIRTUAL_ENV=/home/app/venv

# Python setup
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install dependencies (use poetry or requirements.txt if present)
RUN if [ -f pyproject.toml ]; then pip install poetry && poetry config virtualenvs.create false && poetry install --no-root; fi


# Expose Streamlit default port
EXPOSE 8502

# Streamlit config (optional: disables browser auto-open, sets log dir)
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_PORT=8502
ENV STREAMLIT_SERVER_ENABLECORS=false
ENV STREAMLIT_LOG_LEVEL=info



# Run Streamlit app
CMD ["streamlit", "run", "app.py"]
