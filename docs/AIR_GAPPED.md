# Network isolation and air-gapped deployment

[Back to README](../README.md)

PDF extraction, OCR, embeddings, retrieval, and answer generation run locally. The application disables Chroma telemetry and loads bundled OCR models without a download fallback; the supplied Compose configuration disables Ollama cloud features. Its normal app network is internal, and the localhost-facing gateway removes its external route and sends external DNS to local loopback before serving requests. A claim that nothing leaves the machine also requires the host and browser to be disconnected from external networks.

## Requirements and setup

- Docker Desktop with NVIDIA GPU support for the supplied Compose file
- Python 3.13 and [uv](https://docs.astral.sh/uv/) for host-side development and tests

On a connected staging machine, build the images and use the setup override only while Ollama pulls models:

```powershell
docker compose build
docker compose pull ollama
docker compose -f docker-compose.yml -f docker-compose.setup.yml up -d --no-build --pull never ollama
docker compose -f docker-compose.yml -f docker-compose.setup.yml exec ollama ollama pull llama3.2:3b
docker compose -f docker-compose.yml -f docker-compose.setup.yml exec ollama ollama pull nomic-embed-text
docker compose -f docker-compose.yml -f docker-compose.setup.yml down
```

The setup override attaches only Ollama to an external network. `down` removes that temporary network; the model files remain in `ollama_data/`. The normal configuration does not attach Ollama to it. Place PDFs in `data/`, then start and ingest without building or pulling:

```powershell
docker compose up -d --no-build --pull never
docker compose exec backend uv run --offline python -m app.ingest
```

The backend image includes PyMuPDF, RapidOCR, and its local OCR models, so adding PDFs later does not require a Python install on the host. Open `http://localhost:3000`. The gateway alone publishes ports 3000, 8000, and 11434, each bound to `127.0.0.1`. The browser uses the same-origin `/api` path; the gateway forwards it to the backend and forwards the other two localhost ports for direct API and Ollama access. The frontend, backend, and Ollama containers use only the internal `app` network. The gateway also joins an ingress bridge for Docker Desktop's localhost port publishing, but its startup script removes the default route and Compose points external DNS at local loopback; Docker still resolves the internal service names. Compose mounts `data/` read-only into the backend so PDF links keep working after reingestion. `LLM_MODEL` can override the default `llama3.2:3b`; the supplied Compose file reserves an NVIDIA GPU and has no automatic CPU fallback. There is no authentication or TLS, so this configuration is for local use.

## Air-gapped deployment

Prepare the artifacts on a connected staging machine with the same CPU architecture as the target. Run the setup commands above, then save the three images (the gateway code is included in the frontend image):

```powershell
docker image save -o rag-images.tar local-rag-search-engine-backend:latest local-rag-search-engine-frontend:latest ollama/ollama:latest
```

Transfer `rag-images.tar`, `docker-compose.yml`, `data/`, and `ollama_data/models/` to the target machine. Transfer `chroma_db/` as well if you want to preserve the existing index; otherwise create an empty `chroma_db/` directory and ingest there. The model directory contains Ollama's manifests and blobs. Transfer only `ollama_data/models/`, not the private key in `ollama_data/id_ed25519`. Install Docker Desktop and the required GPU drivers on the target from offline media before disconnecting it.

With the target disconnected from external networks, load the images and start the stack without building or pulling:

```powershell
docker image load -i rag-images.tar
docker compose up -d --no-build --pull never
docker compose exec ollama ollama list
docker compose exec backend uv run --offline python -m app.ingest
```

The backend explicitly disables Chroma telemetry during API requests and ingestion. It loads OCR models from files installed in the image and fails if they are absent. Compose sets `OLLAMA_NO_CLOUD=1`; verify `Ollama cloud disabled: true` in `docker compose logs ollama`. `UV_OFFLINE=1` prevents runtime package downloads. Test the UI, document ingestion, and a cited answer while the target remains disconnected. The supplied configuration isolates the application containers; a connected host or browser can still make unrelated outbound connections, so the absolute "nothing leaves the machine" claim requires host network isolation too. Startup traffic and every dependency's behavior have not been packet-captured.
