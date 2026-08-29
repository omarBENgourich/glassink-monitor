FROM nodered/node-red:4.1.10

WORKDIR /data

COPY --chown=node-red:node-red package.json package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund --no-update-notifier

COPY --chown=node-red:node-red settings.js flows.json line_protocol.js ./

WORKDIR /usr/src/node-red
