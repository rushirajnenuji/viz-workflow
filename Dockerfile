FROM python:3.9-slim

# Install transitive dependencies
RUN apt-get update \
    && apt-get install -y git libspatialindex-dev libgdal-dev libproj-dev build-essential

# Install pdgstaging from GitHub repo
RUN pip install git+https://github.com/rushirajnenuji/viz-workflow.git

WORKDIR /app

CMD ["python3"]
