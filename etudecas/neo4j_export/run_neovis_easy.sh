#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTAINER_NAME="${CONTAINER_NAME:-neo4j-supply-local}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-test12345}"
NEO4J_DATABASE="${NEO4J_DATABASE:-neo4j}"
NEO4J_IMAGE="${NEO4J_IMAGE:-neo4j:5}"
BOLT_PORT="${BOLT_PORT:-7687}"
HTTP_PORT="${HTTP_PORT:-7474}"
NEOVIS_PORT="${NEOVIS_PORT:-8000}"

IMPORT_CYPHER="$ROOT_DIR/import_neo4j.cypher"

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing command: $1" >&2
    exit 1
  fi
}

ensure_docker_access() {
  if ! docker ps >/dev/null 2>&1; then
    echo "Docker is installed but not accessible." >&2
    echo "Check Docker daemon and permissions (docker group / sudo)." >&2
    exit 1
  fi
}

wait_for_neo4j() {
  echo "Waiting for Neo4j to be ready..."
  local max_tries=60
  local i=1
  while [ $i -le $max_tries ]; do
    if docker exec "$CONTAINER_NAME" cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -d "$NEO4J_DATABASE" "RETURN 1;" >/dev/null 2>&1; then
      echo "Neo4j is ready."
      return 0
    fi
    sleep 2
    i=$((i + 1))
  done
  echo "Neo4j did not become ready in time." >&2
  exit 1
}

up() {
  need_cmd docker
  ensure_docker_access

  if docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
    if docker ps --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
      echo "Container already running: $CONTAINER_NAME"
    else
      echo "Starting existing container: $CONTAINER_NAME"
      if ! out="$(docker start "$CONTAINER_NAME" 2>&1)"; then
        echo "$out" >&2
        if echo "$out" | grep -qi "port is already allocated"; then
          echo "" >&2
          echo "Port conflict detected." >&2
          echo "Quick fix (recreate container on other ports):" >&2
          echo "  docker rm \"$CONTAINER_NAME\"" >&2
          echo "  HTTP_PORT=7475 BOLT_PORT=7688 ./run_neovis_easy.sh all" >&2
          echo "Then in neovis_demo.html use URI: bolt://localhost:7688" >&2
        fi
        exit 1
      fi
    fi
  else
    echo "Creating Neo4j container: $CONTAINER_NAME"
    if ! out="$(docker run -d \
      --name "$CONTAINER_NAME" \
      -p "$HTTP_PORT:7474" \
      -p "$BOLT_PORT:7687" \
      -e "NEO4J_AUTH=$NEO4J_USER/$NEO4J_PASSWORD" \
      -v "$ROOT_DIR:/var/lib/neo4j/import/neo4j_export:ro" \
      "$NEO4J_IMAGE" 2>&1)"; then
      echo "$out" >&2
      if echo "$out" | grep -qi "port is already allocated"; then
        echo "" >&2
        echo "Port conflict detected while creating container." >&2
        echo "Try alternate ports, for example:" >&2
        echo "  HTTP_PORT=7475 BOLT_PORT=7688 ./run_neovis_easy.sh all" >&2
      fi
      exit 1
    fi
  fi

  wait_for_neo4j
}

run_import() {
  need_cmd docker
  ensure_docker_access
  [ -f "$IMPORT_CYPHER" ] || { echo "Missing file: $IMPORT_CYPHER" >&2; exit 1; }

  if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
    echo "Container is not running: $CONTAINER_NAME" >&2
    echo "Run: $0 up" >&2
    exit 1
  fi

  wait_for_neo4j
  echo "Running import script..."
  docker exec -i "$CONTAINER_NAME" cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -d "$NEO4J_DATABASE" < "$IMPORT_CYPHER"
  echo "Import done."
}

serve() {
  need_cmd python
  echo "Serving NeoVis demo on http://localhost:$NEOVIS_PORT/neovis_demo.html"
  echo "Use Neo4j credentials in the page:"
  echo "  URI: bolt://localhost:$BOLT_PORT"
  echo "  User: $NEO4J_USER"
  echo "  Password: $NEO4J_PASSWORD"
  echo "  Database: $NEO4J_DATABASE"
  cd "$ROOT_DIR"
  exec python -m http.server "$NEOVIS_PORT"
}

down() {
  need_cmd docker
  ensure_docker_access
  if docker ps --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
    echo "Stopping container: $CONTAINER_NAME"
    docker stop "$CONTAINER_NAME" >/dev/null
  else
    echo "Container not running: $CONTAINER_NAME"
  fi
}

status() {
  need_cmd docker
  ensure_docker_access
  if docker ps --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
    echo "Container running: $CONTAINER_NAME"
  elif docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
    echo "Container exists but stopped: $CONTAINER_NAME"
  else
    echo "Container not created: $CONTAINER_NAME"
  fi
}

all() {
  up
  run_import
  serve
}

help_msg() {
  cat <<EOF
Usage: $0 <command>

Commands:
  up       Start Neo4j container
  import   Run Cypher import script
  serve    Serve neovis_demo.html (blocks)
  all      up + import + serve (blocks)
  status   Show container status
  down     Stop Neo4j container

Environment overrides:
  NEO4J_USER (default: neo4j)
  NEO4J_PASSWORD (default: test12345)
  NEO4J_DATABASE (default: neo4j)
  CONTAINER_NAME (default: neo4j-supply-local)
  BOLT_PORT (default: 7687)
  HTTP_PORT (default: 7474)
  NEOVIS_PORT (default: 8000)
EOF
}

cmd="${1:-help}"
case "$cmd" in
up) up ;;
import) run_import ;;
serve) serve ;;
all) all ;;
status) status ;;
down) down ;;
help|-h|--help) help_msg ;;
*) help_msg; exit 1 ;;
esac
