FROM node:24-bookworm-slim@sha256:91acba91b842bec0bf7ea6f5e09c644c7ccad72c4996ed9616d861d1c7cd60d4 AS node
FROM python:3.14-slim-bookworm@sha256:58b9cb2dde6dc8ca7cabd10942d9d01ead923811b191f259008942f7b402ca7e AS app
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 PATH=/home/frappe/frappe-bench/env/bin:/usr/local/bin:$PATH
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates build-essential pkg-config libmariadb-dev mariadb-client libcairo2-dev libffi-dev libssl-dev libxml2-dev libxslt1-dev libjpeg-dev zlib1g-dev libpq-dev redis-tools openssl rsync ffmpeg wkhtmltopdf fontconfig fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx && npm install -g yarn@1.22.22 && pip install --no-cache-dir frappe-bench==5.29.1 && useradd -m -u 1000 -s /bin/bash frappe
USER frappe
WORKDIR /home/frappe
RUN bench init --frappe-branch v16.52.0 --python /usr/local/bin/python3 --no-backups --skip-assets --skip-redis-config-generation frappe-bench && test "$(git -C frappe-bench/apps/frappe rev-parse HEAD)" = 4515014c87ece6cb20ee91d2cfb121c5cbd1ff4a
WORKDIR /home/frappe/frappe-bench
RUN bench get-app --branch version-16 --skip-assets https://github.com/frappe/payments && git -C apps/payments fetch upstream cca07d9f9392e2ea0e521c5975151db9e4b6c321 && git -C apps/payments checkout cca07d9f9392e2ea0e521c5975151db9e4b6c321 && test "$(git -C apps/payments rev-parse HEAD)" = cca07d9f9392e2ea0e521c5975151db9e4b6c321 && env/bin/pip install -e apps/payments
ENV YARN_CACHE_FOLDER=/home/frappe/.cache/yarn
COPY --chown=frappe:frappe . apps/lms
RUN cp -a apps/lms/apps/bpo_coach apps/bpo_coach && env/bin/pip install -e apps/lms -e apps/bpo_coach && printf 'frappe\npayments\nlms\nbpo_coach\n' > sites/apps.txt && python apps/lms/deploy/apply_bridge.py
RUN --mount=type=cache,target=/home/frappe/.cache/yarn,uid=1000,gid=1000 yarn config set network-concurrency 8 && yarn config set network-timeout 120000 && cd apps/lms && yarn install --frozen-lockfile
RUN --mount=type=cache,target=/home/frappe/.npm,uid=1000,gid=1000 cd apps/bpo_coach/frontend && npm ci && npm run build
RUN bench build --production && python apps/lms/deploy/materialize_assets.py sites/assets /home/frappe/assets-built
COPY --chown=frappe:frappe deploy/entrypoint.py /home/frappe/entrypoint.py
ENTRYPOINT ["python", "/home/frappe/entrypoint.py"]
CMD ["web"]

FROM nginx:1.28-alpine@sha256:a8b39bd9cf0f83869a2162827a0caf6137ddf759d50a171451b335cecc87d236 AS frontend
COPY --from=app /home/frappe/assets-built /usr/share/nginx/html/assets
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
