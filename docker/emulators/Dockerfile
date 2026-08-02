# The Firebase emulator suite. There is no official image, so this is node plus a JRE
# (the Firestore and Pub/Sub emulators are Java) plus firebase-tools.
# trixie rather than bookworm: Debian 12 ships JDK 17 and has no openjdk-21 package,
# and firebase-tools@15 will require 21.
FROM node:22-trixie-slim

# JDK 21, not 17: firebase-tools@15 drops support for Java below 21, and the current
# CLI already warns about it on every start. Taking it now costs nothing and avoids
# a forced bump at whatever moment we next need to move the pin.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      openjdk-21-jre-headless \
      curl \
      ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Pin the CLI. An unpinned emulator suite changes behaviour under you between two
# `docker compose build` runs on two machines, and the resulting "works on mine" is
# expensive to chase.
RUN npm install -g firebase-tools@14

WORKDIR /frame

# Bake the emulator jars into the image so a cold `docker compose up` does not stall for a
# minute downloading them inside the container, and so the stack starts on a machine with
# no network.
RUN firebase setup:emulators:firestore \
 && firebase setup:emulators:pubsub \
 && firebase setup:emulators:storage \
 && firebase setup:emulators:ui

EXPOSE 6310 6311 6312 6313 6314 6315 6316

# firebase.json is mounted from firebase.docker.json and supplies host 0.0.0.0, every port,
# and the "frame" database name. --project must match the id the backend and the seeder use
# or they address different namespaces and the store looks empty.
CMD ["firebase", "emulators:start", \
     "--project", "unops-frame-dev", \
     "--only", "firestore,auth,pubsub,storage", \
     "--import=/frame/emulator-data", \
     "--export-on-exit=/frame/emulator-data"]
